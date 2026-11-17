"""E-ticaret stüdyo karelerinin Claude denetimi (Patron kararı 2026-11-16: "Claude tarafından denetlenmeli, olana kadar
ürettirilmeli").

Qwen kareleri ürettikten sonra Claude ajanı her kareyi kaynak Blender render'ıyla yan yana inceler; kusurlu kareyi
yeni tohumla yeniden ürettirir (`coo.studyo_qwen --renk <slug> --sadece <kare> --tohum <n>`), tekrar bakar. Kare başına
en fazla `MAKS_DENEME` üretim. Sonuç `gorsel/denetim.json`; bot kareleri albüm olarak onay butonlarıyla Patrona gönderir.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ayar import PROGRAMLAR_KLASORU, PY_GORSEL, URUNLER_KLASORU
from .renk_hatti import urun_renkleri

KARELER = ("kapak-beyaz", "krem-fon", "koyu-fon", "doku-yakin")
MAKS_DENEME = 5


def denetim_yolu(sku: str, urunler: Path | None = None) -> Path:
    return (urunler or URUNLER_KLASORU) / sku / "gorsel" / "denetim.json"


def kare_listesi(sku: str, urunler: Path | None = None) -> list[dict[str, Any]]:
    """Denetlenecek kareler: her renk × 4 kare (+ ≥2 renkte vitrin). Kaynak = o rengin Blender render'ı."""
    kok = (urunler or URUNLER_KLASORU) / sku
    out: list[dict[str, Any]] = []
    renkler = urun_renkleri(sku, urunler)
    for r in renkler:
        rk = kok / str(r.get("klasor") or "gorsel")
        for ad in KARELER:
            yol = rk / "studyo-ic" / f"{ad}.png"
            if yol.exists():
                kaynak = rk / ("yakin.png" if ad == "doku-yakin" else "studyo.png")
                out.append({"kare": ad, "renk": r.get("slug"), "renk_ad": r.get("ad"), "hex": r.get("hex"),
                            "yol": str(yol), "kaynak": str(kaynak if kaynak.exists() else rk / "seffaf.png")})
    vitrin = kok / "gorsel" / "renkler-birlikte.png"
    if len(renkler) >= 2 and vitrin.exists():
        out.append({"kare": "vitrin", "renk": None, "renk_ad": ", ".join(str(r.get("ad")) for r in renkler),
                    "hex": None, "yol": str(vitrin),
                    "kaynak": ", ".join(str(kok / str(r.get("klasor")) / "seffaf.png") for r in renkler)})
    return out


def istem(sku: str, urunler: Path | None = None, not_: str = "") -> str:
    kareler = kare_listesi(sku, urunler)
    hedef = denetim_yolu(sku, urunler)
    komut = f"cd {PROGRAMLAR_KLASORU} && {PY_GORSEL} -m coo.studyo_qwen {sku}"
    satirlar = "\n".join(
        f"- `{k['yol']}` — {k['kare']}" + (f", renk {k['renk_ad']} `{k['hex']}` (--renk {k['renk']})" if k["renk"] else
                                           f", vitrin ({k['renk_ad']})") + f"; kaynak render: `{k['kaynak']}`"
        for k in kareler
    )
    return (
        f"Görev: `{sku}` ürününün e-ticaret stüdyo karelerini SATIŞA HAZIR olana kadar denetle ve gerekirse yeniden ürettir.\n"
        f"Kareler (her birini ve kaynağını Read ile aç, yan yana karşılaştır):\n{satirlar}\n"
        + (f"Patronun notu: {not_}\n" if not_ else "")
        + "Her karede şunları kontrol et — biri bile varsa KARE KALIR:\n"
        "1) Ürün kaynakla aynı mı: şekil, oran, yüz/detay, parça sayısı; eklenmiş/silinmiş/eriyen parça yok.\n"
        "2) Renk filament tonu mu (kaynakla aynı ton; turuncuya/pembeye kaymış, solmuş değil); çok renkte her parça kendi rengi.\n"
        "3) GÖLGE gerçekçi mi: tek ışık yönüyle tutarlı, ürünün altında yumuşak temas gölgesi; ürünün etrafında gri "
        "HALE / çift kontur / kopya silüet gölge, havada asılı gölge, ışığa ters gölge, ürünü kesen leke YOK.\n"
        "4) Fon temiz: kapak-beyaz düz beyaz (gri bulut/leke yok); krem-fon ve koyu-fon doğal; yazı, logo, filigran yok.\n"
        "5) Kadraj: ürün tamamen kadrajda, kesilmemiş; doku-yakın'da katman izleri gerçekçi (abartılı oluk değil).\n"
        f"Kalan kare için yeni tohumla yeniden üret (Bash, ~1,5 dk): "
        f"`{komut} --renk <slug> --sadece <kare> --tohum <yeni sayı> --acik-birak`"
        f" (vitrin için: `{komut} --sadece vitrin --tohum <yeni sayı> --acik-birak`). Komut kareyi aynı yola yazar; "
        "yeniden Read ile bak.\n"
        f"Kare başına en fazla {MAKS_DENEME} üretim (ilk dahil). Hepsi bitince ComfyUI'yi kapat: "
        f"`cd {PROGRAMLAR_KLASORU} && {PY_GORSEL} -m coo.qwen_edit --kapat` (pkill KULLANMA).\n"
        f"Sonucu `{hedef}` dosyasına Write ile yaz:\n"
        '{"kareler": [{"yol": "...", "kare": "kapak-beyaz", "renk": "slug", "karar": "gecti|kaldi", "deneme": 2, '
        '"not": "kısa Türkçe gözlem (gölge, renk, şekil)"}], "ozet": "1-2 cümle"}\n'
        "Kare dosyalarını elle düzenleme/çizme; yalnız komutla yeniden üret. Ürün klasöründe başka dosyaya dokunma."
    )


def sonuc_oku(sku: str, urunler: Path | None = None) -> dict[str, Any] | None:
    yol = denetim_yolu(sku, urunler)
    if not yol.exists():
        return None
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
