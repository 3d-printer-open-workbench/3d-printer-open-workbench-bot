"""🔄 Model değişti → bağımlı çıktıları güncelle: saf modül (coo/model_degisim.py) + sahte Telegram ile zincir.

Hiçbir ajan başlatılmaz (_ajan_arka_planda_calistir yakalanır), ERP/İkas/Pinterest'e istek gitmez.
"""
from __future__ import annotations

import asyncio
import json
import os
import struct
import sys
import time
from pathlib import Path

import pytest
import yaml

from coo import model_degisim as md


# ------------------------------------------------------------------------------------------------ yardımcılar
def kutu_stl(yol: Path, x: float, y: float, z: float) -> Path:
    """İkili STL: [0,x]×[0,y]×[0,z] kutusunun iki köşegen üçgeni (sınır kutusu için yeterli)."""
    ucgenler = [((0, 0, 0), (x, 0, 0), (x, y, z)), ((0, 0, 0), (0, y, 0), (x, y, z))]
    govde = b"".join(struct.pack("<12fH", 0, 0, 0, *a, *b, *c, 0) for a, b, c in ucgenler)
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_bytes(b"\0" * 80 + struct.pack("<I", len(ucgenler)) + govde)
    return yol


def eskit(*yollar: Path, saniye: float = 3600) -> None:
    t = time.time() - saniye
    for p in yollar:
        os.utime(p, (t, t))


ACIKLAMA = ("<p>Telefon standı.</p><table><tr><th>Ölçü</th><td>10,2 × 10,4 × 9,8 cm</td></tr>"
            "<tr><th>Malzeme</th><td>Mat PLA</td></tr><tr><th>Ağırlık</th><td>Yaklaşık 180 g</td></tr></table>")


def urun_kur(urunler: Path, sku: str = "tel", yayinda: bool = True, pin: bool = True) -> Path:
    """Yayında, çok renkli, tüm çıktıları ESKİ STL'den üretilmiş bir ürün; STL sonradan değişti."""
    k = urunler / sku
    for alt in ("model/cok_renk/render/studyo-ic", "uretim", "gorsel/konsept", "magaza/gorseller", "medya/pinterest"):
        (k / alt).mkdir(parents=True, exist_ok=True)
    ciktilar = [k / "model" / "cok_renk" / "renkli.3mf", k / "uretim" / f"{sku}.3mf",
                k / "model" / "cok_renk" / "render" / "seffaf.png",
                *[k / "model" / "cok_renk" / "render" / "studyo-ic" / ad for ad in md.STUDYO_DOSYALARI],
                k / "gorsel" / "konsept" / "teknik-poster-3x4.png", k / "magaza" / "gorseller" / "tel-01.jpg",
                k / "magaza" / "ikas-ekran.png"]
    for p in ciktilar:
        p.write_bytes(b"x")
    (k / "uretim" / f"{sku}.gcode").write_text("G1\n; filament used [g] = 100.00, 80.00\n"
                                               "; total filament used [g] = 180.00\n", encoding="utf-8")
    ciktilar.append(k / "uretim" / f"{sku}.gcode")
    (k / "magaza" / "gorseller.json").write_text(json.dumps({"gorseller": [
        {"dosya": "magaza/gorseller/tel-01.jpg", "kaynak": "model/cok_renk/render/studyo-ic/kapak-beyaz.png"}]}),
        encoding="utf-8")
    (k / "magaza" / "paket.json").write_text(json.dumps({
        "sku": sku, "baslik": "Telefon Standı", "aciklama_html": ACIKLAMA, "satis_fiyati_tl": 399.9,
        "gorseller": ["model/cok_renk/render/studyo-ic/kapak-beyaz.png"], "slug": "tel", "meta_baslik": "m",
        "meta_aciklama": "m", "etiketler": ["a"],
        "varyantlar": [{"secenek": "Renk", "deger": "Çok renk: Kızıl", "gorseller": []}], "maliyet": {"birim_maliyet_tl": 200, "basa_bas_tl": 220, "gram": 180}},
        ensure_ascii=False), encoding="utf-8")
    ciktilar += [k / "magaza" / "gorseller.json", k / "magaza" / "paket.json"]
    if yayinda:
        (k / "magaza" / "yukleme.json").write_text(json.dumps({
            "durum": "YUKLENDI", "urun_linki": "https://magaza.example.com/tel",
            "panel_linki": "https://panel.example.com/admin/product/edit/abc", "tarih": "2026-11-18"}), encoding="utf-8")
    v = {"sku": sku, "ad": "Telefon Standı", "durum": "SATISTA", "stl_yolu": f"model/{sku}.stl",
         "boyut_mm": {"x": 102.0, "y": 104.0, "z": 98.0},
         "cok_renk": {"karar": "onay", "sema": "Kızıl", "girdi_3mf": "model/cok_renk/renkli.3mf",
                      "renkler": [{"ad": "Kemik", "hex": "#E1D6C1", "parcalar": "taban"},
                                  {"ad": "Kırmızı", "hex": "#C0392B", "parcalar": "gövde"}]},
         "dilimleme": {"kategori": "figur", "gercek_gram": 180.0, "gercek_sure_dk": 500, "filament_gram": [100.0, 80.0]},
         "erp": {"product_id": 7, "bom_filamentler": [{"filament_id": 9, "net_gr": 100.0}, {"filament_id": 8, "net_gr": 80.0}]},
         "studyo_onayi": "ONAYLANDI", "icerik_onayi": "ONAYLANDI"}
    if pin:
        (k / "medya" / "pinterest" / "pin.json").write_text(json.dumps({"durum": "PAYLASILDI", "pin_url": "https://pin/1",
                                                                         "tarih": "2026-11-17"}), encoding="utf-8")
        ciktilar.append(k / "medya" / "pinterest" / "pin.json")
        v["pinterest"] = {"pin_url": "https://pin/1", "tarih": "2026-11-17", "pano": "Masa"}
    (k / "urun.yaml").write_text(yaml.safe_dump(v, allow_unicode=True, sort_keys=False), encoding="utf-8")
    eskit(*ciktilar)
    kutu_stl(k / "model" / f"{sku}.stl", 102.0, 160.0, 98.0)  # revize STL (derinlik 104 → 160 mm)
    return k


