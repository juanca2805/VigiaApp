'use strict';
// Vigía de aseo — MVP en navegador (modo prueba con COCO-SSD de tfjs-models)

const CLASES = { bottle: 'basura', cup: 'basura', backpack: 'basura', handbag: 'basura', suitcase: 'basura' };
const CIERRE_AUSENTE_S = 4;      // objeto ausente este tiempo => alerta cerrada
const MOV_UMBRAL = 0.04;         // desplazamiento (fracción del encuadre) que reinicia "quieto"
const FPS_ANALISIS = 3;

const $ = id => document.getElementById(id);
const video = $('video'), lienzo = $('lienzo'), ctx = lienzo.getContext('2d');

const defaults = { camara: 'Cámara celular', conf: 0.5, pers: 10, dist: 20, hook: '' };
let cfg = { ...defaults }, cfgGuardada = {};
try { cfgGuardada = JSON.parse(localStorage.getItem('vigia-cfg') || '{}'); cfg = { ...defaults, ...cfgGuardada }; } catch (e) {}
const guardarCfg = () => { try { localStorage.setItem('vigia-cfg', JSON.stringify(cfg)); } catch (e) {} };

let modelo = null;      // COCO-SSD: modo prueba y detección de personas
let propio = null;      // modelo ONNX entrenado (modelo/modelo.json), opcional
let stream = null, facing = 'environment';
let pausado = false, verMov = true, verDet = true;
let tracks = [], alertas = [], eventos = [], sigId = 1;
let prevGris = null, cajasMov = [];

// ---------- Ajustes ----------
function pintarAjustes() {
  $('sCamara').value = cfg.camara; $('sConf').value = cfg.conf; $('sPers').value = cfg.pers;
  $('sDist').value = cfg.dist; $('sHook').value = cfg.hook;
  $('vConf').textContent = Math.round(cfg.conf * 100) + '%';
  $('vPers').textContent = cfg.pers + ' s';
  $('vDist').textContent = cfg.dist + '%';
}
$('sCamara').oninput = e => { cfg.camara = e.target.value; guardarCfg(); };
// el control de confianza fija el umbral base; cada clase suma su diferencia medida al evaluar (modelo.json: umbrales)
function umbralDe(clase) {
  const m = propio && propio.meta;
  const extra = m && m.umbrales && m.umbral ? (m.umbrales[clase] ?? m.umbral) - m.umbral : 0;
  return Math.min(0.95, cfg.conf + extra);
}
$('sConf').oninput = e => { cfg.conf = +e.target.value; pintarAjustes(); guardarCfg(); };
$('sPers').oninput = e => { cfg.pers = +e.target.value; pintarAjustes(); guardarCfg(); };
$('sDist').oninput = e => { cfg.dist = +e.target.value; pintarAjustes(); guardarCfg(); };
$('sHook').oninput = e => { cfg.hook = e.target.value.trim(); guardarCfg(); };

// Enlace de vinculación del panel: ?camara=Pasillo%203&hook=https://…/security/reports?token=…
// Deja el celular configurado y limpia la dirección para no dejar el token a la vista.
(function aplicarEnlace() {
  const q = new URLSearchParams(location.search);
  const camara = q.get('camara'), hook = q.get('hook');
  if (camara === null && hook === null) return;
  if (camara) cfg.camara = camara.trim();
  if (hook) cfg.hook = hook.trim();
  guardarCfg();
  history.replaceState(null, '', location.pathname);
})();
pintarAjustes();

// Latido al panel: lo mantiene "en línea". Solo si el webhook es del panel (…/security/reports).
const LATIDO_MS = 30000;
function urlLatido() {
  try {
    const u = new URL(cfg.hook);
    if (!u.pathname.endsWith('/security/reports')) return null;
    u.pathname = u.pathname.replace(/reports$/, 'heartbeat');
    return u.toString();
  } catch (e) { return null; }
}
function latido() {
  const url = urlLatido();
  if (url && stream) fetch(url, { method: 'POST' }).catch(() => {});
}
setInterval(latido, LATIDO_MS);

