"""Open Workbench Otomatik Sosyal Medya (Reels, TikTok, Pinterest) ve E-Ticaret Kart Kurgu Motoru.

Öncelik sırası (Video = Google Flow & gerçek çekim; Blender yalnızca statik ürün referansı üretir):
  1. Google Flow AI videoları (medya/flow*.mp4, gorsel/flow*.mp4)
  2. Kullanıcının gerçek çekimi (medya/kullanici-cekim*.mp4)
  3. Yazıcı iç kamera timelapse (medya/timelapse*.mp4)
  4. AI Yaşam Alanı görselleri (gorsel/yasam*.png) -> Ken Burns hareketli sinematik klip
  5. Montaj / Stüdyo / Detay kareleri -> Ken Burns + çapraz geçişli fallback

Üretilen çıktılar:
  1. medya/reels-son.mp4       (1080×1920, 9:16 Instagram Reels & TikTok)
  2. medya/pinterest-pin.png   (1000×1500, 2:3 Pinterest Pin)
  3. gorsel/olcu-karti.png     (1536×1536, E-Ticaret Ölçü Kartı)
  4. gorsel/ozellik-karti.png  (1536×1536, E-Ticaret Özellik Kartı)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .ayar import MAGAZA_ADI, URUNLER_KLASORU

ETIKET = "#" + "".join(c for c in MAGAZA_ADI.lower() if c.isalnum())


FONT_ADAYLARI_KALIN = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
]
FONT_ADAYLARI_NORMAL = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
]


def _font_yukle(boyut: int, kalin: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    adaylar = FONT_ADAYLARI_KALIN if kalin else FONT_ADAYLARI_NORMAL
    for yol in adaylar:
        if Path(yol).exists():
            try:
                return ImageFont.truetype(yol, boyut)
            except Exception:
                continue
    return ImageFont.load_default()


def _metin_sar(cizim: ImageDraw.ImageDraw, metin: str, font: Any, maks_genislik: int) -> list[str]:
    kelimeler = metin.split()
    if not kelimeler:
        return []
    satirlar: list[str] = []
    mevcut = kelimeler[0]
    for k in kelimeler[1:]:
        aday = f"{mevcut} {k}"
        kutu = cizim.textbbox((0, 0), aday, font=font)
        if (kutu[2] - kutu[0]) <= maks_genislik:
            mevcut = aday
        else:
            satirlar.append(mevcut)
            mevcut = k
    satirlar.append(mevcut)
    return satirlar


def _baslik_sigdir(
    cizim: ImageDraw.ImageDraw,
    metin: str,
    maks_genislik: int,
    baslangic_boyut: int = 52,
    min_boyut: int = 28,
    maks_satir: int = 2,
    kalin: bool = True,
) -> tuple[list[str], Any]:
    """Başlığı satır sayısına ve genişlik sınırına taşmayacak en büyük fontla sarar."""
    for boyut in range(baslangic_boyut, min_boyut - 1, -4):
        font = _font_yukle(boyut, kalin=kalin)
        satirlar = _metin_sar(cizim, metin, font, maks_genislik)
        if len(satirlar) <= maks_satir and all(
            (cizim.textbbox((0, 0), s, font=font)[2] - cizim.textbbox((0, 0), s, font=font)[0]) <= maks_genislik
            for s in satirlar
        ):
            return satirlar, font

    font = _font_yukle(min_boyut, kalin=kalin)
    satirlar = _metin_sar(cizim, metin, font, maks_genislik)[:maks_satir]
    kirpilmis: list[str] = []
    for s in satirlar:
        while s and (cizim.textbbox((0, 0), s, font=font)[2] - cizim.textbbox((0, 0), s, font=font)[0]) > maks_genislik:
            s = s[:-2].rstrip() + "…" if len(s) > 2 else s[:-1]
        kirpilmis.append(s)
    return kirpilmis, font


def _gradient_dikdortgen(
    genislik: int,
    yukseklik: int,
    renk: tuple[int, int, int],
    bas_alfa: int,
    bitis_alfa: int,
) -> Image.Image:
    """Dikey alfa geçişli gradient katmanı üretir."""
    katman = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 0))
    cizim = ImageDraw.Draw(katman)
    r, g, b = renk
    adim = max(1, yukseklik)
    for y in range(yukseklik):
        oran = y / max(1, adim - 1)
        a = int(bas_alfa + (bitis_alfa - bas_alfa) * oran)
        cizim.line([(0, y), (genislik, y)], fill=(r, g, b, max(0, min(255, a))))
    return katman


@dataclass
class MedyaCiktilari:
    sku: str
    reels_mp4: Path | None = None
    reels_kaynak_turu: str = "yok"


def urun_yaml_oku(sku: str) -> dict[str, Any]:
    yol = URUNLER_KLASORU / sku / "urun.yaml"
    if not yol.exists():
        return {"sku": sku, "ad": sku.replace("-", " ").title()}
    try:
        return yaml.safe_load(yol.read_text(encoding="utf-8")) or {"sku": sku}
    except Exception:
        return {"sku": sku}


def urun_yaml_yaz(sku: str, veri: dict[str, Any]) -> None:
    yol = URUNLER_KLASORU / sku / "urun.yaml"
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(yaml.safe_dump(veri, allow_unicode=True, sort_keys=False), encoding="utf-8")


_urun_yaml_yaz = urun_yaml_yaz


def urun_yaml_kalite_guncelle(sku: str, stl_yolu: Path, rapor: dict[str, Any]) -> dict[str, Any]:
    """STL kalite kapısı sonuçlarını (ölçü, gramaj, hacim ve aşama) urun.yaml dosyasına işler."""
    veri = urun_yaml_oku(sku)
    urun_dir = URUNLER_KLASORU / sku
    try:
        rel_stl = str(stl_yolu.relative_to(urun_dir))
    except ValueError:
        rel_stl = f"model/{stl_yolu.name}"

    veri["stl_yolu"] = rel_stl
    veri["kalite_kapisi"] = {
        "durum": str(rapor.get("durum") or "UNKNOWN"),
        "hacim_cm3": float(rapor.get("hacim_cm3") or 0.0),
        "tahmini_pla_gram": float(rapor.get("tahmini_pla_gram") or 0.0),
    }

    boyut = rapor.get("boyut_mm") or {}
    if isinstance(boyut, dict) and any(float(boyut.get(k) or 0) > 0 for k in ("x", "y", "z")):
        veri["boyut_mm"] = {
            "x": round(float(boyut.get("x") or 0), 2),
            "y": round(float(boyut.get("y") or 0), 2),
            "z": round(float(boyut.get("z") or 0), 2),
        }

    if rapor.get("tahmini_pla_gram"):
        tahmin = round(float(rapor["tahmini_pla_gram"]), 1)
        for bolum_ad in ("dilimleme", "uretim"):
            bolum = veri.setdefault(bolum_ad, {})
            if isinstance(bolum, dict) and float(bolum.get("tahmini_gram") or 0) <= 0:
                bolum["tahmini_gram"] = tahmin

    mevcut_durum = str(veri.get("durum") or "").upper()
    if rapor.get("durum") == "PASS":
        if mevcut_durum in ("", "TASARIM", "ARGE", "REVIZE"):
            veri["durum"] = "URETIME_HAZIR"
    elif rapor.get("durum") == "RED":
        if mevcut_durum in ("", "TASARIM", "ARGE", "URETIME_HAZIR"):
            veri["durum"] = "REVIZE"

    urun_yaml_yaz(sku, veri)
    return veri


def _icerik_gorselleri(urun_klasoru: Path) -> list[Path]:
    """Reels kareleri (patron kararı 2026-11-16): numuneden Flow kullanım görselleri → gerçek numune fotoğrafları →
    Qwen stüdyo kareleri. Kompozit yaşam görseli ve ham Blender render'ı KULLANILMAZ."""
    gorsel = urun_klasoru / "gorsel"
    adaylar: list[Path] = []
    for desen in ("kullanim-*.png", "kullanim-*.jpg", "numune-*.jpg", "numune-*.png"):
        adaylar.extend(sorted(gorsel.glob(desen)))
    veri = urun_yaml_oku(urun_klasoru.name)
    from .renk_hatti import renkler_veriden

    klasorler = [urun_klasoru / str(r["klasor"]) for r in renkler_veriden(veri)
                 if isinstance(r, dict) and r.get("klasor")] or [gorsel]
    for ad in ("krem-fon.png", "koyu-fon.png", "kapak-beyaz.png"):
        adaylar.append(klasorler[0] / "studyo-ic" / ad)
    return [a for a in adaylar if a.is_file() and a.stat().st_size > 0]


