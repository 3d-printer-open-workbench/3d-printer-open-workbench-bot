"""Reels çıktısını "izleyip" düzeltme önerisi listesi çıkarma → Patron seçer → seçilenler ilgili ajana revize istemi.

Patron (2026-11-17): "reels üreteceğim zaman çıktıları izlesin ve düzeltmeleri bana yazsın, ben onaylamak istediğim
maddeleri seçeyim, onları düzeltecek promptları ilgili ajana versin."

Akış: video → `brand-guardian` (Opus, bağımsız denetçi) `coo.video_izle` ile kare panoları + transkript çıkarır,
izler ve `<kid>.json` yazar → bot maddeleri seçilebilir düğmelerle gösterir → "Seçilenleri Düzelt" →
`duzeltme_istemi` üreten ajana (HyperFrames: projeyi düzenle + yeniden render; Flow: aynı başlangıç karesinden yeni
video; diğer: kaynaklardan yeniden kurgu) verilir → yeni video yine denetime girer.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .ayar import MAGAZA_KLASORU, ORTAMLAR_KLASORU, PROGRAMLAR_KLASORU

KAYIT_KLASORU = MAGAZA_KLASORU / "reels_denetim"
PY_VIDEO = ORTAMLAR_KLASORU / ".venv-video" / "bin" / "python"
ONEM_SIMGE = {"yuksek": "🔴", "orta": "🟠", "dusuk": "🟡"}

# kaynak["tur"] → videoyu üreten / düzeltecek ajan
DUZELTEN_AJAN = {"hf": "reels-tiktok-strategist", "flow": "cmo-store-director", "kurgu": "reels-tiktok-strategist"}


def kayit_yolu(kid: str, klasor: Path | None = None) -> Path:
    return (klasor or KAYIT_KLASORU) / f"{kid}.json"


def yeni_kayit(video: Path, kaynak: dict[str, Any], klasor: Path | None = None) -> str:
    """kaynak: {"tur": "hf"|"flow"|"kurgu", "sku": ..., "proje": HyperFrames klasörü, "baslangic_karesi": ...}"""
    kid = uuid.uuid4().hex[:8]
    yol = kayit_yolu(kid, klasor)
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps({"kid": kid, "video": str(video), "kaynak": kaynak, "maddeler": [], "secili": [],
                               "durum": "DENETLENIYOR"}, ensure_ascii=False, indent=2), encoding="utf-8")
    return kid


def oku(kid: str, klasor: Path | None = None) -> dict[str, Any]:
    return json.loads(kayit_yolu(kid, klasor).read_text(encoding="utf-8"))


def yaz(kayit: dict[str, Any], klasor: Path | None = None) -> None:
    kayit_yolu(kayit["kid"], klasor).write_text(json.dumps(kayit, ensure_ascii=False, indent=2), encoding="utf-8")


def denetim_istemi(kid: str, klasor: Path | None = None) -> str:
    k = oku(kid, klasor)
    yol = kayit_yolu(kid, klasor)
    sku = k["kaynak"].get("sku")
    return (
        f"Görev: BAĞIMSIZ REELS DENETİMİ. Video: `{k['video']}`" + (f" (ürün `{sku}`)" if sku else "") + ".\n"
        "1) Videoyu izle: `video-izle` becerisine uy → "
        f"`cd {PROGRAMLAR_KLASORU} && {PY_VIDEO} -m coo.video_izle \"{k['video']}\" --en-fazla 60 --dil tr`; "
        "yazdırılan `izle.md`'yi ve TÜM panoları Read ile oku; ffprobe ile süre/çözünürlük/ses akışını kontrol et.\n"
        + (f"2) Gerçekle karşılaştır: `veri/02_Urunler/{sku}/urun.yaml` (ad, ölçü, malzeme) ve stüdyo görselleri — "
           "üründe şekil/renk bozulması, yanlış ölçü/yazı var mı?\n" if sku else "2) Marka ve konu tutarlılığı.\n")
        + "3) Denetle: ilk 2 sn kanca gücü, tempo (her 2–3 sn değişim), Türkçe yazı (ş/ğ/ı/İ/ö/ü/ç, harf bozulması), "
        "güvenli alan (üst %14, alt %35), ürün sadakati, okunabilirlik/kontrast, ses (var mı, seviye), sonda tek çağrı, "
        "marka/telif riski (logo, lisanslı karakter), 9:16 ve süre.\n"
        f"4) Sonucu `{yol}` dosyasındaki JSON'a yaz: `maddeler` alanını şu biçimde doldur (en fazla 8, önem sırasıyla; "
        "yalnız gerçekten düzeltilmesi gerekenler; uydurma sorun yazma):\n"
        '   [{"no": 1, "zaman": "0:02", "onem": "yuksek|orta|dusuk", "sorun": "kısa Türkçe", '
        '"duzeltme": "uygulanabilir somut talimat (ne, nerede, nasıl)"}]\n'
        "   ve `genel` alanına 1–2 cümlelik genel değerlendirme; `durum`: \"HAZIR\". Diğer alanlara dokunma.\n"
        "5) Son satır: `DENETIM_HAZIR <madde sayısı>` ya da `DENETIM_HATA <neden>`."
    )


def secimi_degistir(kid: str, no: int, klasor: Path | None = None) -> dict[str, Any]:
    k = oku(kid, klasor)
    secili = set(k.get("secili") or [])
    secili ^= {no}
    k["secili"] = sorted(secili)
    yaz(k, klasor)
    return k


def hepsini_sec(kid: str, klasor: Path | None = None) -> dict[str, Any]:
    k = oku(kid, klasor)
    k["secili"] = [m["no"] for m in k.get("maddeler") or []]
    yaz(k, klasor)
    return k


def kapat(kid: str, klasor: Path | None = None) -> dict[str, Any]:
    """"👍 Olduğu Gibi Kalsın": denetim kapanır (📋 Bekleyen İşler'de artık görünmez)."""
    k = oku(kid, klasor)
    k["durum"] = "KAPANDI"
    yaz(k, klasor)
    return k


def ozet_metni(k: dict[str, Any]) -> str:
    satirlar = [f"🔍 *Reels denetimi* — `{Path(k['video']).name}`"]
    if k.get("genel"):
        satirlar.append(f"_{k['genel']}_")
    if not k.get("maddeler"):
        satirlar.append("✅ Düzeltilecek madde bulunmadı.")
    for m in k.get("maddeler") or []:
        satirlar.append(f"{ONEM_SIMGE.get(m.get('onem'), '•')} *{m['no']}.* `{m.get('zaman', '')}` {m.get('sorun', '')}\n"
                        f"   ↳ {m.get('duzeltme', '')}")
    if k.get("maddeler"):
        satirlar.append("\nDüzeltilmesini istediklerini seç (☑), sonra *✅ Seçilenleri Düzelt*.")
    return "\n".join(satirlar)


def butonlar(k: dict[str, Any]) -> list[list[dict[str, str]]]:
    kid = k["kid"]
    secili = set(k.get("secili") or [])
    tuslar = [{"text": ("☑ " if m["no"] in secili else "☐ ") + str(m["no"]), "callback_data": f"rd:sec:{kid}:{m['no']}"}
              for m in k.get("maddeler") or []]
    satirlar = [tuslar[i:i + 4] for i in range(0, len(tuslar), 4)]
    if tuslar:
        satirlar.append([{"text": "☑ Tümünü Seç", "callback_data": f"rd:hepsi:{kid}"},
                         {"text": f"✅ Seçilenleri Düzelt ({len(secili)})", "callback_data": f"rd:uygula:{kid}"}])
    satirlar.append([{"text": "✏️ Not ile Düzenle", "callback_data": f"rd:not:{kid}"},
                     {"text": "👍 Olduğu Gibi Kalsın", "callback_data": f"rd:kapat:{kid}"}])
    return satirlar


def duzeltme_istemi(kid: str, klasor: Path | None = None, serbest_not: str = "") -> tuple[str, str]:
    """Seçili maddeler ve/veya Patronun serbest notu → (ajan, istem). Ajan videoyu yeniden üretir; çıktı yolu istemde."""
    k = oku(kid, klasor)
    secili = set(k.get("secili") or [])
    maddeler = [m for m in k.get("maddeler") or [] if m["no"] in secili]
    liste = "\n".join(f"- [{m['no']}] {m.get('zaman', '')} {m.get('sorun', '')} → {m['duzeltme']}" for m in maddeler)
    if serbest_not.strip():
        liste = (liste + "\n" if liste else "") + f"- [PATRON NOTU — öncelikli] {serbest_not.strip()}"
        k.setdefault("notlar", []).append(serbest_not.strip())
    kaynak = k["kaynak"]
    tur = kaynak.get("tur", "kurgu")
    video = Path(k["video"])
    yeni = video.with_name(video.stem + "-r" + ".mp4") if not video.stem.endswith("-r") else \
        video.with_name(video.stem + "2.mp4")
    ortak = (f"Patronun ONAYLADIĞI düzeltmeler (yalnız bunları uygula, başka şeyi değiştirme):\n{liste}\n"
             f"Yeni videoyu `{yeni}` yoluna yaz (eskisini silme). Ürün görüntüsü/ölçü kuralları aynen geçerli.\n")
    if tur == "hf":
        istem = (f"Görev: HyperFrames Reels REVİZYONU. Proje: `{kaynak.get('proje')}` (yoksa `{video}`'yu üreten "
                 "projeyi Video_Atölyesi altında bul). `hyperframes` + `hyperframes-cli` becerilerini yükle; ilgili "
                 "kompozisyonları düzenle → lint → `check --json` → düzeltilen sahnelerin `snapshot`'ını Read ile gör → "
                 "render.\n" + ortak + "Son satır: `HF_REELS_HAZIR <yol> <sn>` ya da `HF_REELS_HATA <neden>`.")
    elif tur == "flow":
        istem = (f"Görev: Flow konsept Reels REVİZYONU (`{kaynak.get('sku')}`). `flow` becerisine uy. Başlangıç karesi: "
                 f"`{kaynak.get('baslangic_karesi')}`; önceki istem: «{kaynak.get('istem', '')}». Düzeltmeleri istem "
                 "metnine işle, aynı ayarlarla (9:16, Kareler, x1) yeni video üret, indir, sesi koru.\n" + ortak +
                 "Son satır: `KONSEPT_HAZIR 0 video=var` ya da `KONSEPT_HATA <neden>`.")
    else:
        istem = (f"Görev: Reels kurgu REVİZYONU. Video: `{video}`" + (f" (ürün `{kaynak.get('sku')}`)" if kaynak.get("sku")
                 else "") + ". Aynı gerçek kaynaklardan ffmpeg ile düzeltilmiş kurgu üret; Flow sesini/ana sesi koru.\n"
                 + ortak + "Son satır: `REELS_HAZIR <yol>`.")
    k["durum"] = "DUZELTILIYOR"
    k["yeni_video"] = str(yeni)
    yaz(k, klasor)
    return DUZELTEN_AJAN.get(tur, "reels-tiktok-strategist"), istem
