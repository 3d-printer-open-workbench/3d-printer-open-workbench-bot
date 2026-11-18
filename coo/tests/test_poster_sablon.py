"""Yerel teknik poster şablonu (coo/poster_sablon.py + config/konseptler/teknik-poster-sablon.svg) testleri."""
from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

from coo import poster_sablon as ps

VERI = {"ad": "Dalga formunda telefon standı", "satirlar": [
    ("A-01", "YÜKSEKLİK", "9,8 cm"), ("A-02", "GENİŞLİK", "10,2 cm"), ("A-03", "DERİNLİK", "16,0 cm"),
    ("P-01", "MALZEME", "Mat PLA"), ("P-02", "KATMAN", "0,16 mm")]}


def _idler(svg: str) -> dict[str, ET.Element]:
    return {e.get("id"): e for e in ET.fromstring(svg).iter() if e.get("id")}


def _png(yol: Path, boyut=(800, 600), renk=(200, 120, 90)) -> Path:
    from PIL import Image

    Image.new("RGB", boyut, renk).save(yol)
    return yol


def _sahte_render(svg: Path, png: Path) -> None:
    """Gerçek render yerine: SVG'yi doğrula, 1080×1440 boş PNG yaz."""
    ET.parse(svg)
    _png(png, (ps.GENISLIK, ps.YUKSEKLIK), (244, 241, 234))


def test_sablon_sabit_idleri_tasir() -> None:
    e = _idler(ps.SABLON.read_text(encoding="utf-8"))
    for ad in ["urun_foto", "urun_satiri"] + [f"h{i}{s}" for i in range(1, 7)
                                            for s in ("", "_etiket", "_deger", "_nokta", "_cizgi")]:
        assert ad in e, ad
    f = e["urun_foto"]
    assert (f.get("x"), f.get("y"), f.get("width"), f.get("height")) == ("220", "124", "640", "640")
    kok = ET.parse(ps.SABLON).getroot()
    assert (kok.get("width"), kok.get("height")) == ("1080", "1440")
    metin = ps.SABLON.read_text(encoding="utf-8")
    for sabit in ("{MARKA}", "{SERI}", "{SITE}", "PLA / 3D", "#F4F1EA", "Inter", "Roboto Mono"):
        assert sabit in metin
    for ad in ("marka", "seri", "site"):
        assert ad in e, ad


def test_marka_alanlari_yapilandirmadan(monkeypatch) -> None:
    monkeypatch.setattr(ps, "MAGAZA_ADI", "Örnek Atölye")
    monkeypatch.setattr(ps, "MAGAZA_ALAN_ADI", "example.com")
    for k in ("WORKBENCH_POSTER_BRAND", "WORKBENCH_POSTER_SITE", "WORKBENCH_POSTER_SERIES"):
        monkeypatch.delenv(k, raising=False)
    assert ps.marka_alanlari() == {"marka": "ÖRNEK ATÖLYE", "seri": ps.VARSAYILAN_SERI, "site": "example.com"}
    monkeypatch.setenv("WORKBENCH_POSTER_BRAND", "Your Store")
    monkeypatch.setenv("WORKBENCH_POSTER_SITE", "shop.example.org/")
    monkeypatch.setenv("WORKBENCH_POSTER_SERIES", "DESK OBJECTS")
    assert ps.marka_alanlari() == {"marka": "YOUR STORE", "seri": "DESK OBJECTS", "site": "shop.example.org"}
    e = _idler(ps.svg_doldur(VERI, None))
    assert (e["marka"].text, e["seri"].text, e["site"].text) == ("YOUR STORE", "DESK OBJECTS", "shop.example.org")
    e = _idler(ps.svg_doldur(VERI, None, marka={"marka": "X", "seri": "", "site": "example.com"}))
    assert e["seri"].get("display") == "none" and e["marka"].text == "X"
    assert "{" not in ET.tostring(ET.fromstring(ps.svg_doldur(VERI, None)), encoding="unicode")


