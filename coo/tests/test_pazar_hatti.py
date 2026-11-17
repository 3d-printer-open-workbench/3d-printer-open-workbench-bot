"""Pazar araştırması ve fiyat kararı (coo/pazar_hatti.py) testleri."""
from __future__ import annotations

import json
from pathlib import Path

from coo.pazar_hatti import fiyat_onerisi, pazar_istemi, pazar_metni, pazar_oku, pazar_ozeti, psikolojik_fiyat


def _o(fiyat, benzerlik=3, ulke="TR", url="https://www.trendyol.com/x"):
    return {"ad": "saksı", "platform": "Trendyol", "url": url, "fiyat_tl": fiyat, "benzerlik": benzerlik, "ulke": ulke}


def test_psikolojik_fiyat() -> None:
    assert psikolojik_fiyat(437) == 449.9
    assert psikolojik_fiyat(449.9) == 449.9
    assert psikolojik_fiyat(187) == 189.9
    assert psikolojik_fiyat(1210) == 1299.9
    assert psikolojik_fiyat(0) == 0


def test_ozet_filtreler() -> None:
    veri = {"ornekler": [_o(300), _o(400), _o(500), _o(9999, benzerlik=1), _o(800, url="tahmin"), _o(0)]}
    oz = pazar_ozeti(veri)
    assert oz["yeterli"] and oz["ornek"] == 3 and oz["medyan"] == 400 and oz["kapsam"] == "TR"
    assert oz["alt"] == 350 and oz["ust"] == 450


def test_ozet_yetersiz_global_ile_tamamlanir() -> None:
    veri = {"ornekler": [_o(300), _o(400), _o(900, ulke="GLOBAL")]}
    oz = pazar_ozeti(veri)
    assert oz["yeterli"] and oz["kapsam"] == "TR+GLOBAL"
    assert pazar_ozeti({"ornekler": [_o(300)]})["yeterli"] is False
    assert pazar_ozeti(None) is None


MAL = {"birim_maliyet_tl": 210, "basa_bas_tl": 250, "erp_onerilen_tl": 437}


def test_fiyat_marj_firsati() -> None:
    k = fiyat_onerisi(MAL, {"yeterli": True, "alt": 450, "medyan": 520, "ust": 600, "ornek": 6})
    assert k["konum"] == "MARJ_FIRSATI" and k["onerilen_tl"] == 549.9
    assert {s["ad"] for s in k["secenekler"]} >= {"Önerilen", "ERP"}


def test_fiyat_pazarin_ustunde_tabani_korur() -> None:
    k = fiyat_onerisi(MAL, {"yeterli": True, "alt": 150, "medyan": 200, "ust": 260, "ornek": 5})
    assert k["konum"] == "PAZARIN_USTUNDE" and k["onerilen_tl"] == 449.9
    assert all(s["tl"] >= 250 for s in k["secenekler"])  # başa baş altı medyan seçenek olarak sunulmaz


def test_fiyat_bantta_ve_verisiz() -> None:
    assert fiyat_onerisi(MAL, {"yeterli": True, "alt": 300, "medyan": 400, "ust": 500, "ornek": 4})["konum"] == "PAZAR_BANDINDA"
    k = fiyat_onerisi(MAL, None)
    assert k["konum"] == "PAZAR_VERISI_YOK" and k["onerilen_tl"] == 449.9


def test_istem_ve_metin(tmp_path: Path) -> None:
    (tmp_path / "kedi" / "pazar").mkdir(parents=True)
    istem = pazar_istemi("kedi", tmp_path)
    assert "GÖRDÜĞÜN fiyatı" in istem and "PAZAR_HAZIR" in istem and "pazar/fiyat.json" in istem
    veri = {"tarih": "2026-11-16", "ornekler": [_o(300), _o(400), _o(500)], "yorum": "rekabet orta"}
    (tmp_path / "kedi" / "pazar" / "fiyat.json").write_text(json.dumps(veri), encoding="utf-8")
    okunan = pazar_oku("kedi", tmp_path)
    metin = pazar_metni("kedi", okunan, pazar_ozeti(okunan))
    assert "350–450 TL" in metin and "rekabet orta" in metin


def test_fiyat_coz() -> None:
    from coo.pazar_hatti import fiyat_coz
    assert fiyat_coz("499,90") == 499.9
    assert fiyat_coz("1.299,90 TL") == 1299.9
    assert fiyat_coz("499.9") == 499.9
    assert fiyat_coz("1.299") == 1299
    assert fiyat_coz("abc") is None and fiyat_coz("0") is None


def test_onizleme_fiyat_karari_ve_kart(tmp_path: Path) -> None:
    from coo.magaza_hatti import onizleme_metni
    from coo.urun_menusu import urun_karti
    k = fiyat_onerisi(MAL, {"yeterli": True, "alt": 450, "medyan": 520, "ust": 600, "ornek": 6})
    metin = onizleme_metni({"sku": "kedi", "baslik": "x", "satis_fiyati_tl": 549.9, "maliyet": MAL, "fiyat_karari": k})
    assert "Pazar bandı" in metin and "450–600 TL" in metin
    kok = tmp_path / "kedi"
    (kok / "pazar").mkdir(parents=True)
    (kok / "model").mkdir()
    (kok / "model" / "kedi.stl").write_bytes(b"x")
    (kok / "pazar" / "fiyat.json").write_text(json.dumps({"ornekler": [_o(300), _o(400), _o(500)]}), encoding="utf-8")
    yazi, butonlar, _ = urun_karti("kedi", tmp_path)
    assert "350–450 TL" in yazi
    assert any(b["callback_data"] == "pazar:goster:kedi" for satir in butonlar for b in satir)
