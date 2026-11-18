"""Mağaza metni kontrolü ve editör review kaydı (config/marka/magaza-metin-rehberi.md).

Patron kararı 2026-11-17: açıklamalar kısa, insan sesiyle ve profesyonel olur; her metin kıdemli editör
review'undan geçer. Review kaydı olmayan veya review'dan sonra değişmiş metin İkas'a yüklenmez.

    python3 -m coo.metin_denetim <sku>                      # yalnız kontrol (çıkış 1 = hata var)
    python3 -m coo.metin_denetim <sku> --review "not"       # kontrol geçerse review kaydını yazar
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

from .ayar import URUNLER_KLASORU

REHBER = "config/marka/magaza-metin-rehberi.md"
EN_AZ_KELIME, EN_FAZLA_KELIME = 50, 130
EN_FAZLA_MADDE, EN_FAZLA_MADDE_KELIME, EN_FAZLA_TABLO_SATIR = 4, 14, 5
BASLIK_SINIRI, META_SINIRI = 70, 155

YASAKLI = (
    "ilham alan", "ilhamını", "dokunuş kat", "karakter kat", "hayat ver", "şıklık", "şık ve fonksiyonel",
    "mükemmel", "kusursuz", "eşsiz", "benzersiz", "harika", "göz alıcı", "vazgeçilmez", "ideal",
    "uyum sağlar", "sevimli bir yolu", "ile tanışın", "sadece bir", "yaşam alanınız", "tarzınızı",
    "fark yarat", "el yapımı", "su geçirmez", "kalite kontrol", "temas yüzey", "katman kalınlığı",
    "renk değiştirilerek", "fdm", "dilimle",
)
TEKRAR_EDEMEZ = ("siparişe özel", "kargo ücreti", "3b modelden", "filament partisi", "55")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def _duz(parca: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", parca))).strip()


def kelime_sayisi(aciklama_html: str) -> int:
    """Tablo hariç görünen metnin kelime sayısı."""
    return len(_duz(re.sub(r"<table.*?</table>", " ", aciklama_html, flags=re.S | re.I)).split())


def ozet(aciklama_html: str) -> str:
    return hashlib.sha1(aciklama_html.strip().encode("utf-8")).hexdigest()[:12]


def denetle(paket: dict[str, Any]) -> list[str]:
    """Rehbere aykırılıkları döndürür (boş = geçti)."""
    h: list[str] = []
    a = str(paket.get("aciklama_html") or "")
    metin = _duz(re.sub(r"<table.*?</table>", " ", a, flags=re.S | re.I)).lower()
    n = kelime_sayisi(a)
    if n > EN_FAZLA_KELIME:
        h.append(f"açıklama çok uzun: {n} kelime (en fazla {EN_FAZLA_KELIME}, tablo hariç)")
    elif n < EN_AZ_KELIME:
        h.append(f"açıklama çok kısa: {n} kelime (en az {EN_AZ_KELIME})")
    for y in YASAKLI:
        if y in metin:
            h.append(f"yasaklı ifade: '{y}'")
    for t in TEKRAR_EDEMEZ:
        if metin.count(t) > 1:
            h.append(f"tekrar: '{t}' {metin.count(t)} kez geçiyor")
    maddeler = re.findall(r"<li>(.*?)</li>", a, re.S | re.I)
    if len(maddeler) > EN_FAZLA_MADDE:
        h.append(f"{len(maddeler)} madde (en fazla {EN_FAZLA_MADDE})")
    for m in maddeler:
        if re.match(r"\s*<strong>[^<]*:\s*</strong>", m) or re.match(r"\s*<strong>[^<]*</strong>\s*:", m):
            h.append("'Kalın etiket: açıklama' madde kalıbı kullanılmış")
            break
    for m in maddeler:
        if len(_duz(m).split()) > EN_FAZLA_MADDE_KELIME:
            h.append(f"uzun madde ({len(_duz(m).split())} kelime): {_duz(m)[:40]}…")
    satir = len(re.findall(r"<tr", a, re.I))
    if satir > EN_FAZLA_TABLO_SATIR:
        h.append(f"tabloda {satir} satır (en fazla {EN_FAZLA_TABLO_SATIR})")
    if "!" in metin or EMOJI.search(a):
        h.append("ünlem veya emoji var")
    if a.count("—") > 0:
        h.append("uzun tire (—) kullanılmış")
    if len(re.findall(r"<h[1-6]", a, re.I)) > 1:
        h.append("ara başlık kullanılmış (en fazla 1)")
    baslik = str(paket.get("baslik") or "")
    if len(baslik) > BASLIK_SINIRI:
        h.append(f"başlık {len(baslik)} karakter (en fazla {BASLIK_SINIRI})")
    if len(re.findall(r"\s[-–—|]\s|,", baslik)) > 1:
        h.append("başlıkta birden fazla ayraç/virgül (anahtar kelime yığını)")
    meta = str(paket.get("meta_aciklama") or "")
    if len(meta) > META_SINIRI:
        h.append(f"meta açıklama {len(meta)} karakter (en fazla {META_SINIRI})")
    return h


def review_gecerli(paket: dict[str, Any]) -> tuple[bool, str]:
    """Editör review'u var mı ve metin review'dan sonra değişmemiş mi."""
    r = paket.get("metin_review") or {}
    if r.get("sonuc") not in ("ONAY", "DUZELTILDI"):
        return False, "metin editör review'undan geçmedi"
    if r.get("ozet") != ozet(str(paket.get("aciklama_html") or "")):
        return False, "metin review'dan sonra değişmiş; yeniden review gerekli"
    return True, ""


def yukleme_engelleri(paket: dict[str, Any]) -> list[str]:
    """İkas'a yüklemeden önce: rehber kontrolü + geçerli review."""
    engel = denetle(paket)
    tamam, neden = review_gecerli(paket)
    return engel + ([] if tamam else [neden])


