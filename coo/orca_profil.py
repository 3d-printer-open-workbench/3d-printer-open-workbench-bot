"""Open Workbench 2. Katman Üretim Ekibi — STL Geometri Analizi ve OrcaSlicer Profil Üretici.

STL modelinin boyutlarını, yüksekliğini, taban alanını ve sarkma (overhang > 45°) oranını
hesaplar; Elegoo Centauri Carbon (0.4 mm nozul) için en kaliteli dilimleme parametrelerini
hem okunabilir Markdown tablosu olarak hem de OrcaSlicer JSON profili olarak üretir.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

import yaml

from .ayar import ORCA_PROCESS_DIZINLERI, URUNLER_KLASORU


@dataclass
class StlAnaliz:
    dosya_adi: str
    en_x_mm: float
    boy_y_mm: float
    yukseklik_z_mm: float
    hacim_cm3: float
    ucgen_sayisi: int
    sarkma_orani_yuzde: float
    narinlik_orani: float  # Z / min(X, Y)


@dataclass
class DilimlemeOnerisi:
    sku: str
    profil_adi: str
    malzeme: str
    layer_height: float
    initial_layer_print_height: float
    wall_loops: int
    top_shell_layers: int
    bottom_shell_layers: int
    sparse_infill_density: str
    sparse_infill_pattern: str
    seam_position: str
    scarf_angle_threshold: int
    ironing_type: str
    enable_support: bool
    support_type: str
    brim_type: str
    brim_width: float
    outer_wall_speed: int
    inner_wall_speed: int
    tahmini_gram: float
    tahmini_sure_dk: int
    muhendislik_notu: str


def stl_analiz_et(stl_yolu: Path) -> StlAnaliz:
    """Binary veya ASCII STL dosyasını okuyup boyut, hacim ve sarkma (overhang) analizi yapar."""
    veri = stl_yolu.read_bytes()
    ucgenler: list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]] = []

    # Binary STL kontrolü (80 byte başlık + 4 byte üçgen sayısı + N * 50 byte)
    if len(veri) >= 84:
        n_tri = struct.unpack("<I", veri[80:84])[0]
        if 84 + n_tri * 50 == len(veri) and n_tri > 0:
            offset = 84
            for _ in range(n_tri):
                degerler = struct.unpack("<12fH", veri[offset : offset + 50])
                n = (degerler[0], degerler[1], degerler[2])
                v1 = (degerler[3], degerler[4], degerler[5])
                v2 = (degerler[6], degerler[7], degerler[8])
                v3 = (degerler[9], degerler[10], degerler[11])
                ucgenler.append((n, v1, v2, v3))
                offset += 50

    # ASCII STL yedek ayrıştırıcı
    if not ucgenler:
        metin = veri.decode("utf-8", errors="ignore")
        koseler: list[tuple[float, float, float]] = []
        normal = (0.0, 0.0, 1.0)
        for satir in metin.splitlines():
            s = satir.strip()
            if s.startswith("facet normal"):
                parcalar = s.split()
                if len(parcalar) >= 5:
                    normal = (float(parcalar[2]), float(parcalar[3]), float(parcalar[4]))
            elif s.startswith("vertex"):
                parcalar = s.split()
                if len(parcalar) >= 4:
                    koseler.append((float(parcalar[1]), float(parcalar[2]), float(parcalar[3])))
                    if len(koseler) == 3:
                        ucgenler.append((normal, koseler[0], koseler[1], koseler[2]))
                        koseler = []

    if not ucgenler:
        return StlAnaliz(
            dosya_adi=stl_yolu.name,
            en_x_mm=80.0,
            boy_y_mm=80.0,
            yukseklik_z_mm=80.0,
            hacim_cm3=45.0,
            ucgen_sayisi=0,
            sarkma_orani_yuzde=0.0,
            narinlik_orani=1.0,
        )

    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    hacim_mm3 = 0.0
    toplam_alan = 0.0
    sarkma_alani = 0.0

    for _, v1, v2, v3 in ucgenler:
        for vx, vy, vz in (v1, v2, v3):
            if vx < min_x:
                min_x = vx
            if vx > max_x:
                max_x = vx
            if vy < min_y:
                min_y = vy
            if vy > max_y:
                max_y = vy
            if vz < min_z:
                min_z = vz
            if vz > max_z:
                max_z = vz

        # İşaretli tetrahedron hacmi
        hacim_mm3 += (
            v1[0] * (v2[1] * v3[2] - v2[2] * v3[1])
            - v1[1] * (v2[0] * v3[2] - v2[2] * v3[0])
            + v1[2] * (v2[0] * v3[1] - v2[1] * v3[0])
        ) / 6.0

        # Yüzey normali ve alanı
        ux, uy, uz = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
        wx, wy, wz = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
        nx = uy * wz - uz * wy
        ny = uz * wx - ux * wz
        nz = ux * wy - uy * wx
        uzunluk = math.sqrt(nx * nx + ny * ny + nz * nz)
        alan = 0.5 * uzunluk
        toplam_alan += alan
        if uzunluk > 1e-6:
            nz_birim = nz / uzunluk
            # Taban (z ≈ min_z) hariç aşağı bakan dik yüzeyler (nz < -0.707 => >45° sarkma)
            ort_z = (v1[2] + v2[2] + v3[2]) / 3.0
            if ort_z > (min_z + 1.2) and nz_birim < -0.72:
                sarkma_alani += alan

    en_x = max(1.0, round(max_x - min_x, 2))
    boy_y = max(1.0, round(max_y - min_y, 2))
    yuk_z = max(1.0, round(max_z - min_z, 2))
    hacim_cm3 = max(1.0, round(abs(hacim_mm3) / 1000.0, 2))
    sarkma_yuzde = round((sarkma_alani / max(toplam_alan, 1.0)) * 100.0, 2)
    narinlik = round(yuk_z / max(min(en_x, boy_y), 1.0), 2)

    return StlAnaliz(
        dosya_adi=stl_yolu.name,
        en_x_mm=en_x,
        boy_y_mm=boy_y,
        yukseklik_z_mm=yuk_z,
        hacim_cm3=hacim_cm3,
        ucgen_sayisi=len(ucgenler),
        sarkma_orani_yuzde=sarkma_yuzde,
        narinlik_orani=narinlik,
    )


def orca_oneri_hesapla(sku: str, analiz: StlAnaliz, malzeme: str = "PLA") -> DilimlemeOnerisi:
    """STL analiz sonuçlarına göre Elegoo Centauri Carbon için en kaliteli dilimleme profilini belirler."""
    notlar: list[str] = []

    # Katman yüksekliği: detaylı/organik (>15.000 üçgen) modellerde 0.16mm, diğerlerinde 0.20mm
    if analiz.ucgen_sayisi > 15000:
        layer_h = 0.16
        outer_speed = 120
        notlar.append("Yüksek yüzey detayı tespit edildiği için 0.16 mm katman yüksekliği ve 120 mm/s dış duvar hızı seçildi.")
    else:
        layer_h = 0.20
        outer_speed = 150
        notlar.append("Geometri düz/parametrik yapıda olduğu için 0.20 mm katman yüksekliği seçildi.")

    # Duvar ve dolgu
    if analiz.yukseklik_z_mm > 120 or analiz.hacim_cm3 > 80:
        walls = 4
        infill = "15%"
        notlar.append("Gövde rijitliği için 4 duvar (1.6 mm kabuk) ve %15 Gyroid dolgu önerildi.")
    else:
        walls = 3
        infill = "12%"
        notlar.append("3 duvar (1.2 mm kabuk) ve %12 Gyroid dolgu hem sağlamlık hem süre için idealdir.")

    # Destek (Support)
    if analiz.sarkma_orani_yuzde >= 3.5:
        destek = True
        destek_tipi = "tree(auto)"
        notlar.append(
            f"Modelde %{analiz.sarkma_orani_yuzde:.1f} oranında >45° sarkma (overhang) tespit edildi; Otomatik Ağaç Destek (Tree Auto) açıldı."
        )
    else:
        destek = False
        destek_tipi = "normal(auto)"
        notlar.append("Model >45° kritik sarkma içermiyor; desteksiz (supportless) tertemiz basılabilir.")

    # Brim (Etek): Yüksek ve dar tabanlı modellerde devrilmeyi önler
    if analiz.narinlik_orani >= 1.8:
        brim_type = "outer_only"
        brim_w = 5.0
        notlar.append(f"Yükseklik/taban oranı ({analiz.narinlik_orani}) yüksek olduğu için 5 mm dış etek (Brim) açıldı.")
    else:
        brim_type = "no_brim"
        brim_w = 0.0

    # Ütüleme (Ironing): Alçak/düz plaka veya tabela ürünlerde üst yüzeyi pürüzsüzleştirir
    if analiz.yukseklik_z_mm <= 25.0:
        ironing = "top"
        notlar.append("Alçak/plaka geometrisi tespit edildi; üst yüzey ütüleme (Top Surface Ironing) aktif edildi.")
    else:
        ironing = "no_ironing"

    # Gerçekçi gramaj ve süre tahmini (kabuk + iç dolgu yoğunluğu)
    etkin_doluluk = 0.42 if walls == 3 else 0.48
    tahmini_gram = max(8.0, round(analiz.hacim_cm3 * 1.24 * etkin_doluluk, 1))
    katman_sayisi = analiz.yukseklik_z_mm / layer_h
    tahmini_sure_dk = max(15, int(round((tahmini_gram * 1.65) + (katman_sayisi * 0.12))))

    return DilimlemeOnerisi(
        sku=sku,
        profil_adi=f"Workbench - {sku} ({layer_h:.2f}mm {malzeme})",
        malzeme=malzeme,
        layer_height=layer_h,
        initial_layer_print_height=0.20,
        wall_loops=walls,
        top_shell_layers=5 if layer_h == 0.16 else 4,
        bottom_shell_layers=4 if layer_h == 0.16 else 3,
        sparse_infill_density=infill,
        sparse_infill_pattern="gyroid",
        seam_position="aligned",
        scarf_angle_threshold=155,
        ironing_type=ironing,
        enable_support=destek,
        support_type=destek_tipi,
        brim_type=brim_type,
        brim_width=brim_w,
        outer_wall_speed=outer_speed,
        inner_wall_speed=220,
        tahmini_gram=tahmini_gram,
        tahmini_sure_dk=tahmini_sure_dk,
        muhendislik_notu=" ".join(notlar),
    )


def orca_profil_uret(
    sku: str,
    stl_yolu: Path | None = None,
    orcaya_yukle: bool = False,
) -> tuple[DilimlemeOnerisi, Path, Path, Path | None]:
    """Ürün için OrcaSlicer JSON profilini ve Türkçe dilimleme rehberini üretir."""
    urun_klasoru = URUNLER_KLASORU / sku
    model_klasoru = urun_klasoru / "model"
    uretim_klasoru = urun_klasoru / "uretim"
    uretim_klasoru.mkdir(parents=True, exist_ok=True)

    hedef_stl = stl_yolu
    if hedef_stl is None:
        birincil = model_klasoru / f"{sku}.stl"
        if birincil.is_file():
            hedef_stl = birincil
        else:
            adaylar = sorted(p for p in model_klasoru.glob("*.stl") if not p.name.startswith("_")) if model_klasoru.exists() else []
            hedef_stl = adaylar[0] if adaylar else birincil

    if hedef_stl.exists():
        analiz = stl_analiz_et(hedef_stl)
    else:
        analiz = StlAnaliz(
            dosya_adi=f"{sku}.stl",
            en_x_mm=95.0,
            boy_y_mm=95.0,
            yukseklik_z_mm=110.0,
            hacim_cm3=115.0,
            ucgen_sayisi=24000,
            sarkma_orani_yuzde=0.8,
            narinlik_orani=1.16,
        )

    oneri = orca_oneri_hesapla(sku, analiz)

    # 1) OrcaSlicer Process JSON
    orca_json = {
        "type": "process",
        "name": oneri.profil_adi,
        "from": "User",
        "inherits": "0.20mm Standard @Elegoo Centauri Carbon 0.4 nozzle",
        "is_custom_defined": "1",
        "layer_height": f"{oneri.layer_height:.2f}",
        "initial_layer_print_height": f"{oneri.initial_layer_print_height:.2f}",
        "wall_loops": str(oneri.wall_loops),
        "top_shell_layers": str(oneri.top_shell_layers),
        "bottom_shell_layers": str(oneri.bottom_shell_layers),
        "sparse_infill_density": oneri.sparse_infill_density,
        "sparse_infill_pattern": oneri.sparse_infill_pattern,
        "seam_position": oneri.seam_position,
        "seam_slope_type": "external",
        "seam_slope_conditional": "1",
        "ironing_type": oneri.ironing_type,
        "enable_support": "1" if oneri.enable_support else "0",
        "support_type": oneri.support_type,
        "brim_type": oneri.brim_type,
        "brim_width": f"{oneri.brim_width:.1f}",
        "outer_wall_speed": str(oneri.outer_wall_speed),
        "inner_wall_speed": str(oneri.inner_wall_speed),
        "workbench_meta": {
            "sku": sku,
            "boyutlar_mm": [analiz.en_x_mm, analiz.boy_y_mm, analiz.yukseklik_z_mm],
            "tahmini_gram": oneri.tahmini_gram,
            "tahmini_sure_dk": oneri.tahmini_sure_dk,
            "not": oneri.muhendislik_notu,
        },
    }

    json_yolu = uretim_klasoru / "orca_profil.json"
    json_yolu.write_text(json.dumps(orca_json, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2) Manuel Giriş ve Mühendislik Rehberi (.md)
    saat = oneri.tahmini_sure_dk // 60
    dk = oneri.tahmini_sure_dk % 60
    rehber_md = f"""# ⚙️ {sku} — OrcaSlicer Dilimleme ve Kalite Rehberi

