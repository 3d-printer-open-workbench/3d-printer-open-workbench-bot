"""Baskı sonu YZ raporu: tüm baskıyı (timelapse seçkisi + YZ kontrol geçmişi + dilimleme ayarları + bakım
durumu) Gemini'ye inceletir → kalite gözlemleri, DİLİMLEME ayar önerileri ve MAKİNE BAKIM önerileri.

- Ayar önerileri yalnız `orca_dilim.IZINLI_AYARLAR` içindeki anahtarlar ve güvenli aralıklarla kabul edilir;
  Patron onaylarsa ürünün dilimleme KATEGORİSİNE uygulanır (`orca_dilim.kategori_guncelle`).
- Bakım takibi `config/bakim.yaml`: kalem başına aralık (saat) ve son yapıldığı makine saati; makine saati
  ERP'den (`machine.total_worked_hours`). ERP'ye yazılmaz (parça kalemleri saatlik maliyeti değiştirir).
- Gemini ücretsiz katman (ödeme yöntemi tanımlı değil): GEMINI_RAPOR_MODELI (vars. gemini-3.5-flash).
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from .ayar import BASKI_KAYITLARI_KLASORU, CONFIG_KLASORU, _env_dosyasi_yukle
from .orca_dilim import IZINLI_AYARLAR, ayar_dogrula

BAKIM_DOSYASI = CONFIG_KLASORU / "bakim.yaml"
RAPOR_KLASORU = BASKI_KAYITLARI_KLASORU / "raporlar"
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
VARSAYILAN_MODEL = "gemini-3.5-flash"
MAKS_KARE = 10

SEMA = {
    "type": "OBJECT",
    "properties": {
        "genel": {"type": "STRING", "enum": ["BASARILI", "KUSURLU", "BASARISIZ", "BELIRSIZ"]},
        "ozet": {"type": "STRING"},
        "gozlemler": {"type": "ARRAY", "items": {"type": "STRING"}},
        "dilimleme_onerileri": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "ayar": {"type": "STRING"}, "onerilen": {"type": "STRING"}, "gerekce": {"type": "STRING"},
            "guven": {"type": "NUMBER"}}, "required": ["ayar", "onerilen", "gerekce", "guven"]}},
        "bakim_onerileri": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "is": {"type": "STRING"}, "neden": {"type": "STRING"},
            "aciliyet": {"type": "STRING", "enum": ["simdi", "yakinda", "izle"]}},
            "required": ["is", "neden", "aciliyet"]}},
    },
    "required": ["genel", "ozet", "gozlemler", "dilimleme_onerileri", "bakim_onerileri"],
}


# --- Bakım takibi ---------------------------------------------------------------------------------------------
def bakim_oku(dosya: Path | None = None) -> dict[str, Any]:
    d = dosya or BAKIM_DOSYASI
    return (yaml.safe_load(d.read_text(encoding="utf-8")) or {}) if d.exists() else {"kalemler": {}}


def bakim_durumu(makine_saati: float, dosya: Path | None = None) -> list[dict[str, Any]]:
    """Her kalem: {anahtar, is, aralik, gecen, kalan, durum: GECIKTI|YAKLASTI|TAMAM|KAYIT_YOK}."""
    sonuc = []
    for k, v in (bakim_oku(dosya).get("kalemler") or {}).items():
        aralik = float(v.get("aralik_saat") or 0)
        son = v.get("son_saat")
        gecen = makine_saati - float(son) if son is not None else makine_saati
        kalan = aralik - gecen
        if son is None and makine_saati < aralik:
            durum = "KAYIT_YOK"
        elif kalan <= 0:
            durum = "GECIKTI"
        elif kalan <= 0.15 * aralik:
            durum = "YAKLASTI"
        else:
            durum = "TAMAM"
        sonuc.append({"anahtar": k, "is": v.get("is", k), "aralik": aralik, "gecen": round(gecen, 1),
                      "kalan": round(kalan, 1), "durum": durum})
    return sonuc


def bakim_yapildi(anahtar: str, makine_saati: float, dosya: Path | None = None) -> dict[str, Any]:
    d = dosya or BAKIM_DOSYASI
    metin = d.read_text(encoding="utf-8")
    veri = yaml.safe_load(metin) or {}
    kalem = (veri.get("kalemler") or {}).get(anahtar)
    if kalem is None:
        raise ValueError(f"bakım kalemi yok: {anahtar}")
    kalem["son_saat"] = round(float(makine_saati), 2)
    kalem["son_tarih"] = dt.date.today().isoformat()
    yorum = "".join(s for s in metin.splitlines(keepends=True)[:20] if s.startswith("#"))
    d.write_text(yorum + yaml.safe_dump(veri, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return kalem


def bakim_metni(durum: list[dict[str, Any]], makine_saati: float) -> str:
    isaret = {"GECIKTI": "🔴", "YAKLASTI": "🟡", "TAMAM": "🟢", "KAYIT_YOK": "⚪"}
    s = [f"🛠️ *Bakım durumu* — makine `{makine_saati:.1f} sa` (ERP)"]
    for b in durum:
        ek = (f"{-b['kalan']:.0f} sa gecikti" if b["durum"] == "GECIKTI" else
              f"{b['kalan']:.0f} sa kaldı" if b["durum"] in ("YAKLASTI", "TAMAM") else "henüz kaydı yok")
        s.append(f"{isaret[b['durum']]} {b['is']} — her {b['aralik']:.0f} sa · {ek}")
    return "\n".join(s)


# --- Gemini raporu --------------------------------------------------------------------------------------------
def kare_secki(kareler: list[Path], adet: int = MAKS_KARE) -> list[Path]:
    """Baskının başından sonuna eşit aralıklı kareler (ilk ve son dahil)."""
    if len(kareler) <= adet:
        return list(kareler)
    adim = (len(kareler) - 1) / (adet - 1)
    return [kareler[round(i * adim)] for i in range(adet)]


def rapor_istemi(baglam: dict[str, Any]) -> str:
    izinli = {k: (sorted(v[1]) if v[0] == "secim" else f"{v[1]}–{v[2]}") for k, v in IZINLI_AYARLAR.items()}
    return (
        "Sen deneyimli bir FDM 3B baskı mühendisisin (OrcaSlicer, CoreXY, Elegoo Centauri Carbon, 0.4 mm nozul). "
        "Görseller, biten bir baskının kapalı kabin iç kamerasından başından sonuna sıralı karelerdir.\n\n"
        f"BASKI BİLGİSİ:\n{json.dumps(baglam, ensure_ascii=False, indent=1)}\n\n"
        "Görevin:\n"
        "1) genel: BASARILI / KUSURLU (bitti ama kusur var) / BASARISIZ / BELIRSIZ (görüntüden anlaşılmıyor).\n"
        "2) gozlemler: karelerde GERÇEKTEN gördüğün somut şeyler (ilk katman yapışması, kalkma, ipliklenme, "
        "sarkma, destek davranışı, yüzey, tabla temizliği, nozulda birikinti…). Görmediğini yazma.\n"
        "3) dilimleme_onerileri: yalnız gözlemle desteklenen ve şu anahtarlardan olan öneriler: "
        f"{json.dumps(izinli, ensure_ascii=False)}. `onerilen` bu aralık/seçeneklerde olmalı; mevcut değer zaten "
        "iyiyse öneri YAPMA. Sıcaklık, akış, hız profili gibi listede olmayan bir şey gerekiyorsa onu "
        "bakim_onerileri'ne 'Orca'da elle kontrol et: …' diye yaz. guven 0-1.\n"
        "4) bakim_onerileri: görüntüdeki işaretler (tablada kalıntı/parmak izi, nozulda topak, filament tozu, "
        "titreşim izi…) VE verilen bakım durumu (gecikmiş kalemler) üzerinden; aciliyet simdi / yakinda / izle.\n"
        "5) ozet: Patron için 1-2 cümle Türkçe.\n"
        "Emin olmadığın konuda öneri verme; az ama doğru öneri ver."
    )


def _gemini(parcalar: list[dict], model: str, anahtar: str, zaman_asimi: float = 120.0) -> dict[str, Any]:
    govde = {"contents": [{"role": "user", "parts": parcalar}],
             "generationConfig": {"responseMimeType": "application/json", "responseSchema": SEMA, "temperature": 0.2}}
    istek = urllib.request.Request(API.format(model=model), data=json.dumps(govde).encode(), method="POST",
                                   headers={"Content-Type": "application/json", "x-goog-api-key": anahtar})
    with urllib.request.urlopen(istek, timeout=zaman_asimi) as r:
        yanit = json.loads(r.read().decode())
    return json.loads(yanit["candidates"][0]["content"]["parts"][0]["text"])


def rapor_uret(kareler: list[bytes], baglam: dict[str, Any]) -> dict[str, Any]:
    _env_dosyasi_yukle()
    anahtar = os.environ.get("GEMINI_API_KEY", "")
    model = os.environ.get("GEMINI_RAPOR_MODELI") or VARSAYILAN_MODEL
    if not anahtar:
        return {"genel": "BELIRSIZ", "hata": "GEMINI_API_KEY tanımlı değil"}
    if not kareler:
        return {"genel": "BELIRSIZ", "hata": "timelapse karesi yok"}
    parcalar = [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(k).decode()}} for k in kareler]
    parcalar.append({"text": rapor_istemi(baglam)})
    try:
        rapor = _gemini(parcalar, model, anahtar)
    except urllib.error.HTTPError as exc:
        return {"genel": "BELIRSIZ", "hata": f"HTTP {exc.code}: {exc.read()[:160].decode('utf-8', 'ignore')}"}
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError, TimeoutError) as exc:
        return {"genel": "BELIRSIZ", "hata": str(exc)[:160]}
    rapor["model"] = model
    return rapor


def bekleyen_oneriler(limit: int = 10, klasor: Path | None = None) -> list[dict[str, Any]]:
    """Henüz uygulanmamış dilimleme önerisi içeren raporlar (en yeni önce) — "Şimdi Değil" denenler dahil;
    Patron istediği an uygulayabilir. Her öğe: {rid, kategori, sku, oneriler, ertelendi}."""
    k = klasor or RAPOR_KLASORU
    if not k.exists():
        return []
    sonuc = []
    for yol in sorted(k.glob("*.json"), reverse=True):
        try:
            r = json.loads(yol.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if r.get("oneriler") and not r.get("uygulandi") and r.get("kategori"):
            sonuc.append({"rid": yol.stem, "kategori": r["kategori"], "sku": r.get("sku"),
                          "oneriler": r["oneriler"], "ertelendi": r.get("ertelendi")})
            if len(sonuc) >= limit:
                break
    return sonuc


def onerileri_suz(rapor: dict[str, Any], mevcut: dict[str, Any], min_guven: float = 0.5) -> list[dict[str, Any]]:
    """Geçerli (izinli, aralıkta, mevcuttan farklı, yeterince emin) dilimleme önerileri."""
    temiz = []
    for o in rapor.get("dilimleme_onerileri") or []:
        try:
            dogru = ayar_dogrula({o["ayar"]: o["onerilen"]})
        except (ValueError, KeyError):
            continue
        ayar, deger = next(iter(dogru.items()))
        if str(mevcut.get(ayar, "")).strip() == deger or float(o.get("guven") or 0) < min_guven:
            continue
        temiz.append({"ayar": ayar, "mevcut": mevcut.get(ayar), "onerilen": deger, "gerekce": o.get("gerekce", ""),
                      "guven": round(float(o.get("guven") or 0), 2)})
    return temiz


def rapor_kaydet(rapor: dict[str, Any]) -> str:
    RAPOR_KLASORU.mkdir(parents=True, exist_ok=True)
    rid = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    (RAPOR_KLASORU / f"{rid}.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")
    return rid


def rapor_oku(rid: str) -> dict[str, Any] | None:
    yol = RAPOR_KLASORU / f"{rid}.json"
    return json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else None


def _md(metin: Any) -> str:
    return str(metin or "").replace("*", "").replace("_", " ").replace("`", "'")


def rapor_metni(rapor: dict[str, Any], oneriler: list[dict[str, Any]], kategori: str | None) -> str:
    if rapor.get("hata"):
        return f"🤖 Baskı raporu üretilemedi: {_md(rapor['hata'])}"
    isaret = {"BASARILI": "✅", "KUSURLU": "🟡", "BASARISIZ": "🔴", "BELIRSIZ": "⚪"}
    s = [f"🤖 *Baskı sonu YZ raporu* {isaret.get(rapor.get('genel'), '⚪')} {rapor.get('genel')}",
         _md(rapor.get("ozet"))]
    if rapor.get("gozlemler"):
        s.append("\n*Gözlemler:*")
        s += [f"• {_md(g)}" for g in rapor["gozlemler"][:6]]
    if oneriler:
        s.append(f"\n*⚙️ Dilimleme önerileri* (kategori: `{kategori or '?'}`):")
        s += [f"• `{o['ayar']}`: {o['mevcut']} → *{o['onerilen']}* — {_md(o['gerekce'])} (%{round(o['guven'] * 100)})"
              for o in oneriler]
    if rapor.get("bakim_onerileri"):
        s.append("\n*🛠️ Bakım önerileri:*")
        ac = {"simdi": "🔴 şimdi", "yakinda": "🟡 yakında", "izle": "⚪ izle"}
        s += [f"• {ac.get(b.get('aciliyet'), '')} {_md(b.get('is'))} — {_md(b.get('neden'))}"
              for b in rapor["bakim_onerileri"][:6]]
    return "\n".join(s)[:3900]
