"""Konsept kütüphanesi → konsept görsel (3:4 / 9:16) + Veo Reels.

Teknik poster 3:4 görseli iki yoldan biriyle üretilir:
- İsteğe bağlı Canva: `config/konseptler/teknik-poster-canva.yaml` varsa (örnek: `teknik-poster-canva.example.yaml`)
  kendi Canva ana şablonunuz kopyalanıp gerçek veriyle doldurulur (`canva` becerisi; yazılar gerçek fontla).
- Varsayılan: Flow'da ham poster + `coo/teknik_poster.py` ile deterministik bilgi bandı.
Diğer konseptler ve Reels videosu Flow'dan.

Patron (2026-11-16): "Şu konseptte görsel ve reels oluştur" butonu. Seçilen ana konsept **Teknik Poster**: ürün
fotoğrafı + ölçü/malzeme bilgi bandı (`coo/teknik_poster.py`, YZ'ye yazdırılmaz) → galeri ölçü görseli, Pinterest Pin
ve ürün tanıtım Reels'i. Ürün fotoğrafındaki ürün değiştirilmez; görseldeki yazı/rakam uydurma bilgi içermez.
Reddedilen/eski konseptler `config/konseptler/arsiv/` altında durur (listelenmez).

Konsept dosyası: `config/konseptler/<ad>.md` — YAML ön bilgi (ad, baslik, aciklama, oranlar, video,
video_istemi) + gövdede görsel istemi (olduğu gibi Flow'a verilir).
Çıktı: `gorsel/konsept/<ad>-<oran>.png` (3:4 → galeri/Pin, 9:16 → Reels başlangıç karesi),
       `medya/konsept-<ad>-reels.mp4`.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .ayar import CONFIG_KLASORU, PROGRAMLAR_KLASORU, PY_GORSEL, URUNLER_KLASORU

KONSEPT_KLASORU = CONFIG_KLASORU / "konseptler"
_ON_BILGI = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def _slug(metin: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = re.sub(r"[^a-z0-9]+", "-", metin.translate(tr).lower()).strip("-")
    return s[:30] or "konsept"


def konsept_oku(yol: Path) -> dict[str, Any]:
    metin = yol.read_text(encoding="utf-8")
    m = _ON_BILGI.match(metin)
    bilgi = (yaml.safe_load(m.group(1)) or {}) if m else {}
    govde = (m.group(2) if m else metin).strip()
    return {"ad": bilgi.get("ad") or yol.stem, "baslik": bilgi.get("baslik") or yol.stem,
            "aciklama": bilgi.get("aciklama") or "", "oranlar": bilgi.get("oranlar") or ["3:4", "9:16"],
            "video": bool(bilgi.get("video", True)), "video_istemi": bilgi.get("video_istemi") or "",
            "istem": govde, "yol": yol, "bilgi_katmani": bilgi.get("bilgi_katmani") or "",
            "referanslar": [yol.parent / r for r in (bilgi.get("referanslar") or []) if (yol.parent / r).exists()]}


def konseptler(klasor: Path | None = None) -> list[dict[str, Any]]:
    k = klasor or KONSEPT_KLASORU
    return [konsept_oku(p) for p in sorted(k.glob("*.md"))] if k.exists() else []


def konsept_kaydet(metin: str, klasor: Path | None = None) -> dict[str, Any]:
    """Telegram'dan yapıştırılan konsept: ilk satır başlık, kalanı istem. Var olan adı ezmez."""
    satirlar = metin.strip().splitlines()
    if len(satirlar) < 2 or len(metin) < 80:
        raise ValueError("İlk satıra konsept adını, altına istemi yaz (en az birkaç cümle).")
    baslik = satirlar[0].strip().strip("#:* ")[:60]
    k = klasor or KONSEPT_KLASORU
    k.mkdir(parents=True, exist_ok=True)
    ad, i = _slug(baslik), 2
    while (k / f"{ad}.md").exists():
        ad, i = f"{_slug(baslik)}-{i}", i + 1
    on = {"ad": ad, "baslik": baslik, "oranlar": ["3:4", "9:16"], "video": True,
          "kaynak": "Patron (Telegram)"}
    yol = k / f"{ad}.md"
    yol.write_text("---\n" + yaml.safe_dump(on, allow_unicode=True, sort_keys=False) + "---\n"
                   + "\n".join(satirlar[1:]).strip() + "\n", encoding="utf-8")
    return konsept_oku(yol)