def _video_overlay_png_uret(
    yol: Path,
    kanca_baslik: str,
    alt_bant: str,
    sadece_alt: bool = False,
) -> Path:
    """1080×1920 şeffaf PNG üzerine yumuşak gradient scrim + kanca/CTA katmanı çizer."""
    katman = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    if not sadece_alt and kanca_baslik.strip():
        ust_scrim = _gradient_dikdortgen(1080, 400, (14, 13, 12), 205, 0)
        katman.paste(ust_scrim, (0, 0), ust_scrim)

    alt_scrim = _gradient_dikdortgen(1080, 340, (14, 13, 12), 0, 200)
    katman.paste(alt_scrim, (0, 1580), alt_scrim)
    d = ImageDraw.Draw(katman)

    if not sadece_alt and kanca_baslik.strip():
        satirlar, f_kanca = _baslik_sigdir(d, kanca_baslik, 880, baslangic_boyut=48, min_boyut=30, maks_satir=2)
        for i, s in enumerate(satirlar):
            kutu = d.textbbox((0, 0), s, font=f_kanca)
            sg = kutu[2] - kutu[0]
            tx, ty = (1080 - sg) // 2, 152 + i * 62
            d.text((tx + 2, ty + 3), s, fill=(0, 0, 0, 180), font=f_kanca)
            d.text((tx, ty), s, fill=(252, 249, 244, 255), font=f_kanca)

    alt_sat, f_alt = _baslik_sigdir(d, alt_bant, 840, baslangic_boyut=28, min_boyut=22, maks_satir=1)
    if alt_sat:
        kutu_alt = d.textbbox((0, 0), alt_sat[0], font=f_alt)
        ag = kutu_alt[2] - kutu_alt[0]
        pad_x = 34
        bx0 = max(60, (1080 - ag) // 2 - pad_x)
        bx1 = min(1020, (1080 + ag) // 2 + pad_x)
        d.rounded_rectangle([bx0, 1656, bx1, 1724], radius=34, fill=(22, 20, 18, 195), outline=(212, 184, 148, 220), width=2)
        d.text(((1080 - ag) // 2, 1674), alt_sat[0], fill=(248, 244, 236, 255), font=f_alt)

    katman.save(yol, "PNG")
    return yol


def _medya_bilgisi(yol: Path) -> tuple[float, int, int, bool]:
    """ffprobe ile süre (sn), genişlik, yükseklik ve ses akışı varlığını döndürür."""
    try:
        cikti = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration:stream=codec_type,width,height",
                "-of", "json",
                str(yol),
            ],
            stderr=subprocess.DEVNULL,
        )
        veri = json.loads(cikti.decode("utf-8"))
        sure = float((veri.get("format") or {}).get("duration") or 0.0)
        w, h, ses = 0, 0, False
        for st in veri.get("streams") or []:
            if st.get("codec_type") == "video" and not w:
                w = int(st.get("width") or 0)
                h = int(st.get("height") or 0)
            elif st.get("codec_type") == "audio":
                ses = True
        return sure, w, h, ses
    except Exception:
        return 0.0, 0, 0, False


def _klip_normallestir_9_16(
    kaynak: Path,
    hedef: Path,
    sure_sn: float,
    gorsel_mi: bool = False,
    hareket_yonu: int = 0,
    ses_ekle: bool = True,
) -> tuple[bool, float]:
    """Video veya görseli akıcı Ken Burns hareketli 1080×1920 30fps H.264 (+AAC) klibe çevirir."""
    fps = 30
    kare = max(30, int(round(sure_sn * fps)))

    if gorsel_mi:
        try:
            with Image.open(kaynak) as im:
                g_w, g_h = im.size
        except Exception:
            g_w, g_h = 1536, 1536

        if g_w > 0 and (g_h / g_w) >= 1.25:
            # Dikey (9:16 / 3:4) görsel: tam ekran yavaş zoompan
            zoom_expr = "min(zoom+0.0009,1.10)" if hareket_yonu % 2 == 0 else "if(eq(on,1),1.10,max(1.00,zoom-0.0009))"
            vf_gorsel = (
                "scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
                f"zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={kare}:s=1080x1920:fps={fps},"
                "eq=contrast=1.04:saturation=1.08,setsar=1,format=yuv420p"
            )
        else:
            # Kare/yatay görsel: koyu bulanık fon + kesilmeden yavaş yakınlaşan ürün karesi
            fg_h = max(640, min(1160, (int(1000 * g_h / max(g_w, 1)) // 2) * 2))
            zoom_expr = "min(zoom+0.0009,1.10)" if hareket_yonu % 2 == 0 else "if(eq(on,1),1.09,max(1.00,zoom-0.0008))"
            pan_dx = "(on/90)*12" if hareket_yonu % 2 == 1 else "0"
            vf_gorsel = (
                "split[a][b];"
                "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=45:2,eq=brightness=-0.16:saturation=0.85[bg];"
                f"[b]scale=2200:-2,zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)+{pan_dx}':y='ih/2-(ih/zoom/2)':d={kare}:s=1000x{fg_h}:fps={fps}[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2,eq=contrast=1.04:saturation=1.08,setsar=1,format=yuv420p"
            )
        komut = [
            "ffmpeg", "-y",
            "-loop", "1", "-t", f"{sure_sn:.2f}", "-i", str(kaynak),
        ]
        if ses_ekle:
            komut.extend(["-f", "lavfi", "-t", f"{sure_sn:.2f}", "-i", "anullsrc=r=44100:cl=stereo"])
            komut.extend(["-filter_complex", f"[0:v]{vf_gorsel}[vout]", "-map", "[vout]", "-map", "1:a", "-c:a", "aac", "-b:a", "128k"])
        else:
            komut.extend(["-vf", vf_gorsel, "-an"])
        komut.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "19", "-t", f"{sure_sn:.2f}", str(hedef)])
        gercek_sure = sure_sn
    else:
        ham_sure, v_w, v_h, ses_var = _medya_bilgisi(kaynak)
        gercek_sure = min(sure_sn, ham_sure) if ham_sure > 0.6 else sure_sn
        if v_w > 0 and v_h > 0 and (v_h / v_w) >= 1.2:
            vf_vid = (
                "scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,eq=contrast=1.04:saturation=1.08,setsar=1,fps=30,format=yuv420p"
            )
        else:
            vf_vid = (
                "split[a][b];"
                "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=45:2,eq=brightness=-0.16[bg];"
                "[b]scale=1080:1360:force_original_aspect_ratio=decrease[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2,eq=contrast=1.04:saturation=1.08,setsar=1,fps=30,format=yuv420p"
            )
        komut = ["ffmpeg", "-y", "-i", str(kaynak), "-t", f"{gercek_sure:.2f}"]
        if ses_ekle:
            if ses_var:
                komut.extend([
                    "-filter_complex", f"[0:v]{vf_vid}[vout]",
                    "-map", "[vout]", "-map", "0:a",
                    "-af", "aresample=44100,aformat=channel_layouts=stereo",
                    "-c:a", "aac", "-b:a", "128k",
                ])
            else:
                komut.extend([
                    "-f", "lavfi", "-t", f"{gercek_sure:.2f}", "-i", "anullsrc=r=44100:cl=stereo",
                    "-filter_complex", f"[0:v]{vf_vid}[vout]",
                    "-map", "[vout]", "-map", "1:a",
                    "-c:a", "aac", "-b:a", "128k",
                ])
        else:
            komut.extend(["-vf", vf_vid, "-an"])
        komut.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "19", str(hedef)])

    try:
        subprocess.run(komut, check=True, capture_output=True)
        return hedef.exists(), gercek_sure
    except Exception:
        return False, gercek_sure


def _flow_videolari_bul(urun_klasoru: Path) -> list[Path]:
    """Ürün klasöründeki Google Flow videolarını döndürür."""
    bulunan: list[Path] = []
    for alt in ("medya", "gorsel"):
        k = urun_klasoru / alt
        if not k.is_dir():
            continue
        for desen in ("flow*.mp4", "veo*.mp4", "ai-*.mp4"):
            for p in sorted(k.glob(desen)):
                if p.is_file() and p.stat().st_size > 0 and p not in bulunan:
                    bulunan.append(p)
    return bulunan


def _kaynak_klipleri_sec(
    urun_klasoru: Path,
    blender_donen_kullan: bool = False,  # geriye dönük imza; Blender videosu kullanılmaz
) -> tuple[list[tuple[Path, float, bool]], str]:
    """Reels kurgusu yalnız GERÇEK kaynaklardan (Patron kararı 2026-11-16): numune fotoğrafından Flow/Veo
    videoları, kullanıcının çekimi, yazıcı timelapse'i; durağan kare olarak numune ve numuneden Flow kullanım
    görselleri (+ Qwen stüdyo kareleri yalnız destek). Kompozit yaşam görseli, ham Blender render'ı ve dönen
    CGI video KULLANILMAZ. Gerçek kaynak yoksa boş döner (ürün tanıtım Reels'i Teknik Poster konseptinden gelir)."""
    medya = urun_klasoru / "medya"
    klipler: list[tuple[Path, float, bool]] = []
    flow_var = cekim_var = False
    for fp in [v for v in _flow_videolari_bul(urun_klasoru) if "-red" not in v.stem][:2]:
        klipler.append((fp, 6.0, False))
        flow_var = True
    for desen, sure in (("kullanici-cekim*.mp4", 5.0), ("timelapse*.mp4", 4.0)):
        for v in sorted(medya.glob(desen)) if medya.is_dir() else []:
            if v.is_file() and v.stat().st_size > 0:
                klipler.append((v, sure, False))
                cekim_var = True
                break
    gercek_kare = [p for p in _icerik_gorselleri(urun_klasoru) if p.name.startswith(("kullanim-", "numune-"))]
    if medya.is_dir():
        gercek_kare += [medya / ad for ad in ("kullanici-foto.jpg", "kullanici-foto.png") if (medya / ad).is_file()]
    for g in gercek_kare:
        if len(klipler) < 4:
            klipler.append((g, 3.5, True))
            cekim_var = True
    if not (flow_var or cekim_var):
        return [], "yok"
    for g in [p for p in _icerik_gorselleri(urun_klasoru) if p.parent.name == "studyo-ic"]:
        if len(klipler) < 4:
            klipler.append((g, 3.4, True))
    etiket = "flow" if flow_var else "cekim"
    return klipler[:4], etiket


def reels_ve_tiktok_kurgu_uret(
    sku: str,
    kanca_baslik: str | None = None,
    alt_bant: str = f"{MAGAZA_ADI} • Profildeki Linkten İnceleyin",
    blender_donen_kullan: bool = False,
) -> Path | None:
    """Google Flow + gerçek çekim + akıcı xfade ve Ken Burns kurgulu 9:16 Reels/TikTok üretir."""
    urun_klasoru = URUNLER_KLASORU / sku
    medya = urun_klasoru / "medya"
    medya.mkdir(parents=True, exist_ok=True)

    veri = urun_yaml_oku(sku)
    ad = str(veri.get("ad") or sku.replace("-", " ").title())
    kanca = kanca_baslik or f"{ad} — Yaşam Alanınıza Özel Dokunuş"

    kaynak_klipler, _ = _kaynak_klipleri_sec(urun_klasoru, blender_donen_kullan=blender_donen_kullan)
    if not kaynak_klipler:
        return None

    cikti_mp4 = medya / "reels-son.mp4"
    gecis_sn = 0.40

    with tempfile.TemporaryDirectory(prefix="workbench_reels_") as tmp:
        tmp_yol = Path(tmp)
        parcalar: list[tuple[Path, float]] = []
        for idx, (k_yol, sure, gorsel_mi) in enumerate(kaynak_klipler):
            p_yol = tmp_yol / f"parca_{idx:02d}.mp4"
            ok, gercek_s = _klip_normallestir_9_16(
                k_yol, p_yol, sure, gorsel_mi=gorsel_mi, hareket_yonu=idx, ses_ekle=True
            )
            if ok:
                parcalar.append((p_yol, gercek_s))

        if not parcalar:
            return None

        birlesik_mp4 = tmp_yol / "birlesik.mp4"
        if len(parcalar) == 1:
            birlesik_mp4 = parcalar[0][0]
        else:
            # Çoklu klip: xfade (yumuşak geçiş) + acrossfade (ses devamlılığı)
            girdiler: list[str] = []
            for p_yol, _ in parcalar:
                girdiler.extend(["-i", str(p_yol)])

            # xfade/acrossfade aynı zaman tabanı, kare hızı ve ses formatı ister. Flow/Veo videoları kendi
            # sesi ve farklı timebase'iyle gelir → her girdiyi önce ortak biçime getir.
            v_zincir = ""
            a_zincir = ""
            for i in range(len(parcalar)):
                v_zincir += f"[{i}:v]settb=AVTB,fps=30,format=yuv420p,setsar=1[n{i}v];"
                a_zincir += f"[{i}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[n{i}a];"
            son_v = "[n0v]"
            son_a = "[n0a]"
            ofset = parcalar[0][1] - gecis_sn
            gecis_tipleri = ("fade", "smoothleft", "fade", "dissolve")
            for i in range(1, len(parcalar)):
                tip = gecis_tipleri[(i - 1) % len(gecis_tipleri)]
                v_out = f"[v{i}]" if i < len(parcalar) - 1 else "[vout]"
                a_out = f"[a{i}]" if i < len(parcalar) - 1 else "[aout]"
                g_ofset = max(0.3, ofset)
                v_zincir += f"{son_v}[n{i}v]xfade=transition={tip}:duration={gecis_sn:.2f}:offset={g_ofset:.2f}{v_out};"
                a_zincir += f"{son_a}[n{i}a]acrossfade=d={gecis_sn:.2f}{a_out};"
                son_v = v_out
                son_a = a_out
                ofset += parcalar[i][1] - gecis_sn

            filtre_toplam = (v_zincir + a_zincir).rstrip(";")
            subprocess.run(
                [
                    "ffmpeg", "-y", *girdiler,
                    "-filter_complex", filtre_toplam,
                    "-map", "[vout]", "-map", "[aout]",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k",
                    str(birlesik_mp4),
                ],
                check=True,
                capture_output=True,
            )

        kanca_png = tmp_yol / "kanca_overlay.png"
        alt_png = tmp_yol / "alt_overlay.png"
        _video_overlay_png_uret(kanca_png, kanca, "", sadece_alt=False)
        _video_overlay_png_uret(alt_png, "", alt_bant, sadece_alt=True)

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(birlesik_mp4),
                "-loop", "1", "-i", str(kanca_png),
                "-loop", "1", "-i", str(alt_png),
                "-filter_complex",
                (
                    "[1:v]format=rgba,fade=t=out:st=3.8:d=0.6:alpha=1[kanca];"
                    "[2:v]format=rgba[alt];"
                    "[0:v][kanca]overlay=0:0:shortest=1[v1];"
                    "[v1][alt]overlay=0:0:shortest=1[vfinal]"
                ),
                "-map", "[vfinal]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
                "-c:a", "copy", "-shortest",
                str(cikti_mp4),
            ],
            check=True,
            capture_output=True,
        )

    return cikti_mp4 if cikti_mp4.exists() else None


