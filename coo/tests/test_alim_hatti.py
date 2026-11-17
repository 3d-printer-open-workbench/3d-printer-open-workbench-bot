import json

import coo.alim_hatti as ah

FIL = [{"id": 9, "code": "FIL-SUNLU-MATPLA-KMK", "brand": "Sunlu", "material_type": "Mat PLA", "color_name": "Kemik",
        "price_per_kg_tl": 650.0, "spool_weight_gr": 1000}]
MAL = [{"id": 5, "code": "AMB-KUTU-KUCUK", "name": "Kargo Kutusu - Küçük", "category": "AMBALAJ", "unit": "adet",
        "unit_cost_tl": 18.0}]
VERI = {"fatura": {"tedarikci": "OrnekTedarikci", "no": "F-77", "tarih": "2026-11-16", "genel_toplam_tl": 2220,
                   "kargo_tl": 0, "indirim_tl": 0, "kdv_dahil": True},
        "kalemler": [
            {"tur": "FILAMENT", "aciklama": "Sunlu Matte PLA Bone 1kg x2", "eslesen_id": 9, "adet": 2, "miktar": 2000,
             "birim": "gr", "birim_fiyat_tl": 700, "toplam_tl": 1400},
            {"tur": "FILAMENT", "aciklama": "Elegoo PLA Matte Krem 1kg", "eslesen_id": None,
             "yeni": {"code": "FIL-ELEGOO-MATPLA-KREM", "brand": "Elegoo", "material_type": "Mat PLA",
                      "color_name": "Krem", "color_hex": "#E8DFD1"}, "adet": 1, "miktar": 1000, "birim": "gr",
             "birim_fiyat_tl": 520, "toplam_tl": 520},
            {"tur": "MALZEME", "aciklama": "Küçük koli x20", "eslesen_id": 5, "adet": 20, "miktar": 20, "birim": "adet",
             "birim_fiyat_tl": 15, "toplam_tl": 300}]}


def test_dogrula_temiz():
    engel, uyari = ah.dogrula(VERI, FIL, MAL, [])
    assert engel == [] and uyari == []


def test_dogrula_engeller():
    kotu = json.loads(json.dumps(VERI))
    kotu["kalemler"][0]["eslesen_id"] = 99
    kotu["kalemler"][1]["yeni"].pop("brand")
    kotu["kalemler"][2]["miktar"] = 0
    engel, _ = ah.dogrula(kotu, FIL, MAL, [{"invoice_no": "F-77"}])
    metin = " ".join(engel)
    for p in ("#99", "eksik alan", "miktar yok", "çift giriş"):
        assert p in metin


def test_dogrula_uyarilar():
    u = json.loads(json.dumps(VERI))
    u["kalemler"][0]["miktar"] = 2  # makara sayısı yazılmış
    u["fatura"]["genel_toplam_tl"] = 5000
    _, uyari = ah.dogrula(u, FIL, MAL, [])
    metin = " ".join(uyari)
    assert "gram olmalı" in metin and "genel toplam" in metin


def test_ozet_metni():
    m = ah.ozet_metni(VERI, FIL, MAL, [], [])
    assert "➕ stok" in m and "🆕 yeni kalem" in m and "2 kg" in m and "20 adet" in m and "ERP" in m


def test_uygula(monkeypatch):
    cagrilar = []

    def sahte(url, yol, govde=None):
        cagrilar.append((yol, govde))
        if yol == "/api/filaments":
            return {"id": 10}
        if yol.endswith("/alim"):
            return {"filament": {"remaining_weight_gr": 2500}} if "filaments" in yol else {"malzeme": {"stock_quantity": 21}}
        raise AssertionError(yol)

    monkeypatch.setattr(ah, "_istek", sahte)
    s = ah.uygula(VERI, "http://erp")
    assert [x["durum"] for x in s] == ["STOK", "YENI", "STOK"]
    assert ("/api/filaments/10/alim" in [c[0] for c in cagrilar])
    yeni = next(g for y, g in cagrilar if y == "/api/filaments")
    assert yeni["remaining_weight_gr"] == 0 and yeni["price_per_kg_tl"] == 520
    alim = next(g for y, g in cagrilar if y == "/api/filaments/9/alim")
    assert alim["miktar"] == 2000 and alim["fatura_no"] == "F-77" and alim["yeni_kalem"] is False
    assert "ERP'ye işlendi" in ah.sonuc_metni(s)


def test_aciklama_alim_mi():
    assert ah.aciklama_alim_mi("Fatura Trendyol") and ah.aciklama_alim_mi("alım listesi")
    assert not ah.aciklama_alim_mi("fikir kedi saksı")