def test_tr_buyuk_ve_urun_satiri() -> None:
    assert ps.tr_buyuk("Kiraz kapısı şık ağaç çöp üzüm") == "KİRAZ KAPISI ŞIK AĞAÇ ÇÖP ÜZÜM"
    assert ps.urun_satiri("İnce Kemerli Kontrolcü Standı") == "İNCE KEMERLİ KONTROLCÜ STANDI  ·  NO. 01"
    assert ps.urun_satiri("Dalga standı (dik + yatay)") == "DALGA STANDI (DİK + YATAY)  ·  NO. 01"
    uzun = ps.urun_satiri("Çok uzun bir ürün adı " * 4 + "(teknik ek)")
    assert len(uzun) <= ps.URUN_SATIRI_MAKS and "TEKNİK" not in uzun and uzun.endswith("…  ·  NO. 01")


def test_doldurma_idler_renk_ve_gizli_hucre() -> None:
    svg = ps.svg_doldur(VERI, "data:image/png;base64,AAAA")
    e = _idler(svg)
    assert e["urun_satiri"].text == "DALGA FORMUNDA TELEFON STANDI  ·  NO. 01"
    assert e["h1_etiket"].text == "A-01  YÜKSEKLİK" and e["h1_deger"].text == "9,8 cm"
    assert e["h3_deger"].text == "16,0 cm" and e["h4_deger"].text == "Mat PLA" and e["h5_deger"].text == "0,16 mm"
    assert e["h1_nokta"].get("fill") == "#BE5C3A" and e["h4_nokta"].get("fill") == "#3E807C"
    assert e["h5_nokta"].get("fill") == "#3E807C"
    assert e["h6"].get("display") == "none" and not e["h6_deger"].text  # 5 satır → 6. hücre gizli
    assert all(e[f"h{i}"].get("display") != "none" for i in range(1, 6))
    assert e["urun_foto"].get("href") == "data:image/png;base64,AAAA"


def test_az_satir_kalan_hucreleri_gizler_ve_altiyi_asmaz() -> None:
    e = _idler(ps.svg_doldur({"ad": "x", "satirlar": [("P-01", "MALZEME", "PLA")]}, None))
    assert e["h1_nokta"].get("fill") == "#3E807C"
    assert [e[f"h{i}"].get("display") for i in range(2, 7)] == ["none"] * 5
    assert e["urun_foto"].get("display") == "none"
    cok = {"ad": "x", "satirlar": [(f"A-0{i}", "E", str(i)) for i in range(1, 9)]}
    e = _idler(ps.svg_doldur(cok, None))
    assert e["h6_deger"].text == "6" and all(e[f"h{i}"].get("display") != "none" for i in range(1, 7))


def test_foto_kare_kirpilir(tmp_path: Path) -> None:
    import base64
    import io

    from PIL import Image

    url = ps.foto_veri_url(_png(tmp_path / "f.png", (1600, 900)))
    with Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))) as g:
        assert g.size == (900, 900)


def _urun(tmp_path: Path) -> Path:
    kok = tmp_path / "ornek-stand"
    ic = kok / "gorsel"
    ic.mkdir(parents=True)
    _png(ic / "studyo.png", (1200, 1200))
    (kok / "urun.yaml").write_text(yaml.safe_dump({
        "ad": "Dalga standı", "boyut_mm": {"x": 102, "y": 160, "z": 98},
        "dilimleme": {"katman_mm": 0.16, "filament": "Elegoo PLA Matte"}}, allow_unicode=True), encoding="utf-8")
    return kok


