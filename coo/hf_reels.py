"""HyperFrames ile Reels (HTML → MP4) — `Video_Atölyesi/` (WORKBENCH_VIDEO_WORKSHOP) yapısına bağlı.

İki tür:
- Ürün Reels'i: ürün klasöründeki gerçek görseller/videolar + `bilgi_verisi` (ölçü/malzeme) → 9:16 tanıtım.
- Serbest Reels: ürüne bağlı olmayan konu (marka, atölye, sezon, ipucu…) → 9:16.

Videoyu `reels-tiktok-strategist` ajanı `hyperframes` + `hyperframes-cli` becerileriyle yazar, `check` ve
`snapshot` ile denetler, `render` eder. İsteğe bağlı örnek proje: `Video_Atölyesi/ornek-tanitim` (giriş/ölçü/renk/doku/kapanış).
"""
from __future__ import annotations

import datetime as dt
import os
import re
import time
from pathlib import Path

from .ayar import CONFIG_KLASORU, KOK, MAGAZA_ADI, MAGAZA_ALAN_ADI, MAGAZA_KLASORU, URUNLER_KLASORU

ATOLYE = Path(os.environ.get("WORKBENCH_VIDEO_WORKSHOP") or KOK / "Video_Atölyesi").expanduser()
ORNEK_PROJE = ATOLYE / "ornek-tanitim"
MARKA_REHBERI = CONFIG_KLASORU / "marka" / "marka-rehberi.md"
SERBEST_KLASORU = MAGAZA_KLASORU / "serbest_reels"


def _slug(metin: str) -> str:
    tablo = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = re.sub(r"[^a-z0-9]+", "-", metin.translate(tablo).lower()).strip("-")
    return s[:40] or "reels"


def _damga() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M")


def urun_kaynaklari(sku: str, urunler: Path | None = None) -> list[Path]:
    """Videoya girebilecek GERÇEK kaynaklar (YZ'nin yeniden çizdiği değil): poster, stüdyo kareleri, numune,
    kullanım görselleri, Flow/Veo klipleri, timelapse ve kullanıcı çekimleri."""
    kok = (urunler or URUNLER_KLASORU) / sku
    desenler = ["gorsel/konsept/teknik-poster-3x4.png", "gorsel/studyo.png", "gorsel/beyaz.png", "gorsel/yakin.png",
                "gorsel/numune-*", "gorsel/kullanim-*.png", "gorsel/renkler/*/studyo-ic/*.png",
                "medya/kullanim-ajan-*.mp4", "medya/konsept-teknik-poster-reels.mp4", "medya/timelapse*.mp4",
                "medya/baski/*.mp4", "medya/kullanici-cekim*.mp4"]
    bulunan: list[Path] = []
    for d in desenler:
        bulunan += [p for p in sorted(kok.glob(d)) if p.is_file() and not p.name.endswith("-red.mp4")]
    return bulunan


