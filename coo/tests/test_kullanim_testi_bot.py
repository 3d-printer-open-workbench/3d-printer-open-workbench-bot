"""🧪 Kullanım testi — bot akışı (sahte Telegram) + hat (urun.yaml kaydı, özet, bekleyen işler, ürün kartı)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml


class SahteTg:
    def __init__(self) -> None:
        self.mesajlar: list[tuple[str, list]] = []
        self.fotolar: list[str] = []
        self.istekler: list[tuple[str, dict]] = []

    async def mesaj_gonder(self, chat_id, metin, butonlar=None, **_):
        self.mesajlar.append((metin, butonlar or []))
        return {"ok": True}

    async def foto_gonder(self, chat_id, foto, aciklama="", butonlar=None, dosya_adi=""):
        self.fotolar.append(aciklama)
        self.mesajlar.append((aciklama, butonlar or []))
        return {"ok": True}

    async def callback_yanitla(self, cb_id, metin=""):
        return None

    def _json_istek(self, yontem, veri):
        self.istekler.append((yontem, veri))
        return {"ok": True}


def _cb(cm, tg, veri: str) -> None:
    asyncio.run(cm.callback_isle(tg, {"id": "1", "data": veri, "message": {"chat": {"id": 99}, "message_id": 5}}, 99))


def _veriler(butonlar) -> list[str]:
    return [b["callback_data"] for satir in butonlar for b in satir]


RAPOR_KALDI = {
    "tarih": "2026-11-18 12:00", "durum": "KALDI", "sablon": "telefon_standi", "vaat": "Telefon dik durur.",
    "ozet": {"kural": 3, "gecti": 2, "kaldi": 1},
    "kurallar": [
        {"kural": "yerlesme", "senaryo": "iPhone 16", "durum": "GEÇTİ", "deger": 1, "sinir": 1, "birim": "adet",
         "aciklama": "standda durdu"},
        {"kural": "kablo_boslugu", "senaryo": "iPhone 16", "durum": "KALDI", "deger": -16.4, "sinir": "> 0",
         "birim": "mm", "aciklama": "fiş zarfı"},
        {"kural": "egme_10_zorlayici", "senaryo": "iPhone 16", "durum": "KALDI", "deger": 40, "sinir": "≤ 5",
         "birim": "mm", "aciklama": "bilgi", "zorunlu": False},
    ],
    "duzeltme_onerisi": ["Telefonun alt kenarı ortasında 14 mm × 9 mm kablo kanalı aç."],
    "stand": {"kutle_g": 100.5, "kutle_kaynagi": "geometri tahmini"},
}


@pytest.fixture
def ortam(tmp_path: Path, monkeypatch):
    import coo.__main__ as cm
    from coo import bekleyen_isler as bi
    from coo import fikir_hatti, kullanim_testi_hatti as kh, magaza_hatti, pinterest_hatti, urun_menusu

    urunler = tmp_path / "veri" / "02_Urunler"
    urunler.mkdir(parents=True)
    for mod in (cm, bi, kh, urun_menusu, pinterest_hatti, magaza_hatti, fikir_hatti):
        monkeypatch.setattr(mod, "URUNLER_KLASORU", urunler)
    monkeypatch.setattr(bi, "MAGAZA_KLASORU", tmp_path / "magaza")
    monkeypatch.setattr(bi, "BASKI_KAYITLARI_KLASORU", tmp_path / "baski")
    ajanlar: list[tuple[str, str, dict]] = []
    monkeypatch.setattr(cm, "_ajan_arka_planda_calistir",
                        lambda tg, chat_id, ajan, istem, *a, **k: ajanlar.append((ajan, istem, k)))
    d = urunler / "tel"
    (d / "model").mkdir(parents=True)
    (d / "model" / "tel.stl").write_bytes(b"solid x\nendsolid x\n")
    (d / "urun.yaml").write_text(yaml.safe_dump({"sku": "tel", "ad": "Telefon Standı", "durum": "TASARIM",
                                                 "stl_yolu": "model/tel.stl"}, allow_unicode=True), encoding="utf-8")
    return cm, kh, urunler, ajanlar


def _rapor_yaz(kh, urunler: Path, rapor: dict, ad: str = "t1") -> dict:
    k = urunler / "tel" / "model" / "kullanim_testi" / ad
    k.mkdir(parents=True, exist_ok=True)
    (k / "pano.png").write_bytes(b"\x89PNG\r\n")
    r = {**rapor, "rapor": str(k / "rapor.json"), "pano": str(k / "pano.png")}
    (k / "rapor.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    kh.son_sonucu_kaydet("tel", r)
    return r


def _yaml(urunler: Path) -> dict:
    return yaml.safe_load((urunler / "tel" / "urun.yaml").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ hat
def test_kayit_onay_ozet_ve_revize_notu(ortam) -> None:
    _, kh, urunler, _ = ortam
    assert kh.durum("tel")["var"] is False
    _rapor_yaz(kh, urunler, RAPOR_KALDI)
    kt = _yaml(urunler)["kullanim_testi"]
    assert kt["son"]["durum"] == "KALDI" and kt["son"]["rapor"] == "model/kullanim_testi/t1/rapor.json"
    assert kt["onay"] == "BEKLIYOR" and kt["sablon"] == "telefon_standi" and kt["vaat"] == "Telefon dik durur."
    metin = kh.ozet_metni("tel", kh.rapor_oku("tel"))
    assert "KALDI" in metin and "kablo_boslugu: -16.4 mm" in metin and "14 mm × 9 mm" in metin
    assert "egme_10_zorlayici" not in metin  # zorunlu olmayan (bilgi) kural özet/revizede yok
    notu = kh.revize_notu("tel", RAPOR_KALDI, "ön dudağı koru")
    assert "kablo_boslugu" in notu and "egme_10" not in notu and "ön dudağı koru" in notu
    _rapor_yaz(kh, urunler, {**RAPOR_KALDI, "tarih": "2026-11-18 13:00"}, "t2")
    kt = _yaml(urunler)["kullanim_testi"]
    assert kt["gecmis"][-1]["tarih"] == "2026-11-18 12:00"
    kh.onayla("tel")
    assert kh.durum("tel")["onayli"] and _yaml(urunler)["kullanim_testi"]["onaylanan_durum"] == "KALDI"
    assert kh.tur_artir("tel") == 1 and kh.tur_artir("tel") == 2 and kh.tur_artir("tel", sifirla=True) == 0
    assert kh.motor_komutu("tel")[-3:] == ["coo.kullanim_testi", "tel", "--kayit"]


# ------------------------------------------------------------------------------------------------ ürün kartı
def test_urun_kartinda_kullanim_testi_adimi(ortam) -> None:
    _, kh, urunler, _ = ortam
    from coo.urun_menusu import sonraki_adim, urun_karti

    a = sonraki_adim("tel")
    assert a["ad"] == "🧪 Kullanım testi" and a["no"] == 3 and a["buton"] == "kt:baslat:tel"
    metin, butonlar, _ = urun_karti("tel")
    assert "👉 3. 🧪 Kullanım testi" in metin and "4. Renk" in metin and "12. İkas'a yükle" in metin
    assert "kt:baslat:tel" in _veriler(butonlar)
    _rapor_yaz(kh, urunler, RAPOR_KALDI)
    assert "KALDI · onay bekliyor" in urun_karti("tel")[0]
    assert sonraki_adim("tel")["buton"] == "kt:goster:tel"
    kh.onayla("tel")
    assert sonraki_adim("tel")["ad"] == "Renk"
    # dilimlenmiş eski ürün: test adımı akışı kesmez (uyarı ile)
    (urunler / "tel" / "uretim").mkdir()
    (urunler / "tel" / "uretim" / "tel.3mf").write_bytes(b"x")
    _rapor_yaz(kh, urunler, RAPOR_KALDI, "t3")
    assert sonraki_adim("tel")["ad"] != "🧪 Kullanım testi"


# ------------------------------------------------------------------------------------------------ bot
def test_baslat_ajan_sonuc_panosu_ve_onay(ortam) -> None:
    cm, kh, urunler, ajanlar = ortam
    tg = SahteTg()
    _cb(cm, tg, "kt:baslat:tel")
    ajan, istem, k = ajanlar[-1]
    assert ajan == "kullanim-test-muhendisi" and "coo.kullanim_testi tel --kayit" in istem
    assert cm.AJAN_MODELLERI["kullanim-test-muhendisi"] == "opus" and "kullanim-test-muhendisi" in cm.AJAN_KATALOGU
    _rapor_yaz(kh, urunler, RAPOR_KALDI)
    asyncio.run(k["sonraki_islem"](True, "KALDI — kablo −16 mm", None))
    assert any("kullanım testi — KALDI" in f for f in tg.fotolar)
    metin, butonlar = tg.mesajlar[-1]
    assert "KALDI" in metin and _veriler(butonlar)[:3] == ["kt:onay:tel", "ng:kt:tel", "kt:tasarim:tel"]
    _cb(cm, tg, "kt:onay:tel")
    assert _yaml(urunler)["kullanim_testi"]["onay"] == "ONAYLANDI"
    assert "onaylandı" in tg.mesajlar[-1][0]


def test_yeniden_tasarla_otomatik_tekrar_test_en_fazla_uc_tur(ortam, monkeypatch) -> None:
    cm, kh, urunler, ajanlar = ortam
    _rapor_yaz(kh, urunler, RAPOR_KALDI)
    calisma = {"n": 0}

    def sahte_motor(sku, zaman_asimi=1800):
        calisma["n"] += 1
        return _rapor_yaz(kh, urunler, {**RAPOR_KALDI, "tarih": f"tur{calisma['n']}"}, f"r{calisma['n']}")

    monkeypatch.setattr(kh, "motoru_calistir", sahte_motor)
    tg = SahteTg()
    _cb(cm, tg, "kt:tasarim:tel")
    for tur in (1, 2, 3):
        ajan, istem, k = ajanlar[-1]
        assert ajan == "cad-artist" and f"turu {tur}/3" in istem and "kablo kanalı" in istem
        asyncio.run(k["sonraki_islem"](True, "taban +10 mm", None))  # yeni STL → otomatik tekrar test
    assert calisma["n"] == 3 and len([a for a in ajanlar if a[0] == "cad-artist"]) == 3
    assert kh.durum("tel")["tur"] == 3
    _cb(cm, tg, "kt:tasarim:tel")  # 3 tur doldu → Patrona sor, ajan çağrılmaz
    metin, butonlar = tg.mesajlar[-1]
    assert "3 yeniden tasarım turunda" in metin and "kt:tasarimsifir:tel" in _veriler(butonlar)
    assert len([a for a in ajanlar if a[0] == "cad-artist"]) == 3
    _cb(cm, tg, "kt:tasarimsifir:tel")
    assert ajanlar[-1][0] == "cad-artist" and "turu 1/3" in ajanlar[-1][1]


def test_gecti_ise_tasarim_yok_ve_not_ile_guncelle(ortam) -> None:
    cm, kh, urunler, ajanlar = ortam
    _rapor_yaz(kh, urunler, {**RAPOR_KALDI, "durum": "GEÇTİ", "duzeltme_onerisi": []})
    tg = SahteTg()
    _cb(cm, tg, "kt:goster:tel")
    assert "kt:baslat:tel" in _veriler(tg.mesajlar[-1][1]) and "kt:tasarim:tel" not in _veriler(tg.mesajlar[-1][1])
    _cb(cm, tg, "kt:tasarim:tel")
    assert "KALDI sonucu yok" in tg.mesajlar[-1][0] and not ajanlar
    _cb(cm, tg, "ng:kt:tel")
    yontem, istek = tg.istekler[-1]
    assert yontem == "sendMessage" and istek["reply_markup"]["force_reply"] and "[kt|tel]" in istek["text"]
    asyncio.run(cm.mesaj_isle(tg, {"chat": {"id": 99}, "text": "yatay yönü de dene",
                                   "reply_to_message": {"text": istek["text"]}}, 99))
    assert ajanlar[-1][0] == "kullanim-test-muhendisi" and "yatay yönü de dene" in ajanlar[-1][1]
    assert _yaml(urunler)["revize_notlari"][-1]["tur"] == "kt"


def test_dilimleme_ve_magazaya_geciste_uyari_engellemez(ortam, monkeypatch) -> None:
    cm, kh, urunler, _ = ortam
    cagri: list[str] = []

    async def sahte_dilim(tg, chat_id, sku):
        cagri.append(sku)

    monkeypatch.setattr(cm, "_dilimleme_ozeti_gonder", sahte_dilim)
    tg = SahteTg()
    _cb(cm, tg, "orca:analiz:tel")
    assert cagri == ["tel"]  # engellenmedi
    uyari = [m for m in tg.mesajlar if "kullanım testi hiç yapılmadı" in m[0]]
    assert uyari and "kt:baslat:tel" in _veriler(uyari[0][1])
    _rapor_yaz(kh, urunler, RAPOR_KALDI)
    kh.onayla("tel")
    tg2 = SahteTg()
    _cb(cm, tg2, "orca:analiz:tel")
    assert not [m for m in tg2.mesajlar if "Kullanım" in m[0] or "kullanım testi" in m[0]]


def test_bekleyen_islerde_kullanim_testi_onayi(ortam, tmp_path) -> None:
    cm, kh, urunler, _ = ortam
    from coo import bekleyen_isler as bi

    assert not [i for i in bi.urun_isleri("tel", urunler) if i["tur"] == "kt"]
    _rapor_yaz(kh, urunler, RAPOR_KALDI)
    isler = [i for i in bi.urun_isleri("tel", urunler) if i["tur"] == "kt"]
    assert len(isler) == 1
    metin, butonlar = bi.is_detayi(isler[0])
    v = _veriler(butonlar)
    assert "KALDI" in metin and "kablo kanalı" in metin
    assert v[:2] == ["kt:onay:tel", "ng:kt:tel"] and "kt:goster:tel" in v and "kt:tasarim:tel" in v
    assert bi.not_basligi_coz(bi.not_basligi("kt", "tel")) == ("kt", "tel")
    kh.onayla("tel")
    assert not [i for i in bi.urun_isleri("tel", urunler) if i["tur"] == "kt"]
