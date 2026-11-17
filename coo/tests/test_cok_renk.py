import zipfile
from pathlib import Path

import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")
pytest.importorskip("scipy")

from coo.cok_renk import ORCA_KOD, boyali_3mf, temizle  # noqa: E402
from coo.renk_al import lab_srgb, rgb_hex, srgb_lab  # noqa: E402


def _kutu():
    m = trimesh.creation.box([40, 40, 40])
    for _ in range(3):
        m = m.subdivide()
    return m


def test_lab_gidis_donus():
    for h in ("#E2DDC7", "#1E1E1E", "#C0392B"):
        rgb = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)]])
        assert rgb_hex(lab_srgb(srgb_lab(rgb))[0]) == h


def test_temizle_kucuk_adalari_ve_gorulmeyeni_doldurur():
    m = _kutu()
    et = np.where(m.triangles_center[:, 2] > 0, 0, 1)
    et[5] = 1 - et[5]          # tek üçgenlik aykırı ada
    et[m.triangles_center[:, 2] < -19] = -1  # alt yüz hiç görülmedi
    son = temizle(m, et, 2, min_alan_mm2=30)
    assert (son >= 0).all()
    ust = m.triangles_center[:, 2] > 5
    assert (son[ust] == 0).all() and (son[m.triangles_center[:, 2] < -5] == 1).all()


def test_boyali_3mf_orca_kodlari(tmp_path: Path):
    m = _kutu()
    et = (m.triangles_center[:, 0] > 0).astype(int)
    yol = boyali_3mf(m, et, tmp_path / "a.3mf")
    model = zipfile.ZipFile(yol).read("3D/3dmodel.model").decode()
    assert model.count(f'paint_color="{ORCA_KOD[0]}"') == (et == 0).sum()
    assert model.count(f'paint_color="{ORCA_KOD[1]}"') == (et == 1).sum()
