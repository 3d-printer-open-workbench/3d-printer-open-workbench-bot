"""Pinterest pin hattı: pano seçimi, görsel önceliği, bağlantı, istemler (Patron kararı 2026-11-17)."""
from __future__ import annotations

import json
from pathlib import Path

from coo import pinterest_hatti as ph
from coo.urun_menusu import urun_karti


def _urun(tmp: Path, ad: str, kategori: str = "") -> Path:
    kok = tmp / "kedi"
    (kok / "gorsel" / "konsept").mkdir(parents=True)
    (kok / "urun.yaml").write_text(f"sku: kedi\nad: {ad}\nkategori: {kategori}\n", encoding="utf-8")
    return kok


def test_pano_ve_gorsel_ve_link(tmp_path: Path) -> None:
    kok = _urun(tmp_path, "Kişiye Özel İsimlik")
    assert ph.pano_sec("kedi", tmp_path) == ph.PANOLAR["kisiye"]
    (kok / "urun.yaml").write_text("sku: kedi\nad: Diz Çökmüş Samuray Tütsülük\n", encoding="utf-8")
    assert ph.pano_sec("kedi", tmp_path) == ph.PANOLAR["dekor"]
    assert not ph.uygun_mu("kedi", tmp_path)
    (kok / "gorsel" / "kullanim-1.png").write_bytes(b"x")
    (kok / "gorsel" / "konsept" / "teknik_poster-3x4.png").write_bytes(b"x")
    assert [p.name for p in ph.gorsel_adaylari("kedi", tmp_path)] == ["teknik_poster-3x4.png", "kullanim-1.png"]
    assert ph.urun_linki("kedi", tmp_path) == ph.MAGAZA
    (kok / "magaza").mkdir()
    (kok / "magaza" / "yukleme.json").write_text(json.dumps({"urun_linki": "https://example.com/kedi"}))
    assert ph.urun_linki("kedi", tmp_path).endswith("/kedi")


def test_istemler_ve_kart_butonu(tmp_path: Path) -> None:
    kok = _urun(tmp_path, "Masa Düzenleyici")
    (kok / "gorsel" / "konsept" / "teknik_poster-3x4.png").write_bytes(b"x")
    i = ph.hazirla_istemi("kedi", tmp_path)
    assert "pinterest-rehberi.md" in i and "teknik_poster-3x4.png" in i and ph.PANOLAR["masa"] in i and '"durum": "HAZIR"' in i
    ph.pin_yolu("kedi", tmp_path).write_text(json.dumps({"durum": "HAZIR", "gorsel": "/x.png", "pano": "P", "link": "L",
                                                         "yz_isareti": True}))
    p = ph.paylas_istemi("kedi", tmp_path)
    assert "PAYLASILDI" in p and "YZ işareti: evet" in p and "DUR" in p
    butonlar = [b["callback_data"] for satir in urun_karti("kedi", tmp_path)[1] for b in satir]
    assert "pin:hazirla:kedi" in butonlar
