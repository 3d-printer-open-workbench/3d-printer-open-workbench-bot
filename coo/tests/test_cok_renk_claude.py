"""Çok renk boyama Claude + Blender ile (Patron kararı 2026-11-16): kural uygulama ve ajan istemi."""
from __future__ import annotations

import numpy as np
import pytest

np_test = pytest.importorskip("scipy")

from coo.cok_renk_claude import kurallari_uygula  # noqa: E402
from coo.cok_renk_hatti import claude_boyama_istemi  # noqa: E402


def test_kurallar_sirayla_ve_eksenle() -> None:
    parca = np.array([0, 0, 1, 1, 2, 2])
    merkez = np.array([[0, 0, z] for z in (1, 10, 20, 30, 40, 50)], float)
    kurallar = [{"renk": 1, "parcalar": [1, 2]}, {"renk": 2, "parcalar": [2], "z_min": 45}, {"renk": 0, "z_max": 1}]
    assert kurallari_uygula(parca, merkez, kurallar, 0, 3).tolist() == [0, 0, 1, 1, 1, 2]
    with pytest.raises(ValueError):
        kurallari_uygula(parca, merkez, [{"renk": 5, "parcalar": [0]}], 0, 3)


def test_istem_claude_blender_qwen_yok(tmp_path) -> None:
    (tmp_path / "kedi").mkdir()
    i = claude_boyama_istemi("kedi", [{"ad": "Kırmızı", "hex": "#C0392B", "stokta": True, "dogrulandi": True}],
                             urunler=tmp_path, zorunlu=[{"ad": "Kırmızı", "hex": "#C0392B"}])
    assert "coo.cok_renk_claude parcala kedi" in i and "boyali_pano.png" in i and "Qwen" in i and "KULLANMA" in i
    assert "sema_son.json" in i and "#C0392B" in i
