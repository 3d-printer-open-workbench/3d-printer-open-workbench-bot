"""Pinterest pin hattı (Patron kararı 2026-11-17: Postiz yok, Claude in Chrome ile doğrudan pinterest.com).

1) `hazirla_istemi` → pinterest-curator görseli seçer, başlık / açıklama / alt metin / panoyu yazar
   (`medya/pinterest/pin.json`, durum HAZIR). Bot önizlemeyi Patrona onay butonlarıyla gösterir.
2) Patron onaylayınca `paylas_istemi` → ajan Chrome'da pin'i yayınlar, `pin_url` + durum PAYLASILDI yazar.
Arayüz adımları ve kurallar: `config/sosyal/pinterest-rehberi.md`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .ayar import CONFIG_KLASORU, MAGAZA_URL, PINTEREST_PROFIL, URUNLER_KLASORU

REHBER = CONFIG_KLASORU / "sosyal" / "pinterest-rehberi.md"
PROFIL = PINTEREST_PROFIL
MAGAZA = MAGAZA_URL
PANOLAR = {
    "masa": "Masa Düzenleyici ve Standlar | 3D Baskı",
    "cerceve": "Fotoğraf Çerçeveleri | 3D Baskı",
    "kisiye": "Kişiye Özel Hediye ve İsim Tabelaları",
    "isletme": "İşletmelere Özel 3D Duvar Yazısı ve Tabela",
    "dekor": "Dekoratif Objeler ve Ev Dekorasyonu",
}
_ANAHTAR = [("isletme", ("işletme", "isletme", "b2b", "tabela", "duvar yaz", "logo")),
            ("kisiye", ("kişiye", "kisiye", "isim", "hediye", "kisisel")),
            ("cerceve", ("çerçeve", "cerceve", "frame")),
            ("masa", ("masa", "düzenleyici", "duzenleyici", "stand", "organizer", "kalemlik"))]


def _kok(sku: str, urunler: Path | None = None) -> Path:
    return (urunler or URUNLER_KLASORU) / sku


def pin_yolu(sku: str, urunler: Path | None = None) -> Path:
    return _kok(sku, urunler) / "medya" / "pinterest" / "pin.json"


def pano_sec(sku: str, urunler: Path | None = None) -> str:
    """urun.yaml (kategori, ad, urun_tipi) ve mağaza paketinin kategorisinden pano adı."""
    kok = _kok(sku, urunler)
    metin = sku
    y = kok / "urun.yaml"
    if y.exists():
        v = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
        metin += " " + " ".join(str(v.get(k) or "") for k in ("kategori", "ad", "urun_tipi"))
    p = kok / "magaza" / "paket.json"
    if p.exists():
        try:
            metin += " " + str(json.loads(p.read_text(encoding="utf-8")).get("kategori") or "")
        except json.JSONDecodeError:
            pass
    metin = metin.lower()
    for anahtar, kelimeler in _ANAHTAR:
        if any(k in metin for k in kelimeler):
            return PANOLAR[anahtar]
    return PANOLAR["dekor"]


def urun_linki(sku: str, urunler: Path | None = None) -> str:
    y = _kok(sku, urunler) / "magaza" / "yukleme.json"
    if y.exists():
        try:
            link = str(json.loads(y.read_text(encoding="utf-8")).get("urun_linki") or "")
            if link.startswith("http"):
                return link
        except json.JSONDecodeError:
            pass
    return MAGAZA


def gorsel_adaylari(sku: str, urunler: Path | None = None) -> list[Path]:
    """Öncelik: teknik poster → kullanım görselleri → stüdyo krem fon karesi."""
    kok = _kok(sku, urunler)
    aday = sorted((kok / "gorsel" / "konsept").glob("*-3x4.png"))
    aday += sorted(p for p in (kok / "gorsel").glob("kullanim-*.png") if "dikey" not in p.name)
    aday += sorted((kok / "gorsel" / "renkler").glob("*/studyo-ic/krem-fon.png"))
    aday += sorted((kok / "model" / "cok_renk" / "render" / "studyo-ic").glob("krem-fon.png"))
    return [p for p in aday if p.exists()]


def uygun_mu(sku: str, urunler: Path | None = None) -> bool:
    return bool(gorsel_adaylari(sku, urunler))


def oku(sku: str, urunler: Path | None = None) -> dict[str, Any] | None:
    p = pin_yolu(sku, urunler)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def hazirla_istemi(sku: str, urunler: Path | None = None, not_: str = "") -> str:
    kok = _kok(sku, urunler)
    hedef = pin_yolu(sku, urunler)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    adaylar = "\n".join(f"- `{p}`" for p in gorsel_adaylari(sku, urunler)) or "- (görsel yok)"
    return (
        f"Görev: `{sku}` için bir Pinterest pin'i HAZIRLA (yayınlama yok). Önce rehberi oku: `{REHBER}`.\n"
        f"Ürün bilgisi: `{kok / 'urun.yaml'}` (ad, ölçü, malzeme), varsa `{kok / 'magaza' / 'paket.json'}` (başlık, açıklama).\n"
        f"Görsel adayları (öncelik sırasıyla; Read ile bak, ürün birebir gerçek ve dikey olanı seç):\n{adaylar}\n"
        + (f"Patronun notu: {not_}\n" if not_ else "")
        + f"Pano: \"{pano_sec(sku, urunler)}\" (daha uygunu rehberdeki listede varsa onu seç). "
        f"Bağlantı: {urun_linki(sku, urunler)}\n"
        "Kurallar: başlık ≤100, açıklama ≤500 karakter, Türkçe, doğal anahtar kelimeler, gerçek ölçü/malzeme, tek çağrı; "
        "uydurma iddia/indirim/yorum yok. Görsel Flow/Qwen ile üretildiyse yz_isareti true.\n"
        f"Sonucu `{hedef}` dosyasına Write ile yaz:\n"
        '{"durum": "HAZIR", "gorsel": "<mutlak yol>", "baslik": "...", "aciklama": "...", "alt_metin": "...", '
        '"pano": "...", "link": "...", "yz_isareti": true}\n'
        "Başka dosyaya dokunma, Pinterest'e girme."
    )


def paylas_istemi(sku: str, urunler: Path | None = None) -> str:
    pin = oku(sku, urunler) or {}
    hedef = pin_yolu(sku, urunler)
    return (
        f"Görev: Patronun ONAYLADIĞI pin'i Pinterest'te yayınla. Önce rehberi oku: `{REHBER}` (Arayüz adımları).\n"
        f"Pin verisi (aynen kullan, değiştirme): `{hedef}`\n"
        f"Görsel: `{pin.get('gorsel')}` · Pano: \"{pin.get('pano')}\" · Bağlantı: {pin.get('link')} · "
        f"YZ işareti: {'evet' if pin.get('yz_isareti') else 'hayır'}\n"
        "Claude in Chrome araçlarını tek ToolSearch ile yükle (tabs_context_mcp, tabs_create_mcp, navigate, computer, find, "
        "read_page, get_page_text, file_upload, javascript_tool, tabs_close_mcp). Yeni sekme aç; giriş istenirse DUR.\n"
        "Yayınladıktan sonra profilin 'Oluşturulanlar' sekmesinden pin URL'sini al. `pin.json`'u güncelle: "
        '"durum": "PAYLASILDI", "pin_url": "https://tr.pinterest.com/pin/<id>/", "tarih": "YYYY-MM-DD". '
        'Hata olursa "durum": "HATA", "hata": "neden" yaz. Sekmeyi kapat. Son satır: `PIN_PAYLASILDI <url>` ya da `PIN_HATA <neden>`.'
    )
