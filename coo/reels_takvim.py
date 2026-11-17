"""Trend Reels takvimi — bot tarafı (Patron isteği 2026-11-17).

Sayfa: Studio `/reels` (workbench-studio/src/studio/reels.py) okur/günceller ve Claude işlerini `istekler.json`
kuyruğuna yazar. Bot `siradaki_istek` ile sıradaki işi alır, reels-tiktok-strategist ajanını `istem` ile çalıştırır;
ajan sonucu `gelen/<istek_id>.json` dosyasına yazar, `gelen_birlestir` takvime işler. Biçim iki tarafta aynı.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import json
import uuid
from pathlib import Path
from typing import Any

import yaml

from .ayar import CONFIG_KLASORU, MAGAZA_KLASORU, STUDIO_URL, URUNLER_KLASORU

SAYFA = f"{STUDIO_URL}/reels"
REHBER = CONFIG_KLASORU / "sosyal" / "kisa-video-rehberi.md"
MARKA = CONFIG_KLASORU / "marka" / "marka-rehberi.md"


def klasor(k: Path | None = None) -> Path:
    return k or MAGAZA_KLASORU / "reels_takvimi"


@contextlib.contextmanager
def _kilit(k: Path):
    k.mkdir(parents=True, exist_ok=True)
    with open(k / ".kilit", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _oku(yol: Path, bos: Any) -> Any:
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return bos


def _yaz(yol: Path, veri: Any) -> None:
    gecici = yol.with_suffix(".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    gecici.replace(yol)


def takvim(k: Path | None = None) -> list[dict[str, Any]]:
    return _oku(klasor(k) / "takvim.json", {"fikirler": []}).get("fikirler", [])


def istek_ekle(tur: str, metin: str = "", fikir_id: str | None = None, adet: int = 7, k: Path | None = None) -> dict:
    k = klasor(k)
    istek = {"id": uuid.uuid4().hex[:8], "tur": tur, "metin": metin.strip(), "fikir_id": fikir_id,
             "adet": max(1, min(int(adet), 14)), "durum": "bekliyor", "tarih": dt.datetime.now().isoformat(timespec="seconds")}
    with _kilit(k):
        istekler = _oku(k / "istekler.json", [])
        istekler.append(istek)
        _yaz(k / "istekler.json", istekler)
    return istek


def siradaki_istek(k: Path | None = None) -> dict[str, Any] | None:
    """Bekleyen ilk isteği 'calisiyor' yapıp döndürür; zaten çalışan varsa None (aynı anda tek iş)."""
    k = klasor(k)
    with _kilit(k):
        istekler = _oku(k / "istekler.json", [])
        if any(i.get("durum") == "calisiyor" for i in istekler):
            return None
        for i in istekler:
            if i.get("durum") == "bekliyor":
                i["durum"] = "calisiyor"
                _yaz(k / "istekler.json", istekler)
                return i
    return None


def istek_bitir(istek_id: str, durum: str, k: Path | None = None) -> None:
    k = klasor(k)
    with _kilit(k):
        istekler = _oku(k / "istekler.json", [])
        for i in istekler:
            if i.get("id") == istek_id:
                i["durum"] = durum
                i["bitti"] = dt.datetime.now().isoformat(timespec="seconds")
        _yaz(k / "istekler.json", [i for i in istekler if i.get("durum") in ("bekliyor", "calisiyor")] +
             [i for i in istekler if i.get("durum") not in ("bekliyor", "calisiyor")][-30:])


def yarim_kalanlari_sifirla(k: Path | None = None) -> None:
    """Bot yeniden başlayınca 'calisiyor' kalan isteği yeniden kuyruğa al (süreç bot ile birlikte ölmüştür)."""
    k = klasor(k)
    with _kilit(k):
        istekler = _oku(k / "istekler.json", [])
        for i in istekler:
            if i.get("durum") == "calisiyor":
                i["durum"] = "bekliyor"
        if istekler:
            _yaz(k / "istekler.json", istekler)


def gelen_yolu(istek_id: str, k: Path | None = None) -> Path:
    return klasor(k) / "gelen" / f"{istek_id}.json"


def gelen_birlestir(istek: dict[str, Any], k: Path | None = None) -> list[dict[str, Any]]:
    """Ajanın yazdığı fikirleri takvime işler: yeni fikirler eklenir, revizede aynı id'li fikir değiştirilir
    (Patronun notları, durumu ve çekim işaretleri korunur). Dönüş: işlenen fikirler."""
    k = klasor(k)
    gelen = _oku(gelen_yolu(istek["id"], k), {})
    fikirler = gelen.get("fikirler") if isinstance(gelen, dict) else gelen
    if not isinstance(fikirler, list) or not fikirler:
        return []
    simdi = dt.datetime.now().isoformat(timespec="seconds")
    islenen = []
    with _kilit(k):
        tk = _oku(k / "takvim.json", {"fikirler": []})
        mevcut = {f.get("id"): f for f in tk.setdefault("fikirler", [])}
        for f in fikirler:
            if not isinstance(f, dict) or not f.get("baslik"):
                continue
            if istek["tur"] == "revize":
                eski = mevcut.get(istek.get("fikir_id"))
                if not eski:
                    continue
                korunan = {a: eski[a] for a in ("id", "durum", "notlar", "cekim_tamam", "sonuc", "olusturuldu") if a in eski}
                eski.clear()
                eski.update({**f, **korunan, "guncellendi": simdi})
                eski.setdefault("notlar", []).append({"tarih": simdi[:16], "kimden": "Claude",
                                                      "metin": f.get("revize_ozeti") or "Notuna göre revize edildi."})
                eski.pop("revize_ozeti", None)
                islenen.append(eski)
                break
            f = {**f, "id": uuid.uuid4().hex[:8], "durum": "fikir", "olusturuldu": simdi, "istek": istek["id"]}
            tk["fikirler"].append(f)
            islenen.append(f)
        _yaz(k / "takvim.json", tk)
    return islenen


def _urun_ozeti() -> str:
    satirlar = []
    for y in sorted(URUNLER_KLASORU.glob("*/urun.yaml")):
        if y.parent.name.startswith("_"):
            continue
        try:
            v = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if str(v.get("durum") or "").upper() in ("IPTAL", "COP"):
            continue
        gorsel = y.parent / "gorsel"
        varlik = [ad for ad, desen in (("kullanım görseli", "kullanim-*"), ("Teknik Poster", "konsept/*-3x4.png"),
                                       ("numune", "numune-*")) if any(gorsel.glob(desen))]
        satirlar.append(f"- `{y.parent.name}` — {v.get('ad') or y.parent.name} ({v.get('kategori') or '?'}); "
                        f"elde: {', '.join(varlik) or 'yalnız model'}")
    return "\n".join(satirlar) or "- (aktif ürün yok — genel marka/atölye içerikleri öner)"


def istem(istek: dict[str, Any], k: Path | None = None) -> str:
    hedef = gelen_yolu(istek["id"], k)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    bugun = dt.date.today()
    dolu = sorted({f.get("tarih") for f in takvim(k) if f.get("tarih") and f.get("durum") != "iptal"})
    sema = (
        '{"fikirler": [{"tarih": "YYYY-MM-DD", "saat": "HH:MM", "platform": ["Instagram Reels", "TikTok"], '
        '"baslik": "kısa iç ad", "urun_sku": "sku ya da null", "urun_ad": "...", "sure_sn": 15, '
        '"trend": {"ad": "...", "tur": "ses|format|konu|özel gün", "neden": "neden şimdi, kime hitap ediyor", '
        '"ses": "ses/şarkı adı ya da \'orijinal ses\'", "kaynak_url": "https://...", "guven": "yüksek|orta|düşük"}, '
        '"kancalar": [{"tur": "merak boşluğu", "metin": "..."}], '
        '"senaryo": [{"sure": "0-2 sn", "goruntu": "...", "ekran_yazisi": "...", "ses_konusma": "..."}], '
        '"cekim_talimati": ["telefon dikey 9:16, 4K 30fps", "..."], "malzeme": ["numune", "yazıcı timelapse", "..."], '
        '"aciklama": "Türkçe açıklama, tek çağrı", "hashtagler": ["#3dbaski", "..."]'
        + (', "revize_ozeti": "ne değişti, 1 cümle"' if istek["tur"] == "revize" else "") + "}]}"
    )
    ortak = (
        f"Önce oku: `{REHBER}` (kanca türleri, senaryo kuralları) ve `{MARKA}` (marka sesi ve renkleri).\n"
        f"Mağaza ürünleri (ürün dosyaları `{URUNLER_KLASORU}/<sku>/urun.yaml`):\n{_urun_ozeti()}\n"
        "Kurallar: Türkçe; ölçü/malzeme/süre yalnız urun.yaml/ERP gerçeğinden (uydurma yok); 'kesin tutar/viral olur' "
        "deme; telifli şarkıyı ürün videosunda önerirken Instagram'ın kendi ses kütüphanesinde olduğunu belirt; "
        "her fikre farklı türlerden 3 kanca; senaryo saniye saniye ve çekilebilir olsun "
        "(Patron tek kişi, telefon + yazıcı + numune); çekim talimatı somut (açı, ışık, hareket, kaç çekim).\n"
    )
    if istek["tur"] == "revize":
        fikir = next((f for f in takvim(k) if f.get("id") == istek.get("fikir_id")), {})
        return (
            f"Görev: Reels takvimindeki bir fikri Patronun notuna göre REVİZE ET.\n{ortak}"
            f"Mevcut fikir (JSON):\n{json.dumps(fikir, ensure_ascii=False, indent=1)}\n"
            f"PATRONUN NOTU: {istek.get('metin')}\n"
            "Not trendi/sesi değiştirmeyi istiyorsa WebSearch ile güncel, kaynaklı alternatif bul. Notta istenmeyen "
            "alanları (tarih dahil) koru. id/durum/notlar alanlarını yazma.\n"
            f"Sonucu `{hedef}` dosyasına Write ile yaz (fikirler listesinde TEK fikir):\n{sema}\n"
            "Başka dosyaya dokunma. Son satır: `REELS_HAZIR 1` ya da `REELS_HATA <neden>`."
        )
    tema = istek.get("metin") or ""
    return (
        f"Görev: mağaza için {istek['adet']} adet TREND Reels/TikTok fikri üret ve takvime yerleştir.\n{ortak}"
        + (f"Patronun teması: {tema}\n" if tema else "")
        + f"Bugün {bugun.isoformat()}. Fikirleri önümüzdeki 14 güne yay (dolu günler: {', '.join(dolu) or 'yok'}; "
        "aynı güne ikinci fikir koyma). Türkiye'de Reels için iyi saatleri seç (genelde 12:00–13:00 ya da 19:00–21:00).\n"
        "1) TREND ARAŞTIRMASI (WebSearch/WebFetch, ŞU ANKİ hafta): Instagram Reels ve TikTok'ta Türkiye'de ve dünyada "
        "yükselen sesler/formatlar (TikTok Creative Center, Instagram 'trending audio' haftalık listeleri, Later/"
        "Buffer/HubSpot trend yazıları), 3D baskı / masaüstü düzen / ev dekoru / oyuncu odası nişindeki trendler ve "
        "yaklaşan özel günler (yerli takvim). Her trend için kaynak URL yaz; doğrulayamadığın trende guven: düşük yaz.\n"
        "2) Her fikri bir trendle bir mağaza ürününe (ya da atölye/üretim sürecine) bağla; ürün GERÇEK kullanımında "
        "gösterilsin. Formatları çeşitlendir (timelapse, önce/sonra, POV, liste, ASMR baskı sesi, 'bunu tahmin et').\n"
        f"3) Sonucu `{hedef}` dosyasına Write ile yaz:\n{sema}\n"
        "Başka dosyaya dokunma; takvim.json'a YAZMA (bot birleştirir). Son satır: `REELS_HAZIR <adet>` ya da "
        "`REELS_HATA <neden>`."
    )


def bugunun_fikirleri(k: Path | None = None, gun: dt.date | None = None) -> list[dict[str, Any]]:
    g = (gun or dt.date.today()).isoformat()
    return [f for f in takvim(k) if f.get("tarih") == g and f.get("durum") in ("fikir", "onaylandi")]


def hatirlatma_metni(fikirler: list[dict[str, Any]]) -> str:
    satirlar = ["🎬 *Bugünün Reels planı*"]
    for f in fikirler:
        kanca = (f.get("kancalar") or [{}])[0]
        satirlar.append(
            f"\n• *{f.get('baslik')}* {('— ' + f['saat']) if f.get('saat') else ''}"
            f"{' _(henüz onaylanmadı)_' if f.get('durum') == 'fikir' else ''}\n"
            f"  Trend: {(f.get('trend') or {}).get('ad') or '—'}\n"
            f"  Kanca: “{kanca.get('metin') if isinstance(kanca, dict) else kanca}”\n"
            f"  Çekim: {len(f.get('cekim_talimati') or [])} adım · {f.get('sure_sn') or '?'} sn"
        )
    satirlar.append(f"\nSenaryo ve talimatlar: {SAYFA}")
    return "\n".join(satirlar)
