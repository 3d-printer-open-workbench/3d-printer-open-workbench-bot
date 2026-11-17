"""Ekran görüntüsünden / fotoğraftan DOĞRU filament rengi (palete eklemek için).

Sorun: tüm görselin baskın renkleri sitenin arayüzünü (başlık, buton, arka plan) da toplar. Çözüm iki adım:

1) `adaylar`: görsel düz renk kümelerine bölünür (Lab uzayında nicemleme + bağlı bölgeler); her aday bölge
   numaralı kutuyla işaretlenir (`isaretli.png`) → YZ ajanı yalnızca **hangi numaralı bölgelerin filament /
   basılmış ürün** olduğunu ve rengin adını söyler (sayı uydurmaz).
2) `olc`: seçilen bölgelerin pikselleri ölçülür — kenarlar aşındırılır, parlama ve gölge (L*'ın uç %20'leri)
   atılır, Lab medyanı alınır → HEX. Yayılma (ΔE) yüksekse "ışık/gölge fazla, tahmini" uyarısı verilir.
   Ekranda yazılı bir HEX varsa o da gösterilir ve ölçümle farkı (ΔE) raporlanır.

Kullanım (.venv-ai3d):
    python -m coo.renk_al adaylar <gorsel> <klasor>
    python -m coo.renk_al olc <gorsel> <klasor> '<secim.json>'      (secim: {"renkler":[{"ad","bolgeler":[..],...}]})
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

MAKS_KENAR = 900          # aday bulma çözünürlüğü
KUME = 28                 # nicemleme renk sayısı
MIN_ALAN = 0.0012         # görselin %0,12'sinden küçük bölgeler aday değil
MAKS_ADAY = 40


# --- renk uzayı ---------------------------------------------------------------------------------------------
def srgb_lab(rgb: np.ndarray) -> np.ndarray:
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def lab_srgb(lab: np.ndarray) -> np.ndarray:
    lab = np.asarray(lab, np.float64)
    fy = (lab[..., 0] + 16) / 116
    fx, fz = fy + lab[..., 1] / 500, fy - lab[..., 2] / 200
    e = 216 / 24389

    def ters(f):
        return np.where(f ** 3 > e, f ** 3, (116 * f - 16) / (24389 / 27))
    xyz = np.stack([ters(fx), np.where(lab[..., 0] > 8, fy ** 3, lab[..., 0] / (24389 / 27)), ters(fz)], -1)
    xyz = xyz * np.array([0.95047, 1.0, 1.08883])
    m = np.array([[3.2404542, -1.5371385, -0.4985314], [-0.9692660, 1.8760108, 0.0415560],
                  [0.0556434, -0.2040259, 1.0572252]])
    c = np.clip(xyz @ m.T, 0, 1)
    c = np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)
    return np.clip(np.round(c * 255), 0, 255).astype(int)


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(int(v) for v in rgb))


def delta_e(h1: str, h2: str) -> float:
    a, b = srgb_lab(np.array([hex_rgb(h1), hex_rgb(h2)]))
    return float(np.linalg.norm(a - b))


# --- 1) aday bölgeler ---------------------------------------------------------------------------------------
def _yazi_tipi(boyut: int):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, boyut)
    return ImageFont.load_default()


def adaylar(gorsel: Path, klasor: Path) -> dict:
    from scipy import ndimage

    klasor.mkdir(parents=True, exist_ok=True)
    asil = Image.open(gorsel).convert("RGB")
    k = min(1.0, MAKS_KENAR / max(asil.size))
    im = asil.resize((round(asil.width * k), round(asil.height * k)), Image.LANCZOS) if k < 1 else asil
    # gürültüyü azalt, sonra Lab'a yakın algıyla nicemle (PIL median-cut)
    q = im.quantize(KUME, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    idx = np.asarray(q)
    toplam = idx.size
    etiket = np.zeros(idx.shape, np.int32)
    bolgeler = []
    for renk in np.unique(idx):
        lab_, n = ndimage.label(idx == renk)
        if n == 0:
            continue
        alanlar = ndimage.sum(np.ones_like(lab_), lab_, index=np.arange(1, n + 1))
        for j, alan in enumerate(alanlar, start=1):
            if alan / toplam < MIN_ALAN:
                continue
            ys, xs = np.nonzero(lab_ == j)
            bolgeler.append({"alan": int(alan), "kutu": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                             "_maske": (lab_ == j)})
    bolgeler.sort(key=lambda b: -b["alan"])
    bolgeler = bolgeler[:MAKS_ADAY]
    for no, b in enumerate(bolgeler, start=1):
        etiket[b.pop("_maske")] = no
        b["no"] = no
    np.save(klasor / "etiket.npy", etiket)

    # işaretli görsel: her bölgenin dış çizgisi + numara rozeti
    isaret = im.copy().convert("RGBA")
    kat = Image.new("RGBA", isaret.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(kat)
    yazi = _yazi_tipi(max(14, im.width // 45))
    kenar = ndimage.binary_dilation(etiket > 0) & ~ndimage.binary_erosion(etiket > 0)
    for b in bolgeler:
        m = etiket == b["no"]
        sinir = m & ~ndimage.binary_erosion(m)
        ys, xs = np.nonzero(sinir)
        for x, y in zip(xs[::2], ys[::2]):
            d.point((int(x), int(y)), fill=(255, 0, 180, 255))
        cy, cx = ndimage.center_of_mass(m)
        if not m[int(cy), int(cx)]:  # içbükey bölge: merkez dışarıda kalırsa bölgenin bir pikseli
            yy, xx = np.nonzero(m)
            cy, cx = yy[len(yy) // 2], xx[len(xx) // 2]
        t = str(b["no"])
        w, h = d.textbbox((0, 0), t, font=yazi)[2:]
        d.rounded_rectangle((cx - w / 2 - 4, cy - h / 2 - 3, cx + w / 2 + 4, cy + h / 2 + 5), 4, fill=(255, 0, 180, 235))
        d.text((cx - w / 2, cy - h / 2), t, fill="white", font=yazi)
    del kenar
    Image.alpha_composite(isaret, kat).convert("RGB").save(klasor / "isaretli.png")
    im.save(klasor / "kaynak.png")
    rapor = {"gorsel": str(gorsel), "olcek": k, "bolge_sayisi": len(bolgeler), "bolgeler": bolgeler,
             "isaretli": str(klasor / "isaretli.png"), "kaynak": str(klasor / "kaynak.png")}
    (klasor / "adaylar.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    return rapor


# --- 2) ölçüm -----------------------------------------------------------------------------------------------
def _olc_maske(rgb: np.ndarray, maske: np.ndarray) -> dict:
    from scipy import ndimage

    m = ndimage.binary_erosion(maske, iterations=2)
    if m.sum() < 30:
        m = maske
    lab = srgb_lab(rgb[m])
    L = lab[:, 0]
    lo, hi = np.percentile(L, [20, 80])
    sec = lab[(L >= lo) & (L <= hi)] if ((L >= lo) & (L <= hi)).sum() >= 20 else lab
    merkez = np.median(sec, axis=0)
    yayilma = float(np.median(np.linalg.norm(sec - merkez, axis=1)))
    return {"hex": rgb_hex(lab_srgb(merkez)), "lab": [round(float(v), 2) for v in merkez],
            "yayilma_de": round(yayilma, 2), "piksel": int(m.sum())}


def olc(gorsel: Path, klasor: Path, secim: dict) -> dict:
    kaynak = Image.open(klasor / "kaynak.png").convert("RGB")
    rgb = np.asarray(kaynak)
    etiket = np.load(klasor / "etiket.npy")
    sonuc = []
    for r in secim.get("renkler") or []:
        nolar = [int(n) for n in r.get("bolgeler") or []]
        maske = np.isin(etiket, nolar) if nolar else np.zeros(etiket.shape, bool)
        if maske.sum() == 0:
            sonuc.append({**r, "hata": "seçilen bölge bulunamadı"})
            continue
        o = _olc_maske(rgb, maske)
        kayit = {**r, **o}
        y = (r.get("yazili_hex") or "").strip()
        if y and len(y.lstrip("#")) == 6:
            kayit["yazili_hex"] = "#" + y.lstrip("#").upper()
            kayit["yazili_fark_de"] = round(delta_e(kayit["yazili_hex"], o["hex"]), 1)
        kayit["guven"] = "yüksek" if o["yayilma_de"] < 4 else ("orta" if o["yayilma_de"] < 8 else "düşük (ışık/gölge fazla)")
        ys, xs = np.nonzero(maske)
        kayit["kutu"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        sonuc.append(kayit)
    rapor = {"renkler": sonuc}
    rapor["onizleme"] = str(onizleme(kaynak, etiket, sonuc, klasor / "renkler.png"))
    (klasor / "olcum.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    return rapor


def onizleme(kaynak: Image.Image, etiket: np.ndarray, renkler: list[dict], hedef: Path) -> Path:
    """Her renk için: kaynaktan bölge kesiti (çerçeveli) | ölçülen düz renk | ad, HEX, güven."""
    satir_h, gen = 220, 1100
    gecerli = [r for r in renkler if r.get("hex")]
    im = Image.new("RGB", (gen, max(1, len(gecerli)) * satir_h + 20), "white")
    d = ImageDraw.Draw(im)
    b1, b2 = _yazi_tipi(34), _yazi_tipi(24)
    for i, r in enumerate(gecerli):
        y0 = 10 + i * satir_h
        x0, ya, x1, yb = r["kutu"]
        pay = 12
        kes = kaynak.crop((max(0, x0 - pay), max(0, ya - pay), min(kaynak.width, x1 + pay), min(kaynak.height, yb + pay)))
        kes.thumbnail((300, satir_h - 20))
        im.paste(kes, (10, y0 + (satir_h - 20 - kes.height) // 2))
        d.rectangle((330, y0, 520, y0 + satir_h - 20), fill=r["hex"], outline="#999999")
        d.text((545, y0 + 10), f"{r.get('ad', '')}", fill="black", font=b1)
        alt = " · ".join(x for x in (r.get("marka"), r.get("malzeme")) if x)
        d.text((545, y0 + 58), r["hex"] + (f"   ({alt})" if alt else ""), fill="#333333", font=b2)
        d.text((545, y0 + 94), f"Güven: {r['guven']}  (yayılma ΔE {r['yayilma_de']})", fill="#555555", font=b2)
        if r.get("yazili_hex"):
            d.text((545, y0 + 130), f"Sayfada yazan: {r['yazili_hex']} (fark ΔE {r['yazili_fark_de']})", fill="#555555", font=b2)
    im.save(hedef)
    return hedef


def main() -> None:
    komut, gorsel, klasor = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    if komut == "adaylar":
        r = adaylar(gorsel, klasor)
        print(json.dumps({"bolge_sayisi": r["bolge_sayisi"], "isaretli": r["isaretli"]}, ensure_ascii=False))
    elif komut == "olc":
        print(json.dumps(olc(gorsel, klasor, json.loads(sys.argv[4])), ensure_ascii=False))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
