"""Telegram ürün kartı: ürünün gerçek dosya durumuna göre aşama listesi + o aşamada yapılabilecek butonlar.

Saf işlevlerdir (Telegram'a bağlı değil); `coo/__main__.py` çağırır.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .ayar import URUNLER_KLASORU
from .magaza_hatti import paket_oku
from .pazar_hatti import pazar_oku, pazar_ozeti

GIZLI_KLASORLER = {"_sablon", "_genel_baski", "_ozel_baski"}


def _yaml(kok: Path) -> dict[str, Any]:
    yol = kok / "urun.yaml"
    if not yol.exists():
        return {}
    try:
        return yaml.safe_load(yol.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}


def aktif_urunler(urunler_klasoru: Path | None = None, iptal_dahil: bool = False) -> list[str]:
    kok = urunler_klasoru or URUNLER_KLASORU
    skular = []
    for d in sorted(kok.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir() or d.name in GIZLI_KLASORLER or d.name.startswith("."):
            continue
        if not iptal_dahil and str(_yaml(d).get("durum") or "") == "IPTAL":
            continue
        skular.append(d.name)
    return skular


def urun_durumu(sku: str, urunler_klasoru: Path | None = None) -> dict[str, Any]:
    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    v = _yaml(kok)
    dil = v.get("dilimleme") if isinstance(v.get("dilimleme"), dict) else {}
    from .renk_hatti import renkler_veriden

    renkler = renkler_veriden(v)
    # e-ticaret görselleri GEÇERLİ renk kararının render'ından olmalı (renk değişince adım yeniden açılır)
    klasorler = [kok / str(r.get("klasor")) for r in renkler if r.get("klasor")] or [kok / "gorsel"]
    studyo = [p for k in klasorler for p in k.glob("studyo-ic/*.png")]
    numune = list(kok.glob("gorsel/numune-*"))
    kullanim = list(kok.glob("gorsel/kullanim-*"))
    yukleme = None
    if (kok / "magaza" / "yukleme.json").exists():
        try:
            yukleme = json.loads((kok / "magaza" / "yukleme.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            yukleme = None
    kapak = None
    for r in renkler:
        for aday in (kok / str(r.get("klasor") or "") / "studyo-ic" / "kapak-beyaz.png",
                     kok / str(r.get("klasor") or "") / "beyaz.png"):
            if kapak is None and aday.exists():
                kapak = aday
    for aday in (kok / "gorsel" / "beyaz.png", kok / "gorsel" / "studyo.png", *sorted(kok.glob("konsept/flow-1.*"))):
        if kapak is None and aday.exists():
            kapak = aday
    return {
        "sku": sku,
        "ad": str(v.get("ad") or sku),
        "durum": str(v.get("durum") or "—"),
        "konsept": sorted(kok.glob("konsept/flow-*")),
        "stl": (kok / "model" / f"{sku}.stl").exists(),
        "proje_3mf": (kok / "uretim" / f"{sku}.3mf").exists(),
        "gram": dil.get("gercek_gram") or dil.get("tahmini_gram"),
        "sure_dk": dil.get("gercek_sure_dk"),
        "renkler": [str(r.get("ad")) for r in renkler],
        "studyo": len(studyo),
        "numune": len(numune),
        "kullanim": len(kullanim),
        "teknik_poster": sorted(kok.glob("gorsel/konsept/*-3x4.png")),
        "icerik_onayi": str(v.get("icerik_onayi") or ""),
        "studyo_onayi": str(v.get("studyo_onayi") or ""),
        "paket": (kok / "magaza" / "paket.json").exists() and not paket_oku(sku, urunler_klasoru)[1],
        "yuklendi": bool(yukleme and yukleme.get("durum") == "YUKLENDI"),
        "urun_linki": (yukleme or {}).get("urun_linki"),
        "kapak": kapak,
        "pazar": pazar_ozeti(pazar_oku(sku, urunler_klasoru)),
    }


def _b(metin: str, veri: str) -> dict[str, str]:
    return {"text": metin, "callback_data": veri[:64]}


def adimlar(sku: str, urunler_klasoru: Path | None = None) -> list[dict[str, Any]]:
    """Ürünün iş akışı adımları: no, ad, tamam, ayrinti, buton (sıradaki adım için callback)."""
    d = urun_durumu(sku, urunler_klasoru)
    v = _yaml((urunler_klasoru or URUNLER_KLASORU) / sku)
    cr = v.get("cok_renk") if isinstance(v.get("cok_renk"), dict) else {}
    renk_tamam = cr.get("karar") == "onay" or bool(d["renkler"])
    if cr.get("karar") == "onay":
        renk_ayr = "çok renk: " + ", ".join(str(r.get("ad")) for r in cr.get("renkler") or [])
    else:
        renk_ayr = ("tek renk: " + ", ".join(d["renkler"])) if d["renkler"] else "karteladan seç (tek / çok renk)"
    gram = f"{d['gram']} g" if d["gram"] else ""
    sure = f"{int(d['sure_dk']) // 60} sa {int(d['sure_dk']) % 60} dk" if d["sure_dk"] else ""
    pz = d["pazar"]
    from .kullanim_testi_hatti import durum as kt_durum

    kt = kt_durum(sku, urunler_klasoru)
    if kt["onayli"]:
        kt_ayr = f"onaylandı ({kt['durum']})"
    elif kt["var"]:
        kt_ayr = f"{kt['durum']} · onay bekliyor" + (f" · tur {kt['tur']}" if kt["tur"] else "")
    else:
        kt_ayr = "vaat ettiği kullanımı fizik motoruyla dene"
    adim_listesi = [
        {"no": 1, "ad": "Konsept", "tamam": bool(d["konsept"]) or d["stl"], "ayrinti": f"{len(d['konsept'])} görsel",
         "buton": f"fikir:goster:{sku}"},
        {"no": 2, "ad": "3B model", "tamam": d["stl"], "ayrinti": "konsept seç → 3B üret" if not d["stl"] else "hazır",
         "buton": f"fikir:goster:{sku}"},
        # dilimlenmiş (sistemden önceki) ürünlerde akışı kesmez; dilimleme/mağazaya geçişte uyarı verilir
        {"no": 3, "ad": "🧪 Kullanım testi", "tamam": kt["onayli"], "ayrinti": kt_ayr, "istege_bagli": d["proje_3mf"],
         "buton": f"kt:goster:{sku}" if kt["var"] else f"kt:baslat:{sku}"},
        {"no": 3, "ad": "Renk", "tamam": renk_tamam, "ayrinti": renk_ayr, "buton": f"kartela:ac:{sku}"},
        {"no": 4, "ad": "Dilimleme (3MF)", "tamam": d["proje_3mf"], "ayrinti": " · ".join(x for x in (gram, sure) if x),
         "buton": f"orca:analiz:{sku}"},
        {"no": 5, "ad": "E-ticaret görselleri", "tamam": d["studyo"] > 0 and d["studyo_onayi"] == "ONAYLANDI",
         "ayrinti": f"{d['studyo']} kare (Qwen + Claude denetimi)"
                    + {"ONAYLANDI": " · onaylandı", "BEKLIYOR": " · onay bekliyor"}.get(d["studyo_onayi"], ""),
         "buton": f"studyo:sun:{sku}" if d["studyo"] > 0 and d["studyo_onayi"] != "ONAYLANDI" else f"icerik:studyo:{sku}"},
        {"no": 6, "ad": "Teknik Poster poster + Reels", "tamam": bool(d["teknik_poster"]),
         "ayrinti": "ölçü/malzeme posteri · Pinterest · tanıtım Reels" + (" ✓" if d["teknik_poster"] else ""),
         "buton": f"konsept:liste:{sku}"},
        {"no": 7, "ad": "Numune + kullanım görseli", "tamam": d["kullanim"] > 0, "istege_bagli": True,
         "ayrinti": f"numune {d['numune']} · kullanım {d['kullanim']} (numune basılınca)",
         "buton": f"icerik:kullanim:{sku}" if d["numune"] else f"numune:iste:{sku}"},
        {"no": 8, "ad": "Görsel onayı", "tamam": d["icerik_onayi"] == "ONAYLANDI", "ayrinti": {"ONAYLANDI": "onaylandı", "BEKLIYOR": "onay bekliyor",
                                                                              "REDDEDILDI": "reddedildi"}.get(d["icerik_onayi"], ""),
         "buton": f"icerik:sun:{sku}"},
        {"no": 9, "ad": "Pazar fiyatı", "tamam": bool(pz and pz.get("yeterli")),
         "ayrinti": (f"{pz['alt']:.0f}–{pz['ust']:.0f} TL" if pz and pz.get("yeterli") else ("yetersiz veri" if pz else "")),
         "buton": f"pazar:{'goster' if pz else 'arastir'}:{sku}"},
        {"no": 10, "ad": "Mağaza paketi", "tamam": d["paket"], "ayrinti": "", "buton": f"magaza:hazirla:{sku}"},
        {"no": 11, "ad": "İkas'a yükle", "tamam": d["yuklendi"], "ayrinti": d["urun_linki"] or "", "buton": f"magaza:yukle:{sku}"},
    ]
    for i, a in enumerate(adim_listesi):  # 3B modelden sonra kullanım testi girdiği için sıra yeniden numaralanır
        a["no"] = i + 1
    return adim_listesi


def sonraki_adim(sku: str, urunler_klasoru: Path | None = None) -> dict[str, Any] | None:
    for a in adimlar(sku, urunler_klasoru):
        if not a["tamam"] and not a.get("istege_bagli"):
            return a
    return None


def sonraki_butonlari(sku: str, urunler_klasoru: Path | None = None) -> list[list[dict[str, str]]]:
    a = sonraki_adim(sku, urunler_klasoru)
    satir = [_b(f"▶️ Sıradaki: {a['no']}. {a['ad']}", a["buton"])] if a else []
    return [satir + [_b("📦 Ürün Kartı", f"urunmenu:{sku}")]]


def urun_karti(sku: str, urunler_klasoru: Path | None = None,
               calisan: list[str] | None = None) -> tuple[str, list[list[dict[str, str]]], Path | None]:
    d = urun_durumu(sku, urunler_klasoru)
    ad_list = adimlar(sku, urunler_klasoru)
    sira = sonraki_adim(sku, urunler_klasoru)
    satirlar = [f"📦 *{d['ad']}*", f"`{sku}`", ""]
    for a in ad_list:
        if a["tamam"]:
            isaret = "✅"
        elif sira and a["no"] == sira["no"]:
            isaret = "👉"
        else:
            isaret = "▫️" if a.get("istege_bagli") else "⬜"
        satirlar.append(f"{isaret} {a['no']}. {a['ad']}" + (f" — {a['ayrinti']}" if a["ayrinti"] else ""))
    if calisan:
        satirlar += ["", *[f"⏳ *Şu an:* {c}" for c in calisan]]
    elif sira:
        satirlar += ["", f"Sıradaki adım: *{sira['no']}. {sira['ad']}* — aşağıdaki ▶️ butona bas."]
    else:
        satirlar += ["", "🎉 Tüm adımlar tamam."]

    butonlar: list[list[dict[str, str]]] = []
    if sira and not calisan:
        butonlar.append([_b(f"▶️ {sira['no']}. {sira['ad']}", sira["buton"])])
    elif calisan:
        butonlar.append([_b("🔄 Durumu Yenile", f"urunmenu:{sku}")])
    # tüm adımlara doğrudan erişim (yeniden yapmak / atlamak için)
    erisim = [_b(("✅ " if a["tamam"] else "") + f"{a['no']}. {a['ad']}"[:24], a["buton"]) for a in ad_list
              if a["no"] >= 2 and (d["stl"] or a["no"] <= 2)
              and not (a["buton"].startswith("magaza:yukle:") and a["tamam"])]  # yüklü: çift ilan olmasın
    butonlar += [erisim[i:i + 2] for i in range(0, len(erisim), 2)]
    if d["studyo"] and not d["numune"]:  # Patron seçeneği: numune beklemeden, stüdyo karesinden kullanım görseli
        butonlar.append([_b("🏡 Numunesiz Kullanım Görseli (stüdyo karesinden)", f"icerik:kullanimq:{sku}")])
    if d["teknik_poster"] or d["kullanim"] or d["studyo"]:
        butonlar.append([_b("📌 Pinterest'e Gönder", f"pin:hazirla:{sku}"), _b("🎞️ HyperFrames Reels", f"hf:urun:{sku}")])
    if d["proje_3mf"]:
        butonlar.append([_b("📤 Yazıcıya Yükle (başlatmaz)", f"yazici:yukle:{sku}"), _b("🖥️ Orca'da Aç", f"orca:ac:{sku}")])
    butonlar.append([_b("⬅️ Ürünlerim", "menu:urunler"), _b("🗄️ Arşivle", f"fikir:iptal:{sku}")])
    return "\n".join(satirlar), butonlar, d["kapak"]


def urun_listesi_butonlari(urunler_klasoru: Path | None = None, sinir: int = 20) -> list[list[dict[str, str]]]:
    butonlar = []
    for sku in aktif_urunler(urunler_klasoru)[:sinir]:
        d = urun_durumu(sku, urunler_klasoru)
        butonlar.append([_b(f"📦 {d['ad'][:34]} · {d['durum']}", f"urunmenu:{sku}")])
    butonlar.append([_b("💡 Yeni Fikir", "fikir:baslat"), _b("🏠 Ana Menü", "menu:ana")])
    return butonlar
