"""Pazar araştırması → satılabilir fiyat bandı → mağaza fiyat kararı.

Akış:
1. Konsept seçilip 3B üretime geçildiğinde (veya ürün kartındaki "💹 Pazar Fiyatı" ile) Claude
   (`trend-researcher`) benzer ürünleri canlı internetten bulur ve `pazar/fiyat.json` yazar.
   Uydurma yok: her fiyatın açılmış sayfa URL'si ve tarihi vardır.
2. `pazar_ozeti` benzerlik ≥2 olan Türkiye fiyatlarından P25 / medyan / P75 bandını hesaplar.
3. Mağazaya Hazırla'da `fiyat_onerisi` ERP maliyet tabanı ile pazar bandını birleştirir; Patron
   Telegram'da önerilen / ERP / pazar medyanı / elle fiyat arasından seçer.

Saf işlevlerdir; Telegram'a bağlı değildir.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any

from .ayar import URUNLER_KLASORU

MIN_ORNEK = 3


def pazar_yolu(sku: str, urunler_klasoru: Path | None = None) -> Path:
    return (urunler_klasoru or URUNLER_KLASORU) / sku / "pazar" / "fiyat.json"


def pazar_istemi(sku: str, urunler_klasoru: Path | None = None) -> str:
    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    konseptler = sorted(str(p) for p in (kok / "konsept").glob("flow-*"))
    refler = sorted(str(p) for p in (kok / "konsept" / "referans").glob("ref-*"))
    bugun = dt.date.today().isoformat()
    return (
        f"Görev: `{sku}` ürünü için PAZAR FİYAT ARAŞTIRMASI. Ürünü değiştirme, başka dosyaya dokunma.\n"
        f"Ürün bilgisi: `02_Urunler/{sku}/urun.yaml` (fikir, yükseklik, saksı mı). "
        f"Seçilen konsept görselleri: {', '.join(konseptler) or '—'}. Referanslar: {', '.join(refler) or '—'}.\n"
        "Görselleri Read ile incele; ürünün türünü, boyutunu ve tarzını anla.\n\n"
        "1) WebSearch + WebFetch ile BENZER ürünleri bul (en az 6, ideal 8-12):\n"
        "   Öncelik Türkiye: Trendyol, Hepsiburada, Amazon.com.tr, n11, Etsy TR fiyatları, İkas/Shopify mağazaları. "
        "Ek olarak Etsy (global) 2-4 örnek.\n"
        "   Benzerlik ölçütü: aynı ürün tipi (ör. figürlü/karakterli saksı), benzer boyut (±%40), benzer malzeme "
        "(3B baskı / reçine / seramik dekor). Her örneğe benzerlik puanı ver: 3=neredeyse aynı tip ve boyut, "
        "2=aynı tip farklı boyut/malzeme, 1=uzak.\n"
        "2) DOĞRULUK: Yalnızca bizzat açtığın ürün sayfasında GÖRDÜĞÜN fiyatı yaz. Arama sonucu özetinden, "
        "grounding/redirect linkinden veya tahminle fiyat YAZMA. İndirimli fiyat varsa satış fiyatını yaz ve "
        "`not` alanına liste fiyatını ekle. Yabancı para: aynı gün bir kaynaktan kuru al, `kur` alanına "
        "kaynak URL ile yaz ve TL'ye çevir.\n"
        "3) Satış sinyali varsa kaydet: yorum sayısı, favori, 'çok satan' rozeti (yoksa null).\n"
        f"4) `02_Urunler/{sku}/pazar/fiyat.json` dosyasını yaz:\n"
        '   {"sku","tarih":"' + bugun + '","sorgular":[kullandığın aramalar],"kur":{"USD":..,"EUR":..,"kaynak":url}|null,'
        '"ornekler":[{"ad","platform","url","fiyat_tl","para_birimi","orijinal_fiyat","kargo_dahil":bool|null,'
        '"olcu","malzeme","benzerlik":1-3,"yorum_sayisi","favori","ulke":"TR"|"GLOBAL","not"}],'
        '"yorum":"2-3 cümle: pazarın fiyat yapısı, bizim ürünün konumu, farklılaştırıcı"}\n'
        "5) Son satır: `PAZAR_HAZIR <örnek sayısı>` veya yeterli veri yoksa `PAZAR_EKSIK <neden>`."
    )


def _yuzdelik(degerler: list[float], p: float) -> float:
    s = sorted(degerler)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p
    alt, ust = math.floor(k), math.ceil(k)
    return s[alt] + (s[ust] - s[alt]) * (k - alt)


def pazar_oku(sku: str, urunler_klasoru: Path | None = None) -> dict[str, Any] | None:
    yol = pazar_yolu(sku, urunler_klasoru)
    if not yol.exists():
        return None
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def pazar_ozeti(veri: dict[str, Any] | None) -> dict[str, Any] | None:
    """Benzerlik ≥2, URL'li ve fiyatlı Türkiye örneklerinden fiyat bandı. Yetersizse global örnekler de eklenir."""
    if not veri:
        return None
    gecerli = []
    for o in veri.get("ornekler") or []:
        try:
            fiyat = float(o.get("fiyat_tl") or 0)
            benzerlik = int(o.get("benzerlik") or 0)
        except (TypeError, ValueError):
            continue
        if fiyat > 0 and benzerlik >= 2 and str(o.get("url") or "").startswith("http"):
            gecerli.append({**o, "fiyat_tl": fiyat})
    tr = [o for o in gecerli if str(o.get("ulke") or "TR").upper() == "TR"]
    kullanilan = tr if len(tr) >= MIN_ORNEK else gecerli
    if len(kullanilan) < MIN_ORNEK:
        return {"yeterli": False, "ornek": len(kullanilan), "toplam": len(veri.get("ornekler") or [])}
    fiyatlar = [o["fiyat_tl"] for o in kullanilan]
    return {
        "yeterli": True,
        "ornek": len(kullanilan),
        "kapsam": "TR" if kullanilan is tr else "TR+GLOBAL",
        "alt": round(_yuzdelik(fiyatlar, 0.25), 2),
        "medyan": round(statistics.median(fiyatlar), 2),
        "ust": round(_yuzdelik(fiyatlar, 0.75), 2),
        "min": min(fiyatlar),
        "max": max(fiyatlar),
        "tarih": veri.get("tarih"),
    }


