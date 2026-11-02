# Datos

Casi todo lo que hay en esta carpeta **no se sube a git** (ver `.gitignore`): son varios GB y se regeneran
con los scripts de `../entrenamiento/`. Solo se versiona este archivo y la galería de prueba.

## Qué hay (en el equipo donde se entrenó)

| Carpeta o archivo | Qué es | En git |
|---|---|---|
| `fotos_para_probar_v2/` | 40 fotos de prueba (15 heces, 15 basura, 10 sin nada), `galeria.html` y `respuestas.txt` | sí |
| `fotos_para_probar/` | galería anterior, solo heces | no |
| `scatspotter_tar/`, `scatspotter_val/` | shards originales de ScatSpotter descargados de Hugging Face | no |
| `taco_zip/`, `taco_raw/` | TACO original (zip y extraído) | no |
| `fotos_scat/`, `fotos_taco/`, `fotos_todo/` | fotos reducidas con `anotaciones.json` (intermedios de los importadores) | no |
| `dataset/`, `dataset2/` | datasets finales `train/valid/test` (v1 heces; v2 heces + basura) | no |
| `colab_paquete.zip`, `colab_paquete_v2.zip` | paquetes que se suben a Google Drive para Colab | no |
| `modelo_vigia_heces.zip`, `modelo_vigia_heces_basura.zip` | modelos exportados (ONNX + `modelo.json`) | no |
| `_export/`, `_export2/` | modelos extraídos y fotos para evaluar el ONNX en el PC | no |

## Cómo regenerar el dataset v2

```bash
# desde vigia-app/entrenamiento
python importar_scatspotter.py --tar ../datos/scatspotter_tar/*.tar ../datos/scatspotter_val/*.tar --salida ../datos/fotos_scat
python importar_taco.py --raiz ../datos/taco_raw/TACO/data --salida ../datos/fotos_taco
python combinar_coco.py --fuente ../datos/fotos_scat ../datos/fotos_taco --clases heces basura --salida ../datos/fotos_todo
python preparar_dataset.py --imagenes ../datos/fotos_todo --coco ../datos/fotos_todo/anotaciones.json --clases heces basura --salida ../datos/dataset2
```


Dónde conseguir los datos originales:

- **ScatSpotter**: <https://huggingface.co/datasets/frovolts/shitspotter> (shards `.tar` webdataset).
- **TACO**: <https://tacodataset.org> o <https://zenodo.org/records/3587843> (`TACO.zip`).

## Atribución (CC BY 4.0)

Las fotos de `fotos_para_probar_v2/` salen de ScatSpotter (Crall) y TACO (Proença y Simões), ambos bajo
CC BY 4.0. Hay que conservar esta atribución si se redistribuyen.
