"""Konsept görselinden çok görüş (ön / sol / arka) üretir → Hunyuan3D-2mv girdisi.

Tek 3/4 konsept görselinden mesh üretildiğinde ürünün arkası tahmin edilir; Qwen-Image-Edit-2511 ile
aynı nesnenin göz hizasında ön, sol profil ve arka görünümleri üretilir. Hunyuan3D-2mv bu üç görünümü
birlikte kullanır.

Kullanım:
    python3 -m coo.ai3d_gorusler <konsept.png> <cikti_klasoru> [--tohum 7] [--acik-birak]
Çıktı: <cikti>/on.png, sol.png, arka.png ve son satırda JSON rapor.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import qwen_edit
from .qwen_edit import duzenle

ORTAK = ("Same single object with exactly the same design, shape, proportions, details, material and color; "
         "nothing added or removed. Matte surface. Camera at eye level, no perspective tilt, the whole object "
         "fully visible and centered with margin. Pure white seamless background, soft even studio light, "
         "no cast shadow, no text.")
GORUSLER = {
    "on": "Rotate the camera to show this object from the straight front view, facing the object directly. " + ORTAK,
    "sol": ("Rotate the camera 90 degrees around the object to show its exact side profile; the object's front "
            "faces the left edge of the image. " + ORTAK),
    "arka": ("Rotate the camera 180 degrees around the object to show it from directly behind (back view); the "
             "front of the object is not visible. " + ORTAK),
}


def gorusler(konsept: Path, cikti: Path, tohum: int = 7) -> dict:
    cikti.mkdir(parents=True, exist_ok=True)
    rapor: dict = {}
    for ad, istem in GORUSLER.items():
        s = duzenle(konsept, cikti / f"{ad}.png", istem, tohum=tohum, mp=1.0)
        rapor[ad] = s
        if not s.get("basarili"):
            break
    rapor["basarili"] = all(rapor.get(k, {}).get("basarili") for k in GORUSLER)
    return rapor


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("konsept", type=Path)
    ap.add_argument("cikti", type=Path)
    ap.add_argument("--tohum", type=int, default=7)
    ap.add_argument("--acik-birak", action="store_true", help="ComfyUI'yi kapatma")
    a = ap.parse_args()
    try:
        r = gorusler(a.konsept, a.cikti, a.tohum)
    finally:
        if not a.acik_birak:  # ComfyUI ≈20 GB RAM tutar; Hunyuan/Blender'dan önce bırak.
            qwen_edit.sunucu_kapat()
    print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
