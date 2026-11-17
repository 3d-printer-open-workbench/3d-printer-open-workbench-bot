"""Open Workbench 2. Katman — Ürün yaşam döngüsü ve aşama özeti (Telegram /ozet)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import yaml

from .ayar import B2C_ONERILER_KLASORU, KONSEPT_ARGE_KLASORU, URUNLER_KLASORU

_GORSEL_UZANTILARI = {".png", ".jpg", ".jpeg", ".webp"}
_VIDEO_UZANTILARI = {".mp4", ".mov", ".webm"}
_KART_ADLARI = {"olcu-karti", "ozellik-karti", "pinterest-pin"}
_SIRADAKI_IPUCU = {
    "Ar-Ge": "Ar-Ge & urun.yaml belgesini tamamla",
    "3B CAD": "3B CAD modeli (STL/3MF) üret",
    "Render": "Blender GPU stüdyo render al",
    "Üretim": "OrcaSlicer profili / baskı raporu çıkar",
    "Medya/Kart": "Ölçü/özellik kartı & Reels kurgula",
    "ERP/Mağaza": "SEO metni, ERP BOM & İkas yayını tamamla",
}


def _md_temizle(metin: Any) -> str:
    """Telegram legacy Markdown içinde ayrıştırma hatası verecek karakterleri temizler."""
    return str(metin or "").replace("*", "×").replace("_", "-").replace("[", "(").replace("]", ")")


def _callback_kisalt(onek: str, sku: str) -> str:
    """Telegram callback_data için 64 byte sınırı içinde güvenli veri üretir."""
    limit = 64 - len(onek.encode("utf-8"))
    kisa = sku
    while len(kisa.encode("utf-8")) > limit and kisa:
        kisa = kisa[:-1]
    return f"{onek}{kisa}"


def _yaml_oku(dosya: Path) -> dict[str, Any]:
    if not dosya.is_file():
        return {}
    try:
        veri = yaml.safe_load(dosya.read_text(encoding="utf-8"))
        return veri if isinstance(veri, dict) else {}
    except Exception:
        return {}


def _dosyalari_tara(klasor: Path, uzantilar: set[str], gcode_haric: bool = False) -> list[Path]:
    if not klasor.is_dir():
        return []
    bulunan: list[Path] = []
    for p in sorted(klasor.rglob("*")):
        if not p.is_file():
            continue
        ad = p.name.lower()
        if ad.startswith((".", "_")) or ad == ".gitkeep":
            continue
        if gcode_haric and ad.endswith(".gcode.3mf"):
            continue
        if p.suffix.lower() in uzantilar or (".gcode.3mf" in uzantilar and ad.endswith(".gcode.3mf")):
            bulunan.append(p)
    return bulunan


def _sure_kisalt(saniye: float) -> str:
    sn = max(0, int(saniye))
    dk, kalan = divmod(sn, 60)
    sa, dk = divmod(dk, 60)
    if sa > 0:
        return f"{sa}sa {dk:02d}dk"
    return f"{dk}dk {kalan:02d}sn"


def _ilerleme_cubugu(tamam: int, toplam: int) -> str:
    dolu = max(0, min(toplam, tamam))
    return "█" * dolu + "░" * (toplam - dolu)


def _en_iyi_onizleme(urun_dir: Path, renderlar: list[Path], kartlar: list[Path]) -> Path | None:
    tercihler = [
        urun_dir / "gorsel" / "yasam-1.png",
        urun_dir / "gorsel" / "montaj" / "studyo.png",
        urun_dir / "gorsel" / "studyo.png",
        urun_dir / "gorsel" / "yasam-alani.png",
        urun_dir / "gorsel" / "beyaz.png",
        urun_dir / "gorsel" / "montajli-75.png",
        urun_dir / "gorsel" / "yakin.png",
    ]
    for yol in tercihler:
        if yol.is_file():
            return yol
    if renderlar:
        return renderlar[0]
    if kartlar:
        return kartlar[0]
    return None


def _b2c_oneri_ozet_satiri(son_paket: dict[str, Any] | None) -> str:
    if not isinstance(son_paket, dict) or not son_paket.get("adaylar"):
        return ""
    adaylar = [a for a in son_paket.get("adaylar", []) if isinstance(a, dict)]
    paket_id = _md_temizle(son_paket.get("paket_id") or son_paket.get("tarih") or "güncel")
    secildi = sum(1 for a in adaylar if str(a.get("karar") or "").upper() in {"SATIS", "ONAY", "SEÇİLDİ"})
    revize = sum(1 for a in adaylar if str(a.get("karar") or "").upper() == "REVIZE")
    bekleyen = max(0, len(adaylar) - secildi - revize)
    return (
        f"🛍️ *Son Ar-Ge Vitrini* (`{paket_id}`): "
        f"{len(adaylar)} aday • Seçili: `{secildi}` • Revize: `{revize}` • Bekleyen: `{bekleyen}`"
    )


def urun_asama_analiz_et(
    sku: str,
    erp_sku_set: set[str] | None = None,
    urunler_klasoru: Path | None = None,
    konsept_klasoru: Path | None = None,
) -> dict[str, Any]:
    """Bir SKU klasörü ve YAML manifestini okuyarak 6 aşamalı pipeline durumunu çıkarır."""
    urun_kok = urunler_klasoru or URUNLER_KLASORU
    konsept_kok = konsept_klasoru or KONSEPT_ARGE_KLASORU
    urun_dir = urun_kok / sku
    yaml_yolu = urun_dir / "urun.yaml"
    veri = _yaml_oku(yaml_yolu)

    ad = str(veri.get("ad") or sku)
    b2b_mi = sku.upper().startswith("PRN-B2B-") or str(veri.get("urun_tipi") or "").upper() == "B2B"
    kategori = str(veri.get("kategori") or ("B2B" if b2b_mi else "B2C"))
    portfoy = str(veri.get("portfoy") or "AKTIF").upper()
    durum = str(veri.get("durum") or "TASLAK")
    ceo_denetim = str(veri.get("ceo_denetim_durumu") or "-")

    erp_blok = veri.get("erp") if isinstance(veri.get("erp"), dict) else {}
    muh_blok = veri.get("muhasebe") if isinstance(veri.get("muhasebe"), dict) else {}
    medya_blok = veri.get("medya") if isinstance(veri.get("medya"), dict) else {}
    fiyat_tl = erp_blok.get("onerilen_satis_fiyati_tl") or muh_blok.get("onerilen_satis_fiyati_tl")

    # 1) Ar-Ge
    arge_md = konsept_kok / f"{sku}-arge.md"
    arge_ok = yaml_yolu.is_file() or arge_md.is_file()

    # 2) 3B CAD
    model_dir = urun_dir / "model"
    cad_dosyalar = _dosyalari_tara(model_dir, {".stl", ".3mf"}, gcode_haric=True)
    stl_yolu_str = str(veri.get("stl_yolu") or "").strip()
    if stl_yolu_str and not cad_dosyalar and (urun_dir / stl_yolu_str).is_file():
        cad_dosyalar = [urun_dir / stl_yolu_str]
    cad_ok = bool(cad_dosyalar)

    # 3) Render & 5) Kart ayrımları (gorsel/ + model/**/render*, preview*)
    gorsel_dir = urun_dir / "gorsel"
    gorsel_dosyalar = _dosyalari_tara(gorsel_dir, _GORSEL_UZANTILARI)
    renderlar: list[Path] = []
    kartlar: list[Path] = []
    for p in gorsel_dosyalar:
        if any(p.stem.lower().startswith(k) for k in _KART_ADLARI):
            kartlar.append(p)
        else:
            renderlar.append(p)
    for p in _dosyalari_tara(model_dir, _GORSEL_UZANTILARI):
        if p.stem.lower().startswith(("render", "preview")):
            renderlar.append(p)
    render_ok = bool(renderlar)

    # 4) Üretim / Dilimleme
    uretim_dir = urun_dir / "uretim"
    orca_json = uretim_dir / "orca_profil.json"
    baski_raporu = uretim_dir / "baski_raporu.txt"
    dilimleme_md = uretim_dir / "dilimleme-rehberi.md"
    gcode_dosyalar = _dosyalari_tara(uretim_dir, {".gcode", ".gcode.3mf"}) + _dosyalari_tara(
        model_dir, {".gcode", ".gcode.3mf"}
    )
    orca_yolu_str = str(veri.get("orca_profil_yolu") or "").strip()
    orca_kayit_var = bool(orca_yolu_str and (urun_dir / orca_yolu_str).is_file())
    uretim_ok = orca_json.is_file() or baski_raporu.is_file() or dilimleme_md.is_file() or orca_kayit_var or bool(gcode_dosyalar)

    # 5) Medya / Video / Bilgi Kartı
    medya_dir = urun_dir / "medya"
    videolar = _dosyalari_tara(medya_dir, _VIDEO_UZANTILARI)
    for p in _dosyalari_tara(medya_dir, _GORSEL_UZANTILARI):
        if any(p.stem.lower().startswith(k) for k in _KART_ADLARI):
            kartlar.append(p)
    medya_ok = bool(videolar or kartlar)

    # 6) SEO / ERP / Mağaza
    seo_adaylari = [
        urun_dir / "magaza-seo.md",
        medya_dir / "magaza-seo.md",
        medya_dir / "magaza_metni.md",
    ]
    magaza_yol_str = str(medya_blok.get("magaza_metni") or "").strip()
    seo_ok = any(p.is_file() for p in seo_adaylari) or bool(magaza_yol_str and (urun_dir / magaza_yol_str).is_file())
    bom_csv = list(model_dir.rglob("bom.csv")) if model_dir.is_dir() else []
    if erp_sku_set is not None:
        erp_sku_alt = {s.lower() for s in erp_sku_set}
        erp_var = sku.lower() in erp_sku_alt
    else:
        erp_var = bool(erp_blok.get("product_id")) or bool(bom_csv)
    ikas_ok = bool(medya_blok.get("ikas_yuklendi")) or durum.upper() == "SATISTA"
    magaza_ok = ikas_ok or (seo_ok and erp_var)

    adimlar = [
        ("Ar-Ge", arge_ok),
        ("3B CAD", cad_ok),
        ("Render", render_ok),
        ("Üretim", uretim_ok),
        ("Medya/Kart", medya_ok),
        ("ERP/Mağaza", magaza_ok),
    ]
    tamam_sayisi = sum(1 for _, ok in adimlar if ok)
    tamamlananlar = [isim for isim, ok in adimlar if ok]
    eksikler = [isim for isim, ok in adimlar if not ok]

    if ikas_ok:
        mevcut_asama = "Mağazada Canlı"
    elif tamam_sayisi == len(adimlar):
        mevcut_asama = "Yayına Hazır"
    elif tamamlananlar:
        mevcut_asama = tamamlananlar[-1]
    else:
        mevcut_asama = "Başlanmadı"

    siradaki_adim = _SIRADAKI_IPUCU[eksikler[0]] if eksikler else "Yayında — satış & performans takibi"

    boyut_mm = veri.get("boyut_mm") or (veri.get("tasarim") or {}).get("boyutlar_mm") or {}
    orca_ozet: dict[str, Any] = {}
    if orca_json.is_file():
        try:
            orca_veri = json.loads(orca_json.read_text(encoding="utf-8"))
            if isinstance(orca_veri, dict):
                orca_ozet = {
                    k: orca_veri[k]
                    for k in ("layer_height", "sparse_infill_density", "wall_loops", "nozzle_diameter", "tahmini_gram", "tahmini_sure_dk")
                    if k in orca_veri
                }
        except Exception:
            orca_ozet = {}

    return {
        "sku": sku,
        "ad": ad,
        "b2b_mi": b2b_mi,
        "kategori": kategori,
        "portfoy": portfoy,
        "durum": durum,
        "ceo_denetim": ceo_denetim,
        "fiyat_tl": fiyat_tl,
        "tamam_sayisi": tamam_sayisi,
        "toplam_adim": len(adimlar),
        "tamamlama_orani": f"{tamam_sayisi}/{len(adimlar)}",
        "mevcut_asama": mevcut_asama,
        "siradaki_adim": siradaki_adim,
        "adimlar": adimlar,
        "detay": {
            "arge_md": arge_md.is_file(),
            "cad_sayisi": len(cad_dosyalar),
            "render_sayisi": len(renderlar),
            "uretim_dosyalari": [p.name for p in (orca_json, baski_raporu, dilimleme_md) if p.is_file()],
            "video_sayisi": len(videolar),
            "kart_sayisi": len(kartlar),
            "seo_ok": seo_ok,
            "erp_var": erp_var,
            "ikas_ok": ikas_ok,
            "boyut_mm": boyut_mm if isinstance(boyut_mm, dict) else {},
            "orca_ozet": orca_ozet,
        },
        "onizleme_yolu": _en_iyi_onizleme(urun_dir, renderlar, kartlar),
    }


def _urun_satir_bicimle(ozet: dict[str, Any], kisa: bool = False) -> str:
    ad = _md_temizle(ozet["ad"])
    sku = ozet["sku"]
    tamam = ozet["tamam_sayisi"]
    toplam = ozet["toplam_adim"]
    bar = _ilerleme_cubugu(tamam, toplam)
    fiyat = f" • `{ozet['fiyat_tl']} TL`" if ozet.get("fiyat_tl") else ""
    if kisa:
        return (
            f"• `{sku}` *{_md_temizle(ad)}* — *{tamam}/{toplam}* "
            f"(`{ozet['mevcut_asama']}`){fiyat} → {ozet['siradaki_adim']}"
        )
    return (
        f"• *{ad}* (`{sku}`) — *{tamam}/{toplam}* `{bar}`{fiyat}\n"
        f"  Durum: `{ozet['durum']}` • Son: `{ozet['mevcut_asama']}` → {ozet['siradaki_adim']}"
    )


def portfoy_ozet_metni_ve_butonlari(
    erp_urunler: list[dict[str, Any]] | None = None,
    aktif_gorevler: dict[str, dict[str, Any]] | None = None,
    son_paket: dict[str, Any] | None = None,
    urunler_klasoru: Path | None = None,
    konsept_klasoru: Path | None = None,
) -> tuple[str, list[list[dict[str, str]]]]:
    """Tüm ürünlerin aşama özetini ve Telegram butonlarını üretir."""
    urun_kok = urunler_klasoru or URUNLER_KLASORU
    konsept_kok = konsept_klasoru or KONSEPT_ARGE_KLASORU
    skular = (
        [k.name for k in sorted(urun_kok.iterdir()) if k.is_dir() and not k.name.startswith("_")]
        if urun_kok.is_dir()
        else []
    )
    erp_sku_set = (
        {str(u.get("sku") or "") for u in erp_urunler if isinstance(u, dict) and u.get("sku")}
        if erp_urunler is not None
        else None
    )

    analizler = [
        urun_asama_analiz_et(
            sku,
            erp_sku_set=erp_sku_set,
            urunler_klasoru=urun_kok,
            konsept_klasoru=konsept_kok,
        )
        for sku in skular
    ]
    b2c = sorted(
        [a for a in analizler if not a["b2b_mi"]],
        key=lambda x: (-x["tamam_sayisi"], x["sku"]),
    )
    b2b_aktif = [a for a in analizler if a["b2b_mi"] and a["portfoy"] != "PARK"]
    b2b_park = [a for a in analizler if a["b2b_mi"] and a["portfoy"] == "PARK"]

    satirlar: list[str] = ["📊 *Ürün Hattı Özeti*\n"]

    if aktif_gorevler:
        simdi = time.monotonic()
        satirlar.append("⚙️ *Şu An Çalışan Görevler:*")
        for gid, g in list(aktif_gorevler.items())[:5]:
            sure = _sure_kisalt(simdi - float(g.get("baslangic", simdi)))
            satirlar.append(f"• `{gid}` — *{g.get('ajan', 'ajan')}* ({sure})")
        satirlar.append("")

    if son_paket is None and urunler_klasoru is None and B2C_ONERILER_KLASORU.is_dir():
        try:
            from .b2c_arge import paket_yukle

            son_paket = paket_yukle()
        except Exception:
            son_paket = None

    vitrin_satiri = _b2c_oneri_ozet_satiri(son_paket)
    if vitrin_satiri:
        satirlar.append(vitrin_satiri)
        satirlar.append("")

    if b2c:
        satirlar.append(f"🎨 *B2C Tasarım Ürünleri ({len(b2c)}):*")
        for a in b2c:
            satirlar.append(_urun_satir_bicimle(a, kisa=False))
        satirlar.append("")

    if b2b_aktif:
        satirlar.append(f"🏢 *B2B Aktif Koleksiyon ({len(b2b_aktif)}):*")
        for a in b2b_aktif:
            satirlar.append(_urun_satir_bicimle(a, kisa=True))
        satirlar.append("")

    if b2b_park:
        park_ozet = ", ".join(f"`{a['sku']}`({a['tamamlama_orani']})" for a in b2b_park)
        satirlar.append(f"📦 *B2B Park ({len(b2b_park)}):* {park_ozet}")
        satirlar.append("")

    if not analizler:
        satirlar.append("📂 `02_Urunler/` altında henüz aktif ürün bulunmuyor.")

    satirlar.append("💡 Detay için `/ozet <sku>` yazabilir veya aşağıdaki butona basabilirsiniz.")

    butonlar: list[list[dict[str, str]]] = []
    b2c_butonlar = [
        {"text": f"📊 {a['sku'][:16]} ({a['tamamlama_orani']})", "callback_data": _callback_kisalt("urun:ozet:", a["sku"])}
        for a in b2c[:6]
    ]
    for i in range(0, len(b2c_butonlar), 2):
        butonlar.append(b2c_butonlar[i : i + 2])

    butonlar.append(
        [
            {"text": "🔄 Özeti Yenile", "callback_data": "urun:ozet_tumu"},
            {"text": "🔎 B2C Öneriler", "callback_data": "b2c:vitrin"},
            {"text": "🤖 Ajanlar", "callback_data": "ajan:liste"},
        ]
    )
    return "\n".join(satirlar), butonlar


def tek_urun_ozet_metni(
    sku: str,
    erp_urunler: list[dict[str, Any]] | None = None,
    urunler_klasoru: Path | None = None,
    konsept_klasoru: Path | None = None,
) -> tuple[str, Path | None, list[list[dict[str, str]]]]:
    """Tek bir SKU için tüm 6 aşamanın dosya & hazırbulunuşluk detayını üretir."""
    urun_kok = urunler_klasoru or URUNLER_KLASORU
    if not (urun_kok / sku).is_dir():
        return (
            f"❌ `{sku}` klasörü `02_Urunler/` altında bulunamadı.",
            None,
            [[{"text": "📊 Tüm Özeti Gör", "callback_data": "urun:ozet_tumu"}]],
        )

    erp_sku_set = (
        {str(u.get("sku") or "") for u in erp_urunler if isinstance(u, dict) and u.get("sku")}
        if erp_urunler is not None
        else None
    )
    a = urun_asama_analiz_et(
        sku,
        erp_sku_set=erp_sku_set,
        urunler_klasoru=urun_kok,
        konsept_klasoru=konsept_klasoru,
    )
    d = a["detay"]
    bar = _ilerleme_cubugu(a["tamam_sayisi"], a["toplam_adim"])

    satirlar = [
        f"📦 *{_md_temizle(a['ad'])}* (`{a['sku']}`)",
        f"İlerleme: *{a['tamamlama_orani']}* `{bar}` • Durum: `{a['durum']}` • CEO: `{_md_temizle(a['ceo_denetim'])}`",
    ]
    if a.get("fiyat_tl"):
        satirlar.append(f"Önerilen Fiyat: `{a['fiyat_tl']} TL`")
    boyut = d.get("boyut_mm") or {}
    if all(k in boyut for k in ("x", "y", "z")):
        satirlar.append(f"Ölçü: `{boyut['x']} × {boyut['y']} × {boyut['z']} mm`")

    satirlar.append("\n*Aşama Kontrolü:*")
    detay_not = {
        "Ar-Ge": "urun.yaml + Ar-Ge md" if d["arge_md"] else ("urun.yaml var" if a["adimlar"][0][1] else "eksik"),
        "3B CAD": f"{d['cad_sayisi']} model" if d["cad_sayisi"] else "STL/3MF yok",
        "Render": f"{d['render_sayisi']} görsel" if d["render_sayisi"] else "render yok",
        "Üretim": ", ".join(d["uretim_dosyalari"]) if d["uretim_dosyalari"] else "Orca profili yok",
        "Medya/Kart": f"{d['kart_sayisi']} kart, {d['video_sayisi']} video" if (d["kart_sayisi"] or d["video_sayisi"]) else "video/kart yok",
        "ERP/Mağaza": (
            f"SEO:{'ok' if d['seo_ok'] else 'yok'} • ERP:{'ok' if d['erp_var'] else 'yok'} • İkas:{'canlı' if d['ikas_ok'] else 'yok'}"
        ),
    }
    for isim, ok in a["adimlar"]:
        ikon = "✅" if ok else "⬜"
        satirlar.append(f"{ikon} *{isim}*: `{detay_not[isim]}`")

    orca = d.get("orca_ozet") or {}
    if orca:
        parcalar = [f"{k}={v}" for k, v in list(orca.items())[:4]]
        satirlar.append(f"\n⚙️ Orca: `{', '.join(parcalar)}`")

    satirlar.append(f"\n➡️ *Sıradaki Adım:* {a['siradaki_adim']}")

    butonlar = [
        [
            {"text": "🌊 Flow Video", "callback_data": _callback_kisalt("flow:uret:", sku)},
            {"text": "🎬 Kurgu / Kartlar", "callback_data": _callback_kisalt("medya:uret:", sku)},
        ],
        [
            {"text": "⚙️ Dilimleme", "callback_data": _callback_kisalt("orca:analiz:", sku)},
            {"text": "📊 Tüm Ürün Özeti", "callback_data": "urun:ozet_tumu"},
        ],
    ]
    return "\n".join(satirlar), a["onizleme_yolu"], butonlar
