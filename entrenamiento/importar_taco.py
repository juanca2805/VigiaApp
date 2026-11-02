"""Convierte TACO (Trash Annotations in Context) a la carpeta intermedia de combinar_coco.py.

Une las 60 categorías en una sola clase ("basura"), reduce las fotos, escala las cajas y
renombra como taco_bNN_<id>.jpg (el lote sirve de grupo para dividir train/valid/test).

Descartes (se informan al final):
  --excluir          categorías que no se quieren (por defecto 'Cigarette': colillas, demasiado pequeñas)
  --min-lado         cajas cuyo lado mayor es < esta fracción de la foto (a 512 px, 0.03 = ~15 px)
  fotos cuyas únicas cajas eran descartadas se omiten (si no, enseñarían que esa basura es fondo)

Datos: TACO (Proença y Simões), CC BY 4.0 — https://tacodataset.org · doi:10.5281/zenodo.3587843

  python importar_taco.py --raiz taco_raw/TACO/data --salida fotos_taco
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", required=True, type=Path, help="carpeta TACO/data (con annotations.json y batch_*)")
    ap.add_argument("--salida", required=True, type=Path)
    ap.add_argument("--clase", default="basura")
    ap.add_argument("--excluir", nargs="*", default=["Cigarette"])
    ap.add_argument("--min-lado", type=float, default=0.03)
    ap.add_argument("--max-lado", type=int, default=1024)
    ap.add_argument("--calidad", type=int, default=80)
    a = ap.parse_args()

    coco = json.loads((a.raiz / "annotations.json").read_text(encoding="utf-8"))
    nombre = {c["id"]: c["name"] for c in coco["categories"]}
    por_img = {}
    for an in coco["annotations"]:
        por_img.setdefault(an["image_id"], []).append(an)

    a.salida.mkdir(parents=True, exist_ok=True)
    imgs, anns, cuenta = [], [], Counter()
    for im_info in coco["images"]:
        todas = por_img.get(im_info["id"], [])
        W, H = im_info["width"], im_info["height"]
        buenas = []
        for an in todas:
            if nombre[an["category_id"]] in a.excluir:
                cuenta["cajas excluidas por categoría"] += 1
            elif max(an["bbox"][2], an["bbox"][3]) / max(W, H) < a.min_lado:
                cuenta["cajas descartadas por pequeñas"] += 1
            else:
                buenas.append(an)
        if not buenas:
            cuenta["fotos omitidas (sin cajas útiles)"] += 1
            continue

        im = Image.open(a.raiz / im_info["file_name"])
        raw, rot = im.size, ImageOps.exif_transpose(im)
        if rot.size == (W, H):
            im = rot                      # el JSON se anotó con la orientación EXIF aplicada
        elif raw == (W, H):
            pass                          # el JSON se anotó sin aplicar EXIF
        else:
            cuenta["fotos omitidas (tamaño no coincide con el JSON)"] += 1
            continue
        im = im.convert("RGB")
        esc = min(1.0, a.max_lado / max(W, H))
        im = im.resize((round(W * esc), round(H * esc)), Image.LANCZOS)
        lote = int(re.search(r"batch_(\d+)", im_info["file_name"])[1])
        iid = len(imgs) + 1
        fn = f"taco_b{lote:02d}_{iid:05d}.jpg"
        im.save(a.salida / fn, quality=a.calidad)
        imgs.append({"id": iid, "file_name": fn, "width": im.size[0], "height": im.size[1]})
        for an in buenas:
            x, y, w, h = [v * esc for v in an["bbox"]]
            anns.append({"id": len(anns) + 1, "image_id": iid, "category_id": 1,
                         "bbox": [round(x, 1), round(y, 1), round(w, 1), round(h, 1)],
                         "area": round(w * h, 1), "iscrowd": 0})

    out = {"images": imgs, "annotations": anns, "categories": [{"id": 1, "name": a.clase}]}
    (a.salida / "anotaciones.json").write_text(json.dumps(out), encoding="utf-8")
    for k, v in cuenta.items():
        print(f"  {k}: {v}")
    print(f"{len(imgs)} imágenes, {len(anns)} cajas de '{a.clase}', {len({i['file_name'].split('_')[1] for i in imgs})} lotes")


if __name__ == "__main__":
    main()
