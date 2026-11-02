# Cómo funciona la app

Todo el análisis ocurre **en el navegador del celular**. El servidor (nginx en Cloud Run, o `servidor.js` en
local) solo entrega archivos estáticos. No se envía video a ningún lado.

```
cámara del celular ──► cuadro (3 por segundo)
        │
        ├─► detector.js: redimensiona a 512×512, normaliza, corre el modelo ONNX (onnxruntime-web)
        │        └─► lista de {clase, confianza, caja}
        ├─► COCO-SSD (TensorFlow.js): solo detecta personas
        │
        ▼
 seguimiento por IoU ──► regla de persistencia ──► alerta ──► lista en pantalla
                                                               ├─► foto con personas pixeladas
                                                               ├─► Enviar aseo / Descartar
                                                               ├─► exportar JSONL
                                                               └─► webhook (opcional)
```

## Archivos

| Archivo | Qué hace |
|---|---|
| `index.html` | Interfaz y estilos. Carga las librerías desde jsDelivr (tfjs, coco-ssd, onnxruntime-web). |
| `app.js` | Cámara, seguimiento, reglas de alerta, evidencias, ajustes, exportación y webhook. |
| `detector.js` | Prepara la imagen, ejecuta el ONNX y decodifica las salidas. |
| `modelo/modelo.json` | Clases, tamaño de entrada y umbrales del modelo. La app lo lee al iniciar. |
| `manifest.json` | Hace la página instalable como PWA. |

## El modelo (entrada y salida)

- Entrada `input`: `[1,3,512,512]` float32, RGB, escalado directo a 512×512 (sin bordes negros) y
  normalizado con media ImageNet (0,485 / 0,456 / 0,406) y desviación (0,229 / 0,224 / 0,225).
- Salidas: `dets` `[1,Q,4]` con cajas `cx,cy,w,h` normalizadas, y `labels` `[1,Q,C]` con logits por clase.
  La confianza es la sigmoide del logit mayor. El canal sobrante (C = clases + 1) se ignora.
- Si no hay modelo propio, la app usa COCO-SSD en **modo prueba**.

## Regla de alerta

1. **Seguimiento:** cada detección se asocia a un objeto ya visto si las cajas se solapan (IoU); si no, nace uno nuevo.
2. **Quieto:** se mide cuánto tiempo la caja casi no se mueve.
3. **Alerta:** se abre cuando `confianza ≥ umbral de la clase`, `quieto ≥ persistencia` y no hay persona cerca.
4. **Cierre:** si el objeto no aparece durante 4 s, se cierra y se registra `respuesta_s`.

### Umbral por clase

El control de *Confianza* fija un umbral base (`modelo.json` → `umbral`). Cada clase le suma la diferencia
entre su umbral medido y el base (`umbrales`). Con base 0,40, `basura` usa 0,40 y `heces` usa 0,50. Si el
usuario ya movió el control, se respeta su valor guardado.

## Formato de la alerta (JSON)

```json
{
  "id": "A-1761750000000",
  "evento": "alerta",
  "camara": "Parque infantil",
  "clase": "heces",
  "hora": "2026-10-29T08:15:00",
  "persistio_s": 120,
  "respuesta_s": null,
  "confianza": 0.87,
  "caja": [0.41, 0.62, 0.47, 0.68]
}
```
Los eventos son `alerta` y `cerrada` (esta con `respuesta_s`). Un webhook recibe este JSON por POST.

## Qué falta para operar de verdad

Base de datos y backend que reciban las alertas y las fotos, historial, panel de revisión humana antes de
cualquier sanción, y detección en servidor para varias cámaras. Ver [README](../README.md#limitaciones).
