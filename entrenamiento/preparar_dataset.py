"""Convierte un export COCO (CVAT/Roboflow/Label Studio) al formato train/valid/test de RF-DETR.

La división es por GRUPO (cámara + día), no por cuadro, para que cuadros casi idénticos
no caigan en entrenamiento y prueba a la vez.

Nombre de archivo esperado:  <camara>_<fecha o lote>_<lo-que-sea>.jpg
  ej. parque_2026-10-29_081500.jpg   |   taco_b07_00012.jpg
Una imagen sin anotaciones es un negativo (fondo) y se conserva.

Uso:
  python preparar_dataset.py --imagenes fotos/ --coco anotaciones.json --salida dataset/
  python preparar_dataset.py --imagenes fotos/ --coco anotaciones.json --negativos sin_heces/ --salida dataset/
"""
import argparse
import json
import random
import re
import shutil
from collections import defaultdict
from pathlib import Path

from PIL import Image

PATRON = re.compile(r"^(?P<camara>[^_]+)_(?P<fecha>[^_]+)_")   # grupo = primeros dos campos: camara_fecha o fuente_lote
EXT = {".jpg", ".jpeg", ".png"}


def grupo_de(nombre: str) -> str:
    m = PATRON.match(nombre)
    return f"{m['camara']}_{m['fecha']}" if m else "sin_grupo"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--imagenes", required=True, type=Path)
    ap.add_argument("--coco", required=True, type=Path, help="JSON COCO con las anotaciones")
    ap.add_argument("--negativos", type=Path, help="Carpeta extra de imágenes sin objetos")
    ap.add_argument("--salida", required=True, type=Path)
    ap.add_argument("--clases", nargs="+", default=["heces"], help="Clases a conservar")
    ap.add_argument("--valid", type=float, default=0.15)
    ap.add_argument("--test", type=float, default=0.15)
    ap.add_argument("--semilla", type=int, default=42)
    a = ap.parse_args()

    coco = json.loads(a.coco.read_text(encoding="utf-8"))
    nombre_a_clase = {c["id"]: c["name"] for c in coco["categories"]}
    faltan = set(a.clases) - set(nombre_a_clase.values())
    if faltan:
        raise SystemExit(f"Clases no encontradas en el COCO: {sorted(faltan)}. Hay: {sorted(nombre_a_clase.values())}")
    nuevo_id = {nombre: i + 1 for i, nombre in enumerate(a.clases)}

    anots = defaultdict(list)
    for an in coco["annotations"]:
        nombre = nombre_a_clase[an["category_id"]]
        if nombre in nuevo_id:
            anots[an["image_id"]].append({**an, "category_id": nuevo_id[nombre]})

    # items: (ruta_origen, nombre_destino, lista de anotaciones)
    items = []
    for im in coco["images"]:
        ruta = a.imagenes / Path(im["file_name"]).name
        if ruta.exists():
            items.append((ruta, ruta.name, anots.get(im["id"], [])))
        else:
            print(f"AVISO: no existe {ruta}, se omite")
    if a.negativos:
        for p in sorted(a.negativos.iterdir()):
            if p.suffix.lower() in EXT:
                items.append((p, "neg_" + p.name, []))

    # agrupar y repartir grupos completos
    grupos = defaultdict(list)
    for it in items:
        grupos[grupo_de(it[1].removeprefix("neg_"))].append(it)
    if "sin_grupo" in grupos:
        print(f"AVISO: {len(grupos['sin_grupo'])} imágenes sin patrón camara_fecha_; "
              "se tratan como un solo grupo (riesgo de fuga de datos)")
    claves = sorted(grupos)
    random.Random(a.semilla).shuffle(claves)

    total = len(items)
    meta = {"test": a.test * total, "valid": a.valid * total}
    reparto = {"train": [], "valid": [], "test": []}
    cont = {"train": 0, "valid": 0, "test": 0}
    for k in claves:  # test y valid primero, el resto va a train
        destino = "train"
        for nombre in ("test", "valid"):
            if cont[nombre] < meta[nombre]:
                destino = nombre
                break
        reparto[destino] += grupos[k]
        cont[destino] += len(grupos[k])
    if not reparto["valid"] or not reparto["test"]:
        print("AVISO: pocos grupos para llenar valid/test; consigue más cámaras o días distintos")

    if a.salida.exists():
        shutil.rmtree(a.salida)
    for parte, lista in reparto.items():
        carpeta = a.salida / parte
        carpeta.mkdir(parents=True)
        imgs, anns = [], []
        for i, (origen, destino, lista_an) in enumerate(lista, start=1):
            shutil.copy2(origen, carpeta / destino)
            with Image.open(origen) as im:
                w, h = im.size
            imgs.append({"id": i, "file_name": destino, "width": w, "height": h})
            for an in lista_an:
                anns.append({
                    "id": len(anns) + 1, "image_id": i, "category_id": an["category_id"],
                    "bbox": an["bbox"], "area": an.get("area") or an["bbox"][2] * an["bbox"][3],
                    "iscrowd": 0,
                })
        cats = [{"id": i, "name": n} for n, i in nuevo_id.items()]
        (carpeta / "_annotations.coco.json").write_text(
            json.dumps({"images": imgs, "annotations": anns, "categories": cats}), encoding="utf-8")
        pos = len({x["image_id"] for x in anns})
        print(f"{parte:5}: {len(imgs):5} imágenes ({pos} con objetos, {len(imgs) - pos} negativos), {len(anns)} cajas")


if __name__ == "__main__":
    main()
