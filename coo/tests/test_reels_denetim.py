import json
from pathlib import Path

from coo import reels_denetim as rd


def _kayit(tmp_path, tur="hf"):
    kid = rd.yeni_kayit(Path("/v/hf-reels-1.mp4"), {"tur": tur, "sku": "ornek", "proje": "/p/ornek-1"}, tmp_path)
    k = rd.oku(kid, tmp_path)
    k["maddeler"] = [{"no": 1, "zaman": "0:01", "onem": "yuksek", "sorun": "Kanca zayıf", "duzeltme": "İlk kareye soru ekle"},
                     {"no": 2, "zaman": "0:09", "onem": "dusuk", "sorun": "Ses düşük", "duzeltme": "Müziği +3 dB"}]
    k["durum"] = "HAZIR"
    rd.yaz(k, tmp_path)
    return kid


def test_istem_kayit_yolunu_ve_video_izle_icerir(tmp_path):
    kid = _kayit(tmp_path)
    t = rd.denetim_istemi(kid, tmp_path)
    assert "coo.video_izle" in t and str(rd.kayit_yolu(kid, tmp_path)) in t and "DENETIM_HAZIR" in t


def test_secim_toggle_ve_butonlar(tmp_path):
    kid = _kayit(tmp_path)
    k = rd.secimi_degistir(kid, 2, tmp_path)
    assert k["secili"] == [2]
    metinler = [b["text"] for satir in rd.butonlar(k) for b in satir]
    assert "☑ 2" in metinler and "☐ 1" in metinler and any("(1)" in m for m in metinler)
    assert rd.secimi_degistir(kid, 2, tmp_path)["secili"] == []
    assert rd.hepsini_sec(kid, tmp_path)["secili"] == [1, 2]
    assert all(len(b["callback_data"]) <= 64 for satir in rd.butonlar(k) for b in satir)


def test_duzeltme_istemi_yalniz_secilenler_ve_ajan(tmp_path):
    kid = _kayit(tmp_path)
    rd.secimi_degistir(kid, 1, tmp_path)
    ajan, istem = rd.duzeltme_istemi(kid, tmp_path)
    assert ajan == "reels-tiktok-strategist" and "İlk kareye soru ekle" in istem and "Müziği" not in istem
    assert "/p/ornek-1" in istem and "hf-reels-1-r.mp4" in istem
    assert json.loads(rd.kayit_yolu(kid, tmp_path).read_text())["durum"] == "DUZELTILIYOR"


def test_flow_duzeltme_cmo_ya_gider(tmp_path):
    kid = _kayit(tmp_path, "flow")
    rd.hepsini_sec(kid, tmp_path)
    ajan, istem = rd.duzeltme_istemi(kid, tmp_path)
    assert ajan == "cmo-store-director" and "flow" in istem.lower()


def test_ozet_metni(tmp_path):
    k = rd.oku(_kayit(tmp_path), tmp_path)
    m = rd.ozet_metni(k)
    assert "🔴 *1.*" in m and "Seçilenleri Düzelt" in m


def test_not_ile_duzeltme_secimsiz_calisir(tmp_path):
    kid = _kayit(tmp_path)
    ajan, istem = rd.duzeltme_istemi(kid, tmp_path, "ilk sahne daha hızlı")
    assert "PATRON NOTU" in istem and "ilk sahne daha hızlı" in istem and "İlk kareye soru" not in istem
    assert rd.oku(kid, tmp_path)["notlar"] == ["ilk sahne daha hızlı"]


def test_not_dugmesi_her_zaman_var(tmp_path):
    k = rd.oku(_kayit(tmp_path), tmp_path)
    assert any(b["callback_data"].startswith("rd:not:") for satir in rd.butonlar(k) for b in satir)
