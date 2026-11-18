"""Teknik Poster konsepti — Flow posterine GERÇEK ürün bilgisi katmanı + 9:16 Reels karesi + Reels bitirme.

Ürün tanıtım posterinde boyut ve malzeme bilgisi bulunur. Yazıyı yapay zekâ yazmaz (rakam/harf bozar). Poster
Flow'dan gelir; bilgi bandı burada urun.yaml'dan, gerçek fontla sade bir düzenle basılır.

Kullanım (.venv-gorsel veya herhangi bir PIL ortamı):
  python -m coo.teknik_poster bilgi <sku> <poster.jpg> [--cikti gorsel/konsept/teknik_poster-3x4.png]
  python -m coo.teknik_poster dikey <sku> <poster.jpg>      → gorsel/konsept/teknik_poster-9x16.png (Veo başlangıç karesi)
  python -m coo.teknik_poster reels <sku> <veo.mp4>         → medya/konsept-teknik_poster-reels.mp4 (bilgi + site yazısı)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # depo kökü → coo paketi
from coo.ayar import MAGAZA_ADI, MAGAZA_ALAN_ADI  # noqa: E402
from coo.ayar import URUNLER_KLASORU as URUNLER  # noqa: E402
KAGIT = (244, 241, 234)
MUREKKEP = (34, 34, 36)
GRI = (120, 118, 112)
VURGU = (90, 90, 90)
SANS = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
MONO = "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf"
MONO_K = "/usr/share/fonts/truetype/noto/NotoSansMono-Bold.ttf"
SITE = MAGAZA_ALAN_ADI


def _f(yol: str, boyut: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(yol, boyut)
    except OSError:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", boyut)


def tr_buyuk(metin: str) -> str:
    """Türkçe büyük harf: i→İ, ı→I (str.upper() 'Diz'i 'DIZ' yapar)."""
    return metin.replace("i", "İ").replace("ı", "I").upper()


def baslik_satiri(ad: str, en_fazla: int = 48) -> str:
    """Poster başlığı: parantezli teknik ek atılır, sığmazsa kelime sınırında '…' ile kısaltılır."""
    import re

    temiz = re.sub(r"\s*\([^)]*\)?\s*$", "", ad).strip() or ad.strip()
    metin = tr_buyuk(temiz)
    if len(metin) <= en_fazla:
        return metin
    kesik = metin[: en_fazla - 1].rsplit(" ", 1)[0].rstrip(",;:-")
    return kesik + "…"


from coo.bilgi_verisi import _cm, bilgiler  # noqa: E402,F401


def bilgi_bandi(cizim: ImageDraw.ImageDraw, x0: int, y0: int, w: int, h: int, veri: dict, olcek: float = 1.0,
                gorunur: int = 99) -> None:
    """Bilgi bandı: üst kural + başlık satırı + 3×2 ölçü/malzeme ızgarası."""
    s = lambda v: int(v * olcek)  # noqa: E731
    cizim.line([(x0, y0), (x0 + w, y0)], fill=MUREKKEP, width=max(1, s(2)))
    cizim.text((x0, y0 + s(18)), MAGAZA_ADI.upper(), font=_f(SANS, s(26)), fill=MUREKKEP)
    cizim.text((x0 + w, y0 + s(18)), "3D BASKI", font=_f(SANS, s(22)),
               fill=MUREKKEP, anchor="ra")
    cizim.text((x0, y0 + s(56)), baslik_satiri(veri["ad"]), font=_f(MONO, s(20)), fill=GRI)
    satirlar = veri["satirlar"][:gorunur]
    sut, gy0 = 3, y0 + s(104)
    hucre_w, hucre_h = w / sut, (h - s(116)) / 2
    for i, (kod, ad, deger) in enumerate(satirlar):
        cx, cy = x0 + (i % sut) * hucre_w, gy0 + (i // sut) * hucre_h
        cizim.line([(cx, cy), (cx + hucre_w - s(24), cy)], fill=(200, 196, 188), width=1)
        cizim.text((cx, cy + s(10)), ad, font=_f(SANS, s(19)), fill=VURGU)
        cizim.text((cx, cy + s(40)), deger, font=_f(SANS, s(38)), fill=MUREKKEP)


def _kagit_tonu(p: Image.Image) -> tuple[int, int, int]:
    """Posterin kendi kağıt tonu (alt kenar şeridinin medyanı) → bant/tuval aynı renkte olur."""
    a = np.asarray(p.convert("RGB"), np.float32)
    serit = a[-max(4, a.shape[0] // 60):].reshape(-1, 3)
    return tuple(int(v) for v in np.median(serit, 0))


def bilgili_poster(sku: str, poster: Path, cikti: Path) -> Path:
    """3:4 poster: Flow posteri üstte (oran korunur), altta bilgi bandı. Çıktı 1792×2400."""
    W, H = 1792, 2400
    band_h = 420
    p = Image.open(poster).convert("RGB")
    ph = H - band_h - 40
    pw = int(p.width * ph / p.height)
    p = p.resize((pw, ph), Image.LANCZOS)
    tuval = Image.new("RGB", (W, H), _kagit_tonu(p))
    tuval.paste(p, ((W - pw) // 2, 24))
    m = (W - pw) // 2 + 60
    bilgi_bandi(ImageDraw.Draw(tuval), m, ph + 52, W - 2 * m, band_h - 40, bilgiler(sku))
    rng = np.random.default_rng(3)  # hafif kağıt greni (posterle uyum)
    a = np.asarray(tuval, np.float32) + rng.normal(0, 2.0, (H, W, 1))
    cikti.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(cikti)
    return cikti


def dikey_kare(poster: Path, cikti: Path) -> Path:
    """Veo başlangıç karesi (9:16, 1080×1920): poster ortada, altta bilgi bandı için boş kağıt."""
    W, H = 1080, 1920
    p = Image.open(poster).convert("RGB")
    pw = W - 80
    ph = int(p.height * pw / p.width)
    p = p.resize((pw, ph), Image.LANCZOS)
    tuval = Image.new("RGB", (W, H), _kagit_tonu(p))
    tuval.paste(p, (40, 90))
    cikti.parent.mkdir(parents=True, exist_ok=True)
    tuval.save(cikti)
    return cikti


def reels_bitir(sku: str, veo: Path, cikti: Path, sure: float | None = None) -> Path:
    """Veo videosunun altına bilgi bandını sırayla yazar (4. sn'den itibaren) ve son 2 sn'de site adresi."""
    veri = bilgiler(sku)
    W, H = 1080, 1920
    kart_y = H - 330  # opak kağıt kartı: Veo yaklaşsa da diyagramla çakışmaz, alttaki YZ lekelerini örter
    ilk = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(veo), "-frames:v", "1", "-f", "image2pipe",
                          "-vcodec", "png", "-"], capture_output=True).stdout
    import io
    ton = _kagit_tonu(Image.open(io.BytesIO(ilk))) if ilk else KAGIT
    with tempfile.TemporaryDirectory() as td:
        katmanlar = []
        for n in range(len(veri["satirlar"]) + 1):
            k = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(k).rectangle([0, kart_y - 24, W, H], fill=ton + (255,))
            bilgi_bandi(ImageDraw.Draw(k), 70, kart_y, W - 140, 250, veri, olcek=0.62, gorunur=n)
            yol = Path(td) / f"k{n}.png"
            k.save(yol)
            katmanlar.append(yol)
        site = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(site).text((W - 70, H - 70), SITE, font=_f(MONO, 30), fill=MUREKKEP, anchor="rd")
        site.save(Path(td) / "site.png")
        if sure is None:
            sure = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                         "csv=p=0", str(veo)], capture_output=True, text=True).stdout.strip() or 8)
        girdiler = ["-i", str(veo)] + sum((["-i", str(k)] for k in katmanlar), []) + ["-i", str(Path(td) / "site.png")]
        f, onceki = [f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:"
                     f"color=0xF4F1EA,setsar=1[v0]"], "v0"
        bas = 2.0
        adim = max(0.35, (sure - 2.5 - bas) / max(1, len(katmanlar) - 1))
        for i in range(len(katmanlar)):
            t0 = 0 if i == 0 else bas + i * adim
            t1 = bas + (i + 1) * adim if i < len(katmanlar) - 1 else sure + 1
            f.append(f"[{onceki}][{i + 1}:v]overlay=0:0:enable='between(t,{t0:.2f},{t1:.2f})'[v{i + 1}]")
            onceki = f"v{i + 1}"
        f.append(f"[{onceki}][{len(katmanlar) + 1}:v]overlay=0:0:enable='gte(t,{sure - 2:.2f})',format=yuv420p[out]")
        cikti.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *girdiler, "-filter_complex", ";".join(f),
                        "-map", "[out]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-c:a", "aac",
                        "-movflags", "+faststart", str(cikti)], check=True)
    return cikti


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("islem", choices=["bilgi", "dikey", "reels"])
    ap.add_argument("sku")
    ap.add_argument("kaynak", type=Path)
    ap.add_argument("--cikti", type=Path, default=None)
    a = ap.parse_args()
    kok = URUNLER / a.sku
    if a.islem == "bilgi":
        yol = bilgili_poster(a.sku, a.kaynak, a.cikti or kok / "gorsel" / "konsept" / "teknik_poster-3x4.png")
    elif a.islem == "dikey":
        yol = dikey_kare(a.kaynak, a.cikti or kok / "gorsel" / "konsept" / "teknik_poster-9x16.png")
    else:
        yol = reels_bitir(a.sku, a.kaynak, a.cikti or kok / "medya" / "konsept-teknik_poster-reels.mp4")
    print(json.dumps({"basarili": True, "cikti": str(yol)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
