"""Teknik Poster — yerel, açık kaynak ürün posteri şablonu (Canva/Flow gerektirmez; Inkscape ile render).

Şablon: `config/konseptler/teknik-poster-sablon.svg` (1080×1440, 3:4).
Değişken öğeler sabit `id` taşır: `marka`, `seri`, `site`, `urun_foto`, `urun_satiri`, `h1..h6` (her hücrede
`_cizgi`, `_nokta`, `_etiket`, `_deger`). Ürün yazıları YALNIZ `bilgi_verisi.bilgiler(sku)` verisinden basılır
(YZ yazı çizmez). Marka satırları yapılandırmadan gelir (ortam değişkenleri, bkz. .env.example):
  {MARKA} ← WORKBENCH_POSTER_BRAND, yoksa WORKBENCH_SHOP_NAME (büyük harf)
  {SITE}  ← WORKBENCH_POSTER_SITE, yoksa WORKBENCH_SHOP_URL'nin alan adı
  {SERI}  ← WORKBENCH_POSTER_SERIES (varsayılan "TASARIM OBJELER / 3D PRINT SERIES")
Fontlar: Inter + Roboto Mono (SIL OFL 1.1) — depoya dahil değil; kurulum README → "Local poster".

Render: Inkscape 1.4 (Flatpak, `flatpak run --user org.inkscape.Inkscape`) → yoksa sistem `inkscape` → yoksa
Google Chrome/Chromium headless. Poster üretimi Chrome oturumu / Flow / Canva gerektirmez.

Kullanım:
  python -m coo.poster_sablon <sku> [--cikti yol.png] [--foto yol.png] [--motor otomatik|inkscape|chrome]
                                    [--ad teknik-poster] [--kaydet]
Varsayılan çıktı `gorsel/konsept/<ad>-3x4.png` (eskisi `gorsel/konsept/eski/` altına taşınır) +
`<ad>-9x16.png` (coo.teknik_poster.dikey_kare).
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # depo kökü → coo paketi
from coo.ayar import CONFIG_KLASORU, MAGAZA_ADI, MAGAZA_ALAN_ADI, URUNLER_KLASORU  # noqa: E402

SABLON = CONFIG_KLASORU / "konseptler" / "teknik-poster-sablon.svg"
KONSEPT_AD = "teknik-poster"  # çıktı adı: gorsel/konsept/<ad>-3x4.png (konsept_hatti.konsept_ciktilari ile aynı)
VARSAYILAN_SERI = "TASARIM OBJELER / 3D PRINT SERIES"
GENISLIK, YUKSEKLIK = 1080, 1440
FOTO_KUTU = 640
HUCRE_SAYISI = 6
RENKLER = {"A": "#BE5C3A", "P": "#3E807C"}  # nokta: A-kodları terracotta, P-kodları teal
INKSCAPE_FLATPAK = ["flatpak", "run", "--user", "org.inkscape.Inkscape"]

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

Render = Callable[[Path, Path], None]


def tr_buyuk(metin: str) -> str:
    """Türkçe büyük harf: i→İ, ı→I (str.upper() 'Diz'i 'DIZ' yapar)."""
    return metin.replace("i", "İ").replace("ı", "I").upper()


URUN_SATIRI_MAKS = 70  # Roboto Mono 20 px + 1.2 aralık ≈ 13.2 px/karakter → 960 px satıra ~72 karakter sığar


def urun_satiri(ad: str, no: int = 1) -> str:
    """'<AD>  ·  NO. 01'. Sığmazsa önce sondaki parantezli ek atılır, yine sığmazsa kelime sınırında '…'."""
    import re

    ek = f"  ·  NO. {no:02d}"
    yer = URUN_SATIRI_MAKS - len(ek)
    metin = tr_buyuk(ad.strip())
    if len(metin) > yer:
        metin = re.sub(r"\s*\([^)]*\)?\s*$", "", metin).strip() or metin
    if len(metin) > yer:
        metin = metin[: yer - 1].rsplit(" ", 1)[0].rstrip(",;:-") + "…"
    return metin + ek


def _idler(kok: ET.Element) -> dict[str, ET.Element]:
    return {e.get("id"): e for e in kok.iter() if e.get("id")}


def marka_alanlari() -> dict[str, str]:
    """Şablondaki sabit marka satırları: {MARKA}, {SERI}, {SITE} (ortam değişkenleri → coo.ayar)."""
    marka = os.environ.get("WORKBENCH_POSTER_BRAND") or MAGAZA_ADI or "YOUR STORE"
    site = os.environ.get("WORKBENCH_POSTER_SITE") or MAGAZA_ALAN_ADI or ""
    seri = os.environ.get("WORKBENCH_POSTER_SERIES") or VARSAYILAN_SERI
    return {"marka": tr_buyuk(marka.strip()), "seri": seri.strip(), "site": site.strip().rstrip("/")}


def foto_veri_url(foto: Path, kenar: int = 1280) -> str:
    """Ürün fotoğrafı → ortadan kare kırpılmış, `kenar` px PNG data-URL (PIL yoksa dosya olduğu gibi)."""
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover — PIL'siz ortam: slice kırpması SVG'de yapılır
        tur = "jpeg" if foto.suffix.lower() in (".jpg", ".jpeg") else "png"
        return f"data:image/{tur};base64," + base64.b64encode(foto.read_bytes()).decode()
    with Image.open(foto) as g:
        g = g.convert("RGB")
        k = min(g.size)
        x, y = (g.width - k) // 2, (g.height - k) // 2
        g = g.crop((x, y, x + k, y + k))
        if k > kenar:
            g = g.resize((kenar, kenar), Image.LANCZOS)
        tampon = io.BytesIO()
        g.save(tampon, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(tampon.getvalue()).decode()


def svg_doldur(veri: dict, foto_href: str | None, sablon: Path | None = None,
               marka: dict[str, str] | None = None) -> str:
    """Şablondaki id'leri doldurur. veri: {"ad", "satirlar": [(kod, etiket, deger), ...]} (bilgi_verisi biçimi).
    marka: {"marka", "seri", "site"} (varsayılan `marka_alanlari()`); boş alanın öğesi gizlenir."""
    kok = ET.parse(sablon or SABLON).getroot()
    e = _idler(kok)
    for anahtar, deger in (marka if marka is not None else marka_alanlari()).items():
        if anahtar in e:
            e[anahtar].text = deger
            if not deger:
                e[anahtar].set("display", "none")
    e["urun_satiri"].text = urun_satiri(str(veri["ad"]))
    satirlar = list(veri.get("satirlar") or [])[:HUCRE_SAYISI]
    for i in range(1, HUCRE_SAYISI + 1):
        grup = e[f"h{i}"]
        if i > len(satirlar):
            grup.set("display", "none")  # kullanılmayan hücre: çizgi + nokta + etiket + değer birlikte gizlenir
            e[f"h{i}_etiket"].text = ""
            e[f"h{i}_deger"].text = ""
            continue
        kod, etiket, deger = satirlar[i - 1]
        grup.attrib.pop("display", None)
        e[f"h{i}_etiket"].text = f"{kod}  {tr_buyuk(str(etiket))}"
        e[f"h{i}_deger"].text = str(deger)
        e[f"h{i}_nokta"].set("fill", RENKLER.get(str(kod)[:1].upper(), RENKLER["A"]))
    foto = e["urun_foto"]
    if foto_href:
        foto.set("href", foto_href)
        foto.set(f"{{{XLINK_NS}}}href", foto_href)
    else:
        foto.set("display", "none")
    return ET.tostring(kok, encoding="unicode", xml_declaration=False)


# ------------------------------------------------------------------------------------------------ render
def _inkscape_komutu() -> list[str] | None:
    if shutil.which("flatpak"):
        r = subprocess.run(["flatpak", "info", "--user", "org.inkscape.Inkscape"], capture_output=True, text=True)
        if r.returncode == 0:
            return INKSCAPE_FLATPAK
    yol = shutil.which("inkscape")
    return [yol] if yol else None


def _chrome_komutu() -> list[str] | None:
    for ad in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if yol := shutil.which(ad):
            return [yol]
    return None


def inkscape_render(svg: Path, png: Path) -> None:
    komut = _inkscape_komutu()
    if komut is None:
        raise RuntimeError("Inkscape bulunamadı")
    # Flatpak korumalı alanı sistemin /tmp'sini görmez → ara dosyalar ev dizininde (~/.cache/workbench-poster)
    ara_kok = Path.home() / ".cache" / "workbench-poster"
    ara_kok.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ara_kok) as td:
        g, c = Path(td) / "poster.svg", Path(td) / "poster.png"
        shutil.copyfile(svg, g)
        r = subprocess.run([*komut, str(g), "--export-type=png", f"--export-filename={c}",
                            f"--export-width={GENISLIK}", "--export-background=#F4F1EA",
                            "--export-background-opacity=1"], capture_output=True, text=True, timeout=180)
        if r.returncode != 0 or not c.exists():
            raise RuntimeError(f"Inkscape render hatası: {(r.stderr or r.stdout)[-400:]}")
        shutil.move(str(c), png)


def chrome_render(svg: Path, png: Path) -> None:
    komut = _chrome_komutu()
    if komut is None:
        raise RuntimeError("Chrome bulunamadı")
    with tempfile.TemporaryDirectory(dir=svg.parent) as profil:
        html = svg.with_suffix(".html")
        html.write_text("<!doctype html><html><head><meta charset='utf-8'><style>html,body{margin:0;padding:0;"
                        f"overflow:hidden}}</style></head><body>{svg.read_text(encoding='utf-8')}</body></html>",
                        encoding="utf-8")
        r = subprocess.run([*komut, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                            f"--user-data-dir={profil}", f"--window-size={GENISLIK},{YUKSEKLIK}",
                            "--force-device-scale-factor=1", f"--screenshot={png}", html.as_uri()],
                           capture_output=True, text=True, timeout=120)
    if not png.exists():
        raise RuntimeError(f"Chrome render hatası: {(r.stderr or r.stdout)[-400:]}")


MOTORLAR: dict[str, Render] = {"inkscape": inkscape_render, "chrome": chrome_render}


def render_et(svg: Path, png: Path, motor: str = "otomatik") -> str:
    """SVG → PNG. Dönüş: kullanılan motor adı. otomatik: Inkscape, olmazsa Chrome."""
    sira = ["inkscape", "chrome"] if motor == "otomatik" else [motor]
    hatalar = []
    for ad in sira:
        try:
            png.unlink(missing_ok=True)
            MOTORLAR[ad](svg, png)
            return ad
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            hatalar.append(f"{ad}: {exc}")
    raise RuntimeError("Poster render edilemedi — " + " | ".join(hatalar))


# ------------------------------------------------------------------------------------------------ üretim
def varsayilan_cikti(sku: str, urunler: Path | None = None, ad: str = KONSEPT_AD) -> Path:
    return (urunler or URUNLER_KLASORU) / sku / "gorsel" / "konsept" / f"{ad}-3x4.png"


def eskiyi_tasi(yol: Path) -> Path | None:
    """Var olan posteri `<klasör>/eski/<ad>-<zaman>.png` altına taşır (üzerine yazılmaz)."""
    if not yol.exists():
        return None
    hedef = yol.parent / "eski" / f"{yol.stem}-{time.strftime('%Y%m%d-%H%M%S')}{yol.suffix}"
    hedef.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(yol), hedef)
    return hedef


def uret(sku: str, cikti: Path, foto: Path | None = None, *, urunler: Path | None = None,
         motor: str = "otomatik", render: Render | None = None, veri: dict | None = None) -> Path:
    """Teknik poster 3:4 (1080×1440 PNG). foto None → konsept_hatti.poster_fotografi (numune > stüdyo).
    render: test için sahte render (svg, png) → None. veri: test için bilgi_verisi yerine."""
    from .bilgi_verisi import bilgiler
    from .konsept_hatti import poster_fotografi

    veri = veri or bilgiler(sku, urunler)
    if not veri.get("satirlar"):
        raise ValueError(f"{sku}: ölçü/malzeme verisi yok (urun.yaml) — poster uydurma veriyle basılmaz")
    foto = foto or poster_fotografi(sku, urunler)
    if foto is None or not Path(foto).exists():
        raise FileNotFoundError(f"{sku}: poster için ürün fotoğrafı yok (önce e-ticaret stüdyo görselleri)")
    svg_metin = svg_doldur(veri, foto_veri_url(Path(foto)))
    cikti = Path(cikti)
    cikti.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cikti.parent, prefix=".poster-") as td:
        svg = Path(td) / "poster.svg"
        svg.write_text(svg_metin, encoding="utf-8")
        png = Path(td) / "poster.png"
        if render is not None:
            render(svg, png)
        else:
            render_et(svg, png, motor)
        if not png.exists():
            raise RuntimeError("render çıktı üretmedi")
        shutil.move(str(png), cikti)
    return cikti


def uret_varsayilan(sku: str, foto: Path | None = None, *, urunler: Path | None = None, motor: str = "otomatik",
                    render: Render | None = None, dikey: bool = True, ad: str = KONSEPT_AD) -> dict[str, str | None]:
    """Gerçek ürün klasörüne üretim: eski poster eski/ altına, yeni 3:4 + 9:16 dikey kare."""
    hedef = varsayilan_cikti(sku, urunler, ad)
    with tempfile.TemporaryDirectory(dir=hedef.parent if hedef.parent.exists() else None) as td:
        gecici = uret(sku, Path(td) / hedef.name, foto, urunler=urunler, motor=motor, render=render)
        eski = eskiyi_tasi(hedef)
        hedef.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(gecici), hedef)
    sonuc: dict[str, str | None] = {"poster": str(hedef), "eski": str(eski) if eski else None, "dikey": None}
    if dikey:
        from .teknik_poster import dikey_kare

        d = hedef.with_name(f"{ad}-9x16.png")
        eskiyi_tasi(d)
        sonuc["dikey"] = str(dikey_kare(hedef, d))
    return sonuc


def alt_surecle_uret(sku: str, kaydet: bool = True, zaman_asimi: int = 600, ad: str = KONSEPT_AD) -> dict:
    """Bot için: posteri görsel ortamında (.venv-gorsel: PIL/numpy) ayrı süreçte üretir. Dönüş: CLI JSON'u."""
    from .ayar import PROGRAMLAR_KLASORU, PY_GORSEL

    komut = [str(PY_GORSEL), "-m", "coo.poster_sablon", sku, "--ad", ad] + (["--kaydet"] if kaydet else [])
    try:
        r = subprocess.run(komut, cwd=str(PROGRAMLAR_KLASORU), capture_output=True, text=True, timeout=zaman_asimi)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"basarili": False, "hata": str(exc)[-400:]}
    satir = (r.stdout or "").strip().splitlines()[-1:] or [""]
    try:
        return json.loads(satir[0])
    except json.JSONDecodeError:
        return {"basarili": False, "hata": ((r.stderr or "") + (r.stdout or ""))[-400:] or "çıktı yok"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sku")
    ap.add_argument("--cikti", type=Path, default=None, help="verilirse yalnız bu dosyaya yazar (eski taşınmaz, 9:16 yok)")
    ap.add_argument("--foto", type=Path, default=None)
    ap.add_argument("--motor", choices=["otomatik", "inkscape", "chrome"], default="otomatik")
    ap.add_argument("--ad", default=KONSEPT_AD, help="konsept adı → gorsel/konsept/<ad>-3x4.png")
    ap.add_argument("--kaydet", action="store_true", help="model_degisim.cikti_kaydet(sku, 'poster')")
    a = ap.parse_args(argv)
    try:
        if a.cikti:
            sonuc: dict = {"poster": str(uret(a.sku, a.cikti, a.foto, motor=a.motor))}
        else:
            sonuc = uret_varsayilan(a.sku, a.foto, motor=a.motor, ad=a.ad)
            if a.kaydet:
                from .model_degisim import cikti_kaydet

                sonuc["stl_sha256"] = cikti_kaydet(a.sku, "poster")
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(json.dumps({"basarili": False, "hata": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"basarili": True, **sonuc}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
