"""Open Workbench B2C Ar-Ge Vitrin, Görsel Katalog ve Ürün Geliştirme Köprüsü (`coo/b2c_arge.py`).

Ar-Ge Müdürünün canlı internet araştırmasıyla topladığı gerçek B2C ürün örneklerini
JSON paketleri + doğrulanmış indirilen görseller + karşılaştırmalı katalog.png olarak
tutar; Patron onayladığında 02_Urunler/<sku>/ iskeletini otomatik kurar.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .ayar import B2C_ONERILER_KLASORU, CALISMA_ALANI, KONSEPT_ARGE_KLASORU, URUNLER_KLASORU, VERI_KLASORU

FONT_ADAYLARI = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
FONT_DUZ_ADAYLARI = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _font(boyut: int, kalin: bool = False) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    adaylar = FONT_ADAYLARI if kalin else FONT_DUZ_ADAYLARI
    for yol in adaylar:
        if Path(yol).exists():
            try:
                return ImageFont.truetype(yol, boyut)
            except Exception:
                continue
    return ImageFont.load_default()


def paket_id_temizle(paket_id: str) -> str:
    temiz = re.sub(r"[^a-zA-Z0-9_-]+", "-", (paket_id or "").strip()).strip("-")
    # Telegram callback_data <= 64 byte sınırı için paket_id max 28 karakter tutulur
    return (temiz or dt.date.today().strftime("%Y%m%d-b2c"))[:28]


def paket_dosya_yolu(paket_id: str, kok: Path | None = None) -> Path:
    dizin = kok or B2C_ONERILER_KLASORU
    dizin.mkdir(parents=True, exist_ok=True)
    return dizin / f"{paket_id_temizle(paket_id)}.json"


def paket_kaydet(paket_id: str, veri: dict[str, Any], kok: Path | None = None) -> Path:
    temiz_id = paket_id_temizle(paket_id)
    veri["paket_id"] = temiz_id
    veri.setdefault("tarih", dt.date.today().isoformat())
    veri.setdefault("adaylar", [])
    hedef = paket_dosya_yolu(temiz_id, kok=kok)
    hedef.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    return hedef


def en_son_paket_id(kok: Path | None = None) -> str | None:
    dizin = kok or B2C_ONERILER_KLASORU
    if not dizin.exists():
        return None
    jsonlar = sorted(
        (p for p in dizin.glob("*.json") if p.is_file()),
        key=lambda p: (p.stat().st_mtime, p.name),
        reverse=True,
    )
    return jsonlar[0].stem if jsonlar else None


def paket_yukle(paket_id: str | None = None, kok: Path | None = None) -> dict[str, Any] | None:
    dizin = kok or B2C_ONERILER_KLASORU
    pid = paket_id_temizle(paket_id) if paket_id else en_son_paket_id(kok=dizin)
    if not pid:
        return None
    yol = dizin / f"{pid}.json"
    if not yol.exists():
        return None
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except Exception:
        return None


def gorsel_indir(url: str, hedef_yol: Path, zaman_asimi: float = 15.0) -> bool:
    """Görseli URL'den indirir (urllib + curl yedeği), Pillow ile doğrulayıp JPEG/PNG olarak kaydeder."""
    if not url or "grounding-api-redirect" in url:
        return False
    ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    veri = b""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": ua,
            "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=zaman_asimi) as resp:
            if getattr(resp, "status", 200) < 400:
                veri = resp.read()
    except Exception:
        veri = b""

    if len(veri) < 1024:
        try:
            import subprocess

            rc = subprocess.run(
                ["curl", "-sL", "--max-time", str(int(zaman_asimi)), "-H", f"User-Agent: {ua}", url],
                capture_output=True,
                timeout=zaman_asimi + 5,
            )
            if rc.returncode == 0:
                veri = rc.stdout
        except Exception:
            veri = b""

    if not veri or len(veri) < 1024:
        return False
    try:
        img = Image.open(io.BytesIO(veri))
        img.verify()
        img = Image.open(io.BytesIO(veri)).convert("RGB")
        hedef_yol.parent.mkdir(parents=True, exist_ok=True)
        img.save(hedef_yol, quality=92)
        return hedef_yol.exists() and hedef_yol.stat().st_size > 1024
    except Exception:
        return False


