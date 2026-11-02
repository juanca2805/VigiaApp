'use strict';
// Detector ONNX (RF-DETR) para Vigía de aseo.
// Entrada:  float32 NCHW [1,3,H,W], RGB, estirada (sin letterbox), normalizada con media/desv ImageNet.
// Salidas:  "dets"   [1,Q,4]  cajas cx,cy,w,h normalizadas 0..1
//           "labels" [1,Q,C]  logits por clase (score = sigmoide). C = clases + 1 (el último canal se ignora).
(function (raiz) {
  const MEDIA = [0.485, 0.456, 0.406], DESV = [0.229, 0.224, 0.225];
  const sigmoide = x => 1 / (1 + Math.exp(-x));
  const acotar = v => Math.min(1, Math.max(0, v));

  // rgba: Uint8ClampedArray de w*h*4  ->  Float32Array 3*w*h (canal primero)
  function preparar(rgba, w, h) {
    const n = w * h, out = new Float32Array(3 * n);
    for (let i = 0; i < n; i++)
      for (let c = 0; c < 3; c++) out[c * n + i] = (rgba[i * 4 + c] / 255 - MEDIA[c]) / DESV[c];
    return out;
  }

  // Devuelve [{ idx, conf, caja:[x0,y0,x1,y1] normalizada }] con conf >= minConf, ordenado por conf desc.
  function decodificar(dets, labels, q, c, nClases, minConf) {
    const res = [];
    for (let i = 0; i < q; i++) {
      let mejor = -1, mx = -Infinity;
      for (let k = 0; k < Math.min(c, nClases); k++) {
        const v = labels[i * c + k];
        if (v > mx) { mx = v; mejor = k; }
      }
      if (mejor < 0) continue;
      const conf = sigmoide(mx);
      if (conf < minConf) continue;
      const cx = dets[i * 4], cy = dets[i * 4 + 1], w = Math.max(0, dets[i * 4 + 2]), h = Math.max(0, dets[i * 4 + 3]);
      res.push({ idx: mejor, conf, caja: [acotar(cx - w / 2), acotar(cy - h / 2), acotar(cx + w / 2), acotar(cy + h / 2)] });
    }
    return res.sort((a, b) => b.conf - a.conf);
  }

  // ort: onnxruntime (web o node). meta: contenido de modelo.json. buffer: bytes del .onnx o ruta.
  async function crear(ort, meta, modelo, opciones) {
    const sesion = await ort.InferenceSession.create(modelo, opciones || { executionProviders: ['wasm'] });
    const forma = meta.entrada.forma;
    const H = forma[2], W = forma[3];
    const lienzo = typeof document !== 'undefined' ? document.createElement('canvas') : null;
    if (lienzo) { lienzo.width = W; lienzo.height = H; }
    const ctx = lienzo && lienzo.getContext('2d', { willReadFrequently: true });
    const nombreEntrada = meta.entrada.nombre;

    async function correr(tensorDatos, minConf) {
      const salida = await sesion.run({ [nombreEntrada]: new ort.Tensor('float32', tensorDatos, [1, 3, H, W]) });
      const d = salida.dets, l = salida.labels;
      const q = d.dims[1], c = l.dims[2];
      return decodificar(d.data, l.data, q, c, meta.clases.length, minConf).map(r => ({ ...r, clase: meta.clases[r.idx] }));
    }

    return {
      meta,
      // fuente: <video> o <canvas>
      async detectar(fuente, minConf) {
        ctx.drawImage(fuente, 0, 0, W, H);
        return correr(preparar(ctx.getImageData(0, 0, W, H).data, W, H), minConf);
      },
      correr, // para pruebas: recibe el Float32Array ya preparado
    };
  }

  const api = { preparar, decodificar, crear };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else raiz.DetectorONNX = api;
})(typeof window !== 'undefined' ? window : globalThis);
