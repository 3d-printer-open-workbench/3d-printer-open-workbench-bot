"""YZ destekli baskı kontrolü: yazıcı iç kamerası karesi → Gemini görüntü modeli → hata tespiti.

Baskı sürerken düzenli aralıkla (ve kritik katmanlarda) kamera karesi, bir önceki kare ve varsa dilimleyicinin
tabla önizlemesiyle birlikte Gemini'ye gönderilir; model yapılandırılmış JSON döner:
  {"durum": "NORMAL|SUPHELI|HATA", "sorun": "spagetti|tabladan_kopma|kalkma|katman_kaymasi|tikanma|
   nozul_carpma|bos_tabla|diger|yok", "guven": 0-1, "aciklama": "kısa Türkçe"}
Karar (`karar_ver`): HATA (güven ≥ 0.7) → hemen uyar; SUPHELI iki ardışık kontrolde → uyar. Bot ASLA kendisi
durdurmaz: Patrona fotoğraf + "🛑 Durdur" (çift onay) gider. "✅ Sorun Yok" dersen 20 dk sessize alınır.

Ayar: <kök>/.env → GEMINI_API_KEY, GEMINI_GORUNTU_MODELI (vars. gemini-3.5-flash-lite).
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .ayar import BASKI_KAYITLARI_KLASORU, _env_dosyasi_yukle

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
VARSAYILAN_MODEL = "gemini-3.5-flash-lite"
KONTROL_ARALIGI_SN = 300      # baskı boyunca kaç saniyede bir kare değerlendirilir
HATA_GUVEN_ESIGI = 0.7
SESSIZ_SN = 20 * 60           # "Sorun yok" sonrası sessiz süre
KAYIT_KLASORU = BASKI_KAYITLARI_KLASORU / "yz_kontrol"
SORUNLAR = ("spagetti", "tabladan_kopma", "kalkma", "katman_kaymasi", "tikanma", "nozul_carpma", "bos_tabla",
            "diger", "yok")

SEMA = {
    "type": "OBJECT",
    "properties": {
        "durum": {"type": "STRING", "enum": ["NORMAL", "SUPHELI", "HATA"]},
        "sorun": {"type": "STRING", "enum": list(SORUNLAR)},
        "guven": {"type": "NUMBER"},
        "aciklama": {"type": "STRING"},
    },
    "required": ["durum", "sorun", "guven", "aciklama"],
}


def istem(baglam: dict[str, Any]) -> str:
    return (
        "Sen bir FDM 3B baskı kalite kontrol uzmanısın. Görseller Elegoo Centauri Carbon yazıcısının KAPALI kabin "
        "iç kamerasından (geniş açı, yukarıdan-önden, ışık değişebilir).\n"
        f"Basılan ürün: {baglam.get('urun') or 'bilinmiyor'}. İlerleme: katman {baglam.get('katman', '?')}/"
        f"{baglam.get('toplam_katman', '?')} (%{baglam.get('ilerleme', '?')}). "
        f"Ağaç destek: {'VAR (ince dallanan destekler NORMALDİR, spagetti sanma)' if baglam.get('destek') else 'yok'}. "
        f"Filament rengi: {baglam.get('renk') or 'bilinmiyor'}.\n"
        "Görseller sırası: " + ", ".join(baglam.get("gorsel_sirasi") or ["ŞİMDİKİ kare"]) + ".\n\n"
        "ŞİMDİKİ kareyi değerlendir. HATA ölçütleri:\n"
        "- spagetti: parçanın üstünde/çevresinde düzensiz, havada kıvrılan filament yığını\n"
        "- tabladan_kopma: parça yerinden oynamış, devrilmiş, nozulla sürüklenmiş\n"
        "- kalkma: köşeler/kenarlar tabladan belirgin kalkmış (warping)\n"
        "- katman_kaymasi: üst katmanlar alttakilere göre yana kaymış\n"
        "- tikanma: önceki kareye göre yükseklik artmamış, nozul havada / ekstrüzyon yok, damla/topak\n"
        "- nozul_carpma: nozul ve parça çevresinde kırık parçalar, ezilme\n"
        "- bos_tabla: baskı sürüyor görünmesine rağmen tablada parça yok\n"
        "Hafif ipliklenme (stringing), küçük yüzey kusurları, yansıma, kamera bulanıklığı HATA DEĞİLDİR (NORMAL veya "
        "en fazla SUPHELI). İlk katmanlarda (katman < 5) tablada ince bir iz görmek normaldir. Emin değilsen SUPHELI "
        "de, HATA deme. guven: kararından ne kadar eminsin (0-1). aciklama: en fazla 1 kısa Türkçe cümle, "
        "neyi gördüğünü söyle."
    )


def _ayar() -> tuple[str, str]:
    _env_dosyasi_yukle()
    return os.environ.get("GEMINI_API_KEY", ""), os.environ.get("GEMINI_GORUNTU_MODELI") or VARSAYILAN_MODEL


def kare_degerlendir(simdiki: bytes, baglam: dict[str, Any], onceki: bytes | None = None,
                     referans: bytes | None = None, zaman_asimi: float = 40.0) -> dict[str, Any]:
    """Kamera karesini Gemini'ye değerlendirtir. Hata durumunda {"durum": "BILINMIYOR", "hata": ...}."""
    anahtar, model = _ayar()
    if not anahtar:
        return {"durum": "BILINMIYOR", "hata": "GEMINI_API_KEY tanımlı değil"}
    parcalar: list[dict[str, Any]] = []
    sira: list[str] = []
    if referans:
        parcalar.append({"inline_data": {"mime_type": "image/png", "data": base64.b64encode(referans).decode()}})
        sira.append("dilimleyicideki hedef ürün önizlemesi")
    if onceki:
        parcalar.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(onceki).decode()}})
        sira.append("ÖNCEKİ kamera karesi")
    parcalar.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(simdiki).decode()}})
    sira.append("ŞİMDİKİ kamera karesi")
    parcalar.append({"text": istem({**baglam, "gorsel_sirasi": sira})})
    govde = {"contents": [{"role": "user", "parts": parcalar}],
             "generationConfig": {"responseMimeType": "application/json", "responseSchema": SEMA, "temperature": 0}}
    t0 = time.monotonic()
    try:
        istek = urllib.request.Request(API.format(model=model), data=json.dumps(govde).encode(), method="POST",
                                       headers={"Content-Type": "application/json", "x-goog-api-key": anahtar})
        with urllib.request.urlopen(istek, timeout=zaman_asimi) as r:
            yanit = json.loads(r.read().decode())
        metin = yanit["candidates"][0]["content"]["parts"][0]["text"]
        sonuc = json.loads(metin)
    except urllib.error.HTTPError as exc:
        return {"durum": "BILINMIYOR", "hata": f"HTTP {exc.code}: {exc.read()[:160].decode('utf-8', 'ignore')}"}
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError, TimeoutError) as exc:
        return {"durum": "BILINMIYOR", "hata": str(exc)[:160]}
    sonuc["guven"] = max(0.0, min(1.0, float(sonuc.get("guven") or 0)))
    sonuc["model"] = model
    sonuc["sure_sn"] = round(time.monotonic() - t0, 1)
    kullanim = yanit.get("usageMetadata") or {}
    sonuc["token"] = {"giris": kullanim.get("promptTokenCount"), "cikis": kullanim.get("candidatesTokenCount")}
    return sonuc


