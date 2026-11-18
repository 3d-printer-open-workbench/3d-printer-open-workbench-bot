"""Ürün bilgi satırları (ölçü/malzeme) — yalnız urun.yaml'daki doğrulanmış veriden; numpy/PIL gerektirmez.
Teknik Poster bilgi bandı (`teknik_poster.py`) ve Canva teknik poster (`konsept_hatti.canva_poster_istemi`) kullanır."""
from __future__ import annotations

import yaml

from .ayar import URUNLER_KLASORU as URUNLER


def _cm(mm: float) -> str:
    return f"{mm / 10:.1f}".replace(".", ",") + " cm"


def bilgiler(sku: str, urunler=None) -> dict:
    """Yalnızca urun.yaml'daki doğrulanmış veriler."""
    v = yaml.safe_load(((urunler or URUNLER) / sku / "urun.yaml").read_text(encoding="utf-8")) or {}
    b = v.get("boyut_mm") or {}
    dil = v.get("dilimleme") or {}
    filament = str(dil.get("filament") or "")
    mat = "matte" in filament.lower() or "mat " in filament.lower()
    hazne = ((v.get("ai3d") or {}).get("hazne") or {}) if isinstance(v.get("ai3d"), dict) else {}
    drenaj = (v.get("ai3d") or {}).get("drenaj_mm") if isinstance(v.get("ai3d"), dict) else None
    satirlar = []
    if b.get("z"):
        satirlar.append(("A-01", "YÜKSEKLİK", _cm(float(b["z"]))))
    if b.get("x"):
        satirlar.append(("A-02", "GENİŞLİK", _cm(float(b["x"]))))
    if b.get("y"):
        satirlar.append(("A-03", "DERİNLİK", _cm(float(b["y"]))))
    satirlar.append(("P-01", "MALZEME", "Mat PLA" if mat else "PLA"))
    if dil.get("katman_mm"):
        satirlar.append(("P-02", "KATMAN", f"{float(dil['katman_mm']):.2f} mm".replace(".", ",")))
    if hazne.get("ust_cap_mm"):
        satirlar.append(("P-03", "SAKSI AĞZI", f"Ø {_cm(float(hazne['ust_cap_mm']))}"
                         + (f" · drenaj Ø{float(drenaj):.0f} mm" if drenaj else "")))
    return {"ad": str(v.get("ad") or sku), "satirlar": satirlar[:6]}
