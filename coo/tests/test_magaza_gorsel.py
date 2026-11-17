import json
from pathlib import Path

from PIL import Image

from coo.magaza_gorsel import alt_metin, hazirla, kareye_tamamla


def _urun(tmp_path: Path) -> Path:
    kok = tmp_path / "ornek-saksi"
    (kok / "magaza").mkdir(parents=True)
    (kok / "gorsel").mkdir()
    Image.new("RGB", (1024, 1024), (250, 250, 250)).save(kok / "gorsel" / "kapak-beyaz.png")
    Image.new("RGB", (1536, 1024), (230, 225, 215)).save(kok / "gorsel" / "renkler-birlikte.png")
    Image.new("RGB", (1792, 2400), (241, 235, 225)).save(kok / "gorsel" / "teknik_poster-3x4.png")
    (kok / "magaza" / "paket.json").write_text(json.dumps({
        "baslik": "Çay Teyzesi Saksı - El Boyası Görünümlü", "slug": "cay-teyzesi-saksi",
        "gorseller": ["gorsel/kapak-beyaz.png", "gorsel/renkler-birlikte.png", "gorsel/teknik_poster-3x4.png"],
        "varyantlar": [{"deger": "Terrakota", "gorseller": ["gorsel/kapak-beyaz.png"]}]}), encoding="utf-8")
    return kok


def test_kareye_tamamla_kirpmaz_ve_kenar_tonunu_surdurur():
    im = Image.new("RGB", (300, 200), (200, 100, 50))
    k = kareye_tamamla(im)
    assert k.size == (300, 300)
    assert k.getpixel((5, 5)) == (200, 100, 50)


def test_hazirla(tmp_path):
    kok = _urun(tmp_path)
    s = hazirla("ornek-saksi", tmp_path, px=512)
    adlar = [g["dosya"] for g in s["gorseller"]]
    assert adlar == ["magaza/gorseller/cay-teyzesi-saksi-01.jpg", "magaza/gorseller/cay-teyzesi-saksi-02.jpg",
                     "magaza/gorseller/cay-teyzesi-saksi-03.jpg"]
    for a in adlar:
        im = Image.open(kok / a)
        assert im.size == (512, 512) and im.format == "JPEG"
    assert s["varyantlar"][0]["gorseller"][0]["dosya"].endswith("cay-teyzesi-saksi-terrakota-01.jpg")
    assert "tüm renk" in s["gorseller"][1]["alt"] and "Çay Teyzesi Saksı" in s["gorseller"][0]["alt"]
    assert (kok / "magaza" / "gorseller.json").exists()


def test_alt_metin():
    assert alt_metin("gorsel/renkler/krem/studyo-ic/doku-yakin.png", "Saksı", "Krem") == \
        "Saksı (Krem) — 3B baskı yüzey dokusu yakın çekim"