def _ortak_kurallar(proje: Path, cikti: Path) -> str:
    return (
        "ÖNCE Skill aracıyla `hyperframes` becerisini, sonra `hyperframes-cli` becerisini yükle ve kurallarına uy "
        f"(CLI: `node ~/.claude/skills/hyperframes/scripts/plugin-cli.mjs <komut>`, proje klasöründe çalıştır).\n"
        + (f"Örnek proje (yapı, sahne düzeni, ses klasörü): `{ORNEK_PROJE}` — oku, kopyalama değil uyarlama yap.\n"
           if ORNEK_PROJE.exists() else "")
        + f"Proje klasörü: `{proje}` (`init {proje} --skip-skills` ile oluştur; varlıkları `assets/` altına kopyala).\n"
        f"`{ATOLYE / 'node_modules'}` yoksa (🧹 Klasör Temizliği silmiş olabilir) önce `cd {ATOLYE} && npm ci` çalıştır.\n"
        "KURALLAR:\n"
        "- 9:16, 1080x1920, 10–15 sn, Türkçe ekran yazısı. İlk 2 sn'de kanca (soru ya da sonuç), son sahnede tek "
        f"çağrı ({MAGAZA_ALAN_ADI} / profildeki bağlantı). Platform güvenli alan: üst %14 ve alt %35'e önemli öğe koyma.\n"
        "- Ürün görüntüleri YALNIZ verilen dosyalardan; ürünü yeniden çizme, değiştirme, YZ ile üretme.\n"
        "- Ölçü/malzeme/fiyat gibi bilgiler YALNIZ istemde verilen veriden; uydurma rakam/iddia yok.\n"
        f"- Marka sesi ve paleti: `{MARKA_REHBERI}`.\n"
        "- Ses: `assets/bgm` / `assets/sfx` içindeki lisanslı dosyalar ya da örnek projeninkiler; sessiz video verme.\n"
        "- Döngü: lint → `check --json` (hatasız) → `snapshot` ile her sahnenin ortasını Read ile gör → `render`.\n"
        f"- Render çıktısını `{cikti}` yoluna kopyala; ffprobe ile ses akışı ve süreyi doğrula.\n"
        "- Son satır tek satır: `HF_REELS_HAZIR <cikti yolu> <süre sn>` ya da `HF_REELS_HATA <neden>`."
    )


def urun_istemi(sku: str, not_: str = "", urunler: Path | None = None) -> tuple[str, Path, Path]:
    from .bilgi_verisi import bilgiler

    kok = (urunler or URUNLER_KLASORU) / sku
    try:
        veri = bilgiler(sku, urunler)
    except OSError:
        veri = {"ad": sku, "satirlar": []}
    satirlar = "; ".join(f"{k} {ad} = {d}" for k, ad, d in veri["satirlar"]) or "(ölçü verisi yok — ölçü sahnesi koyma)"
    kaynaklar = "\n".join(f"  - `{p}`" for p in urun_kaynaklari(sku, urunler)) or "  (kaynak yok)"
    proje = ATOLYE / f"{sku}-{_damga()}"
    cikti = kok / "medya" / f"hf-reels-{_damga()}.mp4"
    istem = (
        f"Görev: `{sku}` ({veri['ad']}) için HyperFrames ile ürün tanıtım Reels'i üret.\n"
        f"Gerçek veri (BİREBİR): {satirlar}\n"
        f"Kullanılabilir gerçek kaynaklar:\n{kaynaklar}\n"
        f"Paylaşım/senaryo için bak: `{kok}/urun.yaml`, `{kok}/magaza/paket.json` (varsa).\n"
        + (f"Patron notu (öncelikli): {not_}\n" if not_ else "")
        + _ortak_kurallar(proje, cikti)
    )
    return istem, cikti, proje


def serbest_istemi(konu: str) -> tuple[str, Path, Path]:
    slug = _slug(konu)
    proje = ATOLYE / f"serbest-{slug}-{_damga()}"
    cikti = SERBEST_KLASORU / f"{_damga()}-{slug}.mp4"
    istem = (
        f"Görev: {MAGAZA_ADI} için ürüne bağlı olmayan SERBEST bir Reels üret. Konu: «{konu}».\n"
        f"İşletme tanımı ve marka sesi: `{MARKA_REHBERI}`. Görsel gerekiyorsa `veri/02_Urunler/*/gorsel/` ve `medya/` altındaki GERÇEK ürün görselleri "
        "ile yazıcı timelapse'lerinden seç; yoksa yalnız tipografi/hareketli grafik kullan.\n"
        + _ortak_kurallar(proje, cikti)
    )
    return istem, cikti, proje


def yeni_ciktilar(klasor: Path, baslangic: float, desen: str = "*.mp4") -> list[Path]:
    if not klasor.exists():
        return []
    return sorted((p for p in klasor.glob(desen) if p.stat().st_mtime >= baslangic - 1),
                  key=lambda p: p.stat().st_mtime)


def simdi() -> float:
    return time.time()
