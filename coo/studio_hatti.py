"""Telegram'dan Open Workbench Studio araçları: Patron aracı seçer ve ne istediğini yazar; Claude ajanı (cad-artist)
Studio'yu MCP üzerinden (`mcp__workbench-studio__*`: maker_generator_params, make, job_summary, print_check) kullanarak
ürünü üretir. Yerel LLM yok — işi Claude yapar, Studio programı geometriyi üretir.

Ajan sonucu `.workbench/studio_isleri/<id>/sonuc.json` dosyasına yazar; bot önizlemeyi, özeti ve 3MF'i gönderir.
"""
from __future__ import annotations

import json
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from .ayar import KOK, STUDIO_URL

IS_KLASORU = KOK / ".workbench" / "studio_isleri"
ORNEKLER = {
    "kaligraf_flat": "ör. 'Kafe Ağaç' yazısı, 60 cm genişlik, 8 mm kalınlık, siyah, Montserrat, çift taraflı bant",
    "kaligraf_letters": "ör. 'Berber' 3B harfler, harf yüksekliği 200 mm, derinlik 30 mm, el yazısı font, mat siyah",
    "glow_rect": "ör. 30 cm 'OPEN' ışık kutusu, sıcak beyaz LED, duvara asılı",
    "maker_keychain": "ör. 'Elif' isimli anahtarlık, 5 cm, pembe + beyaz",
    "maker_qr_plaque": "ör. https://example.com için masaüstü QR plaket, 'Menü' yazılı, siyah-beyaz",
    "maker_nameplate": "ör. 'Dr. Ayşe Yılmaz — Diş Hekimi' masaüstü isimlik, ahşap rengi",
}


def katalog(url: str = STUDIO_URL) -> dict[str, Any]:
    with urllib.request.urlopen(f"{url}/api/config", timeout=15) as y:
        d = json.load(y)
    return {"aileler": d.get("families") or [], "urunler": d.get("products") or []}


def yeni_is(pid: str) -> tuple[str, Path]:
    iid = time.strftime("%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    k = IS_KLASORU / iid
    k.mkdir(parents=True, exist_ok=True)
    (k / "is.json").write_text(json.dumps({"pid": pid, "baslangic": time.time()}, ensure_ascii=False), encoding="utf-8")
    return iid, k


def is_bilgisi(iid: str) -> dict[str, Any]:
    p = IS_KLASORU / iid / "is.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def is_guncelle(iid: str, **alanlar: Any) -> None:
    p = IS_KLASORU / iid / "is.json"
    d = is_bilgisi(iid)
    d.update(alanlar)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def istem(pid: str, etiket: str, talep: str, klasor: Path, ekler: list[Path] | None = None,
          onceki: dict[str, Any] | None = None) -> str:
    ek = ""
    if ekler:
        ek = ("Patronun eklediği dosyalar (logo / referans; Read ile incele, logo ise job'a yolunu ver): "
              + ", ".join(f"`{p}`" for p in ekler) + "\n")
    rev = ""
    if onceki:
        rev = (f"BU BİR REVİZE: önceki iş klasörü `{onceki.get('job_dir')}` (job.json içindeki parametreleri temel al), "
               f"önceki istek: \"{onceki.get('talep', '')}\". Yalnız Patronun yeni notundaki değişiklikleri uygula.\n")
    return (
        f"Görev: Studio ile **{etiket}** (`{pid}`) üret. Patronun isteği: \"{talep}\"\n"
        + ek + rev
        + "Studio araçlarını MCP üzerinden kullan (`mcp__workbench-studio__*`); geometriyi KENDİN yazma:\n"
        f"1) `maker_generator_params` ile `{pid}` parametre şemasını al (tür, aralık, seçenek, Türkçe etiket).\n"
        "2) İstekten parametreleri çıkar. Söylenmeyenler için şemadaki varsayılanı ya da ürüne en uygun değeri seç ve "
        "bunu `varsayimlar` listesine yaz. Renkleri #RRGGBB olarak ver (gerekirse `color_info`). Metin/yazı Patronun "
        "yazdığı gibi, harfi harfine (Türkçe karakterler dahil).\n"
        f"3) `make` ile üret (job: {{generator: \"{pid}\", name: <kısa ad>, params: {{...}}}}). Hata dönerse mesajı oku, "
        "parametreyi düzelt, en fazla 2 kez yeniden dene.\n"
        "4) `job_summary` ile gerçek ölçü, gram, süre, renk, parça sayısını al; `print_check` varsa çalıştır.\n"
        "5) İş klasöründeki dosyaları bul (job.json, model.3mf, parts/*.stl, render/önizleme PNG). Önizleme yoksa "
        "klasördeki en büyük PNG render'ı seç.\n"
        f"6) Sonucu şu JSON olarak `{klasor / 'sonuc.json'}` dosyasına Write ile yaz:\n"
        '{"basarili": true, "job_dir": "...", "onizleme": "<png yolu>", "proje_3mf": "<model.3mf yolu>", '
        '"stl": ["..."], "ozet": "ölçü · gram · süre · renkler · parça (Türkçe, 2-4 satır)", '
        '"parametreler": {...}, "varsayimlar": ["..."]}\n'
        "Başarısızsa {\"basarili\": false, \"hata\": \"neden (Türkçe)\"} yaz. Yazıcıya iş gönderme, baskı başlatma; "
        "yalnız Studio ile dosya üret."
    )


def sonuc_oku(klasor: Path) -> dict[str, Any] | None:
    p = klasor / "sonuc.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