// Pantalla encendida: con la pantalla apagada el navegador pausa la cámara y el celular deja de reportar.
let pantalla = null;
async function mantenerPantalla() {
  try {
    if ('wakeLock' in navigator && !pantalla) {
      pantalla = await navigator.wakeLock.request('screen');
      pantalla.addEventListener('release', () => { pantalla = null; });
    }
  } catch (e) { pantalla = null; }
}
// el navegador libera el bloqueo al ocultar la pestaña; se pide de nuevo al volver
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && stream) mantenerPantalla(); });

// ---------- Cámara y modelo ----------
async function iniciarCamara() {
  if (stream) stream.getTracks().forEach(t => t.stop());
  stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: facing, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false
  });
  video.srcObject = stream;
  await video.play();
  lienzo.width = video.videoWidth; lienzo.height = video.videoHeight;
  prevGris = null; tracks = [];
}

// Carga modelo/modelo.json + el .onnx si existen; si no, devuelve null y se usa el modo prueba.
async function cargarModeloPropio() {
  if (typeof ort === 'undefined' || typeof DetectorONNX === 'undefined') return null;
  try {
    const r = await fetch('modelo/modelo.json', { cache: 'no-store' });
    if (!r.ok) return null;
    const meta = await r.json();
    return await DetectorONNX.crear(ort, meta, 'modelo/' + meta.archivo);
  } catch (e) {
    console.warn('No se pudo cargar el modelo propio, uso modo prueba:', e);
    return null;
  }
}

async function arrancar() {
  $('btnIniciar').disabled = true;
  try {
    $('estado').textContent = 'Cargando modelo…';
    if (!propio) propio = await cargarModeloPropio();
    // COCO-SSD: modo prueba, o solo para personas si el modelo propio no tiene esa clase
    const necesitaCoco = !propio || !propio.meta.clases.includes('persona');
    if (necesitaCoco && !modelo) modelo = await cocoSsd.load({ base: 'lite_mobilenet_v2' });
    if (propio && cfgGuardada.conf === undefined && propio.meta.umbral) { cfg.conf = propio.meta.umbral; pintarAjustes(); }
    await iniciarCamara();
    $('estado').textContent = propio ? 'Modelo propio: ' + propio.meta.clases.join(', ') : 'Modo prueba (COCO-SSD)';
    $('btnIniciar').style.display = 'none';
    mantenerPantalla();
    latido();
    bucle();
  } catch (e) {
    $('estado').textContent = 'Error: ' + (e.message || e);
    $('btnIniciar').disabled = false;
  }
}
$('btnIniciar').onclick = arrancar;
$('btnCam').onclick = async () => { facing = facing === 'environment' ? 'user' : 'environment'; if (stream) await iniciarCamara(); };
$('btnPausa').onclick = e => { pausado = !pausado; e.target.textContent = pausado ? '▶ Reanudar' : '⏸ Pausar'; if (pausado) video.pause(); else video.play(); };
$('btnMov').onclick = e => { verMov = !verMov; e.target.classList.toggle('on', verMov); };
$('btnDet').onclick = e => { verDet = !verDet; e.target.classList.toggle('on', verDet); };

// ---------- Movimiento (diferencia de cuadros en rejilla) ----------
const GW = 32, GH = 24;
const mini = document.createElement('canvas'); mini.width = GW; mini.height = GH;
const mctx = mini.getContext('2d', { willReadFrequently: true });

