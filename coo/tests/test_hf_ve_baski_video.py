import datetime as dt

from coo import baski_video, hf_reels


def test_is_videosu_urun_klasorune_kopyalanir(tmp_path):
    m = tmp_path / "ornek" / "medya"
    m.mkdir(parents=True)
    (m / "timelapse.mp4").write_bytes(b"mp4")
    an = dt.datetime(2026, 11, 17, 23, 5)
    hedef = baski_video.is_videosu_kopyala("IS_NUMUNE", "ornek", "ornek.gcode", urunler=tmp_path, simdi=an)
    assert hedef == m / "baski" / "20261117-2305-numune.mp4" and hedef.read_bytes() == b"mp4"
    assert (m / "timelapse.mp4").exists()  # kaynak yerinde kalır


def test_hobi_ve_fire_kopyalanmaz(tmp_path):
    m = tmp_path / "ornek" / "medya"
    m.mkdir(parents=True)
    (m / "timelapse.mp4").write_bytes(b"x")
    for s in ("HOBI", "FIRE"):
        assert baski_video.is_videosu_kopyala(s, "ornek", urunler=tmp_path) is None


def test_eslesmeyen_baski_genel_klasore(tmp_path):
    m = tmp_path / "_genel_baski" / "medya"
    m.mkdir(parents=True)
    (m / "timelapse.mp4").write_bytes(b"x")
    genel = tmp_path / "genel"
    hedef = baski_video.is_videosu_kopyala("HEDIYE", None, "Kedi Saksı v2.gcode", urunler=tmp_path, genel=genel,
                                          simdi=dt.datetime(2026, 1, 2, 3, 4))
    assert hedef == genel / "20260102-0304-hediye-Kedi-Saks-v2.mp4"


def test_timelapse_yoksa_none(tmp_path):
    assert baski_video.is_videosu_kopyala("IS_SIPARIS", "yok", urunler=tmp_path) is None


def test_hf_urun_istemi_gercek_veri_ve_kaynak(tmp_path, monkeypatch):
    kok = tmp_path / "ornek"
    (kok / "gorsel" / "konsept").mkdir(parents=True)
    (kok / "medya").mkdir()
    (kok / "gorsel" / "studyo.png").write_bytes(b"x")
    (kok / "medya" / "flow-q-1-red.mp4").write_bytes(b"x")
    (kok / "medya" / "timelapse.mp4").write_bytes(b"x")
    import coo.bilgi_verisi as bv
    monkeypatch.setattr(bv, "bilgiler", lambda sku, urunler=None: {"ad": "Örnek", "satirlar": [("A-01", "YÜKSEKLİK", "11,8 cm")]})
    istem, cikti, _ = hf_reels.urun_istemi("ornek", "PS5 vurgusu", urunler=tmp_path)
    assert "A-01 YÜKSEKLİK = 11,8 cm" in istem and "studyo.png" in istem and "timelapse.mp4" in istem
    assert "-red.mp4" not in istem and "PS5 vurgusu" in istem and "HF_REELS_HAZIR" in istem
    assert cikti.parent == kok / "medya" and cikti.name.startswith("hf-reels-")


def test_hf_serbest_istemi():
    istem, cikti, proje = hf_reels.serbest_istemi("Atölyede bir gün")
    assert "SERBEST" in istem and cikti.parent == hf_reels.SERBEST_KLASORU and "atolyede-bir-gun" in cikti.name
