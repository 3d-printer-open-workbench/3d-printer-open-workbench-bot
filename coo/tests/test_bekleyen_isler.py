import json
from pathlib import Path

import yaml

from coo import bekleyen_isler as bi
from coo import reels_denetim as rd

UZUN = "a" * 36  # fikir_hatti.SKU_MAKS: callback_data 64 bayt sınırı


def _urun(kok: Path, sku: str, **alanlar) -> Path:
    d = kok / sku
    d.mkdir(parents=True, exist_ok=True)
    (d / "urun.yaml").write_text(yaml.safe_dump({"sku": sku, "ad": sku.upper(), **alanlar}, allow_unicode=True),
                                 encoding="utf-8")
    return d


def _tum_callbackler(butonlar):
    return [b["callback_data"] for satir in butonlar for b in satir]


def test_bos_klasorde_bekleyen_yok(tmp_path: Path) -> None:
    isler = bi.tara(tmp_path / "urunler", tmp_path / "reels", tmp_path / "rapor")
    assert isler == []
    metin, butonlar = bi.liste_mesaji(isler)
    assert "bekleyen iş yok" in metin and _tum_callbackler(butonlar) == ["bk:liste", "menu:ana"]


def test_studyo_ve_icerik_onayi_bekliyor(tmp_path: Path) -> None:
    _urun(tmp_path, "kedi", studyo_onayi="BEKLIYOR", icerik_onayi="BEKLIYOR")
    _urun(tmp_path, "onayli", studyo_onayi="ONAYLANDI", icerik_onayi="REDDEDILDI")
    isler = bi.tara(tmp_path, tmp_path / "r", tmp_path / "rp")
    assert [i["id"] for i in isler] == ["es:kedi", "ic:kedi"]
    m, b = bi.is_detayi(isler[0])
    cb = _tum_callbackler(b)
    assert cb[:2] == ["studyo:onay:kedi", "studyo:revize:kedi"]  # mevcut onay / not callback'leri
    assert "icerik:yenile:kedi" in cb and "urunmenu:kedi" in cb and "bk:liste" in cb
    assert any(x["text"] == "🔁 Yeniden Üret" for satir in b for x in satir)


def test_iptal_urun_listelenmez(tmp_path: Path) -> None:
    _urun(tmp_path, "eski", durum="IPTAL", studyo_onayi="BEKLIYOR")
    assert bi.tara(tmp_path, tmp_path / "r", tmp_path / "rp") == []


def test_konsept_secimi_ve_cok_renk(tmp_path: Path) -> None:
    d = _urun(tmp_path, "fil", durum="KONSEPT_SECIMI")
    (d / "konsept").mkdir()
    (d / "konsept" / "flow-1.jpg").write_bytes(b"x")
    ck = d / "model" / "cok_renk"
    ck.mkdir(parents=True)
    (ck / "sema_son.json").write_text(json.dumps({"ad": "Kemik", "renkler": [{"ad": "Kemik"}]}), encoding="utf-8")
    (ck / "renkli.3mf").write_bytes(b"x")
    ids = [i["id"] for i in bi.tara(tmp_path, tmp_path / "r", tmp_path / "rp")]
    assert ids == ["kf:fil", "cr:fil"]
    # aynı şema onaylanınca çok renk bekleyenden düşer
    v = yaml.safe_load((d / "urun.yaml").read_text())
    v["cok_renk"] = {"karar": "onay", "sema": "Kemik"}
    (d / "urun.yaml").write_text(yaml.safe_dump(v, allow_unicode=True))
    assert [i["id"] for i in bi.tara(tmp_path, tmp_path / "r", tmp_path / "rp")] == ["kf:fil"]


