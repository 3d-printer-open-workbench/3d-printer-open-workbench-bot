"""🧪 Kullanım testi — bot/ajan tarafı (saf işlevler; mujoco/trimesh İMPORT ETMEZ, sistem python'unda çalışır).

Motor `coo/kullanim_testi.py` .venv-cad'de alt süreç olarak çalışır:
    {PY_CAD} -m coo.kullanim_testi <sku> --kayit

urun.yaml şeması:
    kullanim_testi:
      sablon: telefon_standi            # config/kullanim_testi/sablonlar.yaml
      vaat: '…'                         # ürünün kullanım vaadi (ajan konsept/ürün metninden yazar)
      yonler: [dik, yatay]              # (isteğe bağlı) şablon ezmeleri: nesneler, kurallar, fizik, kilif, kapasite…
      son: {tarih, durum, rapor, pano, gecti, kaldi, duzeltme_onerisi}
      onay: BEKLIYOR | ONAYLANDI        # Patron kararı (KALDI iken de "olduğu gibi kabul" onaylanabilir)
      tasarim_turu: 0                   # 🛠️ Yeniden Tasarla otomatik turu (en fazla AZAMI_TUR)
      gecmis: [{tarih, durum, rapor}]
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .ayar import PROGRAMLAR_KLASORU, PY_CAD, URUNLER_KLASORU

AZAMI_TUR = 3
NOT_BASLIGI_TURU = "kt"


def _yol(sku: str, urunler: Path | None = None) -> Path:
    return (urunler or URUNLER_KLASORU) / sku / "urun.yaml"


def urun_oku(sku: str, urunler: Path | None = None) -> dict[str, Any]:
    yol = _yol(sku, urunler)
    if not yol.exists():
        return {"sku": sku}
    try:
        v = yaml.safe_load(yol.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {"sku": sku}
    return v if isinstance(v, dict) else {"sku": sku}


def _yaz(sku: str, veri: dict[str, Any], urunler: Path | None = None) -> None:
    _yol(sku, urunler).write_text(yaml.safe_dump(veri, allow_unicode=True, sort_keys=False), encoding="utf-8")


def kayit(urun: dict[str, Any]) -> dict[str, Any]:
    kt = urun.get("kullanim_testi")
    return kt if isinstance(kt, dict) else {}


def stl_yolu(sku: str, urunler: Path | None = None) -> Path | None:
    kok = (urunler or URUNLER_KLASORU) / sku
    v = urun_oku(sku, urunler)
    for aday in ([kok / str(v["stl_yolu"])] if v.get("stl_yolu") else []) + [kok / "model" / f"{sku}.stl"]:
        if aday.is_file():
            return aday
    return None


def son_sonucu_kaydet(sku: str, rapor: dict[str, Any], urunler: Path | None = None) -> dict[str, Any]:
    """Motor sonucunu urun.yaml > kullanim_testi.son'a yazar; onay BEKLIYOR'a döner (yeni test = yeni karar)."""
    veri = urun_oku(sku, urunler)
    kt = kayit(veri)
    kok = (urunler or URUNLER_KLASORU) / sku

    def goreli(p: Any) -> str | None:
        if not p:
            return None
        try:
            return str(Path(p).resolve().relative_to(kok.resolve()))
        except ValueError:
            return str(p)

    son = {"tarih": rapor.get("tarih"), "durum": rapor.get("durum"), "rapor": goreli(rapor.get("rapor")),
           "pano": goreli(rapor.get("pano")), "gecti": (rapor.get("ozet") or {}).get("gecti"),
           "kaldi": (rapor.get("ozet") or {}).get("kaldi"), "duzeltme_onerisi": list(rapor.get("duzeltme_onerisi") or [])}
    gecmis = kt.get("gecmis") if isinstance(kt.get("gecmis"), list) else []
    if isinstance(kt.get("son"), dict):
        eski = kt["son"]
        gecmis.append({"tarih": eski.get("tarih"), "durum": eski.get("durum"), "rapor": eski.get("rapor")})
    kt.setdefault("sablon", rapor.get("sablon"))
    if rapor.get("vaat") and not kt.get("vaat"):
        kt["vaat"] = rapor.get("vaat")
    kt["son"] = son
    kt["onay"] = "BEKLIYOR"
    kt["gecmis"] = gecmis[-10:]
    veri["kullanim_testi"] = kt
    _yaz(sku, veri, urunler)
    return kt


def onayla(sku: str, urunler: Path | None = None, zaman: dt.datetime | None = None) -> dict[str, Any]:
    veri = urun_oku(sku, urunler)
    kt = kayit(veri)
    if not isinstance(kt.get("son"), dict):
        raise ValueError(f"{sku}: onaylanacak kullanım testi sonucu yok")
    kt["onay"] = "ONAYLANDI"
    kt["onay_tarihi"] = (zaman or dt.datetime.now()).isoformat(timespec="seconds")
    kt["onaylanan_durum"] = kt["son"].get("durum")
    veri["kullanim_testi"] = kt
    _yaz(sku, veri, urunler)
    return kt


def tur_artir(sku: str, urunler: Path | None = None, sifirla: bool = False) -> int:
    veri = urun_oku(sku, urunler)
    kt = kayit(veri)
    kt["tasarim_turu"] = 0 if sifirla else int(kt.get("tasarim_turu") or 0) + 1
    veri["kullanim_testi"] = kt
    _yaz(sku, veri, urunler)
    return int(kt["tasarim_turu"])


def durum(sku: str, urunler: Path | None = None) -> dict[str, Any]:
    """Ürün kartı / bekleyen işler için kısa durum."""
    kt = kayit(urun_oku(sku, urunler))
    son = kt.get("son") if isinstance(kt.get("son"), dict) else {}
    return {"var": bool(son), "durum": son.get("durum"), "onay": kt.get("onay") or "",
            "onayli": kt.get("onay") == "ONAYLANDI", "tur": int(kt.get("tasarim_turu") or 0),
            "pano": ((urunler or URUNLER_KLASORU) / sku / son["pano"]) if son.get("pano") else None,
            "rapor": ((urunler or URUNLER_KLASORU) / sku / son["rapor"]) if son.get("rapor") else None,
            "son": son, "sablon": kt.get("sablon")}


def rapor_oku(sku: str, urunler: Path | None = None) -> dict[str, Any] | None:
    d = durum(sku, urunler)
    if not d["rapor"] or not Path(d["rapor"]).exists():
        return None
    try:
        return json.loads(Path(d["rapor"]).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def ozet_metni(sku: str, rapor: dict[str, Any], tur: int = 0) -> str:
    """Telegram özeti (Markdown). Sayılar rapordan aynen."""
    rozet = "✅ GEÇTİ" if rapor.get("durum") == "GEÇTİ" else "❌ KALDI"
    oz = rapor.get("ozet") or {}
    satirlar = [f"🧪 *Kullanım testi* — `{sku}` · {rozet}",
                f"_Vaat:_ {rapor['vaat']}" if rapor.get("vaat") else "",
                f"{oz.get('gecti', 0)}/{oz.get('kural', 0)} kural geçti"
                + (f" · tasarım turu {tur}/{AZAMI_TUR}" if tur else "")]
    kalan = [k for k in rapor.get("kurallar") or [] if k.get("durum") == "KALDI" and k.get("zorunlu", True)]
    if kalan:
        satirlar.append("\n*Kalan kurallar:*")
        gorulen = set()
        for k in kalan:
            anahtar = (k["kural"], k["senaryo"])
            if anahtar in gorulen:
                continue
            gorulen.add(anahtar)
            satirlar.append(f"✗ {k['kural']}: {k['deger']} {k['birim']} (sınır {k['sinir']}) — {k['senaryo']}")
            if len(gorulen) >= 8:
                satirlar.append(f"… toplam {len(kalan)} (rapor.json)")
                break
    if rapor.get("duzeltme_onerisi"):
        satirlar.append("\n*Düzeltme önerisi:*")
        satirlar += [f"• {o}" for o in rapor["duzeltme_onerisi"][:6]]
    st = rapor.get("stand") or {}
    satirlar.append(f"\n_Stand {st.get('kutle_g')} g ({str(st.get('kutle_kaynagi') or '')[:90]}); "
                    "sürtünme/nesne parça yerleşimi varsayımdır (rapor.json > varsayimlar)._")
    return "\n".join(s for s in satirlar if s)[:3800]


def motor_komutu(sku: str, gorsel: bool = True) -> list[str]:
    k = [str(PY_CAD), "-m", "coo.kullanim_testi", sku, "--kayit"]
    return k + ([] if gorsel else ["--gorselsiz"])


def motoru_calistir(sku: str, zaman_asimi: int = 1800) -> dict[str, Any]:
    """Motoru .venv-cad alt sürecinde çalıştırır; urun.yaml'a kaydeder; rapor.json içeriğini döndürür."""
    sonuc = subprocess.run(motor_komutu(sku), cwd=str(PROGRAMLAR_KLASORU), capture_output=True, text=True,
                           timeout=zaman_asimi)
    if sonuc.returncode not in (0, 2):
        raise RuntimeError((sonuc.stderr or sonuc.stdout or "")[-1500:])
    r = rapor_oku(sku)
    if r is None:
        raise RuntimeError("rapor.json okunamadı: " + (sonuc.stdout or "")[-500:])
    return r