def psikolojik_fiyat(tutar: float) -> float:
    """Yukarı yuvarlar: <200 TL → x9,90; <1000 → x49,90/x99,90; üstü → x99,90."""
    if tutar <= 0:
        return 0.0
    adim = 10 if tutar < 200 else 50 if tutar < 1000 else 100
    return round(math.ceil((tutar + 0.10) / adim) * adim - 0.10, 2)


def fiyat_coz(metin: str) -> float | None:
    """'499,90' / '1.299,90 TL' / '499.9' → float."""
    t = re.sub(r"[^\d.,]", "", metin or "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", t):
        t = t.replace(".", "")
    try:
        deger = float(t)
    except ValueError:
        return None
    return round(deger, 2) if deger > 0 else None


def fiyat_onerisi(maliyet: dict[str, Any], ozet: dict[str, Any] | None) -> dict[str, Any]:
    """ERP maliyet tabanı + pazar bandı → önerilen satış fiyatı ve gerekçe.

    Kural: başa başın altına asla inilmez. Pazar verisi yeterliyse hedef pazar medyanıdır (ERP önerisi
    medyanın altındaysa marj yükseltilir); ERP önerisi pazar üst bandını aşıyorsa uyarı verilir.
    """
    basa_bas = float(maliyet.get("basa_bas_tl") or 0)
    erp = float(maliyet.get("erp_onerilen_tl") or 0)
    birim = float(maliyet.get("birim_maliyet_tl") or 0)
    taban = max(basa_bas, birim)
    if not ozet or not ozet.get("yeterli"):
        onerilen = psikolojik_fiyat(max(erp, taban))
        return {"onerilen_tl": onerilen, "konum": "PAZAR_VERISI_YOK",
                "gerekce": "Yeterli pazar verisi yok; ERP maliyet önerisi kullanıldı.", "secenekler": _secenekler(
                    onerilen, erp, None)}
    medyan, alt, ust = ozet["medyan"], ozet["alt"], ozet["ust"]
    if erp > ust:
        onerilen = psikolojik_fiyat(max(erp, taban))
        konum, gerekce = "PAZARIN_USTUNDE", (
            f"ERP önerisi ({erp:.0f} TL) pazarın üst bandını ({ust:.0f} TL) aşıyor; satış zor olabilir. "
            "Maliyeti düşürmeyi (daha küçük ölçü, daha az dolgu) veya premium konumlamayı düşünün.")
    elif erp >= medyan:
        onerilen = psikolojik_fiyat(erp)
        konum, gerekce = "PAZAR_BANDINDA", f"ERP önerisi pazar bandında (medyan {medyan:.0f}, üst {ust:.0f} TL)."
    else:
        onerilen = psikolojik_fiyat(max(medyan, taban))
        konum, gerekce = "MARJ_FIRSATI", (
            f"Pazar medyanı ({medyan:.0f} TL) ERP önerisinin ({erp:.0f} TL) üstünde; fiyat medyana çekildi.")
    if onerilen < taban:
        onerilen = psikolojik_fiyat(taban)
    marj = round((onerilen - birim) / onerilen * 100, 1) if onerilen and birim else None
    return {"onerilen_tl": onerilen, "konum": konum, "gerekce": gerekce, "marj_yuzde": marj,
            "pazar": {"alt": alt, "medyan": medyan, "ust": ust, "ornek": ozet["ornek"]},
            "secenekler": _secenekler(onerilen, erp, medyan, taban)}


