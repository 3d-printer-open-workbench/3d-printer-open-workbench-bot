"""Katman katman baskı analizi: havada başlayan parçalar ve desteksiz sarkma bölgeleri.

Alan oranına dayalı sarkma ölçüsü (%>45° yüzey) küçük ama kritik yerleri kaçırır: çene, el, bardak dibi,
demlik ağzı gibi bir katmanda altında hiç malzeme olmadan BAŞLAYAN parçalar desteksiz basılamaz
(havaya filament akar). Bu betik modeli dilimleyici gibi katmanlara böler:
- ada: bir önceki katmanla hiç kesişmeyen yeni bölge (≥0.5 mm²) → destek ŞART
- sarkma: önceki katmanın 0.3 mm (≈56°) ötesine taşan alan; büyükse destek önerilir
İlk 2 mm (taban yuvarlaması/fil ayağı) sarkma hesabına katılmaz.

`.venv-ai3d` ortamında çalışır (trimesh + shapely); coo paketini içe aktarmaz.
    .venv-ai3d/bin/python coo/baski_analiz.py <model.stl> [--katman 0.2]
Son satır JSON: {"ada": [...], "ada_sayisi", "sarkma_max_mm2", "destek_gerekli", "neden"}
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import trimesh
from shapely.ops import unary_union

ADA_MIN_MM2 = 0.5
KOPRU_MM = 0.3
SARKMA_ESIK_MM2 = 25.0
TABAN_MUAF_MM = 2.0


def analiz(yol: str, katman: float = 0.2) -> dict:
    m = trimesh.load(yol, force="mesh")
    zs = np.arange(m.bounds[0][2] + katman / 2, m.bounds[1][2], katman)
    kesitler = m.section_multiplane([0, 0, 0], [0, 0, 1], zs)
    onceki = None
    adalar, sarkmalar = [], []
    for z, s in zip(zs, kesitler):
        if s is None or not s.polygons_full:
            onceki = None
            continue
        p = unary_union(list(s.polygons_full)).buffer(0)
        if onceki is not None:
            for g in getattr(p, "geoms", [p]):
                if g.area >= ADA_MIN_MM2 and not g.intersects(onceki):
                    c = g.centroid
                    adalar.append({"z_mm": round(float(z), 1), "alan_mm2": round(g.area, 1),
                                   "xy": [round(c.x, 1), round(c.y, 1)]})
            if z > TABAN_MUAF_MM:
                fark = p.difference(onceki.buffer(KOPRU_MM)).area
                if fark > 2.0:
                    sarkmalar.append((round(float(z), 1), round(fark, 1)))
        onceki = p
    sarkmalar.sort(key=lambda x: -x[1])
    smax = sarkmalar[0][1] if sarkmalar else 0.0
    neden = []
    if adalar:
        neden.append(f"{len(adalar)} parça havada başlıyor (ilki z={adalar[0]['z_mm']} mm)")
    if smax > SARKMA_ESIK_MM2:
        neden.append(f"z={sarkmalar[0][0]} mm'de {smax} mm² desteksiz sarkma")
    return {"ada": adalar[:20], "ada_sayisi": len(adalar), "sarkma_max_mm2": smax,
            "sarkma_en_buyuk": sarkmalar[:5], "destek_gerekli": bool(neden), "neden": "; ".join(neden)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stl")
    ap.add_argument("--katman", type=float, default=0.2)
    a = ap.parse_args()
    print(json.dumps(analiz(a.stl, a.katman), ensure_ascii=False))


if __name__ == "__main__":
    main()
