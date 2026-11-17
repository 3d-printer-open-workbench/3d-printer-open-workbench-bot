"""Renk örneği → baskın renkler → renk başına Blender e-ticaret görselleri → mağaza varyantları.

Patron Telegram'dan bir fotoğraf/ekran görüntüsü yollar; baskın renkler Pillow median-cut ile çıkarılır
(numpy gerekmez, bot sistem Python'unda çalışır). Seçilen her renk için ürün o renkte render edilir:
`gorsel/renkler/<renk-slug>/{beyaz,studyo,yakin,seffaf}.png`. Renkler `urun.yaml > renkler` listesine yazılır;
mağaza paketi bunları "Renk" varyantı olarak kullanır.

Not: Görsel rengi, gerçekte basılacak filamentin rengiyle eşleşmelidir — Patron o renkte filamentin
olduğunu teyit etmeden ürün o renkte satışa açılmamalıdır (önizleme mesajında hatırlatılır).
"""
from __future__ import annotations

import colorsys
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFont

from .ayar import COO_KLASORU, PROGRAMLAR_KLASORU, URUNLER_KLASORU

BLENDER_BETIK = COO_KLASORU / "gorsel" / "blender_ciz.py"
MIN_PAY = 0.04  # %4'ten küçük renk kümeleri (gürültü, kenar) atılır
BIRLESTIRME_MESAFESI = 28.0  # RGB uzayında bu kadar yakın renkler tek renk sayılır

# Türkçe renk adları (en yakın komşu). Filament piyasasındaki yaygın adlar.
RENK_ADLARI: dict[str, tuple[int, int, int]] = {
    "Beyaz": (245, 245, 242), "Krem": (236, 226, 204), "Bej": (214, 196, 166), "Kemik": (228, 218, 196),
    "Açık Gri": (190, 190, 190), "Gri": (128, 128, 128), "Koyu Gri": (100, 98, 96), "Antrasit": (60, 62, 66),
    "Siyah": (22, 22, 22), "Vizon": (156, 140, 122), "Kum": (200, 182, 150), "Taş": (176, 168, 156),
    "Kahverengi": (110, 72, 44), "Karamel": (176, 112, 58), "Toprak": (168, 98, 66), "Terakota": (196, 98, 70),
    "Kırmızı": (200, 32, 36), "Bordo": (118, 26, 40), "Pembe": (236, 150, 172), "Pudra": (230, 190, 186),
    "Somon": (240, 140, 112), "Turuncu": (238, 120, 30), "Hardal": (204, 160, 40), "Sarı": (246, 210, 40),
    "Fıstık Yeşili": (170, 200, 110), "Yeşil": (40, 140, 70), "Zeytin Yeşili": (110, 116, 60),
    "Adaçayı": (156, 175, 136), "Mint": (162, 222, 196), "Koyu Yeşil": (24, 82, 52), "Turkuaz": (40, 180, 180),
    "Bebek Mavisi": (160, 200, 230), "Mavi": (40, 100, 200), "Lacivert": (28, 40, 90), "Petrol": (20, 90, 104),
    "Lila": (190, 160, 210), "Mor": (110, 50, 140), "Altın": (200, 168, 80), "Gümüş": (176, 178, 182),
}


