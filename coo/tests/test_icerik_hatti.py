"""İçerik kaynakları — yalnız mutabık kalınan yöntemler (Patron kararları 2026-11-16):
Qwen stüdyo, numune fotoğrafı, numuneden Flow kullanım görseli, teknik poster. Kompozit, ham Blender render'ı,
düz kart ve editoryal föy galeriye / Reels'e girmez."""
from __future__ import annotations

from pathlib import Path

import pytest

from coo.magaza_hatti import mevcut_gorseller, renk_varyantlari
from coo.medya_editoru import _kaynak_klipleri_sec
from coo.renk_hatti import renkler_veriden, urun_renklerini_kaydet

SLUG = "terakota-c46246"


def _urun(tmp_path: Path) -> Path:
    kok = tmp_path / "kedi"
    rk = kok / "gorsel" / "renkler" / SLUG
    rk.mkdir(parents=True)
    for ad in ("seffaf.png", "beyaz.png", "studyo.png", "yakin.png"):  # ham Blender render'ları
        (rk / ad).write_bytes(b"x")
    (kok / "urun.yaml").write_text("sku: kedi\n")
    urun_renklerini_kaydet("kedi", [{"ad": "Terakota", "hex": "#C46246", "slug": SLUG, "klasor": f"gorsel/renkler/{SLUG}",
                                     "gorseller": []}], tmp_path)
    # reddedilen yöntemlerin eski çıktıları — hiçbiri galeriye girmemeli
    for ad in ("yasam-1.png", "olcu-karti.png", "ozellik-karti.png", "editoryal-olcu.png", "studyo.png", "beyaz.png"):
        (kok / "gorsel" / ad).write_bytes(b"x")
    return kok


def test_galeri_yalniz_mutabik_gorseller(tmp_path: Path) -> None:
    kok = _urun(tmp_path)
    r = f"gorsel/renkler/{SLUG}"
    assert mevcut_gorseller("kedi", tmp_path) == []  # Qwen stüdyo yoksa ham render galeriye düşmez
    (kok / r / "studyo-ic").mkdir()
    for ad in ("kapak-beyaz.png", "krem-fon.png", "koyu-fon.png", "doku-yakin.png"):
        (kok / r / "studyo-ic" / ad).write_bytes(b"x")
    (kok / "gorsel" / "numune-1.jpg").write_bytes(b"x")
    (kok / "gorsel" / "kullanim-1.png").write_bytes(b"x")
    (kok / "gorsel" / "konsept").mkdir()
    (kok / "gorsel" / "konsept" / "teknik-poster-3x4.png").write_bytes(b"x")
    galeri = mevcut_gorseller("kedi", tmp_path)
    assert galeri == [f"{r}/studyo-ic/kapak-beyaz.png", f"{r}/studyo-ic/doku-yakin.png", "gorsel/numune-1.jpg",
                      "gorsel/kullanim-1.png", f"{r}/studyo-ic/krem-fon.png", f"{r}/studyo-ic/koyu-fon.png",
                      "gorsel/konsept/teknik-poster-3x4.png"]
    for yasak in ("yasam-", "olcu-karti", "ozellik-karti", "editoryal", "/beyaz.png", "/studyo.png"):
        assert not any(yasak in g for g in galeri), yasak
    assert renk_varyantlari("kedi", tmp_path)[0]["gorseller"][0] == f"{r}/studyo-ic/kapak-beyaz.png"


def test_cok_renk_onayliysa_gorseller_cok_renkli_renderdan() -> None:
    veri = {"renkler": [{"ad": "Krem", "hex": "#E8DFD1", "slug": "krem", "klasor": "gorsel/renkler/krem"}],
            "cok_renk": {"karar": "onay", "sema": "Gece", "renkler": [{"ad": "Siyah", "hex": "#1E1E1E"},
                                                                       {"ad": "Kırmızı", "hex": "#C0392B"}]}}
    r = renkler_veriden(veri)
    assert len(r) == 1 and r[0]["klasor"] == "model/cok_renk/render" and r[0]["filamentler"] == ["#1E1E1E", "#C0392B"]
    veri["cok_renk"]["karar"] = "tek"
    assert renkler_veriden(veri)[0]["slug"] == "krem"


def test_reels_yalniz_gercek_kaynaktan(tmp_path: Path) -> None:
    kok = _urun(tmp_path)
    (kok / "medya").mkdir()
    r = kok / "gorsel" / "renkler" / SLUG / "studyo-ic"
    r.mkdir()
    (r / "kapak-beyaz.png").write_bytes(b"x")
    assert _kaynak_klipleri_sec(kok) == ([], "yok")  # yalnız stüdyo karesi / ham render ile Reels kurgulanmaz
    (kok / "medya" / "flow-1-red.mp4").write_bytes(b"x")  # ürünü değiştirdiği için reddedilen Veo
    assert _kaynak_klipleri_sec(kok)[1] == "yok"
    (kok / "medya" / "timelapse-1.mp4").write_bytes(b"x")
    klipler, tur = _kaynak_klipleri_sec(kok)
    assert tur == "cekim" and klipler[0][0].name == "timelapse-1.mp4"
    assert not any(k[0].name in ("studyo.png", "beyaz.png", "yakin.png", "yasam-1.png", "donen.mp4") for k in klipler)


@pytest.mark.parametrize("modul", ["coo.editoryal", "coo.flow_uretim", "coo.gorsel.birlestir"])
def test_reddedilen_moduller_yok(modul: str) -> None:
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(modul)


def test_numunesiz_kullanim_qwen_karesinden(tmp_path: Path) -> None:
    from coo.icerik_hatti import kullanim_istemi, numunesiz_kaynaklar

    kok = _urun(tmp_path)
    assert numunesiz_kaynaklar("kedi", tmp_path) == []  # Qwen karesi yoksa ham render kullanılmaz
    r = kok / "gorsel" / "renkler" / SLUG / "studyo-ic"
    r.mkdir()
    (r / "kapak-beyaz.png").write_bytes(b"x")
    (r / "krem-fon.png").write_bytes(b"x")
    assert [p.name for p in numunesiz_kaynaklar("kedi", tmp_path)] == ["krem-fon.png", "kapak-beyaz.png"]
    i = kullanim_istemi("kedi", tmp_path, numunesiz=True)
    assert "krem-fon.png" in i and "kullanim-q-1.png" in i and "ÇOK sıkı" in i and "flow-rehberi.md" in i


def test_eski_icerikler_renk_modelinden_eski_olanlari_bulur(tmp_path):
    import os
    from coo.icerik_hatti import eski_icerikler

    kok = tmp_path / "urun-x"
    (kok / "model" / "cok_renk").mkdir(parents=True)
    (kok / "gorsel" / "konsept").mkdir(parents=True)
    (kok / "medya").mkdir()
    eski = kok / "gorsel" / "konsept" / "teknik-poster-3x4.png"
    yeni = kok / "medya" / "reels-son.mp4"
    eski.write_bytes(b"x")
    os.utime(eski, (1000, 1000))
    (kok / "model" / "cok_renk" / "rapor.json").write_text("{}")
    os.utime(kok / "model" / "cok_renk" / "rapor.json", (2000, 2000))
    yeni.write_bytes(b"x")
    assert eski_icerikler("urun-x", tmp_path) == ["gorsel/konsept/teknik-poster-3x4.png"]


def test_eski_icerikler_boyama_yoksa_bos(tmp_path):
    from coo.icerik_hatti import eski_icerikler

    (tmp_path / "urun-y").mkdir()
    assert eski_icerikler("urun-y", tmp_path) == []
