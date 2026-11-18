"""📋 Bekleyen İşler · ✏️ Not ile Güncelle · 🗑️ Ürün Sil · 🧹 Klasör Temizliği — bot akışı (sahte Telegram)."""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import pytest
import yaml


class SahteTg:
    def __init__(self) -> None:
        self.mesajlar: list[tuple[str, list]] = []
        self.istekler: list[tuple[str, dict]] = []

    async def mesaj_gonder(self, chat_id, metin, butonlar=None, **_):
        self.mesajlar.append((metin, butonlar or []))
        return {"ok": True}

    async def foto_gonder(self, chat_id, foto, aciklama="", butonlar=None, dosya_adi=""):
        self.mesajlar.append((aciklama, butonlar or []))
        return {"ok": True}

    async def callback_yanitla(self, cb_id, metin=""):
        return None

    async def klavye_guncelle(self, chat_id, message_id, butonlar):
        self.mesajlar.append(("<klavye>", butonlar))
        return True

    async def klavye_temizle(self, chat_id, message_id):
        return True

    def _json_istek(self, yontem, veri):
        self.istekler.append((yontem, veri))
        return {"ok": True}


def _cb(cm, tg, veri: str) -> None:
    asyncio.run(cm.callback_isle(tg, {"id": "1", "data": veri, "message": {"chat": {"id": 99}, "message_id": 5}}, 99))


def _veriler(butonlar) -> list[str]:
    return [b["callback_data"] for satir in butonlar for b in satir]


@pytest.fixture
def ortam(tmp_path: Path, monkeypatch):
    import shutil

    import coo.__main__ as cm
    from coo import bekleyen_isler as bi
    from coo import fikir_hatti, magaza_hatti, pinterest_hatti
    from coo import klasor_temizlik as kt

    urunler = tmp_path / "veri" / "02_Urunler"
    urunler.mkdir(parents=True)
    for mod in (cm, bi, kt, pinterest_hatti, magaza_hatti, fikir_hatti):
        monkeypatch.setattr(mod, "URUNLER_KLASORU", urunler)
    monkeypatch.setattr(bi, "MAGAZA_KLASORU", tmp_path / "magaza")
    monkeypatch.setattr(bi, "BASKI_KAYITLARI_KLASORU", tmp_path / "baski")
    monkeypatch.setattr(kt, "REELS_DENETIM_KLASORU", tmp_path / "magaza" / "reels_denetim")
    monkeypatch.setattr(kt, "VIDEO_ATOLYESI", tmp_path / "Video_Atölyesi")
    monkeypatch.setattr(kt, "VERI_KLASORU", tmp_path / "veri")
    monkeypatch.setattr(kt, "COP_KLASORU", tmp_path / "veri" / "99_Cop")
    monkeypatch.setattr(kt, "KOK", tmp_path)
    gercek_which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda ad, *a, **k: None if ad == "gio" else gercek_which(ad, *a, **k))
    ajanlar: list[tuple[str, str]] = []
    monkeypatch.setattr(cm, "_ajan_arka_planda_calistir",
                        lambda tg, chat_id, ajan, istem, *a, **k: ajanlar.append((ajan, istem)))
    monkeypatch.setattr(cm.BELLEK, "urun_silme", {})
    monkeypatch.setattr(cm.BELLEK, "temizlik", {})
    return cm, urunler, ajanlar, tmp_path


def _urun(urunler: Path, sku: str, **alanlar) -> Path:
    d = urunler / sku
    d.mkdir(parents=True, exist_ok=True)
    (d / "urun.yaml").write_text(yaml.safe_dump({"sku": sku, "ad": sku.title(), **alanlar}, allow_unicode=True),
                                 encoding="utf-8")
    return d


def test_ana_menu_ve_komut_listesi() -> None:
    import coo.__main__ as cm

    v = _veriler(cm._ust_yonetim_butonlari())
    assert "bk:liste" in v and "tmz:tara" in v
    komutlar = dict(cm.BOT_KOMUTLARI)
    assert "bekleyen" in komutlar and "temizlik" in komutlar


def test_bekleyen_liste_detay_ve_not_ile_guncelle(ortam) -> None:
    cm, urunler, ajanlar, _ = ortam
    d = _urun(urunler, "kedi", studyo_onayi="BEKLIYOR")
    (d / "gorsel").mkdir()
    (d / "gorsel" / "kullanim-q-1.png").write_bytes(b"x")  # pin görsel adayı
    (d / "medya" / "pinterest").mkdir(parents=True)
    (d / "medya" / "pinterest" / "pin.json").write_text('{"durum": "HAZIR", "baslik": "Kedi"}', encoding="utf-8")
    tg = SahteTg()
    asyncio.run(cm.mesaj_isle(tg, {"chat": {"id": 99}, "text": "/bekleyen"}, 99))
    metin, butonlar = tg.mesajlar[-1]
    assert "Bekleyen İşler" in metin and {"bk:g:es:kedi", "bk:g:pn:kedi"} <= set(_veriler(butonlar))

    _cb(cm, tg, "bk:g:pn:kedi")
    metin, butonlar = tg.mesajlar[-1]
    assert "Pinterest" in metin
    assert _veriler(butonlar)[:2] == ["pin:paylas:kedi", "ng:pn:kedi"]

    _cb(cm, tg, "ng:pn:kedi")
    yontem, istek = tg.istekler[-1]
    assert yontem == "sendMessage" and istek["reply_markup"]["force_reply"]
    baslik = istek["text"]
    asyncio.run(cm.mesaj_isle(tg, {"chat": {"id": 99}, "text": "başlık daha kısa olsun",
                                   "reply_to_message": {"text": baslik}}, 99))
    assert ajanlar and ajanlar[-1][0] == "pinterest-curator" and "başlık daha kısa olsun" in ajanlar[-1][1]
    v = yaml.safe_load((d / "urun.yaml").read_text(encoding="utf-8"))
    assert v["revize_notlari"][-1]["not"] == "başlık daha kısa olsun" and v["revize_notlari"][-1]["tur"] == "pn"

    _cb(cm, tg, "bk:g:yok:kedi")
    assert "artık bekleyenlerde değil" in tg.mesajlar[-1][0]


