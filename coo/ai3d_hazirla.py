"""AI mesh'ini (coo/ai3d_mesh.py çıktısı) baskıya hazırlar — `.venv-ai3d` ortamında çalışır.

Kullanım:
    .venv-ai3d/bin/python coo/ai3d_hazirla.py <ham.stl> <cikti.stl> [--taban-kesim 2.5] [--drenaj 6]

Adımlar:
1. Yalnızca ana gövdeyi tut (sıfır hacimli artık üçgenleri at).
2. Tabandan --taban-kesim mm kes → tam düz oturma yüzeyi, Z=0'a indir.
3. --drenaj > 0 ise: yukarıdan açık bir hazne aranır; bulunursa hazne dibinin merkezinden
   tabana Ø drenaj deliği açılır. Hazne yalnızca aynı merkez çevresinde (12 mm) ve
   300 mm²'den büyük kaldığı sürece takip edilir — kolların arasındaki kapalı boşluklar
   hazne sanılmaz.
Son satırda tek satır JSON rapor basar.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Polygon

HAZNE_MIN_ALAN_MM2 = 300.0
HAZNE_MERKEZ_TOLERANS_MM = 12.0


def kesit(m: trimesh.Trimesh, z: float):
    s = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if s is None:
        return None
    T = np.eye(4)
    T[2, 3] = -z
    p, _ = s.to_2D(to_2D=T)
    if not p.polygons_full:
        return None
    return max(p.polygons_full, key=lambda q: q.area)


def hazne_bul(m: trimesh.Trimesh) -> dict | None:
    """Üstten açık hazneyi takip eder; yoksa None. Dönüş: merkez, dip z, üst çap, derinlik."""
    ust = m.bounds[1][2]
    son = None
    ilk_cap = None
    z = ust - 1.0
    while z > 0:
        q = kesit(m, z)
        delikler = [Polygon(i) for i in q.interiors] if q is not None else []
        delikler = [h for h in delikler if h.area > HAZNE_MIN_ALAN_MM2]
        if son is not None:
            delikler = [h for h in delikler
                        if np.hypot(h.centroid.x - son[0], h.centroid.y - son[1]) < HAZNE_MERKEZ_TOLERANS_MM]
        if not delikler:
            if son is None and z > ust - 15.0:
                # Dudak kenarı düzensizse ilk mm'lerde halka kapanmayabilir; aramaya devam.
                z -= 1.0
                continue
            break
        h = max(delikler, key=lambda x: x.area)
        if ilk_cap is None:
            ilk_cap = 2 * (h.area / np.pi) ** 0.5
        son = (h.centroid.x, h.centroid.y, z)
        z -= 1.0
    if son is None:
        return None
    return {"merkez": [round(son[0], 1), round(son[1], 1)], "dip_z": round(son[2], 1),
            "ust_cap_mm": round(ilk_cap, 1), "derinlik_mm": round(ust - son[2], 1)}


def hazirla(girdi: Path, cikti: Path, taban_kesim: float = 2.5, drenaj: float = 0.0) -> dict:
    m = trimesh.load(girdi)
    m = max(m.split(only_watertight=False), key=lambda p: len(p.faces))
    if not m.is_watertight:
        trimesh.repair.fill_holes(m)

    if taban_kesim > 0:
        lo, hi = m.bounds
        kutu = trimesh.creation.box(bounds=[[lo[0] - 5, lo[1] - 5, lo[2] + taban_kesim],
                                            [hi[0] + 5, hi[1] + 5, hi[2] + 5]])
        m = m.intersection(kutu, engine="manifold")
    m.apply_translation([0, 0, -m.bounds[0][2]])

    hazne = hazne_bul(m)
    drenaj_acildi = False
    if drenaj > 0 and hazne:
        cx, cy = hazne["merkez"]
        yuk = hazne["dip_z"] + 6
        sil = trimesh.creation.cylinder(radius=drenaj / 2, height=yuk + 2, sections=48)
        sil.apply_translation([cx, cy, (yuk + 2) / 2 - 1])
        m = m.difference(sil, engine="manifold")
        drenaj_acildi = True

    cikti.parent.mkdir(parents=True, exist_ok=True)
    m.export(cikti)
    taban = kesit(m, 0.2)
    return {
        "cikti": str(cikti),
        "boyut_mm": [round(float(x), 1) for x in m.extents],
        "hacim_cm3": round(float(m.volume) / 1000, 1),
        "su_gecirmez": bool(m.is_watertight),
        "taban_temas_cm2": round(taban.area / 100, 1) if taban is not None else 0.0,
        "hazne": hazne,
        "drenaj_mm": drenaj if drenaj_acildi else 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("girdi", type=Path)
    ap.add_argument("cikti", type=Path)
    ap.add_argument("--taban-kesim", type=float, default=2.5)
    ap.add_argument("--drenaj", type=float, default=0.0, help="Ø mm; 0 = drenaj yok")
    a = ap.parse_args()
    print(json.dumps(hazirla(a.girdi, a.cikti, a.taban_kesim, a.drenaj), ensure_ascii=False))


if __name__ == "__main__":
    main()
