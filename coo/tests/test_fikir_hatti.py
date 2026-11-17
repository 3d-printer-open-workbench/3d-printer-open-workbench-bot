"""/fikir hattı (coo/fikir_hatti.py) birim testleri."""
from __future__ import annotations

import os
import time
from pathlib import Path

import yaml

from coo.fikir_hatti import (
    fikir_bilgisi,
    fikir_linkleri_ekle,
    flow_konsept_istemi,
    linkten_referans,
    referans_ayir,
    referans_yolu,
    referanslar,
    konsept_gorselleri_topla,
    konsept_yolu,
    sku_uret,
    tarif_coz,
    urun_klasoru_hazirla,
)


def test_sku_uret_turkce_ve_benzersiz(tmp_path: Path) -> None:
    sku = sku_uret("Minderde oturup çay içen teyze saksı 140mm", tmp_path)
    assert sku.startswith("minderde-oturup-cay-icen")
    assert sku.isascii() and "140" not in sku
    # callback_data "fikir:sec:<sku>:<n>" 64 baytı aşmamalı
    assert len(f"fikir:sec:{sku}:12".encode()) <= 64
    (tmp_path / sku).mkdir()
    assert sku_uret("Minderde oturup çay içen teyze saksı", tmp_path) == f"{sku}-2"


def test_sku_uret_bos_tarif(tmp_path: Path) -> None:
    assert sku_uret("!!!", tmp_path) == "fikir"


def test_tarif_coz_yukseklik_ve_saksi() -> None:
    assert tarif_coz("kedi saksı 140mm") == {"yukseklik_mm": 140.0, "saksi": True}
    assert tarif_coz("ejderha figürü") == {"yukseklik_mm": 120.0, "saksi": False}
    assert tarif_coz("dev heykel 900 mm")["yukseklik_mm"] == 250.0  # tabla sınırına (256) kırpılır
    assert tarif_coz("minik 20mm figür")["yukseklik_mm"] == 30.0  # alt sınır


def test_urun_klasoru_hazirla_ve_bilgi(tmp_path: Path) -> None:
    (tmp_path / "_sablon").mkdir()
    (tmp_path / "_sablon" / "urun.yaml").write_text("sku: x\ndurum: KONSEPT\nerp: {product_id: null}\n")
    kok = urun_klasoru_hazirla("kedi-saksi", "Kedi saksı 90mm", tmp_path)
    for alt in ("konsept", "model/ai3d", "gorsel", "uretim"):
        assert (kok / alt).is_dir()
    veri = yaml.safe_load((kok / "urun.yaml").read_text())
    assert veri["sku"] == "kedi-saksi" and veri["durum"] == "KONSEPT" and "erp" in veri
    assert fikir_bilgisi("kedi-saksi", tmp_path) == {"tarif": "Kedi saksı 90mm", "yukseklik_mm": 90.0, "saksi": True, "linkler": []}


def test_konsept_gorselleri_topla_numaralandirir(tmp_path: Path) -> None:
    indirilen = tmp_path / "indir"
    indirilen.mkdir()
    urunler = tmp_path / "urunler"
    (urunler / "a" / "konsept").mkdir(parents=True)
    (urunler / "a" / "konsept" / "flow-1.jpg").write_bytes(b"eski")

    eski = indirilen / "eski.png"
    eski.write_bytes(b"0")
    os.utime(eski, (time.time() - 3600, time.time() - 3600))
    baslangic = time.time()
    (indirilen / "not.txt").write_text("x")
    (indirilen / "g1.jpg").write_bytes(b"1")
    (indirilen / "g2.png").write_bytes(b"2")

    yollar = konsept_gorselleri_topla("a", baslangic, urunler, [indirilen])
    assert sorted(p.name for p in yollar) == ["flow-2.jpg", "flow-3.png"]
    assert eski.exists() and (indirilen / "not.txt").exists()
    assert konsept_yolu("a", 3, urunler).name == "flow-3.png"
    assert konsept_yolu("a", 9, urunler) is None


