# Modelo y entrenamiento

## Resumen

| | |
|---|---|
| Modelo | RF-DETR *small* (Apache 2.0), `rfdetr==1.11.2` |
| Resolución | 512 × 512 |
| Clases | `heces`, `basura` |
| Dónde se entrena | Google Colab con GPU T4 (el PC de desarrollo tiene GPU AMD, sin CUDA) |
| Formato final | ONNX (`modelo/rfdetr-small.onnx`, ~120 MB) + `modelo/modelo.json` |
| Duración | ~3 min por época; paro anticipado tras 10 épocas sin mejorar |

## Datos

| Fuente | Clase | Licencia | Qué se hizo |
|---|---|---|---|
| ScatSpotter (Crall) | `heces` | CC BY 4.0 | Fotos con celular de heces de perro en exteriores. Se redujeron a 1280 px. |
| TACO | `basura` | CC BY 4.0 | 60 categorías de basura unidas en una sola clase. Se excluyó `Cigarette` (colillas, muy pequeñas) y las cajas con lado mayor < 3 % de la foto. |

Conjunto final (`dataset2`): 1970 fotos de entrenamiento, 429 de validación y 441 de prueba.

| | Train | Valid | Test |
|---|---|---|---|
| Cajas `heces` | 926 | 189 | 145 |
| Cajas `basura` | 2205 | 416 | 552 |

### Por qué se divide por grupo y no por foto

Las fotos del mismo día (ScatSpotter) o del mismo lote (TACO) se parecen mucho entre sí. Si unas caen en
entrenamiento y otras en prueba, el modelo parece mejor de lo que es. Por eso los nombres de archivo llevan
`<fuente>_<fecha o lote>_<id>.jpg` y `preparar_dataset.py` reparte **grupos completos**.

### Limitaciones de los datos

- **Etiquetas parciales:** las fotos de heces no marcan la basura que pudiera haber, y las de basura no marcan
  heces. El modelo puede aprender que "basura junto a heces" es fondo.
- **Brecha de dominio:** son primeros planos de celular, no cámaras fijas de un conjunto residencial.
- Los negativos (fotos sin objetos) son esenciales para que aprenda a ignorar hojas, sombras y charcos.

## Pipeline

```
importar_scatspotter.py ─┐
                         ├─► combinar_coco.py ─► preparar_dataset.py ─► entrenar.py ─► evaluar.py ─► exportar.py
importar_taco.py ────────┘     (clases unificadas)   (train/valid/test     (checkpoint)   (umbral)      (.onnx + modelo.json)
                                                     por grupo)
```

Los comandos paso a paso están en [../entrenamiento/README.md](../entrenamiento/README.md), y el cuaderno
`entrenamiento/entrenar_colab.ipynb` ejecuta todo en Colab.

## Resultados

Umbrales elegidos con el conjunto de **validación**; resultado final sobre **prueba**. Una detección cuenta
como correcta si su caja se solapa con la real al menos 50 % (IoU 0,5) y es de la misma clase.

### Modelo de dos clases (el desplegado), prueba, por clase

| Clase | Umbral | Precisión | Recall | Aciertos | Falsas | Perdidas |
|---|---|---|---|---|---|---|
| `heces` | 0,3 | 61 % | 57 % | 82 | 53 | 63 |
| `heces` | 0,4 | 71 % | 52 % | 75 | 30 | 70 |
| `heces` | **0,5** | 81 % | 48 % | 69 | 16 | 76 |
| `heces` | 0,6 | 87 % | 40 % | 58 | 9 | 87 |
| `basura` | 0,3 | 78 % | 72 % | 400 | 112 | 152 |
| `basura` | **0,4** | 85 % | 68 % | 377 | 67 | 175 |
| `basura` | 0,5 | 88 % | 66 % | 363 | 48 | 189 |
| `basura` | 0,6 | 92 % | 63 % | 345 | 31 | 207 |

En negrita, el umbral que usa la app. Las dos clases juntas con un solo umbral (0,3) daban 74,4 % de
precisión y 69,9 % de recall en prueba, pero con 0,24 falsas alarmas por foto sin objetos.
Se mantuvo un umbral **por clase** porque `heces` es más difícil que `basura`.

### Modelo anterior (solo heces)

Con 962 / 208 / 209 fotos y umbral 0,45: precisión 82 %, recall 58 % en prueba. El conjunto de prueba era
otro (ScatSpotter completo, sin TACO), así que no se compara de forma directa con el de dos clases.

## Por qué estos números todavía no bastan

1. Son métricas **por foto**. El sistema real alerta por **evento** (objeto quieto N segundos), donde las
   falsas alarmas puntuales se filtran pero las pérdidas también se acumulan. Falta evaluarlo con video.
2. Faltan fotos reales de las cámaras del conjunto (distancia, ángulo, luz nocturna, lluvia).
3. Recall de heces cercano al 50 %: se necesitan más datos de heces, no más épocas.

## Reentrenar

1. Reúne fotos y anotaciones COCO (CVAT, Roboflow, Label Studio) nombradas `<camara>_<AAAA-MM-DD>_<id>.jpg`.
2. Sigue [../entrenamiento/README.md](../entrenamiento/README.md).
3. Elige el umbral en `valid` y confírmalo **una sola vez** en `test`; si lo ajustas mirando `test`, esa
   métrica deja de ser honesta.
4. Copia el `.onnx` y `modelo.json` a `modelo/`. En `modelo.json` puedes añadir `umbrales` por clase.

Plan inicial (métricas objetivo, cronograma, riesgos): [plan_entrenamiento_heces.md](plan_entrenamiento_heces.md).
