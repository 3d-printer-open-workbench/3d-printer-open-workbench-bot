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


def _kule():
    """10 mm kenarlı, 30 mm boyunda ince bölünmüş kutu (z ekseninde katmanlar)."""
    import trimesh

    m = trimesh.creation.box(extents=(10, 10, 30))
    m.apply_translation((0, 0, 15))
    for _ in range(4):
        m = m.subdivide()
    return m


def test_renk_degisimi_tahmini_katman_basina():
    from coo.cok_renk import renk_degisimi_tahmini

    m = _kule()
    z = m.triangles_center[:, 2]
    yatay = (z > 15).astype(np.int64)                       # alt yarı 0, üst yarı 1 → tek değişim
    assert renk_degisimi_tahmini(m, yatay) <= 2
    dikey = (m.triangles_center[:, 0] > 0).astype(np.int64)  # her katmanda iki renk → ~katman sayısı kadar
    assert renk_degisimi_tahmini(m, dikey) >= 100


def test_uc_kirp_ince_kuyrugu_alir_ana_parcayi_korur():
    from coo.cok_renk import renk_degisimi_tahmini, uc_kirp

    m = _kule()
    c = m.triangles_center
    et = (c[:, 2] > 10).astype(np.int64)                     # 0: alt 10 mm, 1: üst 20 mm
    serit = (c[:, 2] > 10) & (c[:, 2] < 25) & (c[:, 0] > 4.9) & (np.abs(c[:, 1]) < 0.7)
    et[serit] = 0                                            # 0 rengi ince bir şeritle 25 mm'ye kadar uzuyor
    once = renk_degisimi_tahmini(m, et)
    yeni, kayit = uc_kirp(m, et, 2)
    assert kayit and kayit[0]["renk"] == 0
    assert renk_degisimi_tahmini(m, yeni) < once
    alt = c[:, 2] < 9
    assert (yeni[alt] == 0).all() and (yeni[c[:, 2] > 26] == 1).all()  # ana parçalar aynen


def test_sinir_yumusat_disli_siniri_duzler():
    from coo.cok_renk import sinir_yumusat

    m = _kule()
    c = m.triangles_center
    rng = np.random.default_rng(0)
    et = (c[:, 2] + rng.uniform(-1.0, 1.0, len(c)) > 15).astype(np.int64)  # z=15 çevresinde dişli sınır
    yeni = sinir_yumusat(m, et, 2)
    hata_once = ((et == 1) != (c[:, 2] > 15)).sum()
    hata_sonra = ((yeni == 1) != (c[:, 2] > 15)).sum()
    assert hata_sonra < hata_once / 2
