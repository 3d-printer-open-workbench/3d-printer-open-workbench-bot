import json
from pathlib import Path

from coo.magaza_hatti import hazirla_istemi, pazar_basliklari, sayfa_bilgisi, yukleme_farklari

ORNEK = (Path(__file__).parent / "veri" / "magaza_urun_ornek.html").read_text(encoding="utf-8")


def test_sayfa_bilgisi_ornek_sayfa():
    b = sayfa_bilgisi(ORNEK)
    assert b["ad"] == "Örnek Masaüstü Düzenleyici - Kalemlik ve Not Kutusu"
    assert b["gorsel"] == 10 and b["teklif"] == 20 and b["fiyatlar"][0] == 35.0 and b["stokta"]
    assert "Open Workbench" in b["baslik"]


def test_yukleme_farklari():
    b = sayfa_bilgisi(ORNEK)
    dogru = {"baslik": b["ad"], "meta_baslik": "Örnek Masaüstü Düzenleyici", "satis_fiyati_tl": 35,
             "gorseller": ["a"] * 10, "varyantlar": [{"deger": "Siyah"}, {"deger": "Beyaz"}]}
    assert yukleme_farklari(dogru, b) == []
    yanlis = dict(dogru, satis_fiyati_tl=49.9, baslik="Başka", gorseller=["a"] * 12)
    f = " ".join(yukleme_farklari(yanlis, b))
    assert "Fiyat farklı" in f and "Ad farklı" in f and "Görsel eksik" in f
    assert "JSON-LD" in yukleme_farklari(dogru, sayfa_bilgisi("<html></html>"))[0]


def test_pazar_basliklari_ve_istem(tmp_path):
    kok = tmp_path / "x"
    (kok / "pazar").mkdir(parents=True)
    (kok / "pazar" / "fiyat.json").write_text(json.dumps({"ornekler": [
        {"ad": "Etsy Kedi Saksı", "platform": "Etsy", "benzerlik": 3, "ulke": "GLOBAL"},
        {"ad": "Sevimli Kedi Figürlü Saksı", "platform": "Trendyol", "benzerlik": 2, "ulke": "TR"},
        {"ad": "Alakasız Vazo", "platform": "n11", "benzerlik": 1, "ulke": "TR"}]}), encoding="utf-8")
    assert pazar_basliklari("x", tmp_path) == ["Sevimli Kedi Figürlü Saksı (Trendyol)", "Etsy Kedi Saksı (Etsy)"]
    ist = hazirla_istemi("x", 10, tmp_path)
    assert "Sevimli Kedi Figürlü Saksı" in ist and "seo_terimleri" in ist and "MARKA" in ist