def gorsel_yolunu_coz(aday: dict[str, Any], calisma_alani: Path | None = None) -> Path | None:
    ham = str(aday.get("gorsel_yolu") or "").strip()
    if not ham:
        return None
    kok = calisma_alani or VERI_KLASORU  # göreli görsel yolları veri/ köküne göre
    p = Path(ham)
    if not p.is_absolute():
        p = kok / ham
    return p if p.exists() and p.is_file() else None


def _metni_satirlara_sar(cizim: ImageDraw.ImageDraw, metin: str, fnt: Any, max_genislik: int, max_satir: int = 2) -> list[str]:
    kelimeler = (metin or "").split()
    if not kelimeler:
        return []
    satirlar: list[str] = []
    guncel = ""
    for k in kelimeler:
        deneme = f"{guncel} {k}".strip()
        bbox = cizim.textbbox((0, 0), deneme, font=fnt)
        if bbox[2] - bbox[0] <= max_genislik:
            guncel = deneme
        else:
            if guncel:
                satirlar.append(guncel)
                if len(satirlar) >= max_satir:
                    satirlar[-1] = satirlar[-1].rstrip(".") + "..."
                    return satirlar
            guncel = k
    if guncel and len(satirlar) < max_satir:
        satirlar.append(guncel)
    return satirlar