def paylasim_metinleri_uret(sku: str, kanca_baslik: str | None = None) -> Path:
    """Instagram, TikTok ve Pinterest için paylaşım açıklamalarını medya/paylasim-metinleri.md dosyasına yazar."""
    veri = urun_yaml_oku(sku)
    ad = str(veri.get("ad") or sku.replace("-", " ").title())
    kanca = kanca_baslik or f"{ad} yaşam alanınıza nasıl uyum sağlıyor?"
    medya = URUNLER_KLASORU / sku / "medya"
    medya.mkdir(parents=True, exist_ok=True)
    dosya = medya / "paylasim-metinleri.md"

    icerik = f"""# 📱 {ad} (`{sku}`) — Sosyal Medya Paylaşım Metinleri

## 1. Instagram Reels Açıklaması
{kanca} ✨
{MAGAZA_ADI} atölyesinde özenle üretilen **{ad}**, yaşam alanınıza sıcak ve minimalist bir dokunuş katmak için tasarlandı.

▫️ Biyopolimer (PLA) sürdürülebilir malzeme
▫️ Mat, dokulu özel yüzey kalitesi
▫️ Kişiye ve mekana özel renk seçenekleri

🔗 Detaylı incelemek ve sipariş vermek için profildeki bağlantıya tıklayın!

{ETIKET} #3dbaski #evdekorasyonu #minimalisttasarim #masaustuduzenleyici #tasarimobjeler #hediyefikirleri #modernyasam

---

## 2. TikTok Açıklaması
{kanca} 🛠️ Yaşam alanındaki duruşuna bayıldık! Siz hangi rengini tercih ederdiniz? Yorumlara yazın 👇 {ETIKET} #3dprinting #dekorasyon #kesfet #tasarim

---

## 3. Pinterest Pin Başlığı ve Açıklaması
- **Pin Başlığı:** {ad} | Modern 3B Tasarım Ev & Masaüstü Dekorasyonu
- **Pin Açıklaması:** {MAGAZA_ADI} atölyesinde üretilen {ad} ile çalışma masanızı ve yaşam alanınızı düzenleyin. Doğal dokulu yüzey ve uzun ömürlü tasarım.
"""
    dosya.write_text(icerik, encoding="utf-8")
    return dosya