- **Model Dosyası:** `{analiz.dosya_adi}`
- **Ölçüler (En × Boy × Yükseklik):** `{analiz.en_x_mm:.1f} × {analiz.boy_y_mm:.1f} × {analiz.yukseklik_z_mm:.1f} mm`
- **Tahmini Filament ve Süre:** `~{oneri.tahmini_gram:.1f} g` • `~{saat} sa {dk} dk` (`{oneri.tahmini_sure_dk} dk`)
- **Mühendislik Notu:** {oneri.muhendislik_notu}

---

## 📋 OrcaSlicer Manuel Giriş Tablosu (Elegoo Centauri Carbon — 0.4 mm Nozul)

| Sekme | Parametre (OrcaSlicer) | Önerilen Değer | Neden? |
|---|---|---|---|
| **Kalite (Quality)** | Katman Yüksekliği (`Layer height`) | **`{oneri.layer_height:.2f} mm`** | Yüzey pürüzsüzlüğü / süre dengesi |
| **Kalite (Quality)** | İlk Katman (`First layer height`) | **`{oneri.initial_layer_print_height:.2f} mm`** | Tabla yapışma güvenliği |
| **Kalite (Quality)** | Dikiş İzi (`Seam position`) | **`{oneri.seam_position}` + Scarf Seam** | Dairesel yüzeylerde dikiş izini gizler |
| **Kalite (Quality)** | Ütüleme (`Ironing`) | **`{oneri.ironing_type}`** | Üst yüzey kalitesi |
| **Güç (Strength)** | Duvar Sayısı (`Wall loops`) | **`{oneri.wall_loops}`** | Darbe ve kargo dayanımı |
| **Güç (Strength)** | Üst / Alt Kabuk (`Top / Bottom shell`) | **`{oneri.top_shell_layers} üst / {oneri.bottom_shell_layers} alt`** | Yastıklama (pillowing) önleme |
| **Güç (Strength)** | İç Dolgu (`Sparse infill`) | **`{oneri.sparse_infill_density} {oneri.sparse_infill_pattern.title()}`** | İzotropik mukavemet, nozul sürtünmez |
| **Hız (Speed)** | Dış / İç Duvar Hızı (`Outer / Inner wall`) | **`{oneri.outer_wall_speed} / {oneri.inner_wall_speed} mm/s`** | Mat ve homojen yüzey parlaklığı |
| **Destek (Support)** | Destek (`Enable support`) | **`{'AÇIK (' + oneri.support_type + ')' if oneri.enable_support else 'KAPALI (Desteksiz)'}`** | Sarkma oranı: `%{analiz.sarkma_orani_yuzde:.1f}` |
| **Diğer (Others)** | Etek (`Brim type`) | **`{oneri.brim_type}` (`{oneri.brim_width:.0f} mm`)** | Narinlik oranı: `{analiz.narinlik_orani}` |

