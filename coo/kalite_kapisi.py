"""Open Workbench 2. Katman 3B Geometri ve Anti-Amatör Kalite Kapısı (`coo/kalite_kapisi.py`).

Elegoo Centauri Carbon (256x256x256 mm) üretilebilirliğini, su geçirmezliği (manifold),
Z=0 taban düzlüğünü ve B2C ürünlerde pahsız/ilkel kaba kutu geometrilerini denetler.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

from .ayar import PROGRAMLAR_KLASORU, PY_CAD

TABLA_LIMIT_MM = 256.0
MIN_B2C_UCGEN = 80
MIN_B2C_NORMAL_CESIT = 14
CAD_PYTHON = PY_CAD


def _mesh_yukle(dosya_yolu: Path):
    import trimesh

    yuklenen = trimesh.load(str(dosya_yolu), force="mesh")
    if isinstance(yuklenen, trimesh.Scene):
        parcalar = [g for g in yuklenen.geometry.values() if isinstance(g, trimesh.Trimesh) and len(g.faces) > 0]
        if not parcalar:
            raise ValueError("3B dosyada geçerli mesh geometrisi bulunamadı.")
        return trimesh.util.concatenate(parcalar)
    return yuklenen


def kalite_kontrol_et(dosya_yolu: Path, mod: str = "b2c") -> dict[str, Any]:
    """STL/3MF dosyasını trimesh/numpy ile denetler ve yapılandırılmış rapor döndürür."""
    mod_norm = (mod or "b2c").strip().lower()
    if mod_norm not in ("b2c", "b2b"):
        raise ValueError(f"Geçersiz kalite kapısı modu: {mod}")

    if not dosya_yolu.exists():
        return {
            "durum": "RED",
            "mod": mod_norm,
            "dosya": str(dosya_yolu),
            "hatalar": [f"Dosya bulunamadı: {dosya_yolu}"],
            "uyarilar": [],
        }

    try:
        import numpy as np
        mesh = _mesh_yukle(dosya_yolu)
    except ImportError:
        return kalite_kapisi_calistir(dosya_yolu, mod=mod_norm)
    except Exception as exc:
        return {
            "durum": "RED",
            "mod": mod_norm,
            "dosya": str(dosya_yolu),
            "hatalar": [f"Mesh okunamadı: {exc}"],
            "uyarilar": [],
        }

    hatalar: list[str] = []
    uyarilar: list[str] = []

    bounds = mesh.bounds
    en_x = float(bounds[1][0] - bounds[0][0])
    boy_y = float(bounds[1][1] - bounds[0][1])
    yuk_z = float(bounds[1][2] - bounds[0][2])
    z_min = float(bounds[0][2])
    ucgen_sayisi = int(len(mesh.faces))
    manifold_mi = bool(mesh.is_watertight)
    hacim_cm3 = float(abs(mesh.volume) / 1000.0) if mesh.is_volume else 0.0

    # OpenCASCADE B-rep -> binary STL aktarımlarında float32 yuvarlaması trimesh is_watertight'ı
    # yanlış negatif çıkarabilir; bu durumda manifold3d ile gerçek su geçirmezliği doğrula.
    if not manifold_mi:
        try:
            import manifold3d

            mf = manifold3d.Manifold(
                manifold3d.Mesh(
                    vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
                    tri_verts=np.asarray(mesh.faces, dtype=np.uint32),
                )
            )
            if mf.status() == manifold3d.Error.NoError and not mf.is_empty():
                mf_vol = float(abs(mf.volume()))
                if mf_vol > 100.0:
                    manifold_mi = True
                    hacim_cm3 = mf_vol / 1000.0
        except Exception:
            pass

    if not manifold_mi:
        hatalar.append("Model su geçirmez (manifold) değil; açık kenar veya ters yüzey normali var.")
    if hacim_cm3 <= 0.1:
        hatalar.append(f"Geçersiz veya boş hacim ({hacim_cm3:.3f} cm³).")

    if abs(z_min) > 0.15:
        hatalar.append(f"Model Z=0 taban düzlemine oturmuyor (z_min={z_min:.2f} mm).")

    if en_x > TABLA_LIMIT_MM or boy_y > TABLA_LIMIT_MM or yuk_z > TABLA_LIMIT_MM:
        mesaj = (
            f"Model tabla sınırını ({TABLA_LIMIT_MM:.0f} mm) aşıyor: "
            f"{en_x:.1f}×{boy_y:.1f}×{yuk_z:.1f} mm."
        )
        if mod_norm == "b2c":
            hatalar.append(mesaj)
        else:
            uyarilar.append(mesaj + " (B2B parçalı baskı ile çözülebilir.)")

    normaller = np.asarray(mesh.face_normals)
    alanlar = np.asarray(mesh.area_faces)
    toplam_alan = float(np.sum(alanlar)) or 1.0

    # Yüzey normali çeşitliliği: keskin köşeli ilkel kutular 6 normal civarında kalır
    gecerli_maske = alanlar > 1e-6
    benzersiz_normaller = np.unique(np.round(normaller[gecerli_maske], 2), axis=0)
    normal_cesitliligi = int(len(benzersiz_normaller))

    # Eksenlere dik olmayan (pah / kavis / eğimli) yüzeylerin alan oranı
    eksen_hizalilik = np.max(np.abs(normaller), axis=1)
    egimli_alan = float(np.sum(alanlar[eksen_hizalilik < 0.985]))
    egimli_yuzey_yuzde = round((egimli_alan / toplam_alan) * 100.0, 1)

    # Taban temas alanı oranı
    z_ort = np.asarray(mesh.triangles_center)[:, 2]
    taban_maske = (z_ort <= z_min + 0.25) & (normaller[:, 2] < -0.9)
    taban_alani_mm2 = float(np.sum(alanlar[taban_maske]))
    if taban_alani_mm2 < 25.0:
        uyarilar.append(f"Taban temas alanı düşük ({taban_alani_mm2:.1f} mm²); yapışma/brim gerekebilir.")

    # >45° sarkma (overhang) oranı — taban yüzeyi hariç
    sarkma_cos = -math.cos(math.radians(45.0))
    sarkma_maske = (normaller[:, 2] < sarkma_cos) & (z_ort > z_min + 0.35)
    sarkma_alani = float(np.sum(alanlar[sarkma_maske]))
    sarkma_orani_yuzde = round((sarkma_alani / toplam_alan) * 100.0, 1)
    if sarkma_orani_yuzde > 35.0:
        uyarilar.append(f"Yüksek sarkma oranı (%{sarkma_orani_yuzde}); ağaç destek gerekebilir.")

    if mod_norm == "b2c":
        if ucgen_sayisi < MIN_B2C_UCGEN or normal_cesitliligi < MIN_B2C_NORMAL_CESIT:
            hatalar.append(
                "B2C kalite reddi (kaba/ilkel kutu geometrisi): "
                f"{ucgen_sayisi} üçgen (min {MIN_B2C_UCGEN}), "
                f"{normal_cesitliligi} yüzey yönü (min {MIN_B2C_NORMAL_CESIT}). "
                "build123d fillet/chamfer, BOSL2 rounding veya Blender detayları ekleyin."
            )
        elif egimli_yuzey_yuzde < 1.5 and normal_cesitliligi < 20:
            hatalar.append(
                f"B2C kalite reddi (pahsız keskin kenarlı blok: %{egimli_yuzey_yuzde} eğimli/pahlı yüzey). "
                "Kenar pahı (fillet/chamfer) veya ergonomik kavis ekleyin."
            )

    return {
        "durum": "PASS" if not hatalar else "RED",
        "mod": mod_norm,
        "dosya": str(dosya_yolu),
        "boyut_mm": {
            "x": round(en_x, 2),
            "y": round(boy_y, 2),
            "z": round(yuk_z, 2),
        },
        "z_min_mm": round(z_min, 3),
        "hacim_cm3": round(hacim_cm3, 2),
        "tahmini_pla_gram": round(hacim_cm3 * 1.24 * 0.42, 1),
        "ucgen_sayisi": ucgen_sayisi,
        "manifold": manifold_mi,
        "normal_cesitliligi": normal_cesitliligi,
        "egimli_yuzey_yuzde": egimli_yuzey_yuzde,
        "taban_alani_mm2": round(taban_alani_mm2, 1),
        "sarkma_orani_yuzde": sarkma_orani_yuzde,
        "hatalar": hatalar,
        "uyarilar": uyarilar,
    }


def kalite_kapisi_calistir(dosya_yolu: Path, mod: str = "b2c") -> dict[str, Any]:
    """Sistem Python içinden .venv-cad Python'una köprü kurarak kalite kapısını çalıştırır."""
    try:
        import trimesh  # noqa: F401
        return kalite_kontrol_et(dosya_yolu, mod=mod)
    except ImportError:
        py_bin = str(CAD_PYTHON) if CAD_PYTHON.exists() else sys.executable
        if py_bin == sys.executable:
            return {
                "durum": "RED",
                "mod": mod,
                "dosya": str(dosya_yolu),
                "hatalar": [".venv-cad / trimesh ortamı bulunamadı."],
                "uyarilar": [],
            }
        proc = subprocess.run(
            [py_bin, "-m", "coo.kalite_kapisi", str(dosya_yolu), "--mod", mod, "--json"],
            cwd=str(PROGRAMLAR_KLASORU),
            capture_output=True,
            text=True,
            timeout=60,
        )
        cikti = (proc.stdout or "").strip()
        if not cikti:
            return {
                "durum": "RED",
                "mod": mod,
                "dosya": str(dosya_yolu),
                "hatalar": [proc.stderr.strip() or "Kalite kapısı çıktı üretemedi."],
                "uyarilar": [],
            }
        return json.loads(cikti)