def tam_medya_paketi_uret(
    sku: str,
    kanca_baslik: str | None = None,
    alt_bant: str = f"{MAGAZA_ADI} • Özel Üretim",
) -> MedyaCiktilari:
    """Gerçek kaynaklı (numuneden Flow/Veo, kullanıcı çekimi, timelapse) 9:16 Reels/TikTok kurgusu + paylaşım metni.
    Ölçü/malzeme görseli ve Pinterest Pin'i Teknik Poster konseptinden gelir (coo/konsept_hatti.py); burada üretilmez."""
    _, kaynak_turu = _kaynak_klipleri_sec(URUNLER_KLASORU / sku)
    reels = reels_ve_tiktok_kurgu_uret(sku, kanca_baslik=kanca_baslik, alt_bant=alt_bant) if kaynak_turu != "yok" else None
    if reels:
        paylasim_metinleri_uret(sku, kanca_baslik=kanca_baslik)
    medya = URUNLER_KLASORU / sku / "medya"
    if reels is None:
        (medya / "reels-son.mp4").unlink(missing_ok=True)
    veri = urun_yaml_oku(sku)
    veri.setdefault("pazarlama", {})
    veri["pazarlama"]["reels_tiktok_video"] = f"medya/{reels.name}" if reels else None
    _urun_yaml_yaz(sku, veri)
    return MedyaCiktilari(sku=sku, reels_mp4=reels, reels_kaynak_turu=kaynak_turu)


def main() -> None:
    p = argparse.ArgumentParser(description="Open Workbench gerçek kaynaklı Reels/TikTok kurgusu")
    p.add_argument("--sku", required=True, help="Ürün SKU kodu (02_Urunler/<sku>)")
    p.add_argument("--kanca", default=None, help="Reels üst kanca başlığı")
    p.add_argument("--alt-bant", default=f"{MAGAZA_ADI} • Özel Üretim", help="Alt CTA metni")
    a = p.parse_args()
    sonuc = tam_medya_paketi_uret(sku=a.sku, kanca_baslik=a.kanca, alt_bant=a.alt_bant)
    print(f"Reels: {sonuc.reels_mp4 or 'üretilmedi — gerçek kaynak (numuneden Flow, çekim, timelapse) yok'}")


if __name__ == "__main__":
    main()
