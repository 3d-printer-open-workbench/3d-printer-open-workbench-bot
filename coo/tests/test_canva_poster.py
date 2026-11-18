from coo import konsept_hatti as kh


def test_tr_buyuk_noktali_i():
    assert kh.tr_buyuk("Kiraz kapısı") == "KİRAZ KAPISI"


def test_canva_sablonu_varsa_teknik_poster_canva_ile_uretilir(monkeypatch, tmp_path):
    sablon = tmp_path / "teknik-poster-canva.yaml"
    sablon.write_text("ana_tasarim: X\n", encoding="utf-8")
    monkeypatch.setattr(kh, "CANVA_SABLON", sablon)
    kok = tmp_path / "urun-x"
    (kok / "gorsel").mkdir(parents=True)
    (kok / "gorsel" / "studyo.png").write_bytes(b"x")
    (kok / "gorsel" / "kullanim-q-1.png").write_bytes(b"x")
    monkeypatch.setattr(kh, "URUNLER_KLASORU", tmp_path)
    import coo.bilgi_verisi as bv
    monkeypatch.setattr(bv, "bilgiler", lambda sku, urunler=None: {"ad": "Örnek ürün", "satirlar": [("A-01", "YÜKSEKLİK", "11,8 cm")]})
    konsept = {"ad": "teknik-poster", "baslik": "Teknik Poster", "oranlar": ["3:4", "9:16"], "video": True,
               "bilgi_katmani": "teknik_poster", "video_istemi": "slow push-in", "yol": "x.md", "referanslar": [],
               "poster_motoru": "canva"}
    t = kh.konsept_istemi("urun-x", konsept)
    assert "CANVA POSTER" in t and "teknik-poster-canva.yaml" in t
    assert "A-01 YÜKSEKLİK = 11,8 cm" in t and "ÖRNEK ÜRÜN" in t
    assert "gorsel/studyo.png" in t and "kullanim-q-1" not in t.split("CANVA POSTER")[1].split("\n")[1]
    assert "-ham.png" not in t and "Görsel modunda EN YÜKSEK" not in t
    assert "ek bant EKLEME" in t


def test_diger_konsept_flow_gorsel_adimini_korur(monkeypatch, tmp_path):
    (tmp_path / "u" / "gorsel").mkdir(parents=True)
    monkeypatch.setattr(kh, "URUNLER_KLASORU", tmp_path)
    konsept = {"ad": "sade", "baslik": "Sade", "oranlar": ["3:4"], "video": False, "yol": "x.md", "referanslar": []}
    t = kh.konsept_istemi("u", konsept)
    assert "Görsel modunda EN YÜKSEK" in t and "CANVA POSTER" not in t


def test_poster_fotografi_cok_renk_kararini_kullanir(tmp_path):
    kok = tmp_path / "u"
    (kok / "gorsel").mkdir(parents=True)
    (kok / "gorsel" / "studyo.png").write_bytes(b"x")  # eski tek renk (gri) kare
    ic = kok / "model" / "cok_renk" / "render" / "studyo-ic"
    ic.mkdir(parents=True)
    (ic / "krem-fon.png").write_bytes(b"x")
    (kok / "urun.yaml").write_text(
        "cok_renk:\n  karar: onay\n  sema: A · B\n  renkler:\n  - {ad: Kemik, hex: '#E1D6C1'}\n"
        "  - {ad: Turuncu, hex: '#E67E22'}\n", encoding="utf-8")
    assert kh.poster_fotografi("u", tmp_path) == ic / "krem-fon.png"


def test_canva_sablonu_yoksa_flow_poster_ve_bilgi_bandi(monkeypatch, tmp_path):
    monkeypatch.setattr(kh, "CANVA_SABLON", tmp_path / "yok.yaml")
    (tmp_path / "u" / "gorsel").mkdir(parents=True)
    monkeypatch.setattr(kh, "URUNLER_KLASORU", tmp_path)
    konsept = {"ad": "teknik-poster", "baslik": "Teknik Poster", "oranlar": ["3:4", "9:16"], "video": True,
               "bilgi_katmani": "teknik_poster", "video_istemi": "slow push-in", "yol": "x.md", "referanslar": [],
               "poster_motoru": "canva"}
    t = kh.konsept_istemi("u", konsept)
    assert "CANVA POSTER" not in t and "-3x4-ham.png" in t and "coo.teknik_poster reels u" in t


def test_varsayilan_yerel_sablon_flow_ve_canva_kullanmaz(monkeypatch, tmp_path):
    sablon = tmp_path / "teknik-poster-canva.yaml"
    sablon.write_text("ana_tasarim: X\n", encoding="utf-8")  # Canva haritası olsa bile yerel varsayılan kazanır
    monkeypatch.setattr(kh, "CANVA_SABLON", sablon)
    (tmp_path / "u" / "gorsel").mkdir(parents=True)
    monkeypatch.setattr(kh, "URUNLER_KLASORU", tmp_path)
    konsept = {"ad": "teknik-poster", "baslik": "Teknik Poster", "oranlar": ["3:4", "9:16"], "video": True,
               "bilgi_katmani": "teknik_poster", "video_istemi": "slow push-in", "yol": "x.md", "referanslar": []}
    assert kh.yerel_poster_mu(konsept)
    t = kh.konsept_istemi("u", konsept)
    assert "POSTER HAZIR" in t and "Canva KULLANMA" in t and "CANVA POSTER" not in t
    assert "teknik-poster-3x4.png" in t and "teknik-poster-9x16.png" in t and "ek bant EKLEME" in t
    assert "-3x4-ham.png" not in t and "Görsel modunda EN YÜKSEK" not in t
    assert not kh.yerel_poster_mu({**konsept, "poster_motoru": "flow"})
    assert not kh.yerel_poster_mu({"ad": "sade", "bilgi_katmani": ""})
