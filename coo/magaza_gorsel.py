"""Mağaza görsel hazırlığı: paket.json görselleri → İkas'a yüklenecek standart dosyalar.

Mağaza teması ürün galerisinde KARE (1:1) kullanır (örnek ölçüm: 1080×1080).
Farklı oranlı görseller (3:2 renkler vitrini, 3:4 Teknik Poster poster) KIRPILMAZ — ürün kesilmesin diye
kenar tonuyla kareye tamamlanır. Kısa kenarı 2048'in altındaysa yüksek kaliteli büyütme (Lanczos + hafif
keskinlik) yapılır; yakınlaştırmada bulanıklık azalır. Çıktı: sRGB progresif JPG (≤ ~900 KB),
SEO adı `<slug>[-<renk>]-<nn>.jpg` ve Türkçe alternatif metin.

Çıktı: `magaza/gorseller/*.jpg` + `magaza/gorseller.json`
  {"kare_px", "gorseller":[{"dosya","kaynak","alt"}], "varyantlar":[{"deger","gorseller":[...]}]}
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter, ImageOps, ImageStat

from .ayar import URUNLER_KLASORU

KARE_PX = 2048
MAKS_KB = 900

# Kaynak dosya adı → alternatif metin kalıbı ({baslik}, {renk})
ALT_KALIPLARI = [
    (r"kapak-beyaz", "{baslik}{renk} — beyaz fonda önden görünüm"),
    (r"renkler-birlikte", "{baslik} — tüm renk seçenekleri yan yana"),
    (r"doku-yakin|yakin", "{baslik}{renk} — 3B baskı yüzey dokusu yakın çekim"),
    (r"krem-fon", "{baslik}{renk} — krem fonda stüdyo çekimi"),
    (r"koyu-fon", "{baslik}{renk} — koyu fonda stüdyo çekimi"),
    (r"numune", "{baslik}{renk} — basılmış ürünün gerçek fotoğrafı"),
    (r"kullanim", "{baslik}{renk} — kullanım alanında"),
    (r"teknik_poster|konsept", "{baslik} — ölçü ve malzeme bilgili tanıtım posteri"),
]


def _slug(metin: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return re.sub(r"[^a-z0-9]+", "-", str(metin).translate(tr).lower()).strip("-")[:60] or "urun"


def alt_metin(kaynak: str, baslik: str, renk: str = "") -> str:
    ad = Path(kaynak).stem
    r = f" ({renk})" if renk else ""
    for desen, kalip in ALT_KALIPLARI:
        if re.search(desen, kaynak):
            return kalip.format(baslik=baslik, renk=r)[:125]
    return f"{baslik}{r} — ürün görseli {ad}"[:125]


def _kenar_tonu(im: Image.Image) -> tuple[int, int, int]:
    """Dış kenar şeridinin medyanı (kareye tamamlarken arka planı sürdürmek için)."""
    w, h = im.size
    s = max(2, min(w, h) // 50)
    seritler = [im.crop((0, 0, w, s)), im.crop((0, h - s, w, h)), im.crop((0, 0, s, h)), im.crop((w - s, 0, w, h))]
    medyanlar = [ImageStat.Stat(p).median for p in seritler]
    return tuple(sorted(m[c] for m in medyanlar)[1] for c in range(3))  # type: ignore[return-value]


def kareye_tamamla(im: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(im).convert("RGB")
    w, h = im.size
    if w == h:
        return im
    k = max(w, h)
    zemin = Image.new("RGB", (k, k), _kenar_tonu(im))
    zemin.paste(im, ((k - w) // 2, (k - h) // 2))
    return zemin


def boyutla(im: Image.Image, px: int = KARE_PX) -> Image.Image:
    if im.width == px:
        return im
    buyutme = im.width < px
    im = im.resize((px, px), Image.LANCZOS)
    if buyutme:  # büyütmede oluşan yumuşaklığı hafifçe geri al
        im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    return im


def jpg_kaydet(im: Image.Image, hedef: Path, maks_kb: int = MAKS_KB) -> int:
    hedef.parent.mkdir(parents=True, exist_ok=True)
    for kalite in (88, 85, 82, 78, 74, 70):
        im.save(hedef, "JPEG", quality=kalite, optimize=True, progressive=True, subsampling="4:2:0")
        if hedef.stat().st_size <= maks_kb * 1024:
            return kalite
    return kalite


def hazirla(sku: str, urunler_klasoru: Path | None = None, px: int = KARE_PX) -> dict[str, Any]:
    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    paket = json.loads((kok / "magaza" / "paket.json").read_text(encoding="utf-8"))
    baslik = str(paket.get("baslik") or sku).split(" - ")[0].split(" | ")[0].strip()
    slug = _slug(paket.get("slug") or baslik)
    cikti = kok / "magaza" / "gorseller"
    for eski in cikti.glob("*.jpg") if cikti.exists() else []:
        eski.unlink()
    sonuc: dict[str, Any] = {"kare_px": px, "gorseller": [], "varyantlar": []}
    islenen: dict[str, str] = {}

    def isle(kaynak: str, renk: str, sira: int) -> dict[str, str]:
        ad = f"{slug}{'-' + _slug(renk) if renk else ''}-{sira:02d}.jpg"
        if kaynak in islenen and not renk:
            ad = islenen[kaynak]
        else:
            im = boyutla(kareye_tamamla(Image.open(kok / kaynak)), px)
            jpg_kaydet(im, cikti / ad)
            islenen[kaynak] = ad
        return {"dosya": f"magaza/gorseller/{ad}", "kaynak": kaynak, "alt": alt_metin(kaynak, baslik, renk)}

    for i, g in enumerate(paket.get("gorseller") or [], 1):
        sonuc["gorseller"].append(isle(g, "", i))
    for v in paket.get("varyantlar") or []:
        deger = str(v.get("deger") or "")
        sonuc["varyantlar"].append({"deger": deger, "gorseller": [isle(g, deger, j)
                                                                   for j, g in enumerate(v.get("gorseller") or [], 1)]})
    (kok / "magaza" / "gorseller.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8")
    return sonuc


def gorseller_oku(sku: str, urunler_klasoru: Path | None = None) -> dict[str, Any] | None:
    yol = (urunler_klasoru or URUNLER_KLASORU) / sku / "magaza" / "gorseller.json"
    try:
        return json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else None
    except json.JSONDecodeError:
        return None


if __name__ == "__main__":
    import sys

    print(json.dumps(hazirla(sys.argv[1]), ensure_ascii=False, indent=2))
