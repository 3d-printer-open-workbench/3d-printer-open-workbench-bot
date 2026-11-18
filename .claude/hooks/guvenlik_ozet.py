#!/usr/bin/env python3
"""Günlük güvenlik özeti: güvenlik kapısının yerel kayıtlarını özetleyip Patrona Telegram'dan gönderir.
Tamamen yerel okuma; yalnız özet metni Telegram botuna gider. 30 günden eski kayıtları siler.

Kullanım: python3 guvenlik_ozet.py [--gun YYYYMMDD] [--gonderme]
"""
from __future__ import annotations

import collections
import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guvenlik_kapisi as gk  # noqa: E402

SAKLAMA_GUN = 30


def ozet(gun: str) -> str:
    dosya = gk.KAYIT_KLASORU / f"arac-{gun}.jsonl"
    if not dosya.exists():
        return f"🛡️ Güvenlik özeti {gun}: kayıt yok (araç çağrısı olmamış)."
    satirlar = []
    for s in dosya.read_text(encoding="utf-8").splitlines():
        try:
            satirlar.append(json.loads(s))
        except json.JSONDecodeError:
            pass
    ajan = [s for s in satirlar if s.get("bot_ajani")]
    engel = [s for s in satirlar if s.get("karar") == "ENGEL"]
    araclar = collections.Counter(s.get("arac") for s in ajan)
    alanlar: collections.Counter[str] = collections.Counter()
    for s in ajan:
        if str(s.get("arac", "")).endswith("__navigate"):
            try:
                url = json.loads(s.get("girdi") or "{}").get("url", "")
            except json.JSONDecodeError:
                url = ""
            h = urllib.parse.urlsplit(url).hostname if url else None
            if h:
                alanlar[h] += 1
    m = [f"🛡️ *Güvenlik özeti* — {gun[6:8]}.{gun[4:6]}.{gun[:4]}",
         f"Araç çağrısı: {len(satirlar)} (bot ajanları: {len(ajan)})",
         f"Engellenen: {len(engel)}" + (" ⚠️" if engel else " ✅")]
    for e in engel[:8]:
        m.append(f"• {e.get('zaman', '')[11:16]} {e.get('arac')} — {e.get('neden', '')[:90]}")
    if araclar:
        m.append("Bot ajanlarının en çok kullandığı: " + ", ".join(f"{a} {n}" for a, n in araclar.most_common(5)))
    if alanlar:
        m.append("Chrome'da açılan siteler: " + ", ".join(f"{h} {n}" for h, n in alanlar.most_common(8)))
    hata = gk.KAYIT_KLASORU / "hook-hatalari.log"
    if hata.exists() and time.time() - hata.stat().st_mtime < 86400:
        m.append("⚠️ Güvenlik kapısında iç hata kaydı var: loglar/guvenlik/hook-hatalari.log")
    return "\n".join(m)


def eski_kayitlari_sil() -> None:
    sinir = time.time() - SAKLAMA_GUN * 86400
    for f in gk.KAYIT_KLASORU.glob("arac-*.jsonl"):
        if f.stat().st_mtime < sinir:
            f.unlink(missing_ok=True)


def main() -> int:
    gun = time.strftime("%Y%m%d")
    if "--gun" in sys.argv:
        gun = sys.argv[sys.argv.index("--gun") + 1]
    metin = ozet(gun)
    print(metin)
    if "--gonderme" not in sys.argv:
        (gk.UYARI_DURUM).unlink(missing_ok=True)  # özet, uyarı hız sınırına takılmasın
        gk.telegram_uyar(metin)
    eski_kayitlari_sil()
    return 0


if __name__ == "__main__":
    sys.exit(main())
