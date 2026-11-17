import coo.teklif_hatti as th

KADEME = [{"tier_name": "Kurumsal Bronz", "min_quantity": 20, "max_quantity": 100, "discount_percent": 7.5, "is_active": True},
          {"tier_name": "Kurumsal Silver", "min_quantity": 100, "max_quantity": 1000, "discount_percent": 15, "is_active": True}]
T = {"musteri": "Kafe", "proje": "Açılış", "kalemler": [
    {"ad": "Duvar yazısı", "adet": 1, "gram_birim": 380, "sure_sn_birim": 34140, "olcu": "1000 mm", "renk": "yeşil",
     "ek_malzeme": [{"material_id": None, "ad": "bant", "miktar": 2, "birim_tutar_tl": 20}], "tasarim_ucreti_tl": 0},
    {"ad": "QR stand", "adet": 30, "gram_birim": 40, "sure_sn_birim": 3600, "ek_malzeme": []}],
    "varsayimlar": ["Kalınlık 10 mm"], "sorular": ["Renk?"], "denetim": {"sonuc": "DUZELTILDI", "notlar": ["adet 30"]}}


def test_kademe():
    assert th.indirim_kademesi(10, KADEME) == (0.0, "")
    assert th.indirim_kademesi(30, KADEME) == (7.5, "Kurumsal Bronz")
    assert th.indirim_kademesi(150, KADEME)[0] == 15


def test_kalem_dogrula():
    assert th.kalem_dogrula(T) == []
    kotu = {"kalemler": [{"ad": "x", "adet": 0, "gram_birim": 0, "sure_sn_birim": 0}, {"ad": "y", "modellenemedi": True}]}
    h = " ".join(th.kalem_dogrula(kotu))
    assert "adet yok" in h and "ölçülmemiş" in h and "modellenemedi" in h


def test_fiyatla(monkeypatch):
    cagrilar = []

    def sahte(url, yol, govde=None):
        if yol == "/api/settings":
            return {"settings": {"default_b2b_margin_percent": 30, "default_vat_enabled": False,
                                 "default_shipping_cost": 150, "esnaf_muafiyeti_enabled": True, "brand_name": "Open Workbench"},
                    "b2b_tiers": KADEME}
        cagrilar.append(govde)
        return {"saved_quote_id": len(cagrilar), "total_production_cost_tl": 100.0 * govde["quantity"],
                "pricing": {"final_sale_price_gross_tl": 150.0 * govde["quantity"], "net_profit_tl": 40.0}}

    monkeypatch.setattr(th, "_erp", sahte)
    f = th.fiyatla(T, "http://erp", filament_id=3, kaydet=False)
    assert cagrilar[0]["print_hours_per_unit"] == 9 and cagrilar[0]["print_minutes_per_unit"] == 29
    assert cagrilar[0]["extra_material_cost_per_unit_tl"] == 40 and cagrilar[0]["shipping_total_tl"] == 150
    assert cagrilar[1]["shipping_total_tl"] == 0 and cagrilar[1]["discount_percent"] == 7.5
    assert cagrilar[1]["filament_id"] == 3 and cagrilar[0]["save_quote"] is False
    assert f["genel_toplam_tl"] == 150 * 31 and f["satirlar"][1]["birim_tl"] == 150
    assert f["teslim_is_gunu"] == 2 + 3  # 9.5 + 30 sa = 39.5 sa → 3 gün + 2 hazırlık
    html = th.pdf_html(T, f, "TEKLIF-X")
    assert "4.650,00 TL" in html and "Esnaf muafiyeti" in html and "Kurumsal Bronz" in html
    assert "100" not in th.pdf_html(T, f, "TEKLIF-X").split("GENEL TOPLAM")[0].split("<table>")[1][:0]
    o = th.ozet_metni(T, f, "TEKLIF-X")
    assert "Opus denetimi" in o and "❓ Renk?" in o and "net kâr" in o
    assert "net kâr" not in html.lower() and "maliyet" not in html.lower()


def test_ajan_modelleri():
    import coo.__main__ as b
    assert b._claude_komut_ve_ortam("claude", "trend-researcher", "x")[0][-3:] == ["--model", "sonnet", "x"]
    assert b._claude_komut_ve_ortam("claude", "ceo-orchestrator", "x")[0][-3:] == ["--model", "opus", "x"]
    assert b._claude_komut_ve_ortam("claude", "cad-artist", "x", model="sonnet")[0][-3:] == ["--model", "sonnet", "x"]
    assert set(b.AJAN_MODELLERI) >= {"ceo-orchestrator", "finance-tracker", "slicer-engineer"}
