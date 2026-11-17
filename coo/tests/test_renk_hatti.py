"""Renk hattı (coo/renk_hatti.py) ve mağaza renk varyantı testleri."""
from __future__ import annotations

import json
from pathlib import Path

import yaml
from PIL import Image

from coo.magaza_hatti import mevcut_gorseller, paket_oku, renk_varyantlari
from coo.renk_hatti import (
    aciklamadan_renk_sku,
    baskin_renkler,
    palet_gorseli,
    renk_adi,
    renk_slug,
    urun_renklerini_kaydet,
)


def _iki_renkli(tmp_path: Path) -> Path:
    img = Image.new("RGB", (200, 100), (245, 245, 242))  # beyaz fon %70
    for x in range(140, 200):
        for y in range(100):
            img.putpixel((x, y), (196, 98, 70))  # terakota %30
    yol = tmp_path / "ornek.png"
    img.save(yol)
    return yol


def test_baskin_renkler_ve_adlar(tmp_path: Path) -> None:
    renkler = baskin_renkler(_iki_renkli(tmp_path))
    assert [r["ad"] for r in renkler] == ["Beyaz", "Terakota"]
    assert abs(renkler[0]["pay"] - 0.7) < 0.02 and renkler[1]["hex"] == "#C46246"
    assert palet_gorseli(renkler, tmp_path / "p.png").exists()


def test_renk_adi_ve_slug() -> None:
    assert renk_adi((20, 20, 24)) == "Siyah"
    assert renk_adi((160, 148, 130)) == "Vizon"
    assert renk_slug("Fıstık Yeşili", "#AAC86E") == "fistik-yesili-aac86e"


def test_aciklamadan_renk_sku() -> None:
    assert aciklamadan_renk_sku("renk cay-teyzesi-saksi") == "cay-teyzesi-saksi"
    assert aciklamadan_renk_sku("Renk  Kedi-Saksi ") == "kedi-saksi"
    assert aciklamadan_renk_sku("bundan reels yap") is None


def _urun_renkli(tmp_path: Path) -> Path:
    kok = tmp_path / "kedi"
    for alt in ("gorsel/renkler/terakota-c46246", "gorsel/renkler/siyah-161616", "magaza"):
        (kok / alt).mkdir(parents=True)
    (kok / "urun.yaml").write_text("sku: kedi\n")
    for d in ("terakota-c46246", "siyah-161616"):
        for ad in ("beyaz.png", "studyo.png"):
            (kok / "gorsel" / "renkler" / d / ad).write_bytes(b"x")
    (kok / "gorsel" / "studyo.png").write_bytes(b"x")  # renksiz eski render
    (kok / "gorsel" / "olcu-karti.png").write_bytes(b"x")
    urun_renklerini_kaydet("kedi", [
        {"ad": a, "hex": h, "slug": s, "klasor": f"gorsel/renkler/{s}",
         "gorseller": [f"gorsel/renkler/{s}/beyaz.png", f"gorsel/renkler/{s}/studyo.png"]}
        for a, h, s in (("Terakota", "#C46246", "terakota-c46246"), ("Siyah", "#161616", "siyah-161616"))
    ], tmp_path)
    return kok


def test_renkler_kaydedilir_ve_tekrar_eklenmez(tmp_path: Path) -> None:
    kok = _urun_renkli(tmp_path)
    tum = urun_renklerini_kaydet("kedi", [{"ad": "Siyah", "hex": "#161616", "slug": "siyah-161616",
                                           "klasor": "x", "gorseller": []}], tmp_path)
    assert [r["ad"] for r in tum] == ["Terakota", "Siyah"]
    assert yaml.safe_load((kok / "urun.yaml").read_text())["sku"] == "kedi"


def test_magaza_ana_gorseller_ilk_renkten(tmp_path: Path) -> None:
    _urun_renkli(tmp_path)
    kok = tmp_path / "kedi"
    assert mevcut_gorseller("kedi", tmp_path) == []  # ham Blender render'ı ve düz kart galeriye girmez
    for d in ("terakota-c46246", "siyah-161616"):
        (kok / "gorsel" / "renkler" / d / "studyo-ic").mkdir()
        for ad in ("kapak-beyaz.png", "krem-fon.png"):
            (kok / "gorsel" / "renkler" / d / "studyo-ic" / ad).write_bytes(b"x")
    assert mevcut_gorseller("kedi", tmp_path) == [
        "gorsel/renkler/terakota-c46246/studyo-ic/kapak-beyaz.png", "gorsel/renkler/terakota-c46246/studyo-ic/krem-fon.png"]
    v = renk_varyantlari("kedi", tmp_path)
    assert [x["deger"] for x in v] == ["Terakota", "Siyah"] and len(v[1]["gorseller"]) == 2


def test_paket_varyant_uyusmazligi_yakalanir(tmp_path: Path) -> None:
    kok = _urun_renkli(tmp_path)
    paket = {
        "sku": "kedi", "baslik": "b", "aciklama_html": "a", "satis_fiyati_tl": 400, "slug": "s",
        "meta_baslik": "m", "meta_aciklama": "d", "etiketler": ["e"], "maliyet": {"birim_maliyet_tl": 100},
        "gorseller": ["gorsel/olcu-karti.png"], "varyantlar": [{"secenek": "Renk", "deger": "Terakota", "gorseller": []}],
    }
    (kok / "magaza" / "paket.json").write_text(json.dumps(paket), encoding="utf-8")
    _, hatalar = paket_oku("kedi", tmp_path)
    assert "renk varyantları urun.yaml ile uyuşmuyor" in hatalar


def test_katman_mm_urun_yamldan_okunur(tmp_path):
    from coo.renk_hatti import katman_mm

    assert katman_mm(tmp_path) == 0.20  # urun.yaml yok → varsayılan
    (tmp_path / "urun.yaml").write_text("dilimleme:\n  katman_mm: 0.16\n", encoding="utf-8")
    assert katman_mm(tmp_path) == 0.16
    (tmp_path / "urun.yaml").write_text("dilimleme:\n  katman_mm: 5\n", encoding="utf-8")
    assert katman_mm(tmp_path) == 0.20  # mantıksız değer → varsayılan
