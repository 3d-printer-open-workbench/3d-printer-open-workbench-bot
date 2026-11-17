"""OrcaSlicer komut satırı ile gerçek dilimleme → yazdırılmaya hazır 3MF proje + G-code.

Neden: Ürün başına OrcaSlicer'a ayrı "process profili" kaydetmek Orca'yı kirletir ve tahmini
gram/süre verir. Bunun yerine ürünün kendi `uretim/<sku>.3mf` proje dosyası üretilir: model, yazıcı
(Elegoo Centauri Carbon 0.4), filament ve baskı ayarları içine gömülü — Orca'da açıp doğrudan
yazdırılır. Aynı çalıştırmada G-code çıkar; gram/süre Orca'nın gerçek dilimlemesinden okunur.

Profil kaynağı: `config/orca/kaynak/` (Orca 2.5.1 resources/profiles — Elegoo + OrcaFilamentLibrary).
CLI `inherits` zincirini çözmediği için profiller `config/orca/{machine,process,filament}/` altına
düzleştirilerek yazılır (ERP `dilimle` aracı da bu klasörü kullanır).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from .ayar import CALISMA_ALANI, COO_KLASORU, CONFIG_KLASORU, PY_AI3D, URUNLER_KLASORU

ORCA_KLASOR = CONFIG_KLASORU / "orca"
KAYNAK = ORCA_KLASOR / "kaynak"
ORCA_BIN = shutil.which("orcaslicer") or str(Path.home() / ".local/bin/orcaslicer")

MAKINE = "Elegoo Centauri Carbon 0.4 nozzle"
TABAN_PROSES = "0.20mm Standard @Elegoo CC 0.4 nozzle"
VARSAYILAN_FILAMENT = "Elegoo PLA Matte @ECC"

KATEGORI_DOSYASI = ORCA_KLASOR / "kategoriler.yaml"
AI3D_PY = PY_AI3D
_ORTAK_WORKBENCH = {"sparse_infill_pattern": "gyroid", "ironing_type": "top", "seam_position": "aligned"}

# YZ'nin yeni kategori yazarken kullanabileceği Orca anahtarları ve güvenli aralıklar (0.4 nozul, PLA/PETG).
_SAYI = r"^\d+(\.\d+)?$"
IZINLI_AYARLAR: dict[str, tuple] = {
    "layer_height": ("aralik", 0.08, 0.28),
    "initial_layer_print_height": ("aralik", 0.15, 0.30),
    "wall_loops": ("tamsayi", 1, 8),
    "top_shell_layers": ("tamsayi", 2, 12),
    "bottom_shell_layers": ("tamsayi", 2, 12),
    "sparse_infill_density": ("yuzde", 0, 100),
    "sparse_infill_pattern": ("secim", {"gyroid", "grid", "cubic", "honeycomb", "line", "rectilinear",
                                        "adaptivecubic", "lightning", "concentric", "triangles", "3dhoneycomb"}),
    "top_surface_pattern": ("secim", {"monotonicline", "monotonic", "concentric", "alignedrectilinear",
                                      "hilbertcurve", "archimedeanchords", "octagramspiral"}),
    "ironing_type": ("secim", {"no ironing", "top", "topmost", "solid"}),
    "seam_position": ("secim", {"aligned", "back", "nearest", "random"}),
    "seam_slope_type": ("secim", {"none", "external", "all"}),
    "wall_generator": ("secim", {"classic", "arachne"}),
    "detect_thin_wall": ("secim", {"0", "1"}),
    "precise_outer_wall": ("secim", {"0", "1"}),
    "outer_wall_speed": ("aralik", 30, 300),
    "inner_wall_speed": ("aralik", 30, 400),
    "brim_type": ("secim", {"no_brim", "outer_only", "auto_brim", "brim_ears"}),
    "brim_width": ("aralik", 0, 15),
    "support_threshold_angle": ("aralik", 10, 70),
    "fuzzy_skin": ("secim", {"none", "external", "all", "allwalls"}),
}


def ayar_dogrula(ayarlar: dict[str, Any]) -> dict[str, str]:
    """YZ/insan yazımı kategori ayarlarını doğrular; geçersizse ValueError."""
    temiz: dict[str, str] = {}
    for k, v in (ayarlar or {}).items():
        if k not in IZINLI_AYARLAR:
            raise ValueError(f"İzinsiz ayar: {k} (izinli: {', '.join(sorted(IZINLI_AYARLAR))})")
        tur, *sinir = IZINLI_AYARLAR[k]
        v = str(v).strip()
        if tur == "secim":
            if v not in sinir[0]:
                raise ValueError(f"{k}={v} geçersiz; seçenekler: {sorted(sinir[0])}")
        elif tur == "yuzde":
            sayi = v.rstrip("%")
            if not re.match(_SAYI, sayi) or not sinir[0] <= float(sayi) <= sinir[1]:
                raise ValueError(f"{k}={v} 0–100% olmalı")
            v = f"{sayi}%"
        else:
            if not re.match(_SAYI, v) or not sinir[0] <= float(v) <= sinir[1]:
                raise ValueError(f"{k}={v} {sinir[0]}–{sinir[1]} aralığında olmalı")
            if tur == "tamsayi" and float(v) != int(float(v)):
                raise ValueError(f"{k} tamsayı olmalı")
        temiz[k] = v
    return temiz


def kategoriler(dosya: Path | None = None) -> dict[str, dict[str, Any]]:
    import yaml

    d = dosya or KATEGORI_DOSYASI
    if not d.exists():
        return {}
    return (yaml.safe_load(d.read_text(encoding="utf-8")) or {}).get("kategoriler") or {}


def workbench_prosesleri(dosya: Path | None = None) -> dict[str, dict[str, str]]:
    """Proses adı → Orca fark ayarları (kategori dosyasından; ERP `dilimle` aynı adları kullanır)."""
    return {k["proses"]: {a: str(v) for a, v in (k.get("ayarlar") or {}).items()}
            for k in kategoriler(dosya).values()}


def kategori_ekle(veri: dict[str, Any], dosya: Path | None = None, profil_yaz: bool = True) -> dict[str, Any]:
    """Yeni baskı kategorisi ekler (YZ ajanı ürüne göre önerir). Var olan anahtarı ezmez.
    veri: {anahtar, baslik, aciklama, anahtar_kelimeler, ayarlar, gerekce}"""
    import yaml

    d = dosya or KATEGORI_DOSYASI
    anahtar = re.sub(r"[^a-z0-9_]", "", str(veri.get("anahtar", "")).lower())
    if not anahtar:
        raise ValueError("anahtar gerekli (küçük harf, a-z0-9_)")
    mevcut = kategoriler(d)
    if anahtar in mevcut:
        raise ValueError(f"'{anahtar}' kategorisi zaten var")
    ayarlar = ayar_dogrula(veri.get("ayarlar") or {})
    if not ayarlar:
        raise ValueError("en az bir ayar gerekli")
    katman = ayarlar.get("layer_height", "0.20")
    proses = f"Workbench {str(veri.get('baslik') or anahtar).split('/')[0].strip().title()[:24]} {float(katman):.2f}"
    proses = re.sub(r"[^A-Za-z0-9 .]", "", proses.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")))
    if proses in workbench_prosesleri(d):
        proses = f"{proses} {anahtar}"
    kayit = {"proses": proses, "baslik": str(veri.get("baslik") or anahtar)[:60],
             "aciklama": str(veri.get("aciklama") or "")[:300],
             "anahtar_kelimeler": [str(x).lower() for x in (veri.get("anahtar_kelimeler") or [])][:20],
             "ayarlar": ayarlar, "ekleyen": "YZ", "gerekce": str(veri.get("gerekce") or "")[:400]}
    ham = yaml.safe_load(d.read_text(encoding="utf-8")) if d.exists() else {}
    ham = ham or {}
    ham.setdefault("kategoriler", {})[anahtar] = kayit
    metin = d.read_text(encoding="utf-8") if d.exists() else ""
    # Yorumlu başlığı korumak için yeni kategoriyi sona ekle.
    ek = yaml.safe_dump({anahtar: kayit}, allow_unicode=True, sort_keys=False)
    d.write_text(metin.rstrip() + "\n\n" + "\n".join("  " + x for x in ek.splitlines()) + "\n", encoding="utf-8")
    if kategoriler(d).get(anahtar) != kayit:
        raise RuntimeError("kategori dosyası yazımı doğrulanamadı")
    if profil_yaz:
        profilleri_hazirla()
    return {"anahtar": anahtar, **kayit}


def kategori_guncelle(anahtar: str, ayarlar: dict[str, Any], dosya: Path | None = None,
                      profil_yaz: bool = True, not_: str = "") -> dict[str, Any]:
    """Var olan kategorinin ayarlarını (doğrulayarak) günceller; dosyanın baştaki yorumları korunur.
    Dönüş: {"anahtar", "onceki": {...}, "yeni": {...}}"""
    import yaml

    d = dosya or KATEGORI_DOSYASI
    temiz = ayar_dogrula(ayarlar)
    if not temiz:
        raise ValueError("güncellenecek ayar yok")
    metin = d.read_text(encoding="utf-8")
    ham = yaml.safe_load(metin) or {}
    kat = (ham.get("kategoriler") or {}).get(anahtar)
    if kat is None:
        raise ValueError(f"'{anahtar}' kategorisi yok")
    onceki = dict(kat.get("ayarlar") or {})
    kat["ayarlar"] = {**onceki, **temiz}
    gecmis = kat.setdefault("degisiklikler", [])
    import datetime as _dt

    gecmis.append({"tarih": _dt.date.today().isoformat(), "ayarlar": temiz, "not": not_[:200]})
    yorum = "".join(s for s in metin.splitlines(keepends=True)[:40] if s.startswith("#"))
    d.write_text(yorum + "\n" + yaml.safe_dump(ham, allow_unicode=True, sort_keys=False), encoding="utf-8")
    if profil_yaz:
        profilleri_hazirla()
    return {"anahtar": anahtar, "onceki": {k: onceki.get(k) for k in temiz}, "yeni": temiz}


def kategori_sec(urun: dict[str, Any], sku: str = "", dosya: Path | None = None) -> tuple[str, str]:
    """Ürün için baskı kategorisi: urun.yaml `baski_kategorisi` > anahtar kelime > AI mesh → figür > standart."""
    kat = kategoriler(dosya)
    acik = str(urun.get("baski_kategorisi") or "")
    if acik in kat:
        return acik, "urun.yaml baski_kategorisi"
    metin = " ".join(str(x) for x in (sku, urun.get("ad"), urun.get("urun_adi"), urun.get("tarif"),
                                      urun.get("kategori"), urun.get("tasarim_araci"))).lower()
    en_iyi, puan = "", 0
    for k, v in kat.items():
        p = sum(1 for w in v.get("anahtar_kelimeler") or [] if w and w in metin)
        if p > puan:
            en_iyi, puan = k, p
    if en_iyi:
        return en_iyi, f"anahtar kelime ({puan})"
    if urun.get("ai3d") and "figur" in kat:
        return "figur", "AI mesh (organik form)"
    return ("standart" if "standart" in kat else next(iter(kat), "")), "varsayılan"


def baski_analizi(stl: Path, katman: float = 0.2) -> dict[str, Any]:
    """Katman katman ada/sarkma analizi (`coo/baski_analiz.py`, .venv-ai3d)."""
    try:
        s = subprocess.run([str(AI3D_PY), str(COO_KLASORU / "baski_analiz.py"), str(stl),
                            "--katman", str(katman)], capture_output=True, text=True, timeout=600)
        return json.loads(s.stdout.strip().splitlines()[-1])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, IndexError) as e:
        return {"hata": f"analiz başarısız: {e}", "destek_gerekli": False, "ada_sayisi": 0}


@lru_cache(maxsize=1)
def _isim_dizini() -> dict[str, Path]:
    dizin: dict[str, Path] = {}
    for yol in KAYNAK.rglob("*.json"):
        try:
            ad = json.loads(yol.read_text(encoding="utf-8")).get("name")
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if ad:
            dizin.setdefault(ad, yol)
    return dizin


def duzlestir(ad: str) -> dict[str, Any]:
    """`inherits` zincirini kökten yaprağa birleştirir."""
    dizin = _isim_dizini()
    if ad not in dizin:
        raise FileNotFoundError(f"Orca profili bulunamadı: {ad} (kaynak: {KAYNAK})")
    veri = json.loads(dizin[ad].read_text(encoding="utf-8"))
    ebeveyn = veri.get("inherits")
    sonuc = duzlestir(ebeveyn) if ebeveyn else {}
    sonuc.update(veri)
    sonuc.pop("inherits", None)
    return sonuc


def _yaz(tur: str, ad: str, veri: dict[str, Any]) -> Path:
    hedef = ORCA_KLASOR / tur / f"{ad}.json"
    hedef.parent.mkdir(parents=True, exist_ok=True)
    veri = dict(veri, name=ad, from_="")
    veri.pop("from_", None)
    veri["from"] = "User"
    hedef.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    return hedef


def profilleri_hazirla(filamentler: tuple[str, ...] = (VARSAYILAN_FILAMENT, "Elegoo PLA @ECC", "Elegoo PETG @ECC")) -> dict[str, Path]:
    """Makine, Open Workbench prosesleri ve filamentleri düzleştirip `config/orca/` altına yazar."""
    yollar = {"machine": _yaz("machine", MAKINE, duzlestir(MAKINE))}
    taban = duzlestir(TABAN_PROSES)
    for ad, fark in workbench_prosesleri().items():
        veri = {**taban, **_ORTAK_WORKBENCH, **fark}
        veri["compatible_printers"] = [MAKINE]
        yollar[f"process:{ad}"] = _yaz("process", ad, veri)
    for f in filamentler:
        yollar[f"filament:{f}"] = _yaz("filament", f, duzlestir(f))
    return yollar


def _profil_yolu(tur: str, ad: str) -> Path:
    yol = ORCA_KLASOR / tur / f"{ad}.json"
    if not yol.exists():
        profilleri_hazirla()
    if not yol.exists():
        raise FileNotFoundError(f"Profil yok: {yol}")
    return yol


def gcode_ozeti(gcode: Path) -> dict[str, Any]:
    """Orca G-code özetinden gram (çok renkte toplam + filament başına), süre ve renk değişimi sayısı."""
    metin = gcode.read_bytes()
    bas, kuyruk = metin[:60000].decode("utf-8", "ignore"), metin[-40000:].decode("utf-8", "ignore")
    alan = bas + "\n" + kuyruk

    def bul(desen: str) -> str | None:
        m = re.search(desen, alan, flags=re.M)
        return m.group(1).strip() if m else None

    gramlar = [float(x) for x in re.findall(r"[\d.]+", bul(r"^; filament used \[g\]\s*=\s*(.+)$") or "")]
    toplam = bul(r"^; total filament used \[g\]\s*=\s*([\d.]+)")
    gram = float(toplam) if toplam else (round(sum(gramlar), 2) if gramlar else None)
    sure = bul(r"estimated printing time.*?=\s*(.+)$")
    degisim = bul(r"^; total filament change\s*=\s*(\d+)")
    return {"gram": gram, "sure_sn": _sure_sn(sure) if sure else None,
            "filament_gram": gramlar if len(gramlar) > 1 else None,
            "renk_degisimi": int(degisim) if degisim else 0}


def _sure_sn(metin: str) -> int:
    toplam = 0
    for deger, birim in re.findall(r"(\d+)\s*([dhms])", metin):
        toplam += int(deger) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[birim]
    return toplam


def dilimle_3mf(
    sku: str,
    proses: str = "Workbench Standart 0.20 Utulu",
    filament: str = VARSAYILAN_FILAMENT,
    urunler_klasoru: Path | None = None,
    zaman_asimi: int = 900,
    destek: bool = False,
    renk_hex: str | None = None,
    boyama: dict[str, Any] | None = None,
    _sadece_ozet: bool = False,
) -> dict[str, Any]:
    """`model/<sku>.stl` → `uretim/<sku>.3mf` (ayarlar gömülü proje) + `uretim/<sku>.gcode`.

    boyama: çok renk — {"girdi_3mf": <coo/cok_renk renkli.3mf>, "renkler": ["#..", ..]}; model yerine boyalı 3MF
    dilimlenir, her renk ayrı filament yuvası (CANVAS) olur.

    destek=True: yalnız tabladan başlayan ağaç destek (katman analizi havada parça bulduğunda).
    renk_hex: Patronun seçtiği ana renk → 3MF'te filament rengi."""
    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    stl = kok / "model" / f"{sku}.stl"
    if not stl.exists():
        return {"basarili": False, "hata": f"STL yok: {stl}"}
    uretim = kok / "uretim"
    gecici = uretim / ("_orca_ozet" if _sadece_ozet else "_orca")
    if gecici.exists():
        shutil.rmtree(gecici)
    gecici.mkdir(parents=True)

    makine_p = _profil_yolu("machine", MAKINE)
    proses_p = _profil_yolu("process", proses)
    fil_p = _profil_yolu("filament", filament)
    if destek:
        veri = json.loads(proses_p.read_text(encoding="utf-8"))
        veri.update(enable_support="1", support_type="tree(auto)", support_style="default",
                    support_on_build_plate_only="1", support_threshold_angle="40")
        proses_p = gecici / f"{proses}.json"
        proses_p.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    renkler = [h for h in ((boyama or {}).get("renkler") or [renk_hex]) if h and re.match(r"^#[0-9A-Fa-f]{6}$", h)]
    fil_yollari = [fil_p]
    if renkler:
        taban = json.loads(fil_p.read_text(encoding="utf-8"))
        fil_yollari = []
        for i, h in enumerate(renkler, start=1):
            veri = dict(taban, filament_colour=[h.upper()], default_filament_colour=[h.upper()])
            yol = gecici / f"{filament}-{i}.json"
            yol.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
            fil_yollari.append(yol)
    girdi = stl
    if boyama:
        girdi = Path(boyama["girdi_3mf"])
        if not girdi.exists():
            return {"basarili": False, "hata": f"boyalı 3MF yok: {girdi}"}
    proje = uretim / f"{sku}.3mf"
    komut = [
        ORCA_BIN, "--arrange", "1", "--orient", "0", "--slice", "0",
        "--load-settings", f"{makine_p};{proses_p}",
        "--load-filaments", ";".join(str(y) for y in fil_yollari),
        "--export-3mf", proje.name,  # Orca bu adı --outputdir'e göre yazar
        "--outputdir", str(gecici),
        str(girdi),
    ]
    try:
        s = subprocess.run(komut, capture_output=True, text=True, timeout=zaman_asimi)
    except subprocess.TimeoutExpired:
        return {"basarili": False, "hata": f"Orca zaman aşımı ({zaman_asimi} sn)"}
    gcodelar = sorted(gecici.glob("*.gcode"), key=lambda p: p.stat().st_mtime)
    if not gcodelar:
        return {"basarili": False, "hata": "G-code oluşmadı",
                "log": ((s.stdout or "") + (s.stderr or ""))[-1500:]}
    if _sadece_ozet:  # karşılaştırma: ürünün 3MF/G-code'una dokunma
        ozet = gcode_ozeti(gcodelar[-1])
        shutil.rmtree(gecici, ignore_errors=True)
        return {"basarili": True, **ozet}
    gcode = uretim / f"{sku}.gcode"
    shutil.move(str(gcodelar[-1]), gcode)
    if (gecici / proje.name).exists():
        shutil.move(str(gecici / proje.name), proje)
    shutil.rmtree(gecici, ignore_errors=True)
    ozet = gcode_ozeti(gcode)
    onizleme = None
    if proje.exists():
        import zipfile

        try:
            with zipfile.ZipFile(proje) as z:
                ad = next((n for n in ("Metadata/plate_1.png", "Metadata/top_1.png") if n in z.namelist()), None)
                if ad:
                    onizleme = uretim / f"{sku}-tabla.png"
                    onizleme.write_bytes(z.read(ad))
        except zipfile.BadZipFile:
            pass
    return {
        "basarili": True,
        "proje_3mf": proje if proje.exists() else None,
        "gcode": gcode,
        "proses": proses,
        "filament": filament,
        "destek": destek,
        "renk_hex": renk_hex,
        "renkler": renkler if boyama else None,
        "onizleme": onizleme,
        **ozet,
    }


