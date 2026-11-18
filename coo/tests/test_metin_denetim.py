import json

import coo.metin_denetim as md

IYI = """<p>Kemer formunda bir oyun kolu standı. Kolu masada dik ve el altında tutar, kullanılmadığında rafta dekor olarak durur.</p>
<ul>
<li>İki yuva, oyun kolunu dik ve sabit tutar.</li>
<li>Kırmızı direkler, siyah kiriş, kemik rengi dalgalı kaide.</li>
<li>14 × 10 cm taban, masada az yer kaplar.</li>
</ul>
<table><tr><th>Ölçü</th><td>14,1 × 10,3 × 11,8 cm</td></tr><tr><th>Malzeme</th><td>Mat PLA</td></tr></table>
<p>Nemli bezle silinebilir; PLA güneşte veya 55 °C üstü ısıda şekil değiştirebilir. Siparişe özel basılır, 2 iş gününde kargoya verilir; kargo ücreti ayrıca hesaplanır.</p>"""


def _paket(**ek):
    p = {"baslik": "Kemer Formlu Oyun Kolu Standı - Minimal Masa Dekoru", "aciklama_html": IYI,
         "meta_aciklama": "Kısa meta."}
    p.update(ek)
    return p


def test_iyi_metin_gecer():
    assert md.denetle(_paket()) == []
    assert 50 <= md.kelime_sayisi(IYI) <= 130


def test_yz_kaliplari_yakalanir():
    kotu = IYI.replace("<li>İki yuva", "<li><strong>Oyun kolu yuvası:</strong> İki yuva").replace(
        "Kemer formunda", "Klasik kemerlerden ilham alan, masanıza dokunuş katan mükemmel")
    h = md.denetle(_paket(aciklama_html=kotu + "<p>Siparişe özel üretim — harika!</p>"))
    metin = " ".join(h)
    for beklenen in ("ilham alan", "dokunuş kat", "mükemmel", "Kalın etiket", "siparişe özel", "ünlem", "uzun tire"):
        assert beklenen in metin, (beklenen, h)


def test_uzunluk_ve_baslik_sinirlari():
    uzun = IYI.replace("</ul>", "</ul><p>" + "kelime " * 120 + "</p>")
    h = md.denetle(_paket(aciklama_html=uzun, baslik="Kemer Formlu – Oyun Kolu Standı, 3D Baskı Kontrolcü Tutucu, "
                                                       "Japon Tarzı Masa Dekoru Hediye"))
    assert any("çok uzun" in x for x in h) and any("başlık" in x for x in h)


def test_review_kaydi_ve_degisince_gecersiz(tmp_path):
    (tmp_path / "x" / "magaza").mkdir(parents=True)
    yol = tmp_path / "x" / "magaza" / "paket.json"
    yol.write_text(json.dumps(_paket()), encoding="utf-8")
    assert md.yukleme_engelleri(_paket()) == ["metin editör review'undan geçmedi"]
    assert md.review_kaydet("x", "sadeleştirildi", urunler_klasoru=tmp_path) == []
    paket = json.loads(yol.read_text(encoding="utf-8"))
    assert md.yukleme_engelleri(paket) == []
    paket["aciklama_html"] += "<p>ek</p>"
    assert md.review_gecerli(paket) == (False, "metin review'dan sonra değişmiş; yeniden review gerekli")


def test_kotu_metin_review_kaydi_yazilmaz(tmp_path):
    (tmp_path / "x" / "magaza").mkdir(parents=True)
    yol = tmp_path / "x" / "magaza" / "paket.json"
    yol.write_text(json.dumps(_paket(aciklama_html="<p>kısa</p>")), encoding="utf-8")
    assert md.review_kaydet("x", "n", urunler_klasoru=tmp_path)
    assert "metin_review" not in json.loads(yol.read_text(encoding="utf-8"))


def test_review_istemi_rehberi_ve_komutu_icerir():
    ist = md.review_istemi("x")
    assert md.REHBER in ist and "coo.metin_denetim x --review" in ist and "DOKUNMA" in ist