def _secenekler(onerilen: float, erp: float, medyan: float | None, taban: float = 0) -> list[dict[str, Any]]:
    secenekler = [{"ad": "Önerilen", "tl": onerilen}]
    if erp:
        secenekler.append({"ad": "ERP", "tl": psikolojik_fiyat(erp)})
    if medyan and medyan >= taban:
        secenekler.append({"ad": "Pazar medyanı", "tl": psikolojik_fiyat(medyan)})
    gorulen, tekil = set(), []
    for s in secenekler:
        if s["tl"] not in gorulen:
            gorulen.add(s["tl"])
            tekil.append(s)
    return tekil


def pazar_metni(sku: str, veri: dict[str, Any] | None, ozet: dict[str, Any] | None, en_fazla: int = 6) -> str:
    if not veri:
        return f"💹 `{sku}` için pazar araştırması yok."
    satirlar = [f"💹 *Pazar araştırması* — `{sku}` ({veri.get('tarih', '')})"]
    if ozet and ozet.get("yeterli"):
        satirlar.append(f"• *Satılabilir bant:* `{ozet['alt']:.0f}–{ozet['ust']:.0f} TL` • *medyan* `{ozet['medyan']:.0f} TL` "
                        f"({ozet['ornek']} benzer ürün, {ozet['kapsam']})")
    else:
        satirlar.append(f"⚠️ Yeterli benzer ürün fiyatı yok ({(ozet or {}).get('ornek', 0)} geçerli örnek).")
    ornekler = sorted(veri.get("ornekler") or [], key=lambda o: (-int(o.get("benzerlik") or 0), o.get("fiyat_tl") or 0))
    for o in ornekler[:en_fazla]:
        sinyal = f" • {o['yorum_sayisi']} yorum" if o.get("yorum_sayisi") else ""
        satirlar.append(f"  – {str(o.get('ad', ''))[:48]} — `{o.get('fiyat_tl')} TL` ({o.get('platform')}, "
                        f"benzerlik {o.get('benzerlik')}{sinyal})\n    {o.get('url')}")
    if veri.get("yorum"):
        satirlar.append(f"\n_{veri['yorum']}_")
    return "\n".join(satirlar)