def dilimle_stl(stl: Path, proses: str, cikti_klasor: Path, filament: str = VARSAYILAN_FILAMENT,
                zaman_asimi: int = 600) -> dict[str, Any]:
    """Tek bir STL'yi (ürün klasörü dışından da) dilimler → {gram, sure_sn}. Teklif hesabı için.
    Not: Orca AppImage /tmp altını göremez; cikti_klasor çalışma alanında olmalı."""
    cikti_klasor.mkdir(parents=True, exist_ok=True)
    gecici = cikti_klasor / f"_orca_{stl.stem}"
    shutil.rmtree(gecici, ignore_errors=True)
    gecici.mkdir()
    komut = [ORCA_BIN, "--arrange", "1", "--orient", "1", "--slice", "0",
             "--load-settings", f"{_profil_yolu('machine', MAKINE)};{_profil_yolu('process', proses)}",
             "--load-filaments", str(_profil_yolu("filament", filament)), "--outputdir", str(gecici), str(stl)]
    try:
        s = subprocess.run(komut, capture_output=True, text=True, timeout=zaman_asimi)
    except subprocess.TimeoutExpired:
        return {"basarili": False, "hata": f"Orca zaman aşımı ({zaman_asimi} sn)", "stl": str(stl)}
    gcodelar = sorted(gecici.glob("*.gcode"))
    if not gcodelar:
        shutil.rmtree(gecici, ignore_errors=True)
        return {"basarili": False, "hata": "G-code oluşmadı (parça tablaya sığmıyor olabilir)", "stl": str(stl),
                "log": ((s.stdout or "") + (s.stderr or ""))[-600:]}
    ozet = gcode_ozeti(gcodelar[-1])
    shutil.rmtree(gecici, ignore_errors=True)
    return {"basarili": ozet.get("gram") is not None, "stl": str(stl), "proses": proses, **ozet}


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 2 and sys.argv[1] == "dilimle-stl":
        # python3 -m coo.orca_dilim dilimle-stl <kategori> <cikti_klasor> <a.stl> [b.stl ...] → toplam gram/süre
        kat = kategoriler().get(sys.argv[2]) or {}
        proses = kat.get("proses") or "Workbench Standart 0.20 Utulu"
        sonuclar = [dilimle_stl(Path(x), proses, Path(sys.argv[3])) for x in sys.argv[4:]]
        print(json.dumps({"proses": proses, "parcalar": sonuclar,
                          "toplam_gram": round(sum(r.get("gram") or 0 for r in sonuclar), 1),
                          "toplam_sure_sn": int(sum(r.get("sure_sn") or 0 for r in sonuclar)),
                          "hatali": [r["stl"] for r in sonuclar if not r.get("basarili")]}, ensure_ascii=False))
        sys.exit(0)
    if len(sys.argv) > 2 and sys.argv[1] == "kategori-ekle":
        try:
            print(json.dumps(kategori_ekle(json.loads(sys.argv[2])), ensure_ascii=False))
        except (ValueError, json.JSONDecodeError) as e:
            print(f"KATEGORI_HATA {e}")
            sys.exit(1)
        sys.exit(0)
    hazir = profilleri_hazirla()
    print("\n".join(f"{k}: {v}" for k, v in hazir.items()))
    if len(sys.argv) > 1:
        print(dilimle_3mf(sys.argv[1]))