def review_kaydet(sku: str, not_: str, editor: str = "kıdemli editör (Opus)",
                  urunler_klasoru: Path | None = None) -> list[str]:
    yol = (urunler_klasoru or URUNLER_KLASORU) / sku / "magaza" / "paket.json"
    paket = json.loads(yol.read_text(encoding="utf-8"))
    hatalar = denetle(paket)
    if hatalar:
        return hatalar
    a = str(paket.get("aciklama_html") or "")
    paket["metin_review"] = {"sonuc": "DUZELTILDI", "editor": editor, "tarih": dt.date.today().isoformat(),
                             "kelime": kelime_sayisi(a), "ozet": ozet(a), "not": not_, "rehber": REHBER}
    yol.write_text(json.dumps(paket, ensure_ascii=False, indent=2), encoding="utf-8")
    return []


def review_istemi(sku: str) -> str:
    """Yazarın paketinden sonra çalışan kıdemli editör görevi (Opus)."""
    return (
        f"Görev: KIDEMLİ E-TİCARET EDİTÖRÜ olarak `{sku}` mağaza metnini review et ve düzenle.\n"
        f"Önce `{REHBER}` dosyasını baştan sona oku. Sonra `veri/02_Urunler/{sku}/urun.yaml` ve "
        f"`veri/02_Urunler/{sku}/magaza/paket.json` dosyalarını aç.\n"
        "1) Her ölçü/özelliği urun.yaml ile karşılaştır; yanlışı düzelt, kaynağı olmayan iddiayı sil.\n"
        "2) `baslik`, `aciklama_html`, `meta_baslik`, `meta_aciklama` alanlarını rehbere göre yeniden yaz: kısa, "
        "insan sesiyle, profesyonel. Okunduğunda yapay, şişkin, tekrar eden ya da reklam kokan cümle kalmasın. "
        "Fiyat, görsel, varyant, maliyet ve etiket alanlarına DOKUNMA; dosya şemasını değiştirme.\n"
        f"3) `python3 -m coo.metin_denetim {sku} --review \"<ne değişti, tek cümle>\"` çalıştır. Hata verirse "
        "metni düzeltip tekrarla (en fazla 3 kez).\n"
        "4) Son satır: `METIN_REVIEW_TAMAM <kelime sayısı>` veya `METIN_REVIEW_HATA <neden>`."
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sku")
    ap.add_argument("--review", metavar="NOT", help="kontrol geçerse review kaydını yaz")
    a = ap.parse_args(argv)
    yol = URUNLER_KLASORU / a.sku / "magaza" / "paket.json"
    if not yol.exists():
        print(f"paket.json yok: {yol}")
        return 1
    if a.review is not None:
        hatalar = review_kaydet(a.sku, a.review)
    else:
        paket = json.loads(yol.read_text(encoding="utf-8"))
        hatalar = denetle(paket)
        tamam, neden = review_gecerli(paket)
        if not tamam:
            print(f"bilgi: {neden}")
    if hatalar:
        print("METIN_HATALI\n- " + "\n- ".join(hatalar))
        return 1
    paket = json.loads(yol.read_text(encoding="utf-8"))
    print(f"METIN_TAMAM {kelime_sayisi(str(paket.get('aciklama_html') or ''))} kelime")
    return 0


if __name__ == "__main__":
    sys.exit(main())
