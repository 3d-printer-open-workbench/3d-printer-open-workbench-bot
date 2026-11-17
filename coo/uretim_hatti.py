"""Üretim aşaması: baskı öncesi kontrol listesi, kritik katman izleme planı, fire/tartı hesapları.

Telegram'a bağlı değildir; `coo/__main__.py` çağırır. Kural: yazıcıya baskı başlatma komutu gönderilmez.
"""
from __future__ import annotations

from typing import Any

STOK_PAYI = 1.10            # gerekli gram + %10 (purge, brim, tahmin hatası)
RENK_FARK_ESIGI = 60.0      # RGB öklid; üstü "farklı renk takılı" (krem↔beyaz ≈20, krem↔terrakota ≈150)
ILK_KATMAN_KONTROL = 2      # bu katman bitince ilk katman fotoğrafı
KRITIK_GECIKME_KATMAN = 4   # ada/sarkma başladıktan bu kadar katman sonra fotoğraf (görünür olsun)


def _hex_rgb(h: str) -> tuple[int, int, int] | None:
    h = (h or "").strip().lstrip("#")
    if len(h) != 6:
        return None
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return None


def renk_farki(a: str, b: str) -> float | None:
    ra, rb = _hex_rgb(a), _hex_rgb(b)
    if ra is None or rb is None:
        return None
    return round(sum((x - y) ** 2 for x, y in zip(ra, rb)) ** 0.5, 1)


def baski_oncesi_kontrol(urun: dict[str, Any], yuklu_filament: dict[str, Any] | None,
                         tabla_bos: bool, yazici_durum: str = "") -> list[dict[str, Any]]:
    """Her madde: {ad, durum: ok|uyari|engel, mesaj}. 'engel' varsa baskı başlatılmamalı."""
    dil = urun.get("dilimleme") if isinstance(urun.get("dilimleme"), dict) else {}
    gram = float(dil.get("gercek_gram") or 0)
    k: list[dict[str, Any]] = []

    k.append({"ad": "Tabla", "durum": "ok" if tabla_bos else "engel",
              "mesaj": "Boş" if tabla_bos else "Dolu işaretli — önceki parça alınmadan baskı başlatma"})
    if yazici_durum == "BASKIDA":
        k.append({"ad": "Yazıcı", "durum": "engel", "mesaj": "Şu an başka bir baskı sürüyor"})

    if not yuklu_filament:
        k.append({"ad": "Filament", "durum": "uyari", "mesaj": "ERP'de makineye takılı filament tanımlı değil"})
    else:
        ad = f"{yuklu_filament.get('brand', '')} {yuklu_filament.get('material_type', '')} " \
             f"{yuklu_filament.get('color_name', '')}".strip()
        hedef = dil.get("renk_hex") or ""
        fark = renk_farki(str(yuklu_filament.get("color_hex") or ""), hedef) if hedef else None
        if fark is None:
            k.append({"ad": "Renk", "durum": "ok" if not hedef else "uyari",
                      "mesaj": f"Takılı: {ad}" + ("" if not hedef else " (renk kodu karşılaştırılamadı)")})
        elif fark > RENK_FARK_ESIGI:
            k.append({"ad": "Renk", "durum": "uyari",
                      "mesaj": f"Takılı {ad} ({yuklu_filament.get('color_hex')}), dilimlenen renk {hedef} — farklı"})
        else:
            k.append({"ad": "Renk", "durum": "ok", "mesaj": f"Takılı {ad} — seçilen renkle uyumlu"})
        kalan = float(yuklu_filament.get("remaining_weight_gr") or 0)
        if gram > 0:
            gerek = round(gram * STOK_PAYI)
            k.append({"ad": "Stok", "durum": "ok" if kalan >= gerek else "engel",
                      "mesaj": f"Makaradaki {kalan:.0f} g / gereken ~{gerek} g"
                               + ("" if kalan >= gerek else " — baskı yarıda biter")})
        mat = str(yuklu_filament.get("material_type") or "").lower()
        prof = str(dil.get("filament") or "").lower()
        if mat and prof and ("petg" in mat) != ("petg" in prof):
            k.append({"ad": "Malzeme", "durum": "engel",
                      "mesaj": f"Takılı {yuklu_filament.get('material_type')}, dilimleme profili {dil.get('filament')}"})

    if gram <= 0:
        k.append({"ad": "Dilimleme", "durum": "uyari", "mesaj": "Gerçek dilimleme verisi yok — önce ⚙️ Dilimle"})
    elif dil.get("destek_gerekli"):
        k.append({"ad": "Destek", "durum": "ok", "mesaj": f"Ağaç destekli: {dil.get('destek_nedeni', '')}"})
    return k


