"""Convierte un shard webdataset de ScatSpotter (.tar con N.jpg + N.json) al formato de preparar_dataset.py.

Reduce las fotos (lado mayor --max-lado), escala las cajas, y las renombra como
<camara>_<AAAA-MM-DD>_<n>.jpg usando la fecha del nombre original (IMG_AAAAMMDD_HHMMSS.jpg),
para que preparar_dataset.py divida por día.

Datos: ScatSpotter (Crall), CC BY 4.0 — citar: https://huggingface.co/datasets/frovolts/shitspotter

  python importar_scatspotter.py --tar test-000000.tar validation-000000.tar --salida fotos_scat/
Produce fotos_scat/*.jpg y fotos_scat/anotaciones.json
"""
import argparse
import io
import json
import re
import tarfile
from pathlib import Path

from PIL import Image, ImageOps

FECHA = re.compile(r"(\d{4})(\d{2})(\d{2})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tar", required=True, type=Path, nargs="+", help="uno o más shards .tar")
    ap.add_argument("--salida", required=True, type=Path)
    ap.add_argument("--max-lado", type=int, default=1280)
    ap.add_argument("--calidad", type=int, default=88, help="calidad JPEG")
    ap.add_argument("--camara", default="foto")
    a = ap.parse_args()

    a.salida.mkdir(parents=True, exist_ok=True)
    imgs, anns = [], []
    omitidas = 0
    for ruta_tar in a.tar:
        with tarfile.open(ruta_tar) as t:
            nombres = {m.name for m in t.getmembers() if m.isfile()}
            ids = sorted(int(n[:-5]) for n in nombres if re.fullmatch(r"\d+\.json", n))
            for n in ids:
                meta = json.loads(t.extractfile(f"{n}.json").read())
                if f"{n}.jpg" not in nombres:
                    continue
                im = ImageOps.exif_transpose(Image.open(io.BytesIO(t.extractfile(f"{n}.jpg").read()))).convert("RGB")
                ow, oh = meta["width"], meta["height"]
                if im.size != (ow, oh):          # EXIF rotó la imagen: el JSON no coincide, se omite
                    omitidas += 1
                    continue
                esc = min(1.0, a.max_lado / max(ow, oh))
                im = im.resize((round(ow * esc), round(oh * esc)), Image.LANCZOS)
                m = FECHA.search(meta.get("file_name", ""))
                fecha = f"{m[1]}-{m[2]}-{m[3]}" if m else "0000-00-00"
                iid = len(imgs) + 1                # numeración global: los n se repiten entre shards
                nombre = f"{a.camara}_{fecha}_{iid:05d}.jpg"
                im.save(a.salida / nombre, quality=a.calidad)
                imgs.append({"id": iid, "file_name": nombre, "width": im.size[0], "height": im.size[1]})
                for an in meta.get("annotations", []):
                    x, y, w, h = [v * esc for v in an["bbox"]]
                    anns.append({"id": len(anns) + 1, "image_id": iid, "category_id": 1,
                                 "bbox": [round(x, 1), round(y, 1), round(w, 1), round(h, 1)], "area": round(w * h, 1), "iscrowd": 0})
        print(f"{ruta_tar.name}: acumulado {len(imgs)} imágenes", flush=True)
    if omitidas:
        print(f"AVISO: {omitidas} imágenes omitidas por tamaño distinto al del JSON (rotación EXIF)")
    coco = {"images": imgs, "annotations": anns, "categories": [{"id": 1, "name": "heces"}]}
    (a.salida / "anotaciones.json").write_text(json.dumps(coco), encoding="utf-8")
    fechas = sorted({i["file_name"].split("_")[1] for i in imgs})
    print(f"{len(imgs)} imágenes, {len(anns)} cajas, {len(fechas)} fechas distintas")


if __name__ == "__main__":
    main()