def kaynak_fotograf(sku: str, urunler_klasoru: Path | None = None) -> Path | None:
    """Konsepte girecek gerçek ürün görseli: numune > numuneden kullanım > GEÇERLİ renk kararının Qwen stüdyo
    karesi (çok renk onaylıysa çok renkli render'dan; krem fon > kapak). Ham Blender render'ı kullanılmaz — yoksa
    None (önce e-ticaret görselleri adımı)."""
    import yaml

    from .renk_hatti import renkler_veriden

    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    try:
        veri = yaml.safe_load((kok / "urun.yaml").read_text(encoding="utf-8")) or {}
    except OSError:
        veri = {}
    klasorler = [kok / str(r["klasor"]) for r in renkler_veriden(veri) if r.get("klasor")] or [kok / "gorsel"]
    adaylar = [*sorted(kok.glob("gorsel/numune-*")), *sorted(kok.glob("gorsel/kullanim-*.png"))]
    for k in klasorler:
        adaylar += [k / "studyo-ic" / "krem-fon.png", k / "studyo-ic" / "kapak-beyaz.png"]
    return next((p for p in adaylar if p.exists()), None)


CANVA_SABLON = KONSEPT_KLASORU / "teknik-poster-canva.yaml"


def tr_buyuk(metin: str) -> str:
    return metin.replace("i", "İ").replace("ı", "I").upper()


def poster_fotografi(sku: str, urunler_klasoru: Path | None = None) -> Path | None:
    """Canva posterinin fotoğrafı: numune > GEÇERLİ renk kararının Qwen stüdyo karesi (çok renk onaylıysa
    model/cok_renk/render; krem fon > kapak) > studyo.png > kaynak_fotograf. Renkli ürün gri karede gösterilmez.
    YZ kullanım sahnesi (kullanim-*) posterde kullanılmaz — poster ürünün kendisini gösterir."""
    import yaml

    from .renk_hatti import renkler_veriden

    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    try:
        veri = yaml.safe_load((kok / "urun.yaml").read_text(encoding="utf-8")) or {}
    except OSError:
        veri = {}
    klasorler = [kok / str(r["klasor"]) for r in renkler_veriden(veri) if r.get("klasor")]
    adaylar = [*sorted(kok.glob("gorsel/numune-*"))]
    for ad in ("krem-fon.png", "kapak-beyaz.png"):
        adaylar += [k / "studyo-ic" / ad for k in klasorler] + sorted(kok.glob(f"gorsel/renkler/*/studyo-ic/{ad}"))
    adaylar.append(kok / "gorsel" / "studyo.png")
    return next((p for p in adaylar if p.exists()), None) or kaynak_fotograf(sku, urunler_klasoru)


def canva_poster_adimlari(sku: str, foto: Path | None, cikti: Path, urunler_klasoru: Path | None = None) -> str:
    """Teknik poster 3:4 görseli Canva ana şablonundan (isteğe bağlı). Yazılar gerçek veriden basılır."""
    from .bilgi_verisi import bilgiler

    try:
        veri = bilgiler(sku, urunler_klasoru)
    except OSError:  # urun.yaml yok → ajan DURUR (veri uydurmaz)
        veri = {"ad": sku, "satirlar": []}
    satirlar = "; ".join(f"{k} {ad} = {deg}" for k, ad, deg in veri["satirlar"]) or "(veri yok — DUR)"
    return (
        f"CANVA POSTER (3:4): ÖNCE `canva` becerisini uygula; şablon haritası `{CANVA_SABLON}`. Ana şablonu kopyala, "
        "kopyada doldur (ana şablona dokunma).\n"
        f"- Ürün fotoğrafı: `{foto}` (kare kırp, yükle, görsel kutusuna koy).\n"
        f"- Ürün satırı: `{tr_buyuk(veri['ad'])}  ·  NO. 01`.\n"
        f"- Bilgi hücreleri sırayla (BİREBİR, başka değer ekleme): {satirlar}. Kullanılmayan hücreleri kaldır.\n"
        f"- PNG dışa aktar → `{cikti}`; Read ile aç, yazıları harf harf doğrula.\n"
    )