function detectarMovimiento() {
  mctx.drawImage(video, 0, 0, GW, GH);
  const d = mctx.getImageData(0, 0, GW, GH).data;
  const gris = new Uint8Array(GW * GH);
  for (let i = 0; i < gris.length; i++) gris[i] = (d[i * 4] + d[i * 4 + 1] + d[i * 4 + 2]) / 3;
  const cajas = [];
  if (prevGris) {
    const activas = new Set();
    for (let i = 0; i < gris.length; i++) if (Math.abs(gris[i] - prevGris[i]) > 28) activas.add(i);
    // agrupar celdas vecinas en cajas
    const vistas = new Set();
    for (const s of activas) {
      if (vistas.has(s)) continue;
      const cola = [s]; vistas.add(s);
      let x0 = GW, y0 = GH, x1 = 0, y1 = 0, n = 0;
      while (cola.length) {
        const c = cola.pop(), x = c % GW, y = (c / GW) | 0;
        n++; x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
        for (const [dx, dy] of [[1,0],[-1,0],[0,1],[0,-1],[1,1],[-1,-1],[1,-1],[-1,1]]) {
          const nx = x + dx, ny = y + dy;
          if (nx < 0 || ny < 0 || nx >= GW || ny >= GH) continue;
          const k = ny * GW + nx;
          if (activas.has(k) && !vistas.has(k)) { vistas.add(k); cola.push(k); }
        }
      }
      if (n >= 3) cajas.push([x0 / GW, y0 / GH, (x1 + 1) / GW, (y1 + 1) / GH]);
    }
  }
  prevGris = gris;
  return cajas;
}

