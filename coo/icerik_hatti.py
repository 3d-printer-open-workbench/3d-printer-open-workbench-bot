"""E-ticaret ve sosyal medya içeriğinin mutabık kalınan kaynakları (Patron kararları, 2026-11-16).

- Stüdyo / e-ticaret görselleri → `coo/studyo_qwen.py` (Qwen, ürünün Blender render'ından; geometri/renk denetimli).
- Ölçü-malzeme posteri, Pinterest Pin ve ürün tanıtım Reels'i → Teknik Poster konsepti (`coo/konsept_hatti.py`,
  bilgi bandı `coo/teknik_poster.py`).
- Kullanım (yaşam alanı) görselleri → yalnız GERÇEK numune fotoğrafından Flow ile; ardından Veo videosu ve
  gerçek kaynaklı Reels kurgusu (`coo/medya_editoru.py`).
YASAK: ürünü YZ sahnesine yapıştırma (kompozit), ürünü YZ'ye yeniden çizdirme, ham Blender render'ını galeri/
sosyal medyada kullanma.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from typing import Any

from .ayar import URUNLER_KLASORU
from .renk_hatti import urun_renkleri



def _kok(sku: str, urunler_klasoru: Path | None) -> Path:
    return (urunler_klasoru or URUNLER_KLASORU) / sku


def renk_hedefleri(sku: str, urunler_klasoru: Path | None = None) -> list[tuple[Path, Path]]:
    """(şeffaf ürün görseli, yaşam görsellerinin klasörü) çiftleri. İlki ana renktir."""
    kok = _kok(sku, urunler_klasoru)
    hedefler = []
    for r in urun_renkleri(sku, urunler_klasoru):
        klasor = kok / str(r.get("klasor") or "")
        if (klasor / "seffaf.png").exists():
            hedefler.append((klasor / "seffaf.png", klasor))
    if not hedefler and (kok / "gorsel" / "seffaf.png").exists():
        hedefler.append((kok / "gorsel" / "seffaf.png", kok / "gorsel"))
    return hedefler


def eski_icerikler(sku: str, urunler_klasoru: Path | None = None) -> list[str]:
    """Geçerli renk modelinden (çok renk boyama raporu) DAHA ESKİ kalan içerikler — ürünün eski rengini gösterir,
    yeniden üretilmeden onaya/mağazaya gitmemeli. Göreli yollar."""
    kok = _kok(sku, urunler_klasoru)
    kaynak = kok / "model" / "cok_renk" / "rapor.json"
    if not kaynak.exists():
        return []
    esik = kaynak.stat().st_mtime
    adaylar = [kok / "model" / "cok_renk" / "render" / "studyo-ic" / "rapor.json"]
    adaylar += sorted((kok / "gorsel" / "konsept").glob("*-3x4.png"))
    adaylar += sorted((kok / "gorsel").glob("kullanim-*"))
    adaylar += sorted((kok / "medya").glob("konsept-*-reels.mp4")) + [kok / "medya" / "reels-son.mp4"]
    adaylar += [kok / "uretim" / f"{sku}.3mf"]
    return [str(p.relative_to(kok)) for p in adaylar if p.exists() and p.stat().st_mtime < esik]


def icerik_ozeti(sku: str, urunler_klasoru: Path | None = None) -> dict[str, Any]:
    kok = _kok(sku, urunler_klasoru)
    medya = kok / "medya"
    return {
        "video": medya / "flow-1.mp4" if (medya / "flow-1.mp4").exists() else None,
        "video_red": (medya / "flow-1-red.mp4").exists(),
        "kullanim": sorted((kok / "gorsel").glob("kullanim-*")),
        "eski": eski_icerikler(sku, urunler_klasoru),
    }


# --- Numune fotoğrafından Flow kullanım görselleri (patron kararı 2026-11-16) ---------------------------
def numune_fotograflari(sku: str, urunler_klasoru: Path | None = None) -> list[Path]:
    kok = _kok(sku, urunler_klasoru)
    return sorted(p for d in ("numune-*.jpg", "numune-*.png") for p in (kok / "gorsel").glob(d))


def numune_kaydet_yolu(sku: str, urunler_klasoru: Path | None = None) -> Path:
    kok = _kok(sku, urunler_klasoru) / "gorsel"
    kok.mkdir(parents=True, exist_ok=True)
    n = len(list(kok.glob("numune-*"))) + 1
    return kok / f"numune-{n}.jpg"


def numunesiz_kaynaklar(sku: str, urunler_klasoru: Path | None = None) -> list[Path]:
    """Numune yokken kullanım görseline kaynak: GEÇERLİ renk kararının Qwen stüdyo kareleri (ürünün gerçek
    modelinden; krem fon > beyaz kapak). Ham Blender render'ı kullanılmaz."""
    kok = _kok(sku, urunler_klasoru)
    klasorler = [kok / str(r["klasor"]) for r in urun_renkleri(sku, urunler_klasoru) if r.get("klasor")] or [kok / "gorsel"]
    return [k / "studyo-ic" / ad for k in klasorler[:1] for ad in ("krem-fon.png", "kapak-beyaz.png")
            if (k / "studyo-ic" / ad).exists()]