def yaml_oku(k: Path) -> dict:
    return yaml.safe_load((k / "urun.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def urunler(tmp_path: Path, monkeypatch) -> Path:
    import coo.__main__  # noqa: F401 — tüm coo modülleri yüklensin

    kok = tmp_path / "veri" / "02_Urunler"
    kok.mkdir(parents=True)
    for ad, mod in list(sys.modules.items()):
        if ad.startswith("coo") and hasattr(mod, "URUNLER_KLASORU"):
            monkeypatch.setattr(mod, "URUNLER_KLASORU", kok)
    from coo import bekleyen_isler as bi

    monkeypatch.setattr(bi, "MAGAZA_KLASORU", tmp_path / "magaza")
    monkeypatch.setattr(bi, "BASKI_KAYITLARI_KLASORU", tmp_path / "baski")
    return kok


# ------------------------------------------------------------------------------------------------ saf modül
def test_stl_olcu_ikili_ve_ascii(tmp_path: Path) -> None:
    assert md.stl_olcu(kutu_stl(tmp_path / "a.stl", 10, 20, 30.5)) == {"x": 10.0, "y": 20.0, "z": 30.5}
    a = tmp_path / "b.stl"
    a.write_text("solid t\nfacet normal 0 0 1\nouter loop\nvertex -5 0 0\nvertex 5 2 0\nvertex 0 0 7\n"
                 "endloop\nendfacet\nendsolid t\n", encoding="utf-8")
    assert md.stl_olcu(a) == {"x": 10.0, "y": 2.0, "z": 7.0}


def test_tarihten_eskiyen_ciktilar_ve_plan(urunler: Path) -> None:
    urun_kur(urunler)
    eski = md.eskiyen_ciktilar("tel")
    assert [a["adim"] for a in eski] == ["renk", "dilimleme", "erp", "studyo", "poster", "magaza_gorselleri", "ikas",
                                         "pinterest"]
    yayinda = {a["adim"] for a in eski if a["yayinda"]}
    assert {"ikas", "pinterest", "studyo", "poster", "magaza_gorselleri"} <= yayinda and "dilimleme" not in yayinda
    assert next(a for a in eski if a["adim"] == "renk")["kanit"] == "tarih"
    assert next(a for a in eski if a["adim"] == "erp")["neden"].startswith("dilimleme eski")
    assert md.zincir_plani("tel") == ["renk", "dilimleme", "erp", "studyo", "poster", "magaza_gorselleri"]
    assert md.yayin_plani("tel") == ["ikas", "pinterest"]


def test_sha_kaydi_tarihi_ezer_ve_stl_degisince_eskir(urunler: Path) -> None:
    k = urun_kur(urunler, pin=False)
    for adim in md.ADIMLAR:
        md.cikti_kaydet("tel", adim)
    assert md.eskiyen_ciktilar("tel") == []  # sha kaydı: dosya tarihi eski olsa da güncel
    kutu_stl(k / "model" / "tel.stl", 102.0, 170.0, 98.0)
    eski = md.eskiyen_ciktilar("tel")
    assert eski and all(a["kanit"] == "sha" for a in eski)
    assert md.zincir_plani("tel")[0] == "renk"


def test_dilimleme_yaml_gcode_uyusmazligi_ve_erp_turetme(urunler: Path) -> None:
    k = urun_kur(urunler, yayinda=False, pin=False)
    simdi = time.time() + 5
    for p in (k / "model" / "cok_renk" / "renkli.3mf", k / "uretim" / "tel.3mf", k / "uretim" / "tel.gcode"):
        os.utime(p, (simdi, simdi))
    (k / "uretim" / "tel.gcode").write_text("; filament used [g] = 110.00, 85.00\n; total filament used [g] = 195.00\n",
                                            encoding="utf-8")
    os.utime(k / "uretim" / "tel.gcode", (simdi, simdi))
    assert md.gcode_gramlari(k / "uretim" / "tel.gcode") == (195.0, [110.0, 85.0])
    rapor = {a["adim"]: a for a in md.durum_raporu("tel")["adimlar"]}
    assert rapor["renk"]["guncel"] is True
    assert rapor["dilimleme"]["guncel"] is False and "G-code" in rapor["dilimleme"]["neden"]
    assert rapor["erp"]["guncel"] is False
    assert md.zincir_plani("tel")[:2] == ["dilimleme", "erp"]


def test_bildirim_bir_kez_ve_model_surumu(urunler: Path) -> None:
    k = urun_kur(urunler)
    assert md.bildirim_kaydi("tel", "kullanim_testi tur 2") is True
    v = yaml_oku(k)
    assert v["model_surumu"]["kaynak"] == "kullanim_testi tur 2" and v["model_surumu"]["olcu"]["y"] == 160.0
    assert v["model_degisimi"]["durum"] == "BEKLIYOR"
    assert v["model_degisimi"]["onceki"]["olcu"] == {"x": 102.0, "y": 104.0, "z": 98.0}  # mağaza metninden
    assert v["model_degisimi"]["onceki"]["gram"] == 180.0
    assert md.bildirim_kaydi("tel", "kullanim_testi tur 2 (Patron onayı)") is False  # aynı STL ikinci kez değil
    assert md.bekliyor_mu("tel")


def test_bildirim_yok_eskiyen_yoksa(urunler: Path) -> None:
    k = urunler / "yeni"
    kutu_stl(k / "model" / "yeni.stl", 10, 10, 10)
    (k / "urun.yaml").write_text(yaml.safe_dump({"sku": "yeni"}), encoding="utf-8")
    assert md.bildirim_kaydi("yeni", "kullanim_testi tur 0") is False
    assert yaml_oku(k)["model_surumu"]["stl_sha256"]  # sürüm yine kaydedilir
    assert "model_degisimi" not in yaml_oku(k)


def test_metin_farklari_olcu_ve_agirlik(urunler: Path) -> None:
    k = urun_kur(urunler)
    f = md.metin_farklari("tel")
    assert [x["alan"] for x in f] == ["Ölçü"] and f[0]["oneri"] == "10,2 × 16 × 9,8 cm"
    v = yaml_oku(k)
    v["dilimleme"]["gercek_gram"] = 240.0
    (k / "urun.yaml").write_text(yaml.safe_dump(v, allow_unicode=True), encoding="utf-8")
    f = md.metin_farklari("tel")
    assert f[1] == {"alan": "Ağırlık", "metinde": "180 g", "yeni": "240 g", "oneri": "Yaklaşık 240 g"}
    assert md.metin_olcusu("<tr><th>Ölçü</th><td>130 × 104 × 241 mm</td></tr>") == {"x": 130.0, "y": 104.0, "z": 241.0}


def test_boyut_guncelle(urunler: Path) -> None:
    k = urun_kur(urunler)
    eski, yeni = md.boyut_guncelle("tel")
    assert eski == {"x": 102.0, "y": 104.0, "z": 98.0} and yeni == {"x": 102.0, "y": 160.0, "z": 98.0}
    assert yaml_oku(k)["boyut_mm"]["y"] == 160.0


class SahteErp:
    def __init__(self, var: bool = True, hata: bool = False) -> None:
        self.var, self.hata, self.cagrilar, self.onaylandi = var, hata, [], False

    def __call__(self, yontem, yol, govde=None, *a, **k):
        self.cagrilar.append((yontem, yol, govde))
        if yontem == "POST":
            if self.hata:
                raise RuntimeError("HTTP 409: yazıcı değil")
            self.onaylandi = True
            return {"status": "success", "gram": 195.0, "saat": 9, "dakika": 10, "gcode_sha256": "ab", "uyari": None}
        g = [110.0, 85.0] if self.onaylandi else [100.0, 80.0]
        urun = {"product_id": 7, "sku": "tel", "total_filament_net_gr": sum(g),
                "print_time": {"hours": 9 if self.onaylandi else 8, "minutes": 10},
                "production_cost_tl": 230.0 if self.onaylandi else 200.0,
                "b2c_pricing": {"break_even_gross_tl": 450.0 if self.onaylandi else 220.0, "recommended_gross_tl": 600.0},
                "filaments": [{"net_weight_gr": x} for x in g], "dimensions_mm": {"x": 102, "y": 104, "z": 98}}
        return [urun] if self.var else []


def test_erp_gcode_guncelle_mevcut_uc(urunler: Path) -> None:
    k = urun_kur(urunler)
    erp = SahteErp()
    s = md.erp_gcode_guncelle("tel", istek=erp)
    assert s["durum"] == "GUNCELLENDI" and s["once"]["gram"] == 180.0 and s["sonra"]["gram"] == 195.0
    post = [c for c in erp.cagrilar if c[0] == "POST"]
    assert post == [("POST", "/api/products/7/gcode-onayla", {"gcode_yolu": str((k / "uretim" / "tel.gcode").resolve())})]
    e = yaml_oku(k)["erp"]
    assert [b["net_gr"] for b in e["bom_filamentler"]] == [110.0, 85.0] and e["birim_uretim_maliyeti_tl"] == 230.0
    assert md.erp_gcode_guncelle("tel", istek=SahteErp(var=False))["durum"] == "YOK"
    assert md.erp_gcode_guncelle("tel", istek=SahteErp(hata=True))["durum"] == "HATA"
    # paket maliyeti yeni gram/maliyetle; fiyat başa başın altında → uyarı, fiyat değişmez
    uyari = md.paket_maliyet_guncelle("tel", s)
    paket = json.loads((k / "magaza" / "paket.json").read_text(encoding="utf-8"))
    assert paket["satis_fiyati_tl"] == 399.9 and paket["maliyet"]["birim_maliyet_tl"] == 230.0
    assert uyari and "başa baş" in uyari[0]


def test_pinterest_kaydi_eski_pini_silmez() -> None:
    k = md.pinterest_kaydi({"pin_url": "https://pin/1", "tarih": "2026-11-17", "pano": "Masa"},
                           {"pin_url": "https://pin/2", "tarih": "2026-11-18", "pano": "Masa"})
    assert k["pin_url"] == "https://pin/2" and k["onceki_pinler"] == [
        {"pin_url": "https://pin/1", "tarih": "2026-11-17", "pano": "Masa"}]


def test_istemler(urunler: Path) -> None:
    urun_kur(urunler)
    i = md.ikas_guncelle_istemi("tel")
    assert "YENİ ÜRÜN AÇMA" in i and "admin/product/edit/abc" in i and "guncelleme.json" in i
    assert "DOKUNMA" in i and "aciklama_html` editör" not in i
    assert "editör review'undan geçti" in md.ikas_guncelle_istemi("tel", metin_degisti=True)
    m = md.metin_guncelle_istemi("tel")
    assert "10,2 × 16 × 9,8 cm" in m and "--review` VERME" in m


def test_bekleyen_islerde_md(urunler: Path) -> None:
    from coo import bekleyen_isler as bi

    urun_kur(urunler)
    assert not [i for i in bi.urun_isleri("tel") if i["tur"] == "md"]  # bildirilmeden listelenmez
    md.bildirim_kaydi("tel", "kullanim_testi tur 1")
    is_ = next(i for i in bi.urun_isleri("tel") if i["tur"] == "md")
    assert is_["onay"] == ("▶️ Zinciri Güncelle", "md:zincir:tel") and is_["not"] == "ng:md:tel"
    md.degisim_yaz("tel", durum="DURDU", adim="dilimleme", hata="Orca")
    is_ = next(i for i in bi.urun_isleri("tel") if i["tur"] == "md")
    assert is_["onay"][1] == "md:devam:tel" and "Orca" in is_["ozet"]
    assert bi.not_basligi_coz(bi.not_basligi("md", "tel")) == ("md", "tel")


# ------------------------------------------------------------------------------------------------ bot (sahte Telegram)
class SahteTg:
    def __init__(self) -> None:
        self.mesajlar: list[tuple[str, list]] = []

    async def mesaj_gonder(self, chat_id, metin, butonlar=None, **_):
        self.mesajlar.append((metin, butonlar or []))
        return {"ok": True}

    async def foto_gonder(self, chat_id, foto, aciklama="", butonlar=None, dosya_adi=""):
        self.mesajlar.append((aciklama, butonlar or []))
        return {"ok": True}

    async def callback_yanitla(self, cb_id, metin=""):
        return None

    def _json_istek(self, yontem, veri):
        return {"ok": True}

    def veriler(self) -> list[str]:
        return [b["callback_data"] for _, bt in self.mesajlar for satir in bt for b in satir]

    def metin(self) -> str:
        return "\n".join(m for m, _ in self.mesajlar)


@pytest.fixture
def bot(urunler: Path, monkeypatch):
    import coo.__main__ as cm

    ajanlar: list[dict] = []
    monkeypatch.setattr(cm, "_ajan_arka_planda_calistir",
                        lambda tg, chat_id, ajan, istem, *a, **k: ajanlar.append({"ajan": ajan, "istem": istem, **k}))
    monkeypatch.setattr(cm, "palet_oku", lambda: [])
    k = urun_kur(urunler)
    return cm, k, ajanlar


def _cb(cm, tg, veri: str) -> None:
    asyncio.run(cm.callback_isle(tg, {"id": "1", "data": veri, "message": {"chat": {"id": 99}, "message_id": 5}}, 99))


def _kt_onayli_rapor(k: Path) -> None:
    v = yaml_oku(k)
    v["kullanim_testi"] = {"son": {"tarih": "2026-11-18 14:00", "durum": "GEÇTİ"}, "onay": "BEKLIYOR", "tasarim_turu": 3}
    (k / "urun.yaml").write_text(yaml.safe_dump(v, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_kt_onay_model_degisti_mesaji(bot) -> None:
    cm, k, _ = bot
    _kt_onayli_rapor(k)
    tg = SahteTg()
    _cb(cm, tg, "kt:onay:tel")
    assert "🔄 *Model değişti*" in tg.metin() and "⚠️ 🛒 İkas yayını" in tg.metin()
    assert {"md:zincir:tel", "ng:md:tel", "md:ertele:tel", "urunmenu:tel"} <= set(tg.veriler())
    assert yaml_oku(k)["model_surumu"]["kaynak"] == "kullanim_testi tur 3 (Patron onayı)"
    tg2 = SahteTg()
    _cb(cm, tg2, "kt:onay:tel")  # aynı STL → ikinci kez bildirim yok
    assert "Model değişti" not in tg2.metin()
    _cb(cm, tg2, "md:ertele:tel")
    assert yaml_oku(k)["model_degisimi"]["durum"] == "ERTELENDI"


def test_zincir_uctan_uca(bot, monkeypatch) -> None:
    cm, k, ajanlar = bot
    md.bildirim_kaydi("tel", "kullanim_testi tur 1")
    cagri: list[str] = []

    async def sahte_dilim(tg, chat_id, sku, kategori=None, zincir=False):
        cagri.append(f"dilim:{kategori}:{zincir}")
        (k / "uretim" / "tel.gcode").write_text("; filament used [g] = 110.00, 85.00\n"
                                                "; total filament used [g] = 195.00\n", encoding="utf-8")
        (k / "uretim" / "tel.3mf").write_bytes(b"y")
        v = yaml_oku(k)
        v["dilimleme"].update(gercek_gram=195.0, gercek_sure_dk=550, filament_gram=[110.0, 85.0])
        (k / "urun.yaml").write_text(yaml.safe_dump(v, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return True

    async def sahte_studyo(tg, chat_id, sku, tohum_degistir=False):
        cagri.append("studyo")
        for ad in md.STUDYO_DOSYALARI:
            (k / "model" / "cok_renk" / "render" / "studyo-ic" / ad).write_bytes(b"z")
        return True

    async def sahte_konsept(tg, chat_id, sku, konsept, not_="", zincir_sonrasi=None):
        cagri.append(f"poster:{konsept['video']}")
        assert "MODEL DEĞİŞTİ" in not_
        (k / "gorsel" / "konsept" / f"{konsept['ad']}-3x4.png").write_bytes(b"p")
        await zincir_sonrasi(True)

    def sahte_gorsel(sku):
        cagri.append("magaza_gorsel")
        (k / "magaza" / "gorseller.json").write_text(json.dumps({"gorseller": [
            {"dosya": "magaza/gorseller/tel-01.jpg"}]}), encoding="utf-8")
        return {"gorseller": [{"dosya": "magaza/gorseller/tel-01.jpg"}], "varyantlar": []}

    monkeypatch.setattr(cm, "_dilimleme_ozeti_gonder", sahte_dilim)
    monkeypatch.setattr(cm, "_studyo_uret", sahte_studyo)
    monkeypatch.setattr(cm, "_konsept_uret", sahte_konsept)
    monkeypatch.setattr(cm, "magaza_gorsel_hazirla", sahte_gorsel)
    asil_erp = md.erp_gcode_guncelle  # cm.model_degisim ile md aynı modül
    monkeypatch.setattr(cm.model_degisim, "erp_gcode_guncelle", lambda sku: asil_erp(sku, istek=SahteErp()))
    monkeypatch.setattr(cm.metin_denetim, "yukleme_engelleri", lambda paket: [])

    tg = SahteTg()
    _cb(cm, tg, "md:zincir:tel")
    assert yaml_oku(k)["boyut_mm"]["y"] == 160.0
    # 1) renk: onaylı şema korunarak cad-artist boyar (onay sorulmaz)
    assert ajanlar[-1]["ajan"] == "cad-artist" and "AYNEN" in ajanlar[-1]["istem"] and "#C0392B" in ajanlar[-1]["istem"]
    ck = k / "model" / "cok_renk"
    (ck / "rapor.json").write_text("{}", encoding="utf-8")
    (ck / "sema_son.json").write_text(json.dumps({"ad": "Kızıl", "renkler": [{"hex": "#e1d6c1"}, {"hex": "#C0392B"}]}),
                                      encoding="utf-8")
    (ck / "renkli.3mf").write_bytes(b"yeni")
    asyncio.run(ajanlar[-1]["sonraki_islem"](True, "BITTI", None))
    # 2-4) dilimleme (aynı kategori) → ERP (mevcut uç) → stüdyo; stüdyo Patron onayında durur
    assert cagri == ["dilim:figur:True", "studyo"]
    v = yaml_oku(k)
    assert v["model_degisimi"]["durum"] == "STUDYO_ONAYI" and v["erp"]["bom_filamentler"][0]["net_gr"] == 110.0
    assert "ERP reçetesi yeni G-code'dan güncellendi" in tg.metin()
    # 5-6) studyo:onay → poster (video yok) → mağaza görselleri → İkas önizlemesi (metin farkı → önce metin)
    _cb(cm, tg, "studyo:onay:tel")
    assert cagri[-2:] == ["poster:False", "magaza_gorsel"]
    v = yaml_oku(k)
    assert v["model_degisimi"]["durum"] == "YAYIN_ONAYI"
    assert v["model_degisimi"]["tamamlanan"] == ["renk", "dilimleme", "erp", "studyo", "poster", "magaza_gorselleri"]
    assert md.zincir_plani("tel") == [] and md.yayin_plani("tel") == ["ikas", "pinterest"]
    assert "Mağaza metni değişmeli" in tg.metin() and "md:metin:tel" in tg.veriler() and "md:pin:tel" in tg.veriler()
    assert "md:ikasok:tel" not in tg.veriler()
    # metin farkı varken İkas güncellemesi engellenir (review kuralı)
    n = len(ajanlar)
    _cb(cm, tg, "md:ikasok:tel")
    assert len(ajanlar) == n and "İkas güncellenmedi" in tg.metin()
    # ✍️ metin → yazar → editör review → yeniden önizleme
    _cb(cm, tg, "md:metin:tel")
    assert ajanlar[-1]["ajan"] == "cmo-store-director" and "10,2 × 16 × 9,8 cm" in ajanlar[-1]["istem"]
    paket = json.loads((k / "magaza" / "paket.json").read_text(encoding="utf-8"))
    paket["aciklama_html"] = ACIKLAMA.replace("10,2 × 10,4 × 9,8", "10,2 × 16 × 9,8").replace("180 g", "200 g")
    paket["metin_review"] = {"sonuc": "DUZELTILDI", "ozet": cm.metin_denetim.ozet(paket["aciklama_html"])}
    (k / "magaza" / "paket.json").write_text(json.dumps(paket, ensure_ascii=False), encoding="utf-8")
    asyncio.run(ajanlar[-1]["sonraki_islem"](True, "METIN_GUNCEL", None))
    assert ajanlar[-1]["ajan"] == "brand-guardian"
    tg3 = SahteTg()
    asyncio.run(ajanlar[-1]["sonraki_islem"](True, "METIN_REVIEW_TAMAM 90", None))  # review sonrası (eski tg)
    assert yaml_oku(k)["model_degisimi"]["metin_guncellendi"] is True
    # ✅ İkas'ı Güncelle → cmo-store-director mevcut ürünü düzenler (yeni ürün yok)
    monkeypatch.setattr(cm, "yukleme_dogrula", lambda sku: {"tamam": True})
    _cb(cm, tg3, "md:ikasok:tel")
    ikas = ajanlar[-1]
    assert ikas["ajan"] == "cmo-store-director" and "YENİ ÜRÜN AÇMA" in ikas["istem"]
    assert "editör review'undan geçti" in ikas["istem"]
    (k / "magaza" / "guncelleme.json").write_text(json.dumps({"durum": "GUNCELLENDI", "tarih": "2026-11-18T15:00:00",
                                                              "gorsel_sayisi": 5, "metin_guncellendi": True}),
                                                  encoding="utf-8")
    asyncio.run(ikas["sonraki_islem"](True, "IKAS_GUNCELLENDI", None))
    v = yaml_oku(k)
    assert v["ikas"]["son_guncelleme"]["gorsel_sayisi"] == 5 and md.yayin_plani("tel") == ["pinterest"]
    # 📌 yeni pin → mevcut paylaş akışı; eski pin onceki_pinler'e
    _cb(cm, tg3, "md:pin:tel")
    assert ajanlar[-1]["ajan"] == "pinterest-curator" and "eski pin" in ajanlar[-1]["istem"]
    pj = k / "medya" / "pinterest" / "pin.json"
    pj.write_text(json.dumps({"durum": "HAZIR", "gorsel": str(k / "gorsel" / "konsept" / "teknik-poster-3x4.png"),
                              "baslik": "B", "aciklama": "A", "pano": "Masa", "link": "l"}), encoding="utf-8")
    asyncio.run(ajanlar[-1]["sonraki_islem"](True, "", None))
    assert "✅ Yeni Pini Paylaş" in json.dumps(tg3.mesajlar, ensure_ascii=False)
    _cb(cm, tg3, "pin:paylas:tel")
    pj.write_text(json.dumps({"durum": "PAYLASILDI", "pin_url": "https://pin/2", "tarih": "2026-11-18",
                              "pano": "Masa"}), encoding="utf-8")
    asyncio.run(ajanlar[-1]["sonraki_islem"](True, "PIN_PAYLASILDI", None))
    v = yaml_oku(k)
    assert v["pinterest"]["pin_url"] == "https://pin/2" and v["pinterest"]["onceki_pinler"][0]["pin_url"] == "https://pin/1"
    assert v["model_degisimi"]["durum"] == "TAMAM" and md.eskiyen_ciktilar("tel") == []
    assert "🎉" in tg3.metin()


def test_zincir_hata_durur_ve_devam_eder(bot, monkeypatch) -> None:
    cm, k, ajanlar = bot
    md.bildirim_kaydi("tel", "kullanim_testi tur 1")
    sonuclar = [False, True]

    async def sahte_dilim(tg, chat_id, sku, kategori=None, zincir=False):
        return sonuclar.pop(0)

    async def sahte_studyo(tg, chat_id, sku, tohum_degistir=False):
        return True

    monkeypatch.setattr(cm, "_dilimleme_ozeti_gonder", sahte_dilim)
    monkeypatch.setattr(cm, "_studyo_uret", sahte_studyo)
    monkeypatch.setattr(cm.model_degisim, "erp_gcode_guncelle", lambda sku: {"durum": "YOK", "hata": "yok"})
    # renk adımı zaten güncel olsun → plan dilimlemeden başlar
    os.utime(k / "model" / "cok_renk" / "renkli.3mf", (time.time() + 5, time.time() + 5))
    md.cikti_kaydet("tel", "renk")
    tg = SahteTg()
    _cb(cm, tg, "md:zincir:tel")
    v = yaml_oku(k)["model_degisimi"]
    assert v["plan"][0] == "dilimleme" and v["durum"] == "DURDU" and v["adim"] == "dilimleme"
    assert "md:devam:tel" in tg.veriler() and "zinciri *⚙️ Dilimleme" in tg.metin()
    from coo import bekleyen_isler as bi

    assert next(i for i in bi.urun_isleri("tel") if i["tur"] == "md")["onay"][1] == "md:devam:tel"
    _cb(cm, tg, "md:devam:tel")
    v = yaml_oku(k)["model_degisimi"]
    assert v["durum"] == "STUDYO_ONAYI" and v["tamamlanan"] == ["dilimleme", "erp"]
    assert "ERP reçetesi yok" in tg.metin()


def test_stl_zincirde_degisirse_durur(bot, monkeypatch) -> None:
    cm, k, ajanlar = bot
    md.bildirim_kaydi("tel", "kullanim_testi tur 1")
    tg = SahteTg()
    _cb(cm, tg, "md:zincir:tel")  # renk ajanı başladı
    kutu_stl(k / "model" / "tel.stl", 102.0, 150.0, 98.0)  # zincir sırasında yeni STL
    ck = k / "model" / "cok_renk"
    (ck / "rapor.json").write_text("{}", encoding="utf-8")
    (ck / "sema_son.json").write_text(json.dumps({"renkler": [{"hex": "#E1D6C1"}, {"hex": "#C0392B"}]}), encoding="utf-8")
    (ck / "renkli.3mf").write_bytes(b"yeni")
    asyncio.run(ajanlar[-1]["sonraki_islem"](True, "", None))
    v = yaml_oku(k)["model_degisimi"]
    assert v["durum"] == "DURDU" and "yeniden değişti" in v["hata"]


def test_not_ile_zincir(bot, monkeypatch) -> None:
    cm, k, ajanlar = bot
    md.bildirim_kaydi("tel", "kullanim_testi tur 1")
    tg = SahteTg()
    asyncio.run(cm._not_ile_guncelle(tg, 99, "md", "tel", "kask turuncu kalsın"))
    assert yaml_oku(k)["model_degisimi"]["not_"] == "kask turuncu kalsın"
    assert "kask turuncu kalsın" in ajanlar[-1]["istem"]


def test_elle_kontrol_onceden_onaylanmis_urun(bot) -> None:
    cm, k, _ = bot
    from coo import urun_menusu

    v = yaml_oku(k)
    v["kullanim_testi"] = {"son": {"durum": "GEÇTİ"}, "onay": "ONAYLANDI", "tasarim_turu": 0}
    (k / "urun.yaml").write_text(yaml.safe_dump(v, allow_unicode=True, sort_keys=False), encoding="utf-8")
    _, butonlar, _ = urun_menusu.urun_karti("tel")
    assert "md:kontrol:tel" in [b["callback_data"] for r in butonlar for b in r]
    tg = SahteTg()
    _cb(cm, tg, "md:kontrol:tel")
    assert "🔄 *Model değişti*" in tg.metin() and "md:zincir:tel" in tg.veriler()
    assert yaml_oku(k)["model_degisimi"]["durum"] == "BEKLIYOR"
    _, butonlar, _ = urun_menusu.urun_karti("tel")
    assert "md:goster:tel" in [b["callback_data"] for r in butonlar for b in r]
    tg2 = SahteTg()
    _cb(cm, tg2, "md:kontrol:tel")  # ikinci kez: aynı STL, yine listeyi gösterir
    assert "Model değişti" in tg2.metin()
