"""Combina varias carpetas (JPG + anotaciones.json COCO) en una sola con clases unificadas.

Cada carpeta de entrada sale de un importador (importar_scatspotter.py, importar_taco.py) y
usa nombres de clase propios. Aquí se unifican por NOMBRE en el orden de --clases
(el orden fija el índice de clase del modelo: heces=0, basura=1, ...).

  python combinar_coco.py --fuente fotos_scat fotos_taco --clases heces basura --salida fotos_todo
"""
import argparse
import json
import shutil
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuente", required=True, nargs="+", type=Path)
    ap.add_argument("--clases", required=True, nargs="+")
    ap.add_argument("--salida", required=True, type=Path)
    a = ap.parse_args()

    id_de = {n: i + 1 for i, n in enumerate(a.clases)}
    if a.salida.exists():
        shutil.rmtree(a.salida)
    a.salida.mkdir(parents=True)
    imgs, anns, vistos = [], [], set()
    for carpeta in a.fuente:
        coco = json.loads((carpeta / "anotaciones.json").read_text(encoding="utf-8"))
        nombre_de = {c["id"]: c["name"] for c in coco["categories"]}
        sobran = set(nombre_de.values()) - set(id_de)
        if sobran:
            print(f"AVISO: {carpeta.name}: clases ignoradas {sorted(sobran)}")
        nuevo = {}
        for im in coco["images"]:
            if im["file_name"] in vistos:
                raise SystemExit(f"Nombre repetido entre fuentes: {im['file_name']}")
            vistos.add(im["file_name"])
            nuevo[im["id"]] = len(imgs) + 1
            imgs.append({**im, "id": nuevo[im["id"]]})
            shutil.copy2(carpeta / im["file_name"], a.salida / im["file_name"])
        n_antes = len(anns)
        for an in coco["annotations"]:
            nombre = nombre_de[an["category_id"]]
            if nombre in id_de:
                anns.append({**an, "id": len(anns) + 1, "image_id": nuevo[an["image_id"]], "category_id": id_de[nombre]})
        print(f"{carpeta.name}: {len(coco['images'])} imágenes, {len(anns) - n_antes} cajas")
    cats = [{"id": i, "name": n} for n, i in id_de.items()]
    (a.salida / "anotaciones.json").write_text(json.dumps({"images": imgs, "annotations": anns, "categories": cats}), encoding="utf-8")
    por_clase = {n: sum(1 for x in anns if x["category_id"] == i) for n, i in id_de.items()}
    print(f"Total: {len(imgs)} imágenes, cajas por clase: {por_clase}")


if __name__ == "__main__":
    main()