---

## 🚀 OrcaSlicer'a Otomatik Profil Olarak Yükleme
Bu profili OrcaSlicer içerisine doğrudan ürün profili olarak eklemek için:
```bash
python3 -m coo.orca_profil --sku {sku} --orcaya-yukle
```
"""
    rehber_yolu = uretim_klasoru / "dilimleme-rehberi.md"
    rehber_yolu.write_text(rehber_md, encoding="utf-8")

    # 3) urun.yaml güncelle
    yaml_yolu = urun_klasoru / "urun.yaml"
    if yaml_yolu.exists():
        try:
            veri = yaml.safe_load(yaml_yolu.read_text(encoding="utf-8")) or {}
            veri.setdefault("tasarim", {})
            veri["tasarim"]["boyutlar_mm"] = [analiz.en_x_mm, analiz.boy_y_mm, analiz.yukseklik_z_mm]
            veri.setdefault("uretim", {})
            veri["uretim"]["orca_profil_dosyasi"] = "uretim/orca_profil.json"
            veri["uretim"]["katman_yuksekligi_mm"] = oneri.layer_height
            veri["uretim"]["duvar_sayisi"] = oneri.wall_loops
            veri["uretim"]["dolgu_yuzdesi"] = int(oneri.sparse_infill_density.rstrip("%"))
            veri["uretim"]["dolgu_deseni"] = oneri.sparse_infill_pattern
            veri["uretim"]["destek_gerekli"] = oneri.enable_support
            veri["uretim"]["tahmini_sure_dk"] = oneri.tahmini_sure_dk
            veri["uretim"]["tahmini_gram"] = oneri.tahmini_gram
            yaml_yolu.write_text(yaml.safe_dump(veri, allow_unicode=True, sort_keys=False), encoding="utf-8")
        except Exception:
            pass

    yuklenen_yol: Path | None = None
    if orcaya_yukle:
        yuklenen_yol = orca_kullanici_profiline_kopyala(sku, json_yolu)

    return oneri, json_yolu, rehber_yolu, yuklenen_yol


def orca_kullanici_profiline_kopyala(sku: str, kaynak_json: Path) -> Path:
    """Üretilen orca_profil.json dosyasını OrcaSlicer kullanıcı process dizinine kopyalar."""
    hedef_dizin = ORCA_PROCESS_DIZINLERI[0]
    for d in ORCA_PROCESS_DIZINLERI:
        if d.parent.exists():
            hedef_dizin = d
            break
    hedef_dizin.mkdir(parents=True, exist_ok=True)
    hedef_dosya = hedef_dizin / f"Workbench_{sku}.json"
    shutil.copy2(kaynak_json, hedef_dosya)
    return hedef_dosya


def main() -> None:
    p = argparse.ArgumentParser(description="Open Workbench Üretim Ekibi — OrcaSlicer Profil Üretici")
    p.add_argument("--sku", required=True, help="Ürün SKU kodu")
    p.add_argument("--stl", type=Path, default=None, help="Özel STL dosya yolu")
    p.add_argument("--orcaya-yukle", action="store_true", help="OrcaSlicer kullanıcı dizinine kopyala")
    a = p.parse_args()

    oneri, json_yolu, rehber_yolu, yuklenen = orca_profil_uret(
        sku=a.sku,
        stl_yolu=a.stl,
        orcaya_yukle=a.orcaya_yukle,
    )
    print(f"OrcaSlicer profili hazır: {oneri.profil_adi}")
    print(f"  - JSON: {json_yolu}")
    print(f"  - Rehber: {rehber_yolu}")
    if yuklenen:
        print(f"  - OrcaSlicer'a yüklendi: {yuklenen}")


if __name__ == "__main__":
    main()
