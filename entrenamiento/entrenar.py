"""Entrena (fine-tuning) RF-DETR sobre el dataset preparado.

  python entrenar.py --dataset dataset/ --tamano nano --epocas 60
  python entrenar.py --dataset dataset/ --tamano small --resolucion 640 --salida corrida2

Para continuar una corrida interrumpida:  --reanudar corrida/checkpoint.pth
Para segunda ronda con falsos positivos nuevos: vuelve a preparar el dataset y
entrena con otro --salida (parte de los pesos COCO, no de la corrida anterior).
"""
import argparse
from pathlib import Path

import rfdetr

TAMANOS = {"nano": rfdetr.RFDETRNano, "small": rfdetr.RFDETRSmall, "medium": rfdetr.RFDETRMedium}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, type=Path)
    ap.add_argument("--tamano", choices=TAMANOS, default="nano")
    ap.add_argument("--epocas", type=int, default=60)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--acumular", type=int, default=4, help="grad_accum_steps (batch efectivo = batch*acumular)")
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--resolucion", type=int, help="Debe ser divisible por patch_size*num_windows; usa el valor por defecto si dudas")
    ap.add_argument("--salida", type=Path, default=Path("corrida"))
    ap.add_argument("--reanudar", type=Path)
    a = ap.parse_args()

    for parte in ("train", "valid"):
        if not (a.dataset / parte / "_annotations.coco.json").exists():
            raise SystemExit(f"Falta {a.dataset / parte / '_annotations.coco.json'}. Corre preparar_dataset.py primero.")

    modelo = TAMANOS[a.tamano]()
    kwargs = dict(
        dataset_dir=str(a.dataset),
        epochs=a.epocas,
        batch_size=a.batch,
        grad_accum_steps=a.acumular,
        lr=a.lr,
        output_dir=str(a.salida),
        early_stopping=True,
        early_stopping_patience=10,
    )
    if a.resolucion:
        kwargs["resolution"] = a.resolucion
    if a.reanudar:
        kwargs["resume"] = str(a.reanudar)
    modelo.train(**kwargs)
    print(f"\nListo. Mejor checkpoint: {a.salida / 'checkpoint_best_total.pth'}")


if __name__ == "__main__":
    main()