def kullanim_istemi(sku: str, urunler_klasoru: Path | None = None, revize_notu: str = "",
                    numunesiz: bool = False) -> str:
    """Flow (Nano Banana düzenleme) ile kullanım görselleri + Veo video. Kaynak: gerçek numune fotoğrafı;
    numunesiz=True (Patron seçeneği, deneme): ürünün Qwen stüdyo karesi — sadakat kontrolü bu kareye göre."""
    kok = _kok(sku, urunler_klasoru)
    if not revize_notu and (kok / "urun.yaml").exists():  # Patronun kayıtlı içerik notu her üretimde geçerli
        v = yaml.safe_load((kok / "urun.yaml").read_text(encoding="utf-8")) or {}
        revize_notu = str(v.get("icerik_revize_notu") or "").strip()
    numuneler = numunesiz_kaynaklar(sku, urunler_klasoru) if numunesiz else numune_fotograflari(sku, urunler_klasoru)
    liste = ", ".join(f"`{p}`" for p in numuneler)
    rehber = URUNLER_KLASORU.parent.parent / "config" / "flow" / "flow-rehberi.md"
    return (
        f"ÖNCE `{rehber}` dosyasını Read ile oku ve Flow'u ORADAKİ adımlarla kullan.\n"
        + (f"Görev: `{sku}` için ÜRÜNÜN STÜDYO FOTOĞRAFINDAN (Qwen; ürünün basılacak 3B modelinden, numune henüz yok) "
           "Flow ile kullanım (yaşam alanı) görselleri ve 9:16 video üret. Aşağıda 'numune fotoğrafı' geçen her yerde "
           "bu stüdyo fotoğrafını kullan. Dosya adlarına `-q` ekle: `gorsel/kullanim-q-1.png`, `gorsel/kullanim-q-2.png`, "
           "`medya/kullanim-q-dikey.png`, video `medya/flow-q-1.mp4`. Sadakat kontrolünü ÇOK sıkı yap (yüz, kıvrım, "
           "detay, renk birebir); şüpheliyse görseli SİL.\n" if numunesiz else
           f"Görev: `{sku}` için GERÇEK NUMUNE FOTOĞRAFINDAN Flow ile kullanım (yaşam alanı) görselleri ve 9:16 video üret.\n")
        + f"{'Kaynak (ürün stüdyo) fotoğrafları' if numunesiz else 'Numune fotoğrafları'}: {liste}\n"
        + (f"PATRON NOTU (ÖNCELİKLİ — sahneyi ve videoyu buna göre kur): {revize_notu}\n"
           "Not, ürünle birlikte kullanılan bir nesne istiyorsa (ör. PS5 kumandası, telefon, kulaklık) o nesneyi ürünün "
           "kullanım yerine (tutucu/yuva/hazne) gerçekçi şekilde OTURT; nesne logosuz/markasız genel görünümde olsun, "
           "ürünü örtmesin. Bu, 'yalnız arka plan' kuralının tek istisnasıdır — ürünün kendisi yine birebir aynı kalır. "
           "Not insan/el istemiyorsa 'no people' geçerli.\n" if revize_notu else "")
        + "MUTLAK KURAL: Ürün fotoğraftaki GERÇEK üründür. Şeklini, yüzünü/detaylarını, rengini, oranını DEĞİŞTİRME; "
        "çevresini/arka planını ve ortam ışığını değiştir. Ürüne yeni detay, desen, doku ekleme.\n"
        "KULLANIM KURALI (Patron kararı 2026-11-17): Kullanım görseli ürünün GERÇEK KULLANIMINI göstermeli — dekor "
        "sahnesi değil. urun.yaml'dan ürünün ne işe yaradığını çıkar ve ürünü o işi yaparken göster: kumanda/kontrolcü "
        "standında kumanda tutucuların üstünde, telefon standında telefon, kalemlikte kalemler, saksıda gerçek bitki, "
        "tütsülükte yanan tütsü, kulaklık askısında kulaklık; sahne de o kullanımın yeri olsun (oyun kumandası → oyuncu "
        "odası/oyun masası). Taşınan nesne ürünün yuvasına gerçekçi oturur, logosuz/markasız genel tasarımda olur, "
        "ürünü örtmez. Ürün sadece dekorsa (biblo, figür) kullanım = yaşam alanında yerinde duruşu.\n\n"
        f"1) `{kok}/urun.yaml` oku (ad, boyut_mm, kategori). En net numune fotoğrafını seç.\n"
        "2) İngilizce 3 düzenleme istemi yaz (`gorsel/sahne/kullanim-istemleri.md`): 2 KARE (1:1) + 1 DİKEY (9:16). "
        "Kalıp: 'Edit this photo: keep the product exactly as it is — same shape, same details, same color, same size "
        "and same position. <Ürünün kullanıldığı nesne varsa: Place a <generic unbranded nesne> resting naturally in the "
        "product's <yuva/tutucu>, without covering the product.> Replace the background and surroundings with <ürünün "
        "gerçek kullanım yeri> (e.g. planter with a real succulent on a sunny windowsill; controller stand holding a "
        "generic game controller on a gaming desk). Match the existing light direction of the product. "
        "Photorealistic, natural shadows, no text, no people.' (Kullanım el gerektiriyorsa ve not izin veriyorsa el olabilir.) Saksı ise birinde hazneye gerçek bir bitki koy "
        "(bitki hazne ağzının içinden çıksın, ürün gövdesini örtmesin).\n"
        "3) Chrome: Claude in Chrome araçlarını tek ToolSearch ile yükle (file_upload, javascript_tool dahil); "
        "tabs_context_mcp; YENİ sekme; https://flow.google.com/ → Yeni proje. Resim modu, Nano Banana, x2.\n"
        "   Yerel dosya yüklemek için: önce javascript_tool ile HTMLInputElement.prototype.click'i, type=file "
        "olanları yakalayıp DOM'a ekleyecek ve dialog AÇMAYACAK şekilde yamala; sonra '+' → 'Medya yükle'ye bas, "
        "find ile file-input'u bul, file_upload ile numune fotoğrafını yükle. 'Kullanım hakları' onay penceresi "
        "çıkarsa DUR ve `KULLANIM_HATA haklar onayı gerekli` yaz (Patron bu kez onaylamadı).\n"
        "4) Her istem için yüklenen fotoğrafı isteme ekle, istemi gönder; sonuçları 1K Orijinal indir "
        "(2K/4K YÜKSELTME). En iyi 2 kareyi `gorsel/kullanim-1.png`, `gorsel/kullanim-2.png`, dikeyi "
        "`medya/kullanim-dikey.png` olarak kaydet (PNG'ye çevir).\n"
        "5) SADAKAT KONTROLÜ: Her sonucu numune fotoğrafıyla yan yana Read ile karşılaştır. Ürünün şekli, yüzü, "
        "detayları, rengi değiştiyse o görseli SİL ve bir kez yeniden üret; yine değiştiyse atla ve notla.\n"
        "6) Video (rehber §2–§5): ayar çipi → Video → Kareler → 9:16 → 'Veo 3.1 - Fast' (yoksa 'Omni 1.2 Flash') → x1; "
        "'Başlat' → 'Çerçeve resmi seçin' → 'Medya yükle' ile `medya/kullanim-dikey.png` → 'İsteme ekle'; 'Bitir' boş. İstem: 'Locked-off shot, the product stays perfectly still and "
        "unchanged in every frame. Very slow push-in, gentle natural light shimmer. No new objects beyond the scene, "
        f"no hands, no text.' İndir → `{kok}/medya/flow-1.mp4`. ffmpeg ile 0/3/6/7.8 sn karelerini çıkarıp ürüne bak; "
        "değiştiyse `medya/flow-1-red.mp4` yap. Kareleri sil.\n"
        "7) Sekmeyi kapat. Giriş/kredi/ödeme ekranında hiçbir şeyi onaylama.\n"
        "8) Son satır: `KULLANIM_HAZIR <kaç görsel>` veya `KULLANIM_HATA <neden>`."
    )