def test_flow_istemi_saksi_ve_guvenlik_kurallari() -> None:
    saksi = flow_konsept_istemi("kedi-saksi", "kedi saksı", True, revize_notu="kulaklar daha büyük")
    duz = flow_konsept_istemi("ejderha", "ejderha figürü", False)
    assert "pot cavity" in saksi and "pot cavity" not in duz
    assert "kulaklar daha büyük" in saksi
    for istem in (saksi, duz):
        assert "1K" in istem and "EN YÜKSEK KALİTELİ" in istem and "x4" in istem
        assert "REFERANS" not in istem and "file_upload ile görseli" not in istem
        assert "KONSEPT_HATA" in istem and "02_Urunler/" in istem


def test_referans_ayir() -> None:
    tarif, linkler = referans_ayir("buna benzer kedi saksı https://www.etsy.com/listing/123/kedi?ref=x, 120mm")
    assert linkler == ["https://www.etsy.com/listing/123/kedi?ref=x"]
    assert tarif == "buna benzer kedi saksı 120mm"
    assert referans_ayir("sadece metin") == ("sadece metin", [])


def test_referansli_istem(tmp_path: Path) -> None:
    yol = referans_yolu("kedi", ".png", tmp_path)
    yol.write_bytes(b"x")
    assert yol.name == "ref-1.png" and referanslar("kedi", tmp_path) == [yol]
    assert referans_yolu("kedi", ".jpg", tmp_path).name == "ref-2.jpg"
    istem = flow_konsept_istemi("kedi", "", True, referans_gorseller=[yol], linkler=["https://ornek.com/u"])
    assert str(yol) in istem and "https://ornek.com/u" in istem
    assert "birebir kopya DEĞİL" in istem and "file_upload ile görseli" in istem
    assert "referanstaki konsept" in istem


def test_linkten_referans_hata_none(tmp_path: Path) -> None:
    assert linkten_referans("http://127.0.0.1:9/yok", "kedi", tmp_path, zaman=2) is None


def test_linkler_yaml(tmp_path: Path) -> None:
    urun_klasoru_hazirla("kedi", "kedi saksı", tmp_path, ["https://a.com/1"])
    fikir_linkleri_ekle("kedi", ["https://a.com/1", "https://b.com/2"], tmp_path)
    assert fikir_bilgisi("kedi", tmp_path)["linkler"] == ["https://a.com/1", "https://b.com/2"]


def test_onarim_sorunlari_temiz_ve_kirli():
    from coo.fikir_hatti import onarim_sorunlari

    temiz = {"sonra": {"manifold": True, "ince_kose_yuzde": 0.0, "hazne_duvar_p5_mm": 6.9},
             "adalar_son": {"kopuk_parca_cm3": []}}
    hz = {"hazne": {"ust_cap_mm": 57}, "taban_temas_cm2": 160}
    assert onarim_sorunlari(temiz, hz, {"durum": "PASS"}, saksi=True) == []

    kirli = {"sonra": {"manifold": False, "ince_kose_yuzde": 2.5, "hazne_duvar_p5_mm": 1.4},
             "adalar_son": {"kopuk_parca_cm3": [3.2]}}
    s = onarim_sorunlari(kirli, {"hazne": None, "taban_temas_cm2": 4}, {"durum": "RED", "hatalar": ["x"]}, True)
    metin = " ".join(s)
    for parca in ("su geçirmez", "ince", "Hazne duvarı", "bağlı olmayan", "açık hazne", "Taban", "Kalite kapısı: x"):
        assert parca in metin


def test_onarim_istemi_kurallari(tmp_path):
    from coo.fikir_hatti import onarim_istemi

    m = onarim_istemi("ornek", ["Hazne duvarı ince"], tmp_path)
    assert "Hazne duvarı ince" in m and "--sadece-olc" in m and "ONARIM_TAMAM" in m
    assert "DEĞİŞTİRME" in m and "onar-oncesi.stl" in m