def kontrol_metni(k: list[dict[str, Any]]) -> str:
    isaret = {"ok": "✅", "uyari": "⚠️", "engel": "⛔"}
    return "\n".join(f"{isaret[m['durum']]} *{m['ad']}:* {m['mesaj']}" for m in k)


def engel_var(k: list[dict[str, Any]]) -> bool:
    return any(m["durum"] == "engel" for m in k)


def kritik_katmanlar(urun: dict[str, Any], toplam_katman: int = 0) -> list[tuple[int, str]]:
    """Baskı sırasında kamera fotoğrafı istenecek katmanlar: ilk katman + havada başlayan parçalar/sarkma."""
    dil = urun.get("dilimleme") if isinstance(urun.get("dilimleme"), dict) else {}
    katman = float(dil.get("katman_mm") or 0.2)
    plan: dict[int, str] = {ILK_KATMAN_KONTROL: "İlk katman tablaya yapıştı mı?"}
    for z in dil.get("riskli_z_mm") or []:
        try:
            n = int(round(float(z) / katman)) + KRITIK_GECIKME_KATMAN
        except (TypeError, ValueError):
            continue
        if toplam_katman and n >= toplam_katman:
            continue
        if all(abs(n - m) > 10 for m in plan):  # birbirine çok yakın anları tek fotoğrafta topla
            plan[n] = f"z≈{float(z):.0f} mm: havada başlayan parça/sarkma — destek tutuyor mu?"
    if toplam_katman > 40:
        orta = toplam_katman // 2
        if all(abs(orta - m) > 10 for m in plan):
            plan[orta] = "Yarı yol kontrolü"
    return sorted(plan.items())


def riskli_z_listesi(analiz: dict[str, Any], en_fazla: int = 4) -> list[float]:
    """baski_analiz çıktısından izlenecek yükseklikler (ada başlangıçları + en büyük sarkmalar)."""
    zs = [float(a["z_mm"]) for a in analiz.get("ada") or []]
    zs += [float(z) for z, alan in analiz.get("sarkma_en_buyuk") or [] if alan > 25.0]
    secilen: list[float] = []
    for z in sorted(zs):
        if all(abs(z - s) > 3.0 for s in secilen):
            secilen.append(round(z, 1))
    return secilen[:en_fazla]


def fire_grami(tahmini_gram: float, ilerleme_yuzde: float) -> float:
    """Yarıda kalan baskıda harcanan filament ≈ toplam × ilerleme (en az 1 g)."""
    if tahmini_gram <= 0:
        return 0.0
    oran = min(max(ilerleme_yuzde, 0.0), 100.0) / 100.0
    return round(max(1.0, tahmini_gram * oran), 1)


def tarti_cozumle(metin: str) -> float | None:
    import re

    m = re.search(r"(\d+(?:[.,]\d+)?)", metin or "")
    if not m:
        return None
    g = float(m.group(1).replace(",", "."))
    return g if 0.5 <= g <= 5000 else None


def tarti_ozeti(tarti_g: float, orca_g: float) -> str:
    if orca_g <= 0:
        return f"⚖️ Tartı: `{tarti_g:.1f} g` (Orca verisi yok)"
    fark = (tarti_g - orca_g) / orca_g * 100
    return (f"⚖️ Tartı `{tarti_g:.1f} g` • Orca `{orca_g:.1f} g` • fark `%{fark:+.1f}`"
            + (" — maliyet tahmini sapıyor, fiyatı tartıyla güncelle" if abs(fark) > 8 else " — tahmin isabetli"))