def revize_notu(sku: str, rapor: dict[str, Any], ek_not: str = "") -> str:
    """cad-artist için ölçülü revize notu (rapordaki öneriler + kalan kurallar)."""
    kalan = [k for k in rapor.get("kurallar") or [] if k.get("durum") == "KALDI" and k.get("zorunlu", True)]
    satirlar = [f"KULLANIM TESTİ KALDI ({rapor.get('tarih')}, şablon {rapor.get('sablon')}).",
                f"Vaat: {rapor.get('vaat')}", "Kalan kurallar:"]
    gorulen = set()
    for k in kalan:
        if (k["kural"], k["senaryo"]) in gorulen:
            continue
        gorulen.add((k["kural"], k["senaryo"]))
        satirlar.append(f"- {k['kural']} [{k['senaryo']}]: {k['deger']} {k['birim']} (sınır {k['sinir']}) — {k['aciklama']}")
    satirlar.append("Uygulanacak ölçülü düzeltmeler:")
    satirlar += [f"- {o}" for o in rapor.get("duzeltme_onerisi") or []]
    if ek_not.strip():
        satirlar.append(f"Test mühendisi / Patron notu: {ek_not.strip()}")
    return "\n".join(satirlar)


def test_istemi(sku: str, not_: str = "") -> str:
    """kullanim-test-muhendisi ajanı istemi."""
    return (
        f"Ürün `{sku}` için KULLANIM TESTİ yap (ajan tanımın: .claude/agents/testing/kullanim-test-muhendisi.md).\n"
        f"1) veri/02_Urunler/{sku}/urun.yaml (ad, fikir.tarif, cmo_konsept_ve_ana_prompt, revize_notu) ve varsa mağaza "
        "metninden ürünün VAADİNİ çıkar. `kullanim_testi:` yoksa veya vaat eksikse yaz: sablon (kulaklik_standi / "
        "kontrolcu_standi / telefon_standi), vaat, gerekiyorsa ezmeler (ör. 'dik + yatay' vaadi → yonler: [dik, yatay]; "
        "iki kol → kapasite: 2). Yalnız `kullanim_testi:` alanına dokun; model dosyalarını DEĞİŞTİRME.\n"
        f"2) Motoru çalıştır: `cd {PROGRAMLAR_KLASORU} && {PY_CAD} -m coo.kullanim_testi {sku} --kayit`.\n"
        "3) rapor.json ve pano.png'yi oku/gör; sayıların fiziksel olarak mantıklı olduğunu denetle (ör. yerleşim "
        "yanlış yönde mi, nesne ölçüsü doğru mu). Motor hatası/yanlış yerleşim görürsen tanımı düzeltip yeniden çalıştır.\n"
        "4) KALDI ise `duzeltme_onerisi`ni denetle; cad-artist'in doğrudan uygulayabileceği ölçülü revize notunu "
        "urun.yaml > kullanim_testi.revize_notu alanına yaz.\n"
        + (f"Patron notu (öncelikli uygula): {not_.strip()}\n" if not_.strip() else "")
        + "Son satırda tek cümle: GEÇTİ/KALDI + en kritik sayı."
    )