def test_uctan_uca_sahte_render_ve_eski_tasima(tmp_path: Path) -> None:
    kok = _urun(tmp_path)
    yakalanan: list[str] = []

    def render(svg: Path, png: Path) -> None:
        yakalanan.append(svg.read_text(encoding="utf-8"))
        _sahte_render(svg, png)

    eski = kok / "gorsel" / "konsept" / "teknik-poster-3x4.png"
    eski.parent.mkdir(parents=True)
    eski.write_bytes(b"eski")
    s = ps.uret_varsayilan("ornek-stand", urunler=tmp_path, render=render)
    assert Path(s["poster"]) == eski and eski.stat().st_size > 100
    assert s["eski"] and Path(s["eski"]).read_bytes() == b"eski" and Path(s["eski"]).parent.name == "eski"
    assert Path(s["dikey"]).name == "teknik-poster-9x16.png" and Path(s["dikey"]).exists()
    e = _idler(yakalanan[0])
    assert e["urun_satiri"].text == "DALGA STANDI  ·  NO. 01"
    assert [e[f"h{i}_deger"].text for i in range(1, 6)] == ["9,8 cm", "10,2 cm", "16,0 cm", "Mat PLA", "0,16 mm"]
    assert e["urun_foto"].get("href", "").startswith("data:image/png;base64,")
    assert not list((kok / "gorsel" / "konsept").glob(".poster-*"))  # ara dosya kalmaz


def test_veri_veya_foto_yoksa_uretmez(tmp_path: Path) -> None:
    kok = _urun(tmp_path)
    (kok / "gorsel" / "studyo.png").unlink()
    with pytest.raises(FileNotFoundError):
        ps.uret("ornek-stand", tmp_path / "p.png", urunler=tmp_path, render=_sahte_render)
    with pytest.raises(ValueError):
        ps.uret("ornek-stand", tmp_path / "p.png", _png(tmp_path / "f.png"), render=_sahte_render,
                veri={"ad": "x", "satirlar": []})


def test_cli_hata_json(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(ps, "uret", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("foto yok")))
    assert ps.main(["x", "--cikti", str(tmp_path / "p.png")]) == 1
    assert json.loads(capsys.readouterr().out) == {"basarili": False, "hata": "foto yok"}


def test_render_motor_sirasi(tmp_path: Path, monkeypatch) -> None:
    sira: list[str] = []

    def bozuk(svg, png):
        sira.append("inkscape")
        raise RuntimeError("yok")

    def iyi(svg, png):
        sira.append("chrome")
        png.write_bytes(b"x")

    monkeypatch.setattr(ps, "MOTORLAR", {"inkscape": bozuk, "chrome": iyi})
    assert ps.render_et(tmp_path / "a.svg", tmp_path / "a.png") == "chrome" and sira == ["inkscape", "chrome"]
    with pytest.raises(RuntimeError):
        ps.render_et(tmp_path / "a.svg", tmp_path / "a.png", "inkscape")


@pytest.mark.skipif(ps._inkscape_komutu() is None, reason="Inkscape kurulu değil")
def test_gercek_inkscape_render(tmp_path: Path) -> None:
    from PIL import Image

    hedef = Path.home() / ".cache" / "workbench-poster" / "test"
    hedef.mkdir(parents=True, exist_ok=True)
    try:
        foto = _png(hedef / "f.png", (900, 900), (190, 92, 58))
        cikti = ps.uret("x", hedef / "p.png", foto, veri=VERI, motor="inkscape")
        with Image.open(cikti) as g:
            g = g.convert("RGB")
            assert g.size == (1080, 1440)
            assert g.getpixel((540, 440)) == (190, 92, 58)  # ürün fotoğrafı kutuda
            assert g.getpixel((5, 5)) == (244, 241, 234)  # kâğıt
            assert g.getpixel((67, 895))[0] > 150  # A-01 noktası terracotta
            alt = g.crop((310, 1170, 540, 1270))  # 6. hücre gizli → boş kâğıt
            assert alt.getextrema() == ((244, 244), (241, 241), (234, 234))
    finally:
        shutil.rmtree(hedef, ignore_errors=True)
