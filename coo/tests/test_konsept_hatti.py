"""Konsept kütüphanesi (coo/konsept_hatti.py) testleri."""
from __future__ import annotations

from pathlib import Path

import pytest

from coo.konsept_hatti import KONSEPT_KLASORU, konsept_ciktilari, konsept_istemi, konsept_kaydet, konseptler


ORNEK = "teknik-poster"


def test_arsivdeki_konseptler_listelenmez(tmp_path: Path) -> None:
    """Örnek konsept listelenir; arsiv/ altındakiler listelenmez."""
    adlar = [k["ad"] for k in konseptler()]
    assert ORNEK in adlar
    k = next(k for k in konseptler() if k["ad"] == ORNEK)
    assert k["yol"].parent == KONSEPT_KLASORU and k.get("bilgi_katmani")
    (tmp_path / "arsiv").mkdir()
    (tmp_path / "arsiv" / "eski.md").write_text("---\nad: eski\n---\nistem\n", encoding="utf-8")
    (tmp_path / "yeni.md").write_text("---\nad: yeni\n---\nistem\n", encoding="utf-8")
    assert [k["ad"] for k in konseptler(tmp_path)] == ["yeni"]


def test_konsept_kaydet_ve_ezmez(tmp_path: Path) -> None:
    metin = "Retro Afiş\n" + "Make a bold retro screenprint poster of the uploaded product. " * 3
    a = konsept_kaydet(metin, tmp_path)
    b = konsept_kaydet(metin, tmp_path)
    assert a["ad"] == "retro-afis" and b["ad"] == "retro-afis-2" and a["baslik"] == "Retro Afiş"
    with pytest.raises(ValueError):
        konsept_kaydet("kısa", tmp_path)


def test_istem_kurallari(tmp_path: Path) -> None:
    kok = tmp_path / "kedi"
    (kok / "gorsel" / "renkler" / "krem" / "studyo-ic").mkdir(parents=True)
    (kok / "gorsel" / "renkler" / "krem" / "studyo-ic" / "krem-fon.png").write_bytes(b"x")
    (kok / "urun.yaml").write_text("sku: kedi\nrenkler: [{ad: Krem, hex: '#E8DFD1', slug: krem, klasor: gorsel/renkler/krem}]\n")
    (kok / "gorsel" / "studyo.png").write_bytes(b"x")  # ham Blender render'ı konsepte girmez
    k = next(k for k in konseptler() if k["ad"] == ORNEK)
    istem = konsept_istemi("kedi", k, tmp_path)
    assert "krem-fon.png" in istem and "POSTER HAZIR" in istem and "haklar" in istem
    assert "Ölçü, fiyat" in istem and "KONSEPT_HAZIR" in istem
    assert konsept_ciktilari("kedi", k["ad"], tmp_path) == {"poster": None, "dikey": None, "reels": None}
    (kok / "gorsel" / "numune-1.jpg").write_bytes(b"x")
    assert "numune-1.jpg" in konsept_istemi("kedi", k, tmp_path)  # gerçek numune fotoğrafı öncelikli


def test_referansli_konsept(tmp_path: Path) -> None:
    ref = tmp_path / "referans" / "ornek"
    ref.mkdir(parents=True)
    (ref / "urun-poster.jpg").write_bytes(b"x")
    (ref / "kimlik-panosu.jpg").write_bytes(b"x")
    (tmp_path / "ornek.md").write_text(
        "---\nad: ornek\nbaslik: Örnek\nbilgi_katmani: teknik_poster\nposter_motoru: flow\nreferanslar:\n"
        "  - referans/ornek/urun-poster.jpg\n  - referans/ornek/kimlik-panosu.jpg\n---\n"
        "Create a poster for the product in IMAGE 1.\n", encoding="utf-8")
    k = next(k for k in konseptler(tmp_path) if k["ad"] == "ornek")
    assert len(k["referanslar"]) == 2 and all(r.exists() for r in k["referanslar"])
    istem = konsept_istemi("kedi", k)
    assert "urun-poster.jpg" in istem and "IMAGE 1" in istem and "otomatik indirme" in istem


def test_teknik_poster_bilgi_katmani_istemi() -> None:
    k = next(k for k in konseptler() if k["ad"] == ORNEK)
    assert k["bilgi_katmani"] == "teknik_poster"
    assert k["poster_motoru"] == "yerel"  # varsayılan: yerel Inkscape SVG şablonu (coo.poster_sablon)
    istem = konsept_istemi("kedi", k)
    assert "POSTER HAZIR" in istem and "CANVA POSTER" not in istem and "Canva KULLANMA" in istem
    assert f"{ORNEK}-3x4.png" in istem and f"{ORNEK}-9x16.png" in istem and "ek bant EKLEME" in istem
    istem = konsept_istemi("kedi", {**k, "poster_motoru": "flow"})  # Flow ham poster + bilgi bandı yolu korunur
    assert "coo.teknik_poster bilgi kedi" in istem and "coo.teknik_poster reels kedi" in istem
    assert "YENİ sekme" in istem and "-3x4-ham.png" in istem and "(3:4):" in istem


def test_teknik_poster_bilgiler_dogrulanmis_veri(tmp_path, monkeypatch) -> None:
    import yaml
    from coo import bilgi_verisi as teknik_poster
    (tmp_path / "kedi").mkdir()
    (tmp_path / "kedi" / "urun.yaml").write_text(yaml.safe_dump({
        "ad": "Kedi", "boyut_mm": {"x": 146.3, "y": 146.5, "z": 137.5},
        "dilimleme": {"katman_mm": 0.2, "filament": "Elegoo PLA Matte @ECC"}}), encoding="utf-8")
    monkeypatch.setattr(teknik_poster, "URUNLER", tmp_path)
    b = teknik_poster.bilgiler("kedi")
    assert ("A-01", "YÜKSEKLİK", "13,8 cm") in b["satirlar"] and ("P-01", "MALZEME", "Mat PLA") in b["satirlar"]
    assert all(s[1] != "SAKSI AĞZI" for s in b["satirlar"])  # hazne verisi yoksa uydurulmaz


def test_teknik_poster_baslik_turkce_buyuk_harf_ve_parantez():
    from coo.teknik_poster import baslik_satiri

    assert baslik_satiri("Diz Çökmüş Samuray Figürlü Tütsülük (tek parça, kül tepsili taban)") == \
        "DİZ ÇÖKMÜŞ SAMURAY FİGÜRLÜ TÜTSÜLÜK"
    uzun = baslik_satiri("Çok Uzun Bir İsim Olan Dekoratif Işıklı Masa Üstü Düzenleyici Kutusu")
    assert len(uzun) <= 48 and uzun.endswith("…") and "IŞIKLI" in uzun