def hex_yap(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def hex_coz(hex_kod: str) -> tuple[int, int, int]:
    h = hex_kod.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mesafe(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    # "redmean" yaklaşık algısal RGB mesafesi
    rm = (a[0] + b[0]) / 2
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return ((2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db) ** 0.5 / 3


def renk_adi(rgb: tuple[int, int, int]) -> str:
    return min(RENK_ADLARI, key=lambda ad: _mesafe(rgb, RENK_ADLARI[ad]))


def renk_slug(ad: str, hex_kod: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ ", "cgiosuCGIOSU-")
    return f"{ad.translate(tr).lower()}-{hex_kod.lstrip('#').lower()}"


def baskin_renkler(gorsel: Path, adet: int = 5) -> list[dict[str, Any]]:
    """Görseldeki baskın renkleri pay sırasıyla döndürür: [{hex, rgb, ad, pay}]."""
    img = Image.open(gorsel).convert("RGB")
    img.thumbnail((320, 320))
    q = img.quantize(colors=12, method=Image.Quantize.MEDIANCUT)
    palet = q.getpalette() or []
    sayimlar = sorted(q.getcolors() or [], reverse=True)
    toplam = sum(n for n, _ in sayimlar) or 1

    kumeler: list[dict[str, Any]] = []
    for n, idx in sayimlar:
        rgb = tuple(palet[idx * 3: idx * 3 + 3])
        for k in kumeler:
            if _mesafe(rgb, k["rgb"]) < BIRLESTIRME_MESAFESI:
                w = k["n"] + n  # ağırlıklı ortalama
                k["rgb"] = tuple(round((k["rgb"][i] * k["n"] + rgb[i] * n) / w) for i in range(3))
                k["n"] = w
                break
        else:
            kumeler.append({"rgb": rgb, "n": n})

    sonuc = []
    for k in sorted(kumeler, key=lambda k: -k["n"]):
        pay = k["n"] / toplam
        if pay < MIN_PAY:
            continue
        rgb = tuple(int(x) for x in k["rgb"])
        sonuc.append({"hex": hex_yap(rgb), "rgb": rgb, "ad": renk_adi(rgb), "pay": round(pay, 3)})
    return sonuc[:adet]


def palet_gorseli(renkler: list[dict[str, Any]], hedef: Path) -> Path:
    """Numaralı renk şeridi (Telegram önizlemesi)."""
    w, h = 1200, 420
    img = Image.new("RGB", (w, h), (250, 248, 244))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 30)
        kucuk = ImageFont.truetype("DejaVuSans.ttf", 24)
    except OSError:
        font = kucuk = ImageFont.load_default()
    n = max(len(renkler), 1)
    gen = w // n
    for i, r in enumerate(renkler):
        x0 = i * gen
        d.rectangle([x0 + 10, 10, x0 + gen - 10, 300], fill=r["rgb"])
        _, _, v = colorsys.rgb_to_hsv(*(c / 255 for c in r["rgb"]))
        yazi = (255, 255, 255) if v < 0.55 else (30, 30, 30)
        d.text((x0 + 26, 24), str(i + 1), fill=yazi, font=font)
        d.text((x0 + 14, 315), r["ad"], fill=(30, 30, 30), font=font)
        d.text((x0 + 14, 360), f"{r['hex']}  %{round(r['pay'] * 100)}", fill=(90, 90, 90), font=kucuk)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    img.save(hedef)
    return hedef


def katman_mm(kok: Path, varsayilan: float = 0.20) -> float:
    """Render dokusu için ürünün gerçek katman yüksekliği (urun.yaml > dilimleme.katman_mm)."""
    yol = kok / "urun.yaml"
    try:
        veri = yaml.safe_load(yol.read_text(encoding="utf-8")) or {}
        deger = float((veri.get("dilimleme") or {}).get("katman_mm") or varsayilan)
    except (OSError, ValueError, TypeError, yaml.YAMLError):
        return varsayilan
    return deger if 0.04 <= deger <= 0.6 else varsayilan


def renk_gorselleri_uret(sku: str, renk: dict[str, Any], urunler_klasoru: Path | None = None,
                         zaman_asimi: int = 1200) -> dict[str, Any]:
    """Tek renk için Blender görsellerini üretir (bloklayıcı; to_thread + GPU kilidiyle çağır)."""
    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    stl = kok / "model" / f"{sku}.stl"
    if not stl.exists():
        return {"basarili": False, "hata": f"STL yok: model/{sku}.stl"}
    slug = renk_slug(renk["ad"], renk["hex"])
    cikti = kok / "gorsel" / "renkler" / slug
    cikti.mkdir(parents=True, exist_ok=True)
    try:
        s = subprocess.run(
            ["blender", "-b", "-P", str(BLENDER_BETIK), "--", "--stl", str(stl), "--cikti", str(cikti),
             "--renk", renk["hex"], "--katman-mm", str(katman_mm(kok))],
            cwd=str(PROGRAMLAR_KLASORU), capture_output=True, text=True, timeout=zaman_asimi,
        )
    except subprocess.TimeoutExpired:
        return {"basarili": False, "hata": f"Blender zaman aşımı ({zaman_asimi} sn)"}
    gorseller = [str(p.relative_to(kok)) for ad in ("beyaz.png", "studyo.png", "yakin.png")
                 if (p := cikti / ad).exists()]
    if not gorseller:
        return {"basarili": False, "hata": "render çıkmadı", "log": ((s.stdout or "") + (s.stderr or ""))[-1200:]}
    return {"basarili": True, "ad": renk["ad"], "hex": renk["hex"], "slug": slug,
            "klasor": str(cikti.relative_to(kok)), "gorseller": gorseller}


def urun_renklerini_kaydet(sku: str, yeni: list[dict[str, Any]], urunler_klasoru: Path | None = None) -> list[dict]:
    """urun.yaml > renkler listesini (slug'a göre) günceller ve son listeyi döndürür."""
    yol = (urunler_klasoru or URUNLER_KLASORU) / sku / "urun.yaml"
    veri = yaml.safe_load(yol.read_text(encoding="utf-8")) if yol.exists() else {}
    mevcut = {r.get("slug"): r for r in (veri.get("renkler") or []) if isinstance(r, dict)}
    for r in yeni:
        mevcut[r["slug"]] = {k: r[k] for k in ("ad", "hex", "slug", "klasor", "gorseller")}
    veri["renkler"] = list(mevcut.values())
    yol.write_text(yaml.safe_dump(veri, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return veri["renkler"]


def renkler_veriden(veri: dict[str, Any]) -> list[dict[str, Any]]:
    """Ürünün geçerli renk(ler)i. Çok renk onaylıysa tek giriş: çok renkli render klasörü (e-ticaret görselleri ve
    mağaza bu render'dan çekilir); tek renk varyantları ise urun.yaml > renkler."""
    cr = veri.get("cok_renk") if isinstance(veri.get("cok_renk"), dict) else {}
    if cr.get("karar") == "onay":
        rk = [r for r in cr.get("renkler") or [] if isinstance(r, dict)]
        return [{"ad": f"Çok renk: {cr.get('sema') or ''}".strip(), "hex": (rk[0].get("hex") if rk else None),
                 "slug": "cok-renk", "klasor": "model/cok_renk/render", "cok_renk": True,
                 "filamentler": [r.get("hex") for r in rk]}]
    return [r for r in (veri.get("renkler") or []) if isinstance(r, dict) and not r.get("cok_renk")]


def urun_renkleri(sku: str, urunler_klasoru: Path | None = None) -> list[dict[str, Any]]:
    yol = (urunler_klasoru or URUNLER_KLASORU) / sku / "urun.yaml"
    if not yol.exists():
        return []
    return renkler_veriden(yaml.safe_load(yol.read_text(encoding="utf-8")) or {})


def aciklamadan_renk_sku(aciklama: str) -> str | None:
    """Fotoğraf açıklaması 'renk <sku>' ise sku'yu döndürür."""
    m = re.match(r"^\s*renk\s+([a-z0-9-]+)\s*$", aciklama or "", flags=re.I)
    return m.group(1).lower() if m else None