// ---------- Seguimiento y regla de persistencia ----------
const centro = b => [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
function iou(a, b) {
  const x0 = Math.max(a[0], b[0]), y0 = Math.max(a[1], b[1]), x1 = Math.min(a[2], b[2]), y1 = Math.min(a[3], b[3]);
  const i = Math.max(0, x1 - x0) * Math.max(0, y1 - y0);
  const u = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - i;
  return u > 0 ? i / u : 0;
}
const personaCerca = (caja, personas) => personas.some(p => {
  const [ax, ay] = centro(caja), [bx, by] = centro(p.caja);
  return Math.hypot(ax - bx, ay - by) < cfg.dist / 100;
});

function actualizarTracks(objetos, personas, ahora) {
  const usados = new Set();
  for (const o of objetos) {
    let mejor = null, mejorIou = 0.25;
    for (const t of tracks) {
      if (usados.has(t) || t.clase !== o.clase) continue;
      const v = iou(t.caja, o.caja);
      if (v > mejorIou) { mejor = t; mejorIou = v; }
    }
    if (!mejor) {
      mejor = { id: sigId++, clase: o.clase, caja: o.caja, ancla: o.caja, desde: ahora, quieto: ahora, alerta: null, descartado: false };
      tracks.push(mejor);
    }
    usados.add(mejor);
    mejor.caja = o.caja; mejor.conf = o.conf; mejor.visto = ahora;
    const [cx, cy] = centro(mejor.caja), [ax, ay] = centro(mejor.ancla);
    if (Math.hypot(cx - ax, cy - ay) > MOV_UMBRAL) { mejor.ancla = mejor.caja; mejor.quieto = ahora; }
    mejor.cerca = personaCerca(mejor.caja, personas);
    if (mejor.cerca) mejor.quieto = ahora;   // con persona cerca el reloj de "quieto" se reinicia

    const quietoS = (ahora - mejor.quieto) / 1000;
    mejor.quietoS = quietoS;
    if (!mejor.alerta && !mejor.descartado && mejor.conf >= umbralDe(mejor.clase) && quietoS >= cfg.pers) abrirAlerta(mejor, quietoS, personas);
  }
  // cerrar los que ya no aparecen
  tracks = tracks.filter(t => {
    if (usados.has(t)) return true;
    if ((ahora - t.visto) / 1000 < CIERRE_AUSENTE_S) return true;
    if (t.alerta && t.alerta.estado !== 'descartada') cerrarAlerta(t.alerta, ahora);
    return false;
  });
}

// ---------- Alertas ----------
function evidencia(personas) {
  const c = document.createElement('canvas');
  const w = 480, h = Math.round(480 * video.videoHeight / video.videoWidth);
  c.width = w; c.height = h;
  const x = c.getContext('2d');
  x.drawImage(video, 0, 0, w, h);
  for (const p of personas) {            // personas en mosaico (privacidad)
    const [x0, y0, x1, y1] = p.caja.map((v, i) => v * (i % 2 ? h : w));
    const bw = Math.max(1, x1 - x0), bh = Math.max(1, y1 - y0);
    const t = document.createElement('canvas'); t.width = 6; t.height = 6;
    t.getContext('2d').drawImage(c, x0, y0, bw, bh, 0, 0, 6, 6);
    x.imageSmoothingEnabled = false;
    x.drawImage(t, 0, 0, 6, 6, x0, y0, bw, bh);
    x.imageSmoothingEnabled = true;
  }
  return c.toDataURL('image/jpeg', 0.6);
}

function emitir(evento, a) {
  const registro = { ...a, evento };
  eventos.push(registro);
  if (cfg.hook) {
    const body = { ...registro };
    fetch(cfg.hook, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).catch(() => {});
  }
}

function abrirAlerta(t, quietoS, personas) {
  const a = {
    id: 'A-' + Date.now(), evento: 'alerta', camara: cfg.camara, clase: t.clase,
    hora: new Date().toISOString(), persistio_s: Math.round(quietoS), respuesta_s: null,
    confianza: +t.conf.toFixed(2), caja: t.caja.map(v => +v.toFixed(3)),
    imagen: evidencia(personas), estado: 'abierta', _t0: Date.now()
  };
  t.alerta = a; alertas.unshift(a);
  emitir('alerta', a);
  avisar(a);
  pintarAlertas();
}

function cerrarAlerta(a, ahora) {
  a.estado = a.estado === 'aseo enviado' ? 'atendida' : 'cerrada (objeto desapareció)';
  a.respuesta_s = Math.round((ahora - a._t0) / 1000);
  emitir('cerrada', a);
  pintarAlertas();
}

function accion(id, tipo) {
  const a = alertas.find(x => x.id === id); if (!a) return;
  if (tipo === 'aseo') { a.estado = 'aseo enviado'; a.aseo_hora = new Date().toISOString(); }
  if (tipo === 'descartar') {
    a.estado = 'descartada'; a.respuesta_s = Math.round((Date.now() - a._t0) / 1000);
    const t = tracks.find(t => t.alerta === a); if (t) t.descartado = true;
    emitir('cerrada', a);
  }
  pintarAlertas();
}

function pintarAlertas() {
  const abiertas = alertas.filter(a => a.estado === 'abierta' || a.estado === 'aseo enviado').length;
  $('contador').textContent = abiertas ? `(${abiertas} abiertas)` : '';
  if (!alertas.length) return;
  $('alertas').innerHTML = alertas.map(a => {
    const activa = a.estado === 'abierta', enviada = a.estado === 'aseo enviado';
    return `<div class="alerta ${activa || enviada ? '' : 'cerrada'}">
      <strong>${a.clase.toUpperCase()} ${Math.round(a.confianza * 100)}%</strong> · ${a.camara}
      <small>${new Date(a.hora).toLocaleTimeString()} · quieto ${a.persistio_s}s · ${a.estado}${a.respuesta_s != null ? ' · respuesta ' + a.respuesta_s + 's' : ''}</small>
      <img src="${a.imagen}" alt="evidencia">
      ${(activa || enviada) && !urlLatido() ? `<button class="p" ${enviada ? 'disabled' : ''} onclick="accion('${a.id}','aseo')">Enviar aseo</button>
      <button class="d" onclick="accion('${a.id}','descartar')">Descartar</button>` : ''}
    </div>`;
  }).join('');
}
window.accion = accion;

function avisar(a) {
  try { navigator.vibrate && navigator.vibrate([300, 150, 300]); } catch (e) {}
  try {
    const ac = new (window.AudioContext || window.webkitAudioContext)();
    const o = ac.createOscillator(); o.frequency.value = 880; o.connect(ac.destination);
    o.start(); o.stop(ac.currentTime + 0.2);
  } catch (e) {}
  try {
    if (window.Notification && Notification.permission === 'granted')
      new Notification('Vigía de aseo', { body: `${a.clase} detectada en ${a.camara}` });
  } catch (e) {}
}
$('btnNotif').onclick = async () => {
  if (!window.Notification) return alert('Este navegador no soporta notificaciones.');
  const p = await Notification.requestPermission();
  $('btnNotif').textContent = p === 'granted' ? '🔔 Avisos activos' : '🔕 Avisos bloqueados';
};
$('btnJson').onclick = () => {
  const lineas = eventos.map(e => { const { imagen, _t0, ...r } = e; return JSON.stringify({ ...r, imagen: imagen ? '(foto)' : null }); }).join('\n');
  const blob = new Blob([lineas || ''], { type: 'application/x-ndjson' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'vigia-eventos.jsonl'; a.click();
};

// ---------- Bucle principal ----------
function dibujar(objetos, personas) {
  ctx.clearRect(0, 0, lienzo.width, lienzo.height);
  const W = lienzo.width, H = lienzo.height;
  ctx.lineWidth = Math.max(2, W / 320); ctx.font = `${Math.max(14, W / 40)}px system-ui`;
  if (verMov) {
    ctx.strokeStyle = '#38bdf8';
    cajasMov.forEach(b => ctx.strokeRect(b[0] * W, b[1] * H, (b[2] - b[0]) * W, (b[3] - b[1]) * H));
  }
  if (verDet) {
    for (const o of [...objetos, ...personas]) {
      const t = tracks.find(t => t.caja === o.caja);
      const color = o.clase === 'persona' ? '#a78bfa' : (t && t.alerta ? '#ef4444' : '#f59e0b');
      const [x0, y0, x1, y1] = [o.caja[0] * W, o.caja[1] * H, o.caja[2] * W, o.caja[3] * H];
      ctx.strokeStyle = color; ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
      let txt = `${o.clase.toUpperCase()} ${Math.round(o.conf * 100)}%`;
      if (t && !t.alerta && !t.cerca) txt += ` ${Math.floor(t.quietoS || 0)}/${cfg.pers}s`;
      ctx.fillStyle = color; ctx.fillRect(x0, Math.max(0, y0 - 22), ctx.measureText(txt).width + 10, 22);
      ctx.fillStyle = '#000'; ctx.fillText(txt, x0 + 5, Math.max(16, y0 - 6));
    }
  }
}

async function bucle() {
  const paso = 1000 / FPS_ANALISIS;
  while (true) {
    const ini = performance.now();
    if (!pausado && video.readyState >= 2) {
      cajasMov = detectarMovimiento();
      const W = video.videoWidth, H = video.videoHeight;
      const norm = p => ({ conf: p.score, caja: [p.bbox[0] / W, p.bbox[1] / H, (p.bbox[0] + p.bbox[2]) / W, (p.bbox[1] + p.bbox[3]) / H] });
      let personas = [], objetos = [];
      if (propio) {
        const dets = (await propio.detectar(video, 0.25)).map(d => ({ clase: d.clase, conf: d.conf, caja: d.caja }));
        objetos = dets.filter(d => d.clase !== 'persona');
        personas = dets.filter(d => d.clase === 'persona');
      }
      if (modelo) {
        const pred = await modelo.detect(video, 20, 0.3);
        if (!propio) objetos = pred.filter(p => CLASES[p.class]).map(p => ({ ...norm(p), clase: CLASES[p.class] }));
        if (!propio || !propio.meta.clases.includes('persona'))
          personas = pred.filter(p => p.class === 'person').map(p => ({ ...norm(p), clase: 'persona' }));
      }
      actualizarTracks(objetos, personas, Date.now());
      dibujar(tracks.map(t => ({ clase: t.clase, conf: t.conf, caja: t.caja })).filter(t => tracks.some(x => x.caja === t.caja)), personas);
      $('sello').textContent = `${cfg.camara} · ${new Date().toLocaleString()}`;
    }
    const resto = paso - (performance.now() - ini);
    await new Promise(r => setTimeout(r, Math.max(10, resto)));
  }
}