def konsept_istemi(sku: str, konsept: dict[str, Any], urunler_klasoru: Path | None = None, not_: str = "") -> str:
    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    foto = kaynak_fotograf(sku, urunler_klasoru)
    ad = konsept["ad"]
    hedef = kok / "gorsel" / "konsept"
    oranlar = konsept["oranlar"]
    video = konsept["video"] and "9:16" in oranlar
    refler = konsept.get("referanslar") or []
    bilgi = konsept.get("bilgi_katmani") == "teknik_poster"
    canva = bilgi and CANVA_SABLON.exists()
    py = f"cd {PROGRAMLAR_KLASORU} && {PY_GORSEL} -m coo.teknik_poster"
    ref_satiri = (
        f"Stil referansları (ürün DEĞİL, yalnızca stil/düzen/palet): {', '.join(f'`{r}`' for r in refler)}. "
        "Yükleme sırası: 1) ürün fotoğrafı (IMAGE 1), 2) referanslar sırayla (IMAGE 2, 3). Üçünü de isteme ekle.\n"
        if refler else "")
    rehber = KONSEPT_KLASORU.parent / "flow" / "flow-rehberi.md"
    return (
        f"ÖNCE `{rehber}` dosyasını Read ile oku ve Flow'u ORADAKİ adımlarla kullan (Ajan modu kapalı, video "
        "'Kareler' + 'Başlat' başlangıç karesi, her indirme yeni sekme, model/kredi tablosu).\n"
        f"Görev: `{sku}` ürünü için '{konsept['baslik']}' konseptinde Google Flow ile görsel"
        + (" ve Reels videosu" if video else "") + " üret.\n"
        f"Ürün fotoğrafı (gerçek ürün, yüklenecek): `{foto}`\n"
        f"Ürün bilgisi: `{kok}/urun.yaml` (ad, renk). Konsept istemi: `{konsept['yol']}` (ön bilgiden sonraki gövde).\n"
        + ref_satiri
        + (f"PATRON NOTU (öncelikli — bir önceki sonuca göre düzeltme; notun istediği değişikliği poster/video "
           f"istemine ve Canva alanlarına işle, ürün sadakati ve yazı kuralları aynen geçerli): {not_.strip()}\n"
           if not_.strip() else "")
        + "\n"
        "KURALLAR:\n"
        "- Konsept istemini OLDUĞU GİBİ kullan; başına yalnızca şu satırı ekle: 'The uploaded photo shows a "
        "3D-printed product; keep the product in the photo exactly as it is (shape, face, details, color).'\n"
        "- Görselde yazı varsa: yalnız küçük kodlar/indeks numaraları/kısa Türkçe ifadeler. Ölçü, fiyat, malzeme "
        "iddiası, marka/logo, sahte kelime YAZDIRMA; bozuk/anlamsız harf içeren sonucu ELE.\n"
        "- Üst yarıdaki ürün fotoğraftakinden belirgin farklıysa (yüz, renk, şekil) o sonucu ELE.\n\n"
        "1) Claude in Chrome araçlarını tek ToolSearch ile yükle (file_upload, javascript_tool dahil); "
        "tabs_context_mcp; YENİ sekme; https://flow.google.com/ → Yeni proje.\n"
        "2) Yerel dosya yüklemek için: javascript_tool ile HTMLInputElement.prototype.click'i type=file olanları "
        "yakalayıp DOM'a ekleyecek ve dialog AÇMAYACAK şekilde yamala; '+' → 'Medya yükle'; find ile file-input'u "
        "bul; file_upload ile ürün fotoğrafını yükle. 'Kullanım hakları' onayı çıkarsa DUR → `KONSEPT_HATA haklar "
        "onayı gerekli`.\n"
        + (canva_poster_adimlari(sku, poster_fotografi(sku, urunler_klasoru), hedef / f"{ad}-3x4.png", urunler_klasoru)
           + f"4b) 9:16 başlangıç karesi: `{py} dikey {sku} {hedef}/{ad}-3x4.png --cikti {hedef}/{ad}-9x16.png` "
           "(Flow'da 9:16 görsel ÜRETME).\n"
           if canva else (
        "3) Görsel modunda EN YÜKSEK KALİTELİ görsel modelini seç (kredi harcayabilir). Her oran için ("
        + ", ".join(["3:4"] if bilgi else oranlar) + "): oranı seç, çıktı x4, yüklenen fotoğrafı isteme ekle, istemi gönder "
        "(9:16 için istemdeki '3:4' ifadesini '9:16' yap). %100 olana kadar bekle (en fazla ~5 dk).\n"
        "4) Sonuçları Read/ekran görüntüsüyle değerlendir; kurallara uymayanları ele; her oran için EN İYİ 1 "
        "sonucu aç → 'Medyayı indir' → '2K' (poster baskı kalitesi; kredi harcayabilir). Chrome indirmeyi engellerse "
        "(İndirilenler'e dosya gelmezse) — Chrome sekme başına tek otomatik indirmeye izin veriyor — HER indirme "
        "için YENİ sekme aç (tabs_create_mcp), görselin /edit/<id> adresine git, 'Medyayı indir' → '2K'; yine "
        "gelmezse DUR → "
        "`KONSEPT_HATA Chrome otomatik indirme izni gerekli`. İndirilen dosyayı "
        f"`{hedef}/{ad}-<oran: 3x4 veya 9x16>" + ("-ham" if bilgi else "") + ".png` olarak kaydet (PNG'ye çevir; İndirilenler'den taşı).\n"
        + (
            f"4b) BİLGİ KATMANI (yazıyı YZ değil biz basarız): `{py} bilgi {sku} {hedef}/{ad}-3x4-ham.png "
            f"--cikti {hedef}/{ad}-3x4.png` (3:4 posteri önce `{ad}-3x4-ham.png` adıyla kaydet) ve "
            f"`{py} dikey {sku} {hedef}/{ad}-3x4-ham.png --cikti {hedef}/{ad}-9x16.png`. 9:16 görseli Flow'da "
            "AYRICA ÜRETME; video başlangıç karesi bu dosyadır.\n" if bilgi else ""
        )
           ))
        + (
            f"5) Video (rehber §2–§5): ayar çipi → Video → Kareler → 9:16 → model 'Veo 3.1 - Fast' (yoksa 'Omni 1.2 "
            f"Flash') → x1. 'Başlat' → 'Çerçeve resmi seçin' → 'Medya yükle' ile `{hedef}/{ad}-9x16.png` → 'İsteme ekle'; "
            "'Bitir' boş. İstem: '" + konsept["video_istemi"].replace("'", "’") + "' "
            + (f"İndir (yeni sekmede, '720p Orijinal') → `{kok}/medya/konsept-{ad}-reels.mp4` (Canva posteri ölçü/"
               "malzeme bilgisini zaten içeriyor; ek bant EKLEME, Flow'un kendi sesini koru). " if canva
               else f"İndir (yeni sekmede, '720p Orijinal') → `{kok}/medya/{ad}-veo-ham.mp4`, sonra "
               f"`{py} reels {sku} {kok}/medya/{ad}-veo-ham.mp4` (ölçü/malzeme bandı + site) → "
               f"`{kok}/medya/konsept-{ad}-reels.mp4`. " if bilgi else f"İndir → `{kok}/medya/konsept-{ad}-reels.mp4`. ")
            + "ffmpeg ile 0/4/7.8 sn karelerini çıkar; üst yarıdaki "
            "ürün değiştiyse videoyu SİL ve notla.\n"
            if video else "5) Video üretme.\n"
        )
        + "6) Sekmeleri kapat. Son satır tek satır: `KONSEPT_HAZIR <görsel sayısı> video=<var|yok> model=<ad> "
        "kredi=<harcanan>` veya `KONSEPT_HATA <neden>`. Giriş/ödeme/abonelik/kredi satın alma ekranında hiçbir şeyi "
        "onaylama. Aynı başarısız adımı 3 kereden fazla deneme."
    )


def konsept_ciktilari(sku: str, ad: str, urunler_klasoru: Path | None = None) -> dict[str, Path | None]:
    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    yol = lambda p: p if p.exists() else None  # noqa: E731
    return {"poster": yol(kok / "gorsel" / "konsept" / f"{ad}-3x4.png"),
            "dikey": yol(kok / "gorsel" / "konsept" / f"{ad}-9x16.png"),
            "reels": yol(kok / "medya" / f"konsept-{ad}-reels.mp4")}
