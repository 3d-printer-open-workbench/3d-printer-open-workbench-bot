"""İş için yapılan baskının (numune / sipariş / hediye-tanıtım) yazıcı timelapse'ini kalıcı klasöre kopyalar.

`TimelapseToplayici.mp4_derle` her baskıda `<sku>/medya/timelapse.mp4` üzerine yazar; Patron (2026-11-17): "iş için
üretim seçtiysem numune, hediye veya sipariş direkt klasöre kopyalasın". Ürün eşleştiyse
`<sku>/medya/baski/<tarih>-<tür>.mp4`, eşleşmediyse `03_Magaza/baski_videolari/<tarih>-<tür>-<dosya>.mp4`.
Hobi ve fire kopyalanmaz.
"""
from __future__ import annotations

import datetime as dt
import re
import shutil
from pathlib import Path

from .ayar import MAGAZA_KLASORU, URUNLER_KLASORU

IS_TURLERI = {"IS_NUMUNE": "numune", "IS_SIPARIS": "siparis", "HEDIYE": "hediye"}
GENEL_KLASOR = MAGAZA_KLASORU / "baski_videolari"


def is_videosu_kopyala(senaryo: str, sku: str | None, dosya_adi: str = "", urunler: Path | None = None,
                       genel: Path | None = None, simdi: dt.datetime | None = None) -> Path | None:
    tur = IS_TURLERI.get(senaryo)
    if not tur:
        return None
    urunler = urunler or URUNLER_KLASORU
    kaynak = urunler / (sku or "_genel_baski") / "medya" / "timelapse.mp4"
    if not kaynak.is_file() or kaynak.stat().st_size == 0:
        return None
    damga = (simdi or dt.datetime.now()).strftime("%Y%m%d-%H%M")
    if sku:
        hedef = urunler / sku / "medya" / "baski" / f"{damga}-{tur}.mp4"
    else:
        ad = re.sub(r"[^A-Za-z0-9]+", "-", Path(dosya_adi).stem).strip("-")[:40] or "baski"
        hedef = (genel or GENEL_KLASOR) / f"{damga}-{tur}-{ad}.mp4"
    hedef.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(kaynak, hedef)
    return hedef