def _paket(d: Path, secim: str | None) -> None:
    (d / "magaza").mkdir(parents=True, exist_ok=True)
    (d / "gorsel").mkdir(exist_ok=True)
    (d / "gorsel" / "k.png").write_bytes(b"x")
    paket = {"baslik": "B", "aciklama_html": "<p>a</p>", "satis_fiyati_tl": 449.9, "gorseller": ["gorsel/k.png"],
             "slug": "b", "meta_baslik": "m", "meta_aciklama": "m", "etiketler": ["a"], "kategori": "k",
             "maliyet": {"birim_maliyet_tl": 100, "fire_yuzde": 15}}
    from coo.magaza_hatti import ZORUNLU_ALANLAR
    for a in ZORUNLU_ALANLAR:
        paket.setdefault(a, "x")
    if secim:
        paket["fiyat_karari"] = {"secim": secim}
    (d / "magaza" / "paket.json").write_text(json.dumps(paket), encoding="utf-8")


def test_fiyat_secimi_sonra_yukleme(tmp_path: Path) -> None:
    d = _urun(tmp_path, "vazo", icerik_onayi="ONAYLANDI")
    _paket(d, None)
    isler = bi.tara(tmp_path, tmp_path / "r", tmp_path / "rp")
    assert [i["id"] for i in isler] == ["fy:vazo"]
    assert isler[0]["onay"][1] == "magaza:fiyat:vazo:44990" and isler[0]["not"] == "ng:mg:vazo"
    _paket(d, "PATRON")
    isler = bi.tara(tmp_path, tmp_path / "r", tmp_path / "rp")
    assert [i["id"] for i in isler] == ["yk:vazo"] and isler[0]["onay"][1] == "magaza:yukle:vazo"
    (d / "magaza" / "yukleme.json").write_text('{"durum": "YUKLENDI", "panel_linki": "x"}', encoding="utf-8")
    assert bi.tara(tmp_path, tmp_path / "r", tmp_path / "rp") == []


def test_onayli_paketsiz_urun_hazirlaya_yonlendirir(tmp_path: Path) -> None:
    _urun(tmp_path, "lamba", icerik_onayi="ONAYLANDI")
    (i,) = bi.tara(tmp_path, tmp_path / "r", tmp_path / "rp")
    assert i["id"] == "yk:lamba" and i["onay"][1] == "magaza:hazirla:lamba" and i["not"] is None


def test_pin_reels_ve_dilimleme(tmp_path: Path) -> None:
    d = _urun(tmp_path, "kus")
    (d / "medya" / "pinterest").mkdir(parents=True)
    (d / "medya" / "pinterest" / "pin.json").write_text(json.dumps({"durum": "HAZIR", "baslik": "Kuş"}), encoding="utf-8")
    reels = tmp_path / "reels"
    kid = rd.yeni_kayit(tmp_path / "v.mp4", {"tur": "hf", "sku": "kus"}, reels)
    k = rd.oku(kid, reels)
    k.update(durum="HAZIR", maddeler=[{"no": 1, "sorun": "x", "duzeltme": "y"}])
    rd.yaz(k, reels)
    rapor = tmp_path / "rapor"
    rapor.mkdir()
    (rapor / "20261118-101010.json").write_text(json.dumps(
        {"kategori": "figur", "sku": "kus", "oneriler": [{"ayar": "a", "onerilen": "1"}]}), encoding="utf-8")
    isler = bi.tara(tmp_path, reels, rapor)
    assert [i["id"] for i in isler] == ["pn:kus", f"rd:{kid}", "dl:20261118-101010"]
    assert isler[0]["onay"][1] == "pin:paylas:kus" and isler[0]["not"] == "ng:pn:kus"
    assert isler[1]["onay"][1] == f"rd:kapat:{kid}" and isler[1]["not"] == f"rd:not:{kid}"
    assert isler[2]["onay"][1] == "rapor:uygula:20261118-101010"
    # "👍 Olduğu Gibi Kalsın" → kayıt kapanır, bekleyenden düşer
    rd.kapat(kid, reels)
    assert [i["id"] for i in bi.tara(tmp_path, reels, rapor)] == ["pn:kus", "dl:20261118-101010"]


