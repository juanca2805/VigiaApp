# Vigía de aseo

Herramienta de visión por computador para un **conjunto residencial en Bogotá, Colombia**. Una cámara
detecta **heces de perro y basura** en zonas comunes y genera una **alerta con foto de evidencia** para el
administrador y el personal de aseo. Una alerta **nunca es una multa**: toda sanción exige revisión humana.

Esta versión es un **prototipo funcional** que corre completo en el navegador del celular (PWA). Sirve para
demostrar que la detección funciona; todavía no es un sistema de operación (ver [Limitaciones](#limitaciones)).

> Demo desplegada en Cloud Run: <https://vigia-aseo-123029776689.us-east1.run.app> (abrir desde el celular y permitir la cámara).

## Qué hace

- Muestra la cámara del celular y analiza **3 cuadros por segundo** con un modelo propio (RF-DETR, formato ONNX).
- Detecta dos clases: `heces` y `basura`. La clase `persona` se detecta con COCO-SSD, solo para no alertar
  mientras alguien está cerca y para pixelar a las personas en las fotos.
- **Regla de alerta (persistencia):** se abre una alerta si el objeto
  1. supera la confianza configurada (cada clase con su propio umbral),
  2. lleva **quieto** al menos N segundos (10 s en pruebas; 120 s o más en producción),
  3. y **no hay una persona cerca** (distancia configurable).
- Cuando el objeto desaparece 4 s, la alerta se **cierra** y se registra `respuesta_s`.
- Cada alerta guarda una **foto con las personas en mosaico**, y tiene los botones *Enviar aseo* y *Descartar*.
- Exporta las alertas en JSONL y puede enviarlas a un **webhook** (n8n, WhatsApp, correo).
- No hay reconocimiento facial.

## Resultados del modelo

RF-DETR *small*, 512 px, entrenado en Google Colab (T4) con ScatSpotter (heces) y TACO (basura).
Medido sobre fotos de **prueba que el entrenamiento no vio**, separadas por fecha o lote (no por foto):

| Clase | Umbral | Precisión | Recall |
|---|---|---|---|
| `heces` | 0,50 | 81 % | 48 % |
| `basura` | 0,40 | 85 % | 68 % |

Con el modelo solo de heces (versión anterior) se midió 82 % de precisión y 58 % de recall a umbral 0,45, pero
con otro conjunto de prueba, por lo que no es comparable de forma directa.
Detalle, método y advertencias: [docs/modelo-y-entrenamiento.md](docs/modelo-y-entrenamiento.md).

## Estructura del repositorio

```
vigia-app/
├── index.html, app.js, detector.js, manifest.json   la app (HTML/CSS/JS puro, sin compilar)
├── modelo/              modelo.json (clases y umbrales) y el .onnx (no está en git, ver abajo)
├── servidor.js          servidor HTTPS local para probar en el celular
├── Dockerfile, nginx.conf, .gcloudignore   despliegue en Cloud Run
├── entrenamiento/       scripts de Python y cuaderno de Colab para entrenar, evaluar y exportar
├── datos/               datos de entrenamiento y galería de prueba (casi todo fuera de git, ver datos/README.md)
└── docs/
    ├── contexto_proyecto.md          idea original, usuarios, reglas, restricciones legales
    ├── arquitectura.md               cómo funciona la app por dentro
    ├── modelo-y-entrenamiento.md     datos, entrenamiento, métricas y umbrales
    ├── despliegue.md                 correr en local y publicar en Cloud Run
    └── plan_entrenamiento_heces.md   plan inicial del modelo de heces
```

## Cómo probarlo

**Opción A: la demo publicada.** Abre la URL de arriba en el celular, pulsa *Iniciar* y apunta a las fotos de
`datos/fotos_para_probar_v2/galeria.html` (las respuestas están en `respuestas.txt`).

**Opción B: en tu red local.**
```bash
cd vigia-app
# 1. consigue el modelo (ver "El modelo no está en git") y déjalo en modelo/
# 2. genera un certificado autofirmado (la cámara del navegador exige HTTPS):
openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=vigia"
node servidor.js        # https://<IP-de-tu-PC>:8443 desde el celular, en la misma WiFi
```
Más detalle (firewall, Cloud Run) en [docs/despliegue.md](docs/despliegue.md).

### El modelo no está en git

`modelo/rfdetr-small.onnx` pesa unos 120 MB y GitHub rechaza archivos de más de 100 MB, por eso está en la
[Release `modelo-v2`](https://github.com/juanca2805/VigiaApp/releases/tag/modelo-v2). Descarga `rfdetr-small.onnx`
y `modelo.json` y déjalos en `modelo/`, o con la CLI de GitHub:
```bash
gh release download modelo-v2 --repo juanca2805/VigiaApp --dir modelo --clobber
```
También puedes reentrenarlo siguiendo [entrenamiento/README.md](entrenamiento/README.md). Sin el `.onnx`, la app cae al
**modo prueba** (COCO-SSD: detecta botellas, vasos y mochilas como "basura" para validar el flujo).

## Limitaciones

- **No hay base de datos ni backend.** Las alertas viven en la memoria de la página (se pierden al recargar);
  solo los ajustes se guardan en `localStorage`. Se pueden exportar a JSONL o enviar a un webhook.
- Un celular ve **una sola cámara**; con varias cámaras IP haría falta correr la detección en un servidor.
- Las fotos de entrenamiento son de **primeros planos hechos con celular**; las cámaras fijas del conjunto
  verán cosas más pequeñas y lejanas. Falta entrenar con fotos reales del conjunto.
- Recall de heces ≈ 48 %: de cada dos heces, una se escapa. Hay que reentrenar con más datos antes de operar.
- Va "un poquito lento" en el celular (se probó en un teléfono; no se midió el tiempo por cuadro).
- Los umbrales se calcularon sobre fotos sueltas, no sobre eventos con persistencia.
- Faltan las clases `derrame` y `piso sucio` del documento original.

## Privacidad y legal (Colombia)

Las imágenes son datos personales (Ley 1581 de 2012: aviso visible, finalidad clara, conservación corta). Las
multas en propiedad horizontal exigen debido proceso (Ley 675 de 2001). Más en
[docs/contexto_proyecto.md](docs/contexto_proyecto.md).

## Licencias y atribuciones

- Modelo base **RF-DETR** (Roboflow): Apache 2.0.
- Datos de heces: **ScatSpotter** (Crall), CC BY 4.0, <https://huggingface.co/datasets/frovolts/shitspotter>.
- Datos de basura: **TACO** (Proença y Simões), CC BY 4.0, <https://tacodataset.org>, doi:10.5281/zenodo.3587843.
- Librerías en el navegador: TensorFlow.js y COCO-SSD (Apache 2.0), onnxruntime-web (MIT).
- Este repositorio todavía no tiene licencia propia: defínela antes de publicarlo.

## Integración con el panel de Condo Manager

El panel de seguridad registra cada celular como una cámara con su ubicación y genera un enlace de vinculación:

```
https://<vigia>/?camara=Pasillo%20piso%203&hook=https%3A%2F%2F<api>%2Fsecurity%2Freports%3Ftoken%3D<token>
```

Al abrirlo, la app guarda el nombre de la cámara y el webhook y limpia la dirección. Cada alerta se envía al panel con su foto y, mientras la cámara está activa, un latido cada 30 s la mantiene "en línea". También puede configurarse a mano en Ajustes (Camara y Webhook).
