# Entrenamiento (RF-DETR, Apache 2.0)

Scripts para preparar datos, entrenar, evaluar y exportar el modelo de `heces` y `basura`.
Contexto, datos y resultados: [../docs/modelo-y-entrenamiento.md](../docs/modelo-y-entrenamiento.md).

Se entrenó en **Google Colab (GPU T4)** con `entrenar_colab.ipynb`. En un PC sin GPU NVIDIA solo se pueden
correr los scripts de preparación de datos.

## Scripts

| Script | Para qué |
|---|---|
| `importar_scatspotter.py` | Convierte shards `.tar` de ScatSpotter a fotos reducidas + `anotaciones.json` (clase `heces`). Nombra `foto_<fecha>_<id>.jpg`. |
| `importar_taco.py` | Convierte TACO: une las 60 categorías en `basura`, quita `Cigarette` y cajas diminutas. Nombra `taco_bNN_<id>.jpg` (el lote es el grupo). |
| `combinar_coco.py` | Junta carpetas importadas en una sola con las clases unificadas (`--clases heces basura`). |
| `preparar_dataset.py` | Convierte un COCO en `train/valid/test` **repartiendo grupos completos** (cámara + fecha, o fuente + lote). |
| `entrenar.py` | Entrena RF-DETR (`--tamano nano\|small\|medium`). Paro anticipado con paciencia 10. |
| `evaluar.py` | Precisión/recall para umbrales 0,1 a 0,95 (IoU 0,5) y escribe `umbral.json`. |
| `exportar.py` | Exporta a ONNX, lo prueba con onnxruntime y escribe `modelo.json`. |
| `entrenar_colab.ipynb` | Ejecuta todo lo anterior en Colab (descarga del paquete desde Google Drive). |

## Flujo

```
fotos + anotaciones COCO ──► preparar_dataset.py ──► dataset/{train,valid,test}
                                                         │
                          entrenar.py ◄──────────────────┘
                              │ corrida/checkpoint_best_total.pth
                          evaluar.py  ──► umbral.json
                              │
                          exportar.py ──► export/<modelo>.onnx + modelo.json
```

## Pasos

```bash
pip install -r requirements.txt

# 1. Datos (ver ../datos/README.md para regenerar el dataset de ScatSpotter + TACO)
python preparar_dataset.py --imagenes fotos/ --coco anotaciones.json --clases heces basura --salida dataset/

# 2. Entrenar. Prueba corta primero (--epocas 2) para verificar que todo corre
python entrenar.py --dataset dataset/ --tamano small --epocas 50 --salida corrida

# 3. Evaluar: umbral en valid, confirmación única en test
python evaluar.py --checkpoint corrida/checkpoint_best_total.pth --dataset dataset/ --parte valid
python evaluar.py --checkpoint corrida/checkpoint_best_total.pth --dataset dataset/ --parte test

# 4. Exportar y dejar el modelo en la app
python exportar.py --checkpoint corrida/checkpoint_best_total.pth --umbral umbral.json --salida export/ --copiar-a ../modelo
```

La app lee `modelo/modelo.json` al iniciar y usa el modelo propio; sin él cae al modo prueba (COCO-SSD).

### Usar Colab

1. Genera `colab_paquete_v2.zip` (scripts + `dataset2`) y súbelo a Google Drive. La subida directa a Colab
   se cortaba con archivos grandes; por Drive se copia completo.
2. Abre `entrenar_colab.ipynb` en Colab con GPU T4 y ejecuta las celdas en orden. La celda de instalación
   comprueba que `rfdetr` se importe y la de copia verifica el tamaño exacto del zip.
3. Descarga `modelo_vigia.zip` (ONNX + `modelo.json`) y pega los resultados de `evaluar.py`.

## Notas

- **Umbral por clase:** `evaluar.py` calcula un solo umbral (el de mayor recall entre los que tienen precisión ≥ 70 %).
  Con dos clases de dificultad distinta conviene afinarlo por clase y añadir `"umbrales": {"heces": 0.5, "basura": 0.4}`
  a `modelo.json`; la app lo aplica (ver [../docs/arquitectura.md](../docs/arquitectura.md)).
- **Clases del cabezal:** los ids de categoría se reasignan a 0..N-1 y el cabezal tiene N+1 salidas; la
  sobrante se ignora (`evaluar.py` y `detector.js` ya la descartan).
- **Fotos sin objetos** (carpeta `--negativos` o imágenes sin cajas) enseñan hojas, sombras y charcos.
- Si el script avisa "sin patrón camara_fecha_", esas imágenes quedan juntas en una sola parte: renómbralas.
- No toques `test` para elegir umbrales: si lo haces, esa métrica deja de ser honesta.
- Versión probada: `rfdetr==1.11.2` (la API cambia entre versiones).
