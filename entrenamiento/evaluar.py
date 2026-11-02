"""Evalúa el modelo en el conjunto de prueba y propone el umbral de confianza.

  python evaluar.py --checkpoint corrida/checkpoint_best_total.pth --dataset dataset/ --parte test

Mide precisión/recall por caja (IoU >= 0.5) a varios umbrales, y falsos positivos por
imagen negativa (fondo). Escribe umbral.json con el umbral que cumple la precisión meta
con el mayor recall. La evaluación por EVENTO (alerta tras N segundos) se hace después,
con video real: este script solo mide por imagen.
"""
import argparse
import json
from pathlib import Path

import numpy as np

IOU_MIN = 0.5


def iou_xyxy(a, b) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def contar(preds, gts, umbral):
    """preds: [(xyxy, conf, clase)], gts: [(xyxy, clase)] de UNA imagen. Devuelve (tp, fp, fn)."""
    preds = sorted((p for p in preds if p[1] >= umbral), key=lambda p: -p[1])
    libres = set(range(len(gts)))
    tp = 0
    for caja, _, clase in preds:
        mejor, mejor_iou = None, IOU_MIN
        for j in libres:
            if gts[j][1] != clase:
                continue
            v = iou_xyxy(caja, gts[j][0])
            if v >= mejor_iou:
                mejor, mejor_iou = j, v
        if mejor is not None:
            libres.discard(mejor)
            tp += 1
    return tp, len(preds) - tp, len(libres)


def barrido(imagenes, umbrales, precision_meta):
    """imagenes: [(preds, gts)]. Devuelve (filas, umbral_elegido o None)."""
    filas = []
    for u in umbrales:
        tp = fp = fn = fp_neg = 0
        n_neg = sum(1 for _, g in imagenes if not g)
        for preds, gts in imagenes:
            a, b, c = contar(preds, gts, u)
            tp += a; fp += b; fn += c
            if not gts:
                fp_neg += b
        prec = tp / (tp + fp) if tp + fp else 1.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        filas.append({"umbral": round(float(u), 2), "precision": round(prec, 3), "recall": round(rec, 3),
                      "tp": tp, "fp": fp, "fn": fn,
                      "fp_por_imagen_negativa": round(fp_neg / n_neg, 3) if n_neg else None})
    validos = [f for f in filas if f["precision"] >= precision_meta and f["tp"] > 0]
    elegido = max(validos, key=lambda f: (f["recall"], -f["umbral"]), default=None)
    return filas, elegido


def cargar_gt(carpeta: Path):
    coco = json.loads((carpeta / "_annotations.coco.json").read_text(encoding="utf-8"))
    nombres = {c["id"]: c["name"] for c in coco["categories"]}
    por_img = {im["id"]: (im["file_name"], []) for im in coco["images"]}
    for an in coco["annotations"]:
        x, y, w, h = an["bbox"]
        por_img[an["image_id"]][1].append(([x, y, x + w, y + h], nombres[an["category_id"]]))
    return list(por_img.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True, type=Path)
    ap.add_argument("--dataset", required=True, type=Path)
    ap.add_argument("--parte", default="test", choices=["valid", "test"])
    ap.add_argument("--precision-meta", type=float, default=0.70)
    ap.add_argument("--salida", type=Path, default=Path("umbral.json"))
    a = ap.parse_args()

    from PIL import Image
    from rfdetr import RFDETR

    modelo = RFDETR.from_checkpoint(str(a.checkpoint))
    nombres = modelo.class_names
    carpeta = a.dataset / a.parte
    imagenes = []
    for archivo, gts in cargar_gt(carpeta):
        det = modelo.predict(Image.open(carpeta / archivo).convert("RGB"), threshold=0.05)
        # la cabeza del modelo tiene una posición sobrante (índice >= len(nombres)); se descarta
        preds = [(list(map(float, b)), float(c), nombres[int(k)])
                 for b, c, k in zip(det.xyxy, det.confidence, det.class_id) if 0 <= int(k) < len(nombres)]
        imagenes.append((preds, gts))

    filas, elegido = barrido(imagenes, np.arange(0.1, 0.96, 0.05), a.precision_meta)
    print(f"{'umbral':>7} {'prec':>6} {'recall':>7} {'TP':>5} {'FP':>5} {'FN':>5} {'FP/img neg':>11}")
    for f in filas:
        print(f"{f['umbral']:>7} {f['precision']:>6} {f['recall']:>7} {f['tp']:>5} {f['fp']:>5} {f['fn']:>5} {str(f['fp_por_imagen_negativa']):>11}")
    if elegido:
        print(f"\nUmbral propuesto: {elegido['umbral']} (precisión {elegido['precision']}, recall {elegido['recall']})")
        a.salida.write_text(json.dumps({"umbral": elegido["umbral"], "precision_meta": a.precision_meta,
                                        "metricas": elegido, "parte": a.parte}, indent=2), encoding="utf-8")
    else:
        print(f"\nNingún umbral alcanza precisión {a.precision_meta}. Más datos, más negativos difíciles o otra ronda.")


if __name__ == "__main__":
    main()