def tasarim_istemi(sku: str, rapor: dict[str, Any], tur: int, ek_not: str = "") -> str:
    """cad-artist: KALDI notunu uygula → yeni STL (aynı yol) → kalite kapısı."""
    ajan_notu = str(kayit(urun_oku(sku)).get("revize_notu") or "").strip()
    if ajan_notu:
        ek_not = (ajan_notu + ("\n" + ek_not if ek_not.strip() else "")).strip()
    return (
        f"`{sku}` KULLANIM TESTİNDEN KALDI — yeniden tasarım turu {tur}/{AZAMI_TUR}.\n"
        "cad-artist tanımındaki 'Kullanım testi KALDI notu' bölümünü uygula.\n\n"
        + revize_notu(sku, rapor, ek_not)
        + f"\n\nModel: veri/02_Urunler/{sku}/model/{sku}.stl (önce mevcut STL'yi model/arsiv/ altına tarihli kopyala, "
        "sonra aynı yola yeni STL yaz). Ürünün görünüşünü/konseptini koru; yalnız ölçülü düzeltmeleri uygula. Ardından "
        f"`{PY_CAD} -m coo.kalite_kapisi veri/02_Urunler/{sku}/model/{sku}.stl --mod b2c` PASS olmalı. "
        "Kullanım testini SEN çalıştırma; bot yeni STL ile otomatik tekrar test eder. Son satırda yaptığın "
        "değişiklikleri mm cinsinden tek cümleyle yaz."
    )
