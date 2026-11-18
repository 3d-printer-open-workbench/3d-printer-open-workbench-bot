"""Kullanım testi: CoACD öncesi ağ temizliği (dejenere üçgenler CoACD'yi C++ assert ile çökertiyordu, 2026-11-18)."""
from __future__ import annotations

import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")

from coo import kullanim_testi as kt  # noqa: E402


def test_ag_temizle_dejenere_ve_yinelenen_ucgenleri_atar():
    kutu = trimesh.creation.box(extents=(10, 10, 10))
    v = np.vstack([kutu.vertices, kutu.vertices[:1]])          # yinelenen nokta
    f = np.vstack([kutu.faces, [[0, 0, 1]], [[0, 1, len(v) - 1]], kutu.faces[:1]])  # sıfır alan + kopya
    kirli = trimesh.Trimesh(v, f, process=False)
    temiz = kt.ag_temizle(kirli)
    assert len(temiz.faces) == len(kutu.faces)
    assert abs(temiz.volume - kutu.volume) < 1e-6


def test_coacd_guvenli_alt_surecte_parca_dondurur():
    pytest.importorskip("coacd")
    parcalar = kt._coacd_guvenli(trimesh.creation.box(extents=(20, 10, 5)), zaman_asimi=120)
    assert parcalar and all(p.shape[1] == 3 for p in parcalar)