def test_callback_verileri_64_bayt_sinirinda(tmp_path: Path) -> None:
    d = _urun(tmp_path, UZUN, studyo_onayi="BEKLIYOR", icerik_onayi="BEKLIYOR", durum="KONSEPT_SECIMI")
    (d / "konsept").mkdir()
    (d / "konsept" / "flow-1.jpg").write_bytes(b"x")
    (d / "medya" / "pinterest").mkdir(parents=True)
    (d / "medya" / "pinterest" / "pin.json").write_text('{"durum": "HAZIR"}', encoding="utf-8")
    _paket(d, None)
    isler = bi.tara(tmp_path, tmp_path / "r", tmp_path / "rp")
    assert len(isler) >= 5
    _, liste = bi.liste_mesaji(isler)
    tum = _tum_callbackler(liste)
    for i in isler:
        tum += _tum_callbackler(bi.is_detayi(i)[1])
    for tur in bi.NOT_TURLERI:
        tum.append(bi.not_dugmesi(tur, f"{UZUN}.12")["callback_data"])
    assert all(0 < len(c.encode()) <= 64 for c in tum), [c for c in tum if len(c.encode()) > 64]


def test_not_basligi_gidis_donus() -> None:
    baslik = bi.not_basligi("ks", f"{UZUN}.3")
    assert baslik.startswith(bi.GUNCELLEME_NOTU_BASLIGI)
    assert bi.not_basligi_coz(baslik) == ("ks", f"{UZUN}.3")
    assert bi.anahtar_coz(f"{UZUN}.3") == (UZUN, 3)
    assert bi.anahtar_coz("kedi") == ("kedi", None)
    assert bi.not_basligi_coz("başka mesaj [ks|kedi]") is None
    assert bi.not_basligi_coz(f"{bi.GUNCELLEME_NOTU_BASLIGI} [zz|kedi]") is None  # bilinmeyen tür


def test_revize_notu_tarihle_kaydedilir(tmp_path: Path) -> None:
    import datetime as dt

    _urun(tmp_path, "kedi", revize_notu="eski alan korunur")
    bi.revize_notu_ekle("kedi", "pn", " başlık daha kısa ", tmp_path, dt.datetime(2026, 11, 18, 10, 0, 0))
    notlar = bi.revize_notu_ekle("kedi", "cr", "şapka siyah", tmp_path)
    v = yaml.safe_load((tmp_path / "kedi" / "urun.yaml").read_text(encoding="utf-8"))
    assert v["revize_notu"] == "eski alan korunur"
    assert v["revize_notlari"][0] == {"tarih": "2026-11-18T10:00:00", "tur": "pn", "is": "Pinterest pini",
                                      "not": "başlık daha kısa"}
    assert len(notlar) == 2 and notlar[1]["tur"] == "cr"


def test_istemler_notu_tasir(tmp_path: Path) -> None:
    from coo import hf_reels, pinterest_hatti
    from coo.konsept_hatti import konsept_istemi
    from coo.magaza_hatti import hazirla_istemi
    from coo.renk_hatti import renk_revize_istemi

    d = _urun(tmp_path, "kedi", renkler=[{"ad": "Kırmızı", "hex": "#C0392B", "slug": "kirmizi",
                                          "klasor": "gorsel/renkler/kirmizi"}])
    (d / "gorsel").mkdir()
    (d / "gorsel" / "studyo.png").write_bytes(b"x")
    konsept = {"ad": "teknik-poster", "baslik": "Teknik Poster", "oranlar": ["3:4"], "video": False, "yol": "k.md"}
    assert "NOT_X" in konsept_istemi("kedi", konsept, tmp_path, not_="NOT_X")
    assert "PATRON NOTU" not in konsept_istemi("kedi", konsept, tmp_path)
    assert "NOT_Y" in hazirla_istemi("kedi", 10, tmp_path, not_="NOT_Y")
    assert "PATRON NOTU" not in hazirla_istemi("kedi", 10, tmp_path)
    assert "NOT_Z" in pinterest_hatti.hazirla_istemi("kedi", tmp_path, not_="NOT_Z")
    assert "NOT_H" in hf_reels.urun_istemi("kedi", "NOT_H", tmp_path)[0]
    istem = renk_revize_istemi("kedi", "NOT_R", tmp_path)
    assert "NOT_R" in istem and "Kırmızı" in istem and "RENK_HAZIR" in istem