def katalog_gorseli_olustur(
    paket: dict[str, Any],
    cikti_yolu: Path | None = None,
    calisma_alani: Path | None = None,
) -> Path:
    """Aday listesinden karşılaştırmalı, görselli ve net okunaklı B2C öneri kataloğu üretir."""
    adaylar = paket.get("adaylar") or []
    paket_id = paket_id_temizle(str(paket.get("paket_id") or "b2c-paket"))
    hedef = cikti_yolu or (B2C_ONERILER_KLASORU / f"{paket_id}_katalog.png")
    hedef.parent.mkdir(parents=True, exist_ok=True)

    sutun = 2
    satir_sayisi = max(1, (len(adaylar) + sutun - 1) // sutun)
    kart_g, kart_y = 620, 470
    bosluk = 28
    baslik_yuk = 92
    tuval_g = sutun * kart_g + (sutun + 1) * bosluk
    tuval_y = baslik_yuk + satir_sayisi * kart_y + (satir_sayisi + 1) * bosluk

    im = Image.new("RGB", (tuval_g, tuval_y), "#F3EFE8")
    dr = ImageDraw.Draw(im)

    f_baslik = _font(28, kalin=True)
    f_alt = _font(17, kalin=False)
    f_kart_bas = _font(21, kalin=True)
    f_kart_govde = _font(16, kalin=False)
    f_rozet = _font(15, kalin=True)

    baslik_metni = str(paket.get("baslik") or "B2C Ürün Önerileri")
    dr.rectangle([0, 0, tuval_g, baslik_yuk], fill="#1D2620")
    dr.text((bosluk, 20), baslik_metni, font=f_baslik, fill="#F7F4ED")
    dr.text(
        (bosluk, 58),
        f"Paket: {paket_id}  |  Tarih: {paket.get('tarih', '')}  |  {len(adaylar)} Aday (Seçim için Telegram'dan Geliştir'e basın)",
        font=f_alt,
        fill="#C9D1C8",
    )

    for idx, aday in enumerate(adaylar):
        s_satir = idx // sutun
        s_sutun = idx % sutun
        x0 = bosluk + s_sutun * (kart_g + bosluk)
        y0 = baslik_yuk + bosluk + s_satir * (kart_y + bosluk)
        x1, y1 = x0 + kart_g, y0 + kart_y

        dr.rounded_rectangle([x0, y0, x1, y1], radius=18, fill="#FFFFFF", outline="#D8D2C5", width=2)

        foto_kutu = (x0 + 16, y0 + 16, x1 - 16, y0 + 276)
        fg = foto_kutu[2] - foto_kutu[0]
        fy = foto_kutu[3] - foto_kutu[1]
        dr.rounded_rectangle(foto_kutu, radius=12, fill="#EAE5DA")

        g_yol = gorsel_yolunu_coz(aday, calisma_alani=calisma_alani)
        if g_yol:
            try:
                with Image.open(g_yol) as g_im:
                    thumb = ImageOps.contain(g_im.convert("RGB"), (fg, fy))
                    tx = foto_kutu[0] + (fg - thumb.width) // 2
                    ty = foto_kutu[1] + (fy - thumb.height) // 2
                    im.paste(thumb, (tx, ty))
            except Exception:
                dr.text((foto_kutu[0] + 24, foto_kutu[1] + 115), "Görsel yüklenemedi", font=f_kart_govde, fill="#777777")
        else:
            dr.text((foto_kutu[0] + 24, foto_kutu[1] + 115), "Görsel doğrulanmadı", font=f_kart_govde, fill="#777777")

        # Numara ve durum rozeti
        durum = str(aday.get("durum") or "ONERILDI").upper()
        rozet_renk = "#2A6B4A" if durum == "GELISTIRILIYOR" else ("#993D3D" if durum == "ELENDI" else "#1D2620")
        dr.rounded_rectangle([x0 + 26, y0 + 26, x0 + 90, y0 + 58], radius=8, fill=rozet_renk)
        dr.text((x0 + 40, y0 + 33), f"#{idx + 1}", font=f_rozet, fill="#FFFFFF")

        dr.rounded_rectangle([x1 - 168, y0 + 26, x1 - 26, y0 + 58], radius=8, fill=rozet_renk)
        dr.text((x1 - 156, y0 + 33), durum[:14], font=f_rozet, fill="#FFFFFF")

        # Metin alanı
        my = y0 + 290
        ad_satirlari = _metni_satirlara_sar(dr, str(aday.get("ad") or aday.get("sku") or "Ürün"), f_kart_bas, kart_g - 36, 2)
        for sat in ad_satirlari:
            dr.text((x0 + 18, my), sat, font=f_kart_bas, fill="#1B1F1C")
            my += 27

        ozet = str(aday.get("ozet") or "")
        for sat in _metni_satirlara_sar(dr, ozet, f_kart_govde, kart_g - 36, 2):
            dr.text((x0 + 18, my + 2), sat, font=f_kart_govde, fill="#4E5550")
            my += 21

        # Alt metrik barı
        alt_y = y1 - 58
        dr.line([(x0 + 18, alt_y), (x1 - 18, alt_y)], fill="#E4DFD4", width=2)
        fiyat = aday.get("onerilen_satis_tl") or aday.get("rakip_fiyat") or "-"
        gram = aday.get("tahmini_gram") or "-"
        cad = str(aday.get("cad_rotasi") or "build123d")[:22]
        lisans = str(aday.get("lisans") or "Orijinal")[:22]
        ust_bar = _metni_satirlara_sar(dr, f"Hedef: {fiyat} TL  |  ~{gram}g  |  {cad}", f_rozet, kart_g - 36, 1)
        alt_bar = _metni_satirlara_sar(dr, f"Kaynak: {aday.get('kaynak_platform', '-')}  •  Lisans: {lisans}", f_kart_govde, kart_g - 36, 1)
        if ust_bar:
            dr.text((x0 + 18, alt_y + 8), ust_bar[0], font=f_rozet, fill="#1F4D3A")
        if alt_bar:
            dr.text((x0 + 18, alt_y + 30), alt_bar[0], font=f_kart_govde, fill="#636B65")

    im.save(hedef)
    return hedef


def aday_kart_metni(aday: dict[str, Any], idx: int, paket_id: str) -> str:
    durum = str(aday.get("durum") or "ONERILDI")
    satirlar = [
        f"*{idx + 1}. {aday.get('ad', aday.get('sku', 'Aday Ürün'))}* (`{aday.get('sku', '')}`)",
        f"• *Durum:* `{durum}` • *Kategori:* `{aday.get('kategori', 'B2C_DEKOR')}`",
        f"• *Özet:* {aday.get('ozet', '-')}",
        f"• *Rakip Fiyat:* {aday.get('rakip_fiyat', '-')} → *Hedef Satış:* `{aday.get('onerilen_satis_tl', '-')} TL` (Kâr: `{aday.get('tahmini_kar_marji', '-')}`)",
        f"• *Baskı & CAD Rotası:* `~{aday.get('tahmini_gram', '-')} g`, `~{aday.get('tahmini_saat', '-')} sa` • `{aday.get('cad_rotasi', 'build123d')}`",
        f"• *Lisans:* `{aday.get('lisans', '-')}`",
        f"• *Kaynak ({aday.get('kaynak_platform', 'Web')}):* {aday.get('kaynak_url', 'doğrulanmadı')}",
        f"_(Paket: `{paket_id}`)_",
    ]
    return "\n".join(satirlar)


def aday_butonlari(paket_id: str, idx: int) -> list[list[dict[str, str]]]:
    pid = paket_id_temizle(paket_id)
    return [
        [
            {"text": "💡 Bu Konseptle Fikir", "callback_data": f"b2c:gelistir:{pid}:{idx}"},
            {"text": "✏️ Notla Fikir", "callback_data": f"b2c:revize:{pid}:{idx}"},
            {"text": "🗑️ Ele", "callback_data": f"b2c:ele:{pid}:{idx}"},
        ]
    ]


def aday_durum_guncelle(
    paket_id: str,
    idx: int,
    yeni_durum: str,
    revize_notu: str | None = None,
    kok: Path | None = None,
) -> dict[str, Any] | None:
    paket = paket_yukle(paket_id, kok=kok)
    if not paket:
        return None
    adaylar = paket.get("adaylar") or []
    if idx < 0 or idx >= len(adaylar):
        return None
    adaylar[idx]["durum"] = yeni_durum
    if revize_notu is not None:
        adaylar[idx]["revize_notu"] = revize_notu
    paket_kaydet(paket_id, paket, kok=kok)
    return adaylar[idx]


def urun_iskelesi_kur(
    paket_id: str,
    idx: int,
    ek_not: str = "",
    kok_b2c: Path | None = None,
    urunler_dizini: Path | None = None,
    arge_dizini: Path | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    """Seçilen B2C adayından 02_Urunler/<sku>/urun.yaml ve 01_Konsept_ve_ArGe/<sku>-arge.md oluşturur."""
    paket = paket_yukle(paket_id, kok=kok_b2c)
    if not paket:
        raise ValueError(f"B2C paketi bulunamadı: {paket_id}")
    adaylar = paket.get("adaylar") or []
    if idx < 0 or idx >= len(adaylar):
        raise IndexError(f"Geçersiz aday indeksi: {idx}")

    aday = adaylar[idx]
    aday["durum"] = "GELISTIRILIYOR"
    if ek_not:
        aday["revize_notu"] = ek_not
    paket_kaydet(paket_id, paket, kok=kok_b2c)

    sku = re.sub(r"[^a-z0-9-]+", "-", str(aday.get("sku") or f"b2c-urun-{idx + 1}").lower()).strip("-")
    hedef_urunler = urunler_dizini or URUNLER_KLASORU
    hedef_arge = arge_dizini or KONSEPT_ARGE_KLASORU

    urun_dir = hedef_urunler / sku
    for alt in ("model", "gorsel", "medya", "uretim"):
        (urun_dir / alt).mkdir(parents=True, exist_ok=True)

    sablon_yolu = hedef_urunler / "_sablon" / "urun.yaml"
    if sablon_yolu.exists():
        manifest = yaml.safe_load(sablon_yolu.read_text(encoding="utf-8")) or {}
    else:
        manifest = {}

    cad_rotasi = str(aday.get("cad_rotasi") or "build123d")
    arac_kodu = "blender" if "blender" in cad_rotasi.lower() else ("openscad" if "scad" in cad_rotasi.lower() or "bosl" in cad_rotasi.lower() else "build123d")

    manifest["sku"] = sku
    manifest["ad"] = str(aday.get("ad") or sku)
    manifest["kategori"] = str(aday.get("kategori") or "B2C_DEKOR")
    manifest["urun_tipi"] = "STANDART"
    manifest["durum"] = "TASARIM"
    manifest["cmo_konsept_ve_ana_prompt"] = (
        f"B2C Aday Referansı: {aday.get('ozet', '')} | Kaynak: {aday.get('kaynak_url', '')} "
        + (f"| Patron Notu: {ek_not}" if ek_not else "")
    ).strip()
    manifest["revize_notu"] = ek_not or str(aday.get("revize_notu") or "")
    manifest["tasarim_araci"] = arac_kodu

    dilim = manifest.setdefault("dilimleme", {})
    if aday.get("tahmini_gram"):
        try:
            dilim["tahmini_gram"] = float(aday["tahmini_gram"])
        except Exception:
            pass
    if aday.get("tahmini_saat"):
        try:
            toplam_sa = float(aday["tahmini_saat"])
            dilim["tahmini_saat"] = int(toplam_sa)
            dilim["tahmini_dakika"] = int(round((toplam_sa - int(toplam_sa)) * 60))
        except Exception:
            pass

    erp = manifest.setdefault("erp", {})
    if aday.get("onerilen_satis_tl"):
        try:
            erp["onerilen_satis_fiyati_tl"] = float(aday["onerilen_satis_tl"])
        except Exception:
            pass

    yaml_yolu = urun_dir / "urun.yaml"
    yaml_yolu.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")

    hedef_arge.mkdir(parents=True, exist_ok=True)
    arge_md_yolu = hedef_arge / f"{sku}-arge.md"
    arge_md = (
        f"# {manifest['ad']} (`{sku}`) — B2C Ar-Ge Kartı\n\n"
        f"- **Tarih:** {paket.get('tarih', dt.date.today().isoformat())}\n"
        f"- **Kaynak Paketi:** `{paket_id}` (Aday #{idx + 1})\n"
        f"- **Platform & URL:** {aday.get('kaynak_platform', '-')} — {aday.get('kaynak_url', 'doğrulanmadı')}\n"
        f"- **Rakip Fiyatı:** {aday.get('rakip_fiyat', '-')}\n"
        f"- **Hedef Satış Fiyatı:** {aday.get('onerilen_satis_tl', '-')} TL (Tahmini Kâr: {aday.get('tahmini_kar_marji', '-')})\n"
        f"- **Ticari Lisans:** {aday.get('lisans', '-')}\n"
        f"- **Önerilen Endüstriyel CAD Rotası:** `{cad_rotasi}` (Studio kaba 2B ekstrüzyonu yasak)\n"
        f"- **Özet & Farklılaştırma:** {aday.get('ozet', '')}\n"
        + (f"- **Patron Geliştirme Notu:** {ek_not}\n" if ek_not else "")
    )
    arge_md_yolu.write_text(arge_md, encoding="utf-8")
    return aday, urun_dir, arge_md_yolu


def main() -> None:
    parser = argparse.ArgumentParser(description="Open Workbench B2C Ar-Ge Vitrin Aracı")
    sub = parser.add_subparsers(dest="alt_komut", required=True)

    p_kat = sub.add_parser("katalog", help="Paket JSON dosyasından katalog.png üret")
    p_kat.add_argument("paket_id", nargs="?", default=None)

    sub.add_parser("liste", help="Kayıtlı B2C öneri paketlerini listele")
    args = parser.parse_args()

    if args.alt_komut == "liste":
        dizin = B2C_ONERILER_KLASORU
        if not dizin.exists():
            print("Kayıtlı B2C paketi yok.")
            return
        for p in sorted(dizin.glob("*.json")):
            print(p.stem)
    elif args.alt_komut == "katalog":
        paket = paket_yukle(args.paket_id)
        if not paket:
            raise SystemExit("B2C paketi bulunamadı.")
        yol = katalog_gorseli_olustur(paket)
        print(str(yol))


if __name__ == "__main__":
    main()