def karar_ver(sonuc: dict[str, Any], gecmis: list[dict[str, Any]]) -> str | None:
    """Uyarı gerekiyorsa sebep metni, yoksa None. gecmis: bu baskının önceki değerlendirmeleri (eskiden yeniye)."""
    durum = sonuc.get("durum")
    if durum == "HATA" and float(sonuc.get("guven") or 0) >= HATA_GUVEN_ESIGI:
        return "hata"
    if durum == "HATA":
        durum = "SUPHELI"  # düşük güvenli HATA şüphe sayılır
    if durum == "SUPHELI" and gecmis and gecmis[-1].get("durum") in ("SUPHELI", "HATA"):
        return "iki_supheli"
    return None


def kaydet(dosya_adi: str, sonuc: dict[str, Any], kare: bytes | None = None) -> Path:
    """Değerlendirmeyi (ve uyarı karesini) baskı kaydına yazar — ileride eşik ayarı ve öğrenme için."""
    guvenli = "".join(c if c.isalnum() or c in "-_." else "_" for c in Path(dosya_adi).stem)[:80] or "baski"
    klasor = KAYIT_KLASORU / guvenli
    klasor.mkdir(parents=True, exist_ok=True)
    zaman = time.strftime("%Y%m%d-%H%M%S")
    if kare is not None:
        (klasor / f"{zaman}-{sonuc.get('durum', 'X')}.jpg").write_bytes(kare)
    with (klasor / "kontrol.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"zaman": zaman, **sonuc}, ensure_ascii=False) + "\n")
    return klasor


def ozet_satiri(sonuc: dict[str, Any]) -> str:
    d = sonuc.get("durum")
    if d == "BILINMIYOR":
        return f"🤖 YZ kontrol yapılamadı ({str(sonuc.get('hata', ''))[:80]})"
    isaret = {"NORMAL": "🟢", "SUPHELI": "🟡", "HATA": "🔴"}.get(d, "⚪")
    sorun = "" if sonuc.get("sorun") in (None, "yok") else f" · {sonuc['sorun'].replace('_', ' ')}"
    return f"🤖 {isaret} YZ: *{d}*{sorun} (%{round(float(sonuc.get('guven') or 0) * 100)}) — {str(sonuc.get('aciklama', '')).replace('*', '').replace('_', ' ').replace('`', '')}"
