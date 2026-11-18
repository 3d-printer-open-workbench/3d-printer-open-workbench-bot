"""📋 Bekleyen İşler: Patron kararı bekleyen her işi ürün klasörlerinden ve kayıtlardan çıkarır.

Patron (2026-11-18): "açıkta bekleyen işleri seçip not yazabileyim onaylayabileyim bot üzerinden".

Saf işlevlerdir (Telegram'a bağlı değil); klasörler parametreyle verilebilir (testler geçici klasör kullanır).
Her iş mevcut callback'leri kullanır — yeni onay mantığı icat edilmez:

| tür | iş                                   | ✅ onay                    | ✏️ not                  | 🔁 yeniden             |
|-----|--------------------------------------|---------------------------|-------------------------|------------------------|
| kf  | konsept seçimi (Flow konseptleri)    | fikir:goster (seç)        | ng:kf (revize notu)     | fikir:yeni             |
| kt  | kullanım testi onayı bekliyor        | kt:onay                   | ng:kt                   | kt:tasarim (KALDI)     |
| md  | model değişti, güncelleme bekliyor   | md:zincir / md:yayin      | ng:md                   | md:devam (DURDU)       |
| cr  | çok renk render onayı                | cokrenk:onay              | ng:cr                   | cokrenk:baslat         |
| es  | e-ticaret görsel onayı               | studyo:onay               | studyo:revize           | icerik:yenile          |
| ic  | içerik/görsel onayı (Onay ②)         | icerik:onay               | icerik:revize           | —                      |
| fy  | mağaza paketi fiyat seçimi           | magaza:fiyat (önerilen)   | ng:mg                   | magaza:hazirla         |
| yk  | onaylı ama İkas'a yüklenmemiş        | magaza:yukle / hazirla    | ng:mg (paket varsa)     | —                      |
| pn  | hazır ama paylaşılmamış Pinterest pini| pin:paylas               | ng:pn                   | pin:hazirla            |
| rd  | durumu HAZIR Reels denetimi          | rd:kapat (olduğu gibi)    | rd:not                  | — (madde seçimi)       |
| dl  | bekleyen dilimleme önerisi           | rapor:uygula              | —                       | — (⏳ rapor:ertele)     |

"✏️ Not ile Güncelle" için ortak yol: `ng:<tür>:<anahtar>` → ForceReply (`GUNCELLEME_NOTU_BASLIGI [tür|anahtar]`)
→ yanıt işleyici notu `urun.yaml > revize_notlari` listesine tarihle yazar ve ilgili üretimi notla yeniden başlatır.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

import yaml

from .ayar import BASKI_KAYITLARI_KLASORU, MAGAZA_KLASORU, URUNLER_KLASORU

GIZLI_KLASORLER = {"_sablon", "_genel_baski", "_ozel_baski"}
GUNCELLEME_NOTU_BASLIGI = "✏️ Güncelleme notu"

# ng:<tür>:<anahtar> — not ile yeniden üretilebilen işler (anahtar: sku, konseptte "<sku>.<konsept sırası>")
NOT_TURLERI: dict[str, str] = {
    "kf": "Konsept seçenekleri (Flow)",
    "kt": "Kullanım testi",
    "md": "Model değişti → bağımlı çıktılar zinciri",
    "ks": "Konsept poster + Reels",
    "hf": "HyperFrames Reels",
    "cr": "Çok renk render'ı",
    "rk": "Renk render'ı",
    "pn": "Pinterest pini",
    "mg": "Mağaza paketi",
}

SIRA = ("kf", "kt", "md", "cr", "es", "ic", "fy", "yk", "pn", "rd", "dl")
SIMGE = {"kf": "💡", "kt": "🧪", "md": "🔄", "cr": "🎨", "es": "🛍️", "ic": "📋", "fy": "💰", "yk": "🚀", "pn": "📌", "rd": "🎞️", "dl": "⚙️"}
_ANAHTAR_DESENI = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_BASLIK_DESENI = re.compile(r"\[([a-z]{2})\|([a-z0-9._-]+)\]")


def _yaml(kok: Path) -> dict[str, Any]:
    yol = kok / "urun.yaml"
    if not yol.exists():
        return {}
    try:
        v = yaml.safe_load(yol.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return v if isinstance(v, dict) else {}


def _json(yol: Path) -> dict[str, Any] | None:
    if not yol.exists():
        return None
    try:
        v = json.loads(yol.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return v if isinstance(v, dict) else None


def _b(metin: str, veri: str) -> dict[str, str]:
    return {"text": metin, "callback_data": veri}


def _is(tur: str, anahtar: str, baslik: str, ozet: str, sku: str | None = None, onay: tuple[str, str] | None = None,
        not_: str | None = None, yeniden: str | None = None, goster: tuple[str, str] | None = None,
        ek: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    return {"id": f"{tur}:{anahtar}", "tur": tur, "sku": sku, "baslik": baslik, "ozet": ozet, "onay": onay,
            "not": not_, "yeniden": yeniden, "goster": goster, "ek": ek or []}


def urun_isleri(sku: str, urunler: Path | None = None) -> list[dict[str, Any]]:
    """Tek ürünün Patron kararı bekleyen işleri (IPTAL ürün → boş)."""
    from .magaza_hatti import paket_oku, yukleme_oku
    from .pinterest_hatti import oku as pin_oku

    kok = (urunler or URUNLER_KLASORU) / sku
    v = _yaml(kok)
    if str(v.get("durum") or "") == "IPTAL":
        return []
    ad = str(v.get("ad") or sku)
    isler: list[dict[str, Any]] = []
    stl_var = (kok / "model" / f"{sku}.stl").exists()

    # kf — Flow konseptleri geldi, Patron seçmedi
    konseptler = sorted(p for p in (kok / "konsept").glob("flow-*")
                        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    if konseptler and not stl_var and str(v.get("durum") or "") == "KONSEPT_SECIMI":
        isler.append(_is("kf", sku, f"Konsept seçimi — {ad}", f"{len(konseptler)} konsept görseli seçimini bekliyor; "
                         "seçilen konseptten 3B model üretilir.", sku, onay=("✅ Konseptleri Gör / Seç", f"fikir:goster:{sku}"),
                         not_=f"ng:kf:{sku}", yeniden=f"fikir:yeni:{sku}"))

    # kt — kullanım testi sonucu Patron onayında
    from .kullanim_testi_hatti import durum as kt_durum

    kt = kt_durum(sku, urunler)
    if kt["var"] and not kt["onayli"]:
        son = kt["son"]
        kaldi = son.get("durum") == "KALDI"
        ozet = (f"{'❌ KALDI' if kaldi else '✅ GEÇTİ'} — {son.get('gecti')}/{(son.get('gecti') or 0) + (son.get('kaldi') or 0)}"
                f" kural geçti ({son.get('tarih')})")
        if kaldi and son.get("duzeltme_onerisi"):
            ozet += "\nÖneri: " + str(son["duzeltme_onerisi"][0])[:300]
        isler.append(_is("kt", sku, f"Kullanım testi onayı — {ad}", ozet, sku,
                         onay=("✅ Onayla" if not kaldi else "✅ Olduğu Gibi Onayla", f"kt:onay:{sku}"),
                         not_=f"ng:kt:{sku}", goster=("🖼️ Panoyu Göster", f"kt:goster:{sku}"),
                         ek=[("🛠️ Yeniden Tasarla", f"kt:tasarim:{sku}")] if kaldi else
                         [("🔁 Testi Yinele", f"kt:baslat:{sku}")]))

    # md — model değişti (kullanım testi revizyonu), bağımlı çıktılar güncelleme bekliyor
    from . import model_degisim

    if model_degisim.bekliyor_mu(sku, urunler):
        md = model_degisim.degisim_oku(sku, urunler)
        eski = model_degisim.eskiyen_ciktilar(sku, urunler)
        yayinda = [a for a in eski if a["yayinda"]]
        ozet = (f"Model değişti ({str(md.get('kaynak') or 'STL güncellendi').replace('_', ' ')}); {len(eski)} çıktı eski"
                + (f", {len(yayinda)} tanesi yayında" if yayinda else "") + ": "
                + ", ".join(a["ad"].split(" ", 1)[1] for a in eski))
        if md.get("durum") == "DURDU":
            ozet += f"\n⛔ Zincir *{model_degisim.ADIMLAR.get(str(md.get('adim')), md.get('adim'))}* adımında durdu: " \
                    + str(md.get("hata") or "")[:200]
            onay = ("🔁 Kaldığı Yerden Devam", f"md:devam:{sku}")
        elif md.get("durum") == "YAYIN_ONAYI":
            onay = ("🛒 Yayın Güncellemesi", f"md:yayin:{sku}")
        else:
            onay = ("▶️ Zinciri Güncelle", f"md:zincir:{sku}")
        isler.append(_is("md", sku, f"Model değişti, güncelleme bekliyor — {ad}", ozet, sku, onay=onay,
                         not_=f"ng:md:{sku}", goster=("🔄 Eskiyenleri Göster", f"md:goster:{sku}")))

    # cr — çok renk boyama sonucu Patron onayında
    cr = v.get("cok_renk") if isinstance(v.get("cok_renk"), dict) else {}
    ck = kok / "model" / "cok_renk"
    sema = _json(ck / "sema_son.json")
    if sema is not None and (ck / "renkli.3mf").exists():
        karar = str(cr.get("karar") or "")
        sema_tarihi = dt.date.fromtimestamp((ck / "sema_son.json").stat().st_mtime).isoformat()
        bekliyor = (not karar
                    or (karar == "onay" and str(cr.get("sema") or "") != str(sema.get("ad") or ""))
                    or (karar == "tek" and str(cr.get("tarih") or "") < sema_tarihi))
        if bekliyor:
            renkler = ", ".join(str(r.get("ad")) for r in sema.get("renkler") or [] if isinstance(r, dict))
            isler.append(_is("cr", sku, f"Çok renk onayı — {ad}", f"Şema *{sema.get('ad', '')}*: {renkler}. "
                             "Onaylarsan çok filamentli 3MF dilimlenir.", sku,
                             onay=("✅ Onayla → Çok Renk 3MF", f"cokrenk:onay:{sku}"), not_=f"ng:cr:{sku}",
                             yeniden=f"cokrenk:baslat:{sku}", ek=[("⚪ Tek Renk Dilimle", f"cokrenk:tek:{sku}")]))

    # es — e-ticaret (Qwen stüdyo) kareleri onay bekliyor
    if str(v.get("studyo_onayi") or "") == "BEKLIYOR":
        isler.append(_is("es", sku, f"E-ticaret görsel onayı — {ad}", "Qwen stüdyo kareleri Claude denetiminden geçti, "
                         "onayını bekliyor.", sku, onay=("✅ Onayla", f"studyo:onay:{sku}"), not_=f"studyo:revize:{sku}",
                         yeniden=f"icerik:yenile:{sku}", goster=("🖼️ Kareleri Göster", f"studyo:sun:{sku}")))

    # ic — içerik/görsel onayı (Onay ②)
    if str(v.get("icerik_onayi") or "") == "BEKLIYOR":
        isler.append(_is("ic", sku, f"Görsel/içerik onayı (Onay ②) — {ad}", "Galeri, teknik poster ve Reels "
                         "onayını bekliyor.", sku, onay=("✅ Onayla", f"icerik:onay:{sku}"), not_=f"icerik:revize:{sku}",
                         goster=("🖼️ İçerikleri Göster", f"icerik:sun:{sku}"), ek=[("❌ Reddet", f"icerik:red:{sku}")]))

    # fy / yk — mağaza: fiyat seçimi ve İkas yüklemesi
    yukleme = yukleme_oku(sku, urunler)
    yuklendi = bool(yukleme and yukleme.get("durum") == "YUKLENDI")
    if not yuklendi:
        paket, hatalar = paket_oku(sku, urunler) if (kok / "magaza" / "paket.json").exists() else (None, ["yok"])
        karar = (paket or {}).get("fiyat_karari") if isinstance((paket or {}).get("fiyat_karari"), dict) else {}
        if paket is not None and not hatalar and karar.get("secim") != "PATRON":
            tl = float(paket.get("satis_fiyati_tl") or 0)
            isler.append(_is("fy", sku, f"Fiyat seçimi — {ad}", f"Mağaza paketi hazır; önerilen satış fiyatı "
                             f"*{tl:.2f} TL*. Fiyat Patron kararıdır.", sku,
                             onay=(f"✅ {tl:.2f} TL ile Onayla", f"magaza:fiyat:{sku}:{int(round(tl * 100))}"),
                             not_=f"ng:mg:{sku}", yeniden=f"magaza:hazirla:{sku}",
                             ek=[("✏️ Elle Fiyat", f"magaza:elle:{sku}")]))
        elif str(v.get("icerik_onayi") or "") == "ONAYLANDI":
            if paket is not None and not hatalar:
                isler.append(_is("yk", sku, f"İkas'a yüklenmedi — {ad}", "Görseller onaylı, fiyat seçili; mağazaya "
                                 "yükleme onayını bekliyor.", sku, onay=("🚀 İkas'a Yükle", f"magaza:yukle:{sku}"),
                                 not_=f"ng:mg:{sku}"))
            else:
                isler.append(_is("yk", sku, f"İkas'a yüklenmedi — {ad}", "Görseller onaylı; mağaza paketi (fiyat + "
                                 "metin) henüz hazır değil.", sku, onay=("🛒 Mağazaya Hazırla", f"magaza:hazirla:{sku}")))

    # pn — pin hazırlandı, paylaşılmadı
    pin = pin_oku(sku, urunler)
    if pin and pin.get("durum") == "HAZIR":
        isler.append(_is("pn", sku, f"Pinterest pini — {ad}", f"*{pin.get('baslik', '')}* — pano: "
                         f"_{pin.get('pano', '')}_. Paylaşım onayını bekliyor.", sku,
                         onay=("✅ Pinterest'te Paylaş", f"pin:paylas:{sku}"), not_=f"ng:pn:{sku}",
                         yeniden=f"pin:hazirla:{sku}", ek=[("❌ Vazgeç", f"pin:iptal:{sku}")]))
    return isler


def reels_isleri(klasor: Path | None = None, urunler: Path | None = None) -> list[dict[str, Any]]:
    k = klasor or (MAGAZA_KLASORU / "reels_denetim")
    if not k.exists():
        return []
    isler = []
    for yol in sorted(k.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        r = _json(yol)
        if not r or r.get("durum") != "HAZIR" or not r.get("kid"):
            continue
        sku = (r.get("kaynak") or {}).get("sku") or None
        if sku and str(_yaml((urunler or URUNLER_KLASORU) / str(sku)).get("durum") or "") == "IPTAL":
            continue
        adet = len(r.get("maddeler") or [])
        isler.append(_is("rd", str(r["kid"]), f"Reels denetimi — {Path(str(r.get('video'))).name}",
                         f"{adet} düzeltme maddesi" if adet else "Düzeltilecek madde yok", sku,
                         onay=("👍 Olduğu Gibi Kalsın", f"rd:kapat:{r['kid']}"), not_=f"rd:not:{r['kid']}"))
    return isler


def dilimleme_isleri(klasor: Path | None = None) -> list[dict[str, Any]]:
    from .baski_rapor import bekleyen_oneriler

    isler = []
    for b in bekleyen_oneriler(klasor=klasor or (BASKI_KAYITLARI_KLASORU / "raporlar")):
        ozet = ", ".join(f"{o.get('ayar')} → {o.get('onerilen')}" for o in b["oneriler"])
        isler.append(_is("dl", b["rid"], f"Dilimleme önerisi — {b['kategori']}" + (f" ({b['sku']})" if b.get("sku") else ""),
                         f"`{b['kategori']}` kategorisi: {ozet}" + (" — ⏳ ertelendi" if b.get("ertelendi") else ""),
                         b.get("sku"), onay=("⚙️ Uygula", f"rapor:uygula:{b['rid']}"),
                         ek=[("⏳ Şimdi Değil", f"rapor:ertele:{b['rid']}")]))
    return isler


def tara(urunler: Path | None = None, reels_klasoru: Path | None = None,
         rapor_klasoru: Path | None = None) -> list[dict[str, Any]]:
    """Tüm bekleyen işler (tür sırasına göre)."""
    kok = urunler or URUNLER_KLASORU
    isler: list[dict[str, Any]] = []
    if kok.exists():
        for d in sorted(kok.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if d.is_dir() and d.name not in GIZLI_KLASORLER and not d.name.startswith((".", "_")):
                isler += urun_isleri(d.name, kok)
    isler += reels_isleri(reels_klasoru, kok)
    isler += dilimleme_isleri(rapor_klasoru)
    return sorted(isler, key=lambda i: SIRA.index(i["tur"]))


def is_bul(is_id: str, isler: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((i for i in isler if i["id"] == is_id), None)


def liste_mesaji(isler: list[dict[str, Any]], sinir: int = 40) -> tuple[str, list[list[dict[str, str]]]]:
    if not isler:
        return ("📋 *Bekleyen İşler*\n\n✅ Kararını bekleyen iş yok.",
                [[_b("🔄 Yenile", "bk:liste"), _b("🏠 Ana Menü", "menu:ana")]])
    sayac: dict[str, int] = {}
    for i in isler:
        sayac[i["tur"]] = sayac.get(i["tur"], 0) + 1
    metin = (f"📋 *Bekleyen İşler* ({len(isler)})\n"
             + " · ".join(f"{SIMGE[t]} {n}" for t, n in sayac.items())
             + "\n\nBir işe dokun → kısa özet ve karar düğmeleri (onayla / not ile güncelle / yeniden üret).")
    butonlar = [[_b(f"{SIMGE[i['tur']]} {i['baslik']}"[:60], f"bk:g:{i['id']}")] for i in isler[:sinir]]
    butonlar.append([_b("🔄 Yenile", "bk:liste"), _b("🏠 Ana Menü", "menu:ana")])
    return metin, butonlar


def is_detayi(is_: dict[str, Any]) -> tuple[str, list[list[dict[str, str]]]]:
    metin = f"{SIMGE[is_['tur']]} *{is_['baslik']}*\n{is_['ozet']}"
    butonlar: list[list[dict[str, str]]] = []
    ilk = []
    if is_.get("onay"):
        ilk.append(_b(*is_["onay"]))
    if is_.get("not"):
        ilk.append(_b("✏️ Not ile Güncelle", is_["not"]))
    if ilk:
        butonlar.append(ilk)
    ikinci = []
    if is_.get("goster"):
        ikinci.append(_b(*is_["goster"]))
    if is_.get("yeniden"):
        ikinci.append(_b("🔁 Yeniden Üret", is_["yeniden"]))
    ikinci += [_b(m, c) for m, c in is_.get("ek") or []]
    for i in range(0, len(ikinci), 2):
        butonlar.append(ikinci[i:i + 2])
    alt = [_b("📋 Bekleyen İşler", "bk:liste")]
    if is_.get("sku"):
        alt.insert(0, _b("📦 Ürün Kartı", f"urunmenu:{is_['sku']}"))
    butonlar.append(alt)
    return metin, butonlar


# --- ✏️ Not ile Güncelle ortak yolu --------------------------------------------------------------------
def not_dugmesi(tur: str, anahtar: str) -> dict[str, str]:
    if tur not in NOT_TURLERI:
        raise ValueError(f"bilinmeyen not türü: {tur}")
    return _b("✏️ Not ile Güncelle", f"ng:{tur}:{anahtar}")


def not_basligi(tur: str, anahtar: str) -> str:
    return (f"{GUNCELLEME_NOTU_BASLIGI} [{tur}|{anahtar}] — {NOT_TURLERI.get(tur, tur)}: ne değişsin? "
            "Notun isteme eklenip yeniden üretilecek.")


def not_basligi_coz(metin: str) -> tuple[str, str] | None:
    """ForceReply başlığından (tür, anahtar); başlık değilse ya da tür bilinmiyorsa None."""
    if not metin.startswith(GUNCELLEME_NOTU_BASLIGI):
        return None
    m = _BASLIK_DESENI.search(metin)
    if not m or m.group(1) not in NOT_TURLERI or not _ANAHTAR_DESENI.match(m.group(2)):
        return None
    return m.group(1), m.group(2)


def anahtar_coz(anahtar: str) -> tuple[str, int | None]:
    """'<sku>' → (sku, None); '<sku>.<n>' → (sku, n)."""
    sku, _, no = anahtar.partition(".")
    return sku, (int(no) if no.isdigit() else None)


def revize_notu_ekle(sku: str, tur: str, not_: str, urunler: Path | None = None,
                     zaman: dt.datetime | None = None) -> list[dict[str, Any]]:
    """Notu urun.yaml > revize_notlari listesine tarihle ekler; listeyi döndürür."""
    yol = (urunler or URUNLER_KLASORU) / sku / "urun.yaml"
    if not yol.parent.is_dir():
        raise FileNotFoundError(sku)
    veri = (yaml.safe_load(yol.read_text(encoding="utf-8")) or {}) if yol.exists() else {}
    notlar = veri.get("revize_notlari") if isinstance(veri.get("revize_notlari"), list) else []
    notlar.append({"tarih": (zaman or dt.datetime.now()).isoformat(timespec="seconds"), "tur": tur,
                   "is": NOT_TURLERI.get(tur, tur), "not": not_.strip()})
    veri["revize_notlari"] = notlar
    yol.write_text(yaml.safe_dump(veri, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return notlar
