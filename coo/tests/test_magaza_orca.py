"""Mağaza paketi (coo/magaza_hatti.py) ve Orca 3MF dilimleme (coo/orca_dilim.py) testleri."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from coo.magaza_hatti import hazirla_istemi, mevcut_gorseller, onizleme_metni, paket_oku, yukle_istemi
from coo.orca_dilim import KAYNAK, MAKINE, _sure_sn, duzlestir, gcode_ozeti


def _urun(tmp_path: Path) -> Path:
    kok = tmp_path / "kedi"
    (kok / "gorsel").mkdir(parents=True)
    (kok / "magaza").mkdir()
    for ad in ("studyo.png", "beyaz.png", "numune-1.jpg"):
        (kok / "gorsel" / ad).write_bytes(b"x")
    return kok


def _paket(**ek) -> dict:
    p = {
        "sku": "kedi", "baslik": "Kedi Saksı", "aciklama_html": "<p>x</p>", "satis_fiyati_tl": 449.9,
        "gorseller": ["gorsel/numune-1.jpg", "gorsel/beyaz.png"], "slug": "kedi-saksi", "meta_baslik": "m",
        "meta_aciklama": "d", "etiketler": ["saksı"],
        "maliyet": {"birim_maliyet_tl": 210.0, "basa_bas_tl": 250, "erp_onerilen_tl": 437, "fire_yuzde": 10,
                    "ek_malzeme_tl": 18, "gram": 262.6},
    }
    p.update(ek)
    return p


def test_gorsel_sirasi_numune_once(tmp_path: Path) -> None:
    _urun(tmp_path)
    # Qwen stüdyo görseli yoksa ham Blender render'ı galeriye GİRMEZ; yalnız gerçek numune
    assert mevcut_gorseller("kedi", tmp_path) == ["gorsel/numune-1.jpg"]
    kok = tmp_path / "kedi"
    (kok / "gorsel" / "studyo-ic").mkdir()
    for ad in ("kapak-beyaz.png", "krem-fon.png"):
        (kok / "gorsel" / "studyo-ic" / ad).write_bytes(b"x")
    assert mevcut_gorseller("kedi", tmp_path) == ["gorsel/studyo-ic/kapak-beyaz.png", "gorsel/numune-1.jpg",
                                                  "gorsel/studyo-ic/krem-fon.png"]


def test_paket_gecerli(tmp_path: Path) -> None:
    kok = _urun(tmp_path)
    (kok / "magaza" / "paket.json").write_text(json.dumps(_paket()), encoding="utf-8")
    paket, hatalar = paket_oku("kedi", tmp_path)
    assert hatalar == [] and paket["satis_fiyati_tl"] == 449.9
    assert "449.9 TL" in onizleme_metni(paket)


@pytest.mark.parametrize(
    "degisiklik,beklenen",
    [
        ({"satis_fiyati_tl": 150}, "maliyetin"),
        ({"satis_fiyati_tl": 0}, "satış fiyatı yok"),
        ({"gorseller": ["gorsel/yok.png"]}, "görsel yok"),
        ({"slug": ""}, "eksik alan: slug"),
    ],
)
def test_paket_hatalari(tmp_path: Path, degisiklik: dict, beklenen: str) -> None:
    kok = _urun(tmp_path)
    (kok / "magaza" / "paket.json").write_text(json.dumps(_paket(**degisiklik)), encoding="utf-8")
    _, hatalar = paket_oku("kedi", tmp_path)
    assert any(beklenen in h for h in hatalar), hatalar


def test_paket_yok(tmp_path: Path) -> None:
    _urun(tmp_path)
    assert paket_oku("kedi", tmp_path) == (None, ["paket.json oluşmadı"])


def test_istemler_kurallari_icerir(tmp_path: Path) -> None:
    _urun(tmp_path)
    h = hazirla_istemi("kedi", 10, tmp_path)
    assert "fire_yuzde=10" in h and "kargo_tl=0" in h and "YÜKLEME YAPMA" in h and "MAGAZA_EKSIK" in h
    y = yukle_istemi("kedi", tmp_path)
    assert "BİREBİR" in y and "YENİSİNİ AÇMA" in y and "giriş gerekli" in y


def test_sure_sn() -> None:
    assert _sure_sn("8h 47m 58s") == 31678
    assert _sure_sn("1d 2h 3m 4s") == 93784


def test_gcode_ozeti(tmp_path: Path) -> None:
    g = tmp_path / "a.gcode"
    g.write_text("; HEADER\n; filament used [g] = 262.60\n; estimated printing time (normal mode) = 8h 47m 58s\nG28\n")
    assert gcode_ozeti(g) == {"gram": 262.6, "sure_sn": 31678, "filament_gram": None, "renk_degisimi": 0}


@pytest.mark.skipif(not KAYNAK.exists(), reason="Orca kaynak profilleri yok")
def test_makine_profili_duzlesir() -> None:
    m = duzlestir(MAKINE)
    assert "inherits" not in m and m["name"] == MAKINE
    assert m.get("printer_model") and m.get("nozzle_diameter")


def test_vitrin_karesi_kapaktan_sonra(tmp_path: Path) -> None:
    kok = _urun(tmp_path)
    (kok / "gorsel" / "renkler-birlikte.png").write_bytes(b"x")
    (kok / "gorsel" / "studyo-ic").mkdir()
    (kok / "gorsel" / "studyo-ic" / "kapak-beyaz.png").write_bytes(b"x")
    assert mevcut_gorseller("kedi", tmp_path)[:2] == ["gorsel/studyo-ic/kapak-beyaz.png", "gorsel/renkler-birlikte.png"]


def test_olcu_bilgisi_yalniz_teknik_poster_posterinden(tmp_path: Path) -> None:
    kok = _urun(tmp_path)
    for ad in ("olcu-karti.png", "ozellik-karti.png", "editoryal-olcu.png"):  # reddedilen eski çıktılar
        (kok / "gorsel" / ad).write_bytes(b"x")
    (kok / "gorsel" / "konsept").mkdir()
    (kok / "gorsel" / "konsept" / "teknik-poster-3x4.png").write_bytes(b"x")
    g = mevcut_gorseller("kedi", tmp_path)
    assert g[-1] == "gorsel/konsept/teknik-poster-3x4.png"
    assert not any(x in " ".join(g) for x in ("olcu-karti", "ozellik-karti", "editoryal"))


def test_gcode_ozeti_cok_renk(tmp_path: Path) -> None:
    g = tmp_path / "c.gcode"
    g.write_text("; HEADER\nG1 X0\n; filament used [g] = 16.36, 9.02, 3.75, 3.72\n; total filament used [g] = 32.85\n"
                 "; total filament change = 101\n; estimated printing time (normal mode) = 1h 2m 3s\n", encoding="utf-8")
    o = gcode_ozeti(g)
    assert o["gram"] == 32.85 and o["filament_gram"] == [16.36, 9.02, 3.75, 3.72] and o["renk_degisimi"] == 101
    assert o["sure_sn"] == 3723