def test_urun_sil_iki_asamali_ve_satistaki_listede_yok(ortam) -> None:
    cm, urunler, _, tmp = ortam
    _urun(urunler, "taslak", durum="TASARIM", erp={"product_id": 3})
    satis = _urun(urunler, "satista", durum="SATISTA")
    (satis / "magaza").mkdir()
    (satis / "magaza" / "yukleme.json").write_text('{"durum": "YUKLENDI", "panel_linki": "x"}', encoding="utf-8")
    tg = SahteTg()
    _cb(cm, tg, "usil:liste")
    metin, butonlar = tg.mesajlar[-1]
    assert "Ürün Sil" in metin and _veriler(butonlar) == ["usil:s:0", "usil:onay", "usil:iptal"]
    assert "Taslak" in butonlar[0][0]["text"]
    _cb(cm, tg, "usil:onay")
    assert "Önce silinecek" in tg.mesajlar[-1][0]
    _cb(cm, tg, "usil:s:0")
    _cb(cm, tg, "usil:onay")
    metin, butonlar = tg.mesajlar[-1]
    assert "Emin misin" in metin and "ERP kaydı SİLİNMEZ" in metin and _veriler(butonlar) == ["usil:evet", "usil:iptal"]
    assert (urunler / "taslak").is_dir()  # ilk onayda hiçbir şey silinmez
    _cb(cm, tg, "usil:evet")
    assert not (urunler / "taslak").exists() and (urunler / "satista").is_dir()
    assert list((tmp / "veri" / "99_Cop").rglob("taslak/urun.yaml"))
    assert "1 ürün çöp kutusuna" in tg.mesajlar[-1][0]


def test_urun_sil_kod_duzeyinde_satistakini_reddeder(ortam) -> None:
    cm, urunler, _, _ = ortam
    _urun(urunler, "x", durum="TASARIM")
    tg = SahteTg()
    _cb(cm, tg, "usil:liste")
    _cb(cm, tg, "usil:s:0")
    cm.urun_yaml_guncelle("x", {"durum": "SATISTA"})  # liste açıldıktan sonra satışa çıktı
    _cb(cm, tg, "usil:evet")
    assert (urunler / "x").is_dir() and "silinmedi: satışta" in tg.mesajlar[-1][0]


def test_klasor_temizligi_tara_sec_onayla(ortam) -> None:
    cm, urunler, _, tmp = ortam
    d = _urun(urunler, "ayi", durum="TASARIM")
    eski = time.time() - 3 * 86400
    aday = d / "gorsel" / "sahne" / "qwen-tmp" / "render-7.png"
    korunan = d / "gorsel" / "beyaz.png"
    for f in (aday, korunan):
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x" * 100)
        os.utime(f, (eski, eski))
    tg = SahteTg()
    asyncio.run(cm.mesaj_isle(tg, {"chat": {"id": 99}, "text": "/temizlik"}, 99))
    metin, butonlar = tg.mesajlar[-1]
    assert "henüz hiçbir şey silinmedi" in metin and _veriler(butonlar) == ["tmz:s:gorsel", "tmz:onay", "tmz:iptal"]
    _cb(cm, tg, "tmz:s:gorsel")
    _cb(cm, tg, "tmz:onay")
    assert "Emin misin" in tg.mesajlar[-1][0] and aday.exists()
    _cb(cm, tg, "tmz:evet")
    assert not aday.exists() and korunan.exists()
    assert "1 öğe" in tg.mesajlar[-1][0]


def test_sonuc_mesajlarinda_not_ile_guncelle_var(ortam, monkeypatch) -> None:
    cm, urunler, ajanlar, _ = ortam
    _urun(urunler, "kedi")
    assert _veriler(cm._fikir_alt_butonlari("kedi"))[-1] == "ng:kf:kedi"
    # mağaza paketi notu: önceki fire oranıyla, notlu istemle yeniden hazırlanır
    d = urunler / "kedi"
    (d / "uretim").mkdir()
    (d / "uretim" / "kedi.gcode").write_text(";")
    (d / "magaza").mkdir()
    (d / "magaza" / "paket.json").write_text('{"maliyet": {"fire_yuzde": 15}}', encoding="utf-8")
    tg = SahteTg()
    asyncio.run(cm._not_ile_guncelle(tg, 99, "mg", "kedi", "başlık kısalsın"))
    ajan, istem = ajanlar[-1]
    assert ajan == "cmo-store-director" and "başlık kısalsın" in istem and "fire_yuzde=15" in istem