def rapor_ozeti(sonuc: dict[str, Any]) -> str:
    ikon = "✅ PASS" if sonuc.get("durum") == "PASS" else "❌ RED"
    b = sonuc.get("boyut_mm") or {}
    satirlar = [
        f"📐 *Geometri & Kalite Kapısı:* {ikon} (`{sonuc.get('mod', 'b2c').upper()}`)",
        f"• *Boyut:* `{b.get('x', 0)}×{b.get('y', 0)}×{b.get('z', 0)} mm` • *Hacim:* `{sonuc.get('hacim_cm3', 0)} cm³`",
        f"• *Manifold:* `{'Evet' if sonuc.get('manifold') else 'HAYIR'}` • *Üçgen:* `{sonuc.get('ucgen_sayisi', 0)}` • *Normal Çeşidi:* `{sonuc.get('normal_cesitliligi', 0)}`",
        f"• *Pahlı/Eğimli Yüzey:* `%{sonuc.get('egimli_yuzey_yuzde', 0)}` • *Sarkma (>45°):* `%{sonuc.get('sarkma_orani_yuzde', 0)}`",
    ]
    for h in sonuc.get("hatalar") or []:
        satirlar.append(f"• ⛔ *Hata:* {h}")
    for u in sonuc.get("uyarilar") or []:
        satirlar.append(f"• ⚠️ *Uyarı:* {u}")
    return "\n".join(satirlar)


def main() -> None:
    parser = argparse.ArgumentParser(description="Open Workbench 3B Geometri ve Anti-Amatör Kalite Kapısı")
    parser.add_argument("dosya", type=Path, help="Denetlenecek .stl veya .3mf dosyası")
    parser.add_argument("--mod", choices=["b2c", "b2b"], default="b2c", help="Kalite süzgeci modu")
    parser.add_argument("--json", action="store_true", help="JSON biçiminde çıktı ver")
    args = parser.parse_args()

    sonuc = kalite_kontrol_et(args.dosya, mod=args.mod)
    if args.json:
        print(json.dumps(sonuc, ensure_ascii=False, indent=2))
    else:
        print(rapor_ozeti(sonuc))
    if sonuc.get("durum") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
