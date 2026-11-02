"""Exporta el mejor checkpoint a ONNX y genera modelo.json para la app.

  python exportar.py --checkpoint corrida/checkpoint_best_total.pth --umbral umbral.json --salida export/

Resultado en export/:  <modelo>.onnx  +  modelo.json (clases, resolución, umbral, entradas/salidas).
Después copia ambos a vigia-app/ para usarlos con onnxruntime-web.
"""
import argparse
import json
from pathlib import Path

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True, type=Path)
    ap.add_argument("--umbral", type=Path, help="umbral.json generado por evaluar.py")
    ap.add_argument("--salida", type=Path, default=Path("export"))
    ap.add_argument("--copiar-a", type=Path, help="Carpeta modelo/ de la app, p. ej. ../vigia-app/modelo")
    a = ap.parse_args()

    from rfdetr import RFDETR

    modelo = RFDETR.from_checkpoint(str(a.checkpoint))
    a.salida.mkdir(parents=True, exist_ok=True)
    ruta = Path(modelo.export(output_dir=str(a.salida)))
    print(f"ONNX: {ruta}")

    import onnxruntime as ort
    sesion = ort.InferenceSession(str(ruta), providers=["CPUExecutionProvider"])
    entrada = sesion.get_inputs()[0]
    salidas = [o.name for o in sesion.get_outputs()]
    # prueba de humo: una pasada con ruido, comprueba que el grafo corre
    forma = [d if isinstance(d, int) else 1 for d in entrada.shape]
    sesion.run(None, {entrada.name: np.random.rand(*forma).astype(np.float32)})

    umbral = 0.5
    if a.umbral and a.umbral.exists():
        umbral = json.loads(a.umbral.read_text(encoding="utf-8"))["umbral"]
    meta = {
        "archivo": ruta.name,
        "clases": modelo.class_names,
        "entrada": {"nombre": entrada.name, "forma": entrada.shape},
        "salidas": salidas,
        "umbral": umbral,
        "nota": "Entrada RGB float32 NCHW normalizada con media ImageNet [0.485,0.456,0.406] y desv [0.229,0.224,0.225]. El formato de las salidas (cajas/logits) se confirma con 'salidas' al integrar en la app.",
    }
    (a.salida / "modelo.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Metadatos: {a.salida / 'modelo.json'}  (umbral {umbral})")

    if a.copiar_a:
        import shutil
        a.copiar_a.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ruta, a.copiar_a / ruta.name)
        shutil.copy2(a.salida / "modelo.json", a.copiar_a / "modelo.json")
        print(f"Copiado a la app: {a.copiar_a}")


if __name__ == "__main__":
    main()
