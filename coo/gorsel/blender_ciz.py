#!/usr/bin/env python3
"""STL'den gerçek 3D katman dokulu ürün görselleri üretir.

Blender 4.0+ içinde başsız çalışır:
    blender -b -P coo/gorsel/blender_ciz.py -- \
        --stl /yol/model.stl --cikti /yol/gorsel/ \
        [--renk "#E8DFD1"] [--cozunurluk 1536] [--donen]

Çıktılar (--cikti klasöründe):
    studyo.png   — yüksek kontrast stüdyo ışığında üç çeyrek açı (1536×1536)
    beyaz.png    — saf beyaz fonda e-ticaret karesi (1536×1536)
    yakin.png    — katman dokusunu gösteren yakın plan (1536×1536)
    seffaf.png   — arka plansız PNG (Google Flow / sahne birleştirme için)
    donen.mp4    — yalnızca --donen verilirse 360° stüdyo videosu (varsayılan KAPALI)
"""
from __future__ import annotations

import argparse
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy
from mathutils import Vector


def _argumanlari_coz() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--stl", required=True, type=Path)
    p.add_argument("--cikti", required=True, type=Path)
    p.add_argument("--renk", default="#E8DFD1", help="Filament rengi (hex)")
    p.add_argument("--etiket", type=Path, default=None, help="Çok renk: coo/cok_renk.py etiket.npz (renk başına malzeme)")
    p.add_argument("--katman-mm", type=float, default=0.20, help="Katman yüksekliği (mm)")
    p.add_argument("--cozunurluk", type=int, default=1536)
    p.add_argument("--ornek", type=int, default=48, help="Cycles örnekleme (samples)")
    p.add_argument("--donen", action="store_true", help="360° donen.mp4 üret (varsayılan: kapalı; video için Google Flow kullanılır)")
    p.add_argument("--sadece-kare", action="store_true", help="Geriye dönük uyumluluk bayrağı (varsayılan davranış)")
    return p.parse_args(argv)


def _hex_rgb(h: str) -> tuple[float, float, float, float]:
    h = h.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(r), lin(g), lin(b), 1.0)


def _sahneyi_temizle() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _cycles_ayarla(coz: int, ornek: int = 48) -> bpy.types.Scene:
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    gpu_aktif = False
    aktif_etiket = "CPU"
    for tip in ("OPTIX", "CUDA", "HIP"):
        try:
            prefs.compute_device_type = tip
            if hasattr(prefs, "refresh_devices"):
                prefs.refresh_devices()
            else:
                prefs.get_devices()
            uygun_gpu = [d for d in prefs.devices if d.type == tip]
            if uygun_gpu:
                for d in prefs.devices:
                    d.use = d.type == tip
                sc.cycles.device = "GPU"
                gpu_aktif = True
                aktif_etiket = f"GPU ({tip}: {uygun_gpu[0].name})"
                break
        except Exception:
            continue
    if not gpu_aktif:
        prefs.compute_device_type = "NONE"
        sc.cycles.device = "CPU"
        ornek = min(ornek, 24)
    print(f"[blender_ciz] Cycles cihaz: {aktif_etiket}, samples={ornek}, res={coz}x{coz}", flush=True)
    sc.cycles.samples = ornek
    sc.cycles.use_denoising = True
    denoise_adaylar = ("OPTIX", "OPENIMAGEDENOISE") if gpu_aktif else ("OPENIMAGEDENOISE",)
    for dn in denoise_adaylar:
        try:
            sc.cycles.denoiser = dn
            break
        except Exception:
            continue
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.025
    sc.render.resolution_x = coz
    sc.render.resolution_y = coz
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = 0.35
    return sc


def _stl_yukle_ve_ortala(yol: Path) -> tuple[bpy.types.Object, float, float]:
    if hasattr(bpy.ops.wm, "stl_import"):
        bpy.ops.wm.stl_import(filepath=str(yol))
    else:
        bpy.ops.import_mesh.stl(filepath=str(yol))
    obj = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.shade_smooth()
    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
    except Exception:
        pass

    kok = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    min_v = Vector((min(v.x for v in kok), min(v.y for v in kok), min(v.z for v in kok)))
    max_v = Vector((max(v.x for v in kok), max(v.y for v in kok), max(v.z for v in kok)))
    merkez_xy = (min_v + max_v) * 0.5
    obj.location.x -= merkez_xy.x
    obj.location.y -= merkez_xy.y
    obj.location.z -= min_v.z
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    boyut = max_v - min_v
    cap = max(boyut.x, boyut.y, boyut.z)
    return obj, cap, boyut.z


def _pla_malzemesi(renk_hex: str, katman_mm: float) -> bpy.types.Material:
    mat = bpy.data.materials.new("Workbench_PLA_Mat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    cikti = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = _hex_rgb(renk_hex)
    bsdf.inputs["Roughness"].default_value = 0.42
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.35
    if "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = 0.04

    tex_coord = nt.nodes.new("ShaderNodeTexCoord")
    ayir = nt.nodes.new("ShaderNodeSeparateXYZ")
    dalga = nt.nodes.new("ShaderNodeTexWave")
    dalga.wave_type = "BANDS"
    dalga.bands_direction = "Z"
    dalga.wave_profile = "SIN"
    # Blender BANDS/Z dalgası: n = z·ölçek·20 → periyot = (2π/20)/ölçek. Periyot = katman yüksekliği (mm)
    # olacak şekilde ölçek seçilir (eski 1/katman değeri 0.06 mm periyot veriyordu → görünmez/aliasing).
    dalga.inputs["Scale"].default_value = (2 * math.pi / 20.0) / max(katman_mm, 0.05)
    dalga.inputs["Distortion"].default_value = 0.0

    # Gerçek FDM kesiti: yuvarlak boncuk tepeler + dar, keskin oluklar. Sinüs (0..1) ** 0.35 tepeleri
    # genişletir, olukları sivriltir; düz sinüs makro karede "kumaş dokusu" gibi silik kalıyordu.
    profil = nt.nodes.new("ShaderNodeMath")
    profil.operation = "POWER"
    profil.inputs[1].default_value = 0.35

    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.85
    bump.inputs["Distance"].default_value = katman_mm * 0.5

    nt.links.new(tex_coord.outputs["Object"], ayir.inputs["Vector"])
    nt.links.new(ayir.outputs["Z"], dalga.inputs["Vector"])
    nt.links.new(dalga.outputs["Fac"], profil.inputs[0])
    nt.links.new(profil.outputs["Value"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs["BSDF"], cikti.inputs["Surface"])
    return mat


def _zemin_ve_isiklar(cap: float, yukseklik: float) -> tuple[bpy.types.Object, list[bpy.types.Object]]:
    bpy.ops.mesh.primitive_plane_add(size=max(cap * 36, yukseklik * 28, 2200.0), location=(0, 0, 0))
    zemin = bpy.context.active_object
    zmat = bpy.data.materials.new("Zemin_Mat")
    zmat.use_nodes = True
    zbsdf = zmat.node_tree.nodes.get("Principled BSDF")
    # Temiz açık stüdyo yüzeyi + belirgin temas gölgesi (açık renk PLA'yı boğmaz)
    zbsdf.inputs["Base Color"].default_value = (0.76, 0.74, 0.70, 1.0)
    zbsdf.inputs["Roughness"].default_value = 0.58
    zemin.data.materials.append(zmat)

    def alan_isigi(ad: str, konum: tuple, hedef_z: float, guc: float, boyut: float, renk=(1.0, 0.97, 0.93)):
        bpy.ops.object.light_add(type="AREA", location=konum)
        isik = bpy.context.active_object
        isik.name = ad
        isik.data.energy = guc
        isik.data.size = boyut
        isik.data.color = renk
        yon = Vector((0, 0, hedef_z)) - Vector(konum)
        isik.rotation_euler = yon.to_track_quat("-Z", "Y").to_euler()
        return isik

    u = cap * 2.2
    hz = yukseklik * 0.45
    olcek = (cap / 100.0) ** 2
    isiklar = [
        alan_isigi("Ana_Isik", (u * 0.95, -u * 0.75, yukseklik + u * 0.85), hz, 520000 * olcek, cap * 1.15, (1.0, 0.96, 0.90)),
        alan_isigi("Dolgu_Isik", (-u * 1.05, -u * 0.55, yukseklik + u * 0.45), hz, 120000 * olcek, cap * 2.1, (0.93, 0.96, 1.0)),
        alan_isigi("Kontur_Isik", (-u * 0.25, u * 1.05, yukseklik + u * 0.95), hz, 340000 * olcek, cap * 1.0, (1.0, 0.98, 0.95)),
    ]

    dunya = bpy.data.worlds.new("Studyo_Dunya")
    bpy.context.scene.world = dunya
    dunya.use_nodes = True
    bg = dunya.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.78, 0.76, 0.72, 1.0)
    bg.inputs["Strength"].default_value = 0.40
    return zemin, isiklar


def _kamera_kur(konum: tuple, hedef: tuple, odak_mm: float = 65.0) -> bpy.types.Object:
    bpy.ops.object.camera_add(location=konum)
    kam = bpy.context.active_object
    kam.data.lens = odak_mm
    kam.data.clip_start = 1.0
    kam.data.clip_end = 10000.0
    yon = Vector(hedef) - Vector(konum)
    kam.rotation_euler = yon.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = kam
    return kam


def _kare_cek(sc: bpy.types.Scene, kam: bpy.types.Object, konum: tuple, hedef: tuple, lens: float, dosya: Path) -> None:
    kam.location = konum
    kam.data.lens = lens
    yon = Vector(hedef) - Vector(konum)
    kam.rotation_euler = yon.to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = str(dosya)
    bpy.ops.render.render(write_still=True)


MAKRO_GENISLIK_MM = 52.0  # yakın kare genişliği: 0.16 mm katman ≈ 4.7 px (Qwen 1024 girdisinde ≈ 3 px)
MAKRO_LENS = 100.0


def _makro_cek(sc: bpy.types.Scene, kam: bpy.types.Object, obj: bpy.types.Object, bakis: tuple, hedef: tuple,
               cap: float, dosya: Path) -> None:
    """Ürün yüzeyine gerçek makro kare: bakış ışını yüzeyde nereye çarpıyorsa oraya ~40 mm kadraj.

    Eski yakın plan bütün figürü kadrajlıyordu (≈0.1 mm/px) → 0.2 mm katman 2 px'e düşüp Qwen'de
    siliniyordu. Ayrıca üstten sıyırma ışığı (raking light) eklenir: yatay oluklar gölge verir."""
    # Bakış noktasından ürüne ızgara halinde ışın atılır (yalnız ürün; zemin hariç). En iyi hedef:
    # kameraya dönük, dik (normal.z≈0 → yatay katman olukları en net), orta yükseklikte bir yüzey.
    # Dönüşümler uygulanmış olduğundan nesne koordinatı = dünya koordinatı.
    bakis_v = Vector(bakis)
    yuk = max(v.co.z for v in obj.data.vertices)
    en_iyi = None
    for i in range(-8, 9):
        for j in range(-8, 9):
            hedef_p = Vector(hedef) + Vector((i * cap / 16.0, j * cap / 16.0, (j - i) * yuk / 40.0))
            yon = (hedef_p - bakis_v).normalized()
            ok, nokta, normal, _i = obj.ray_cast(bakis_v, yon)
            if not ok or not (0.45 * yuk <= nokta.z <= 0.95 * yuk):
                continue
            donuk = -normal.dot(yon)
            if donuk <= 0.3:
                continue
            # Üst bölge (yüz/baş) daha tanınır bir detay karesi verir
            puan = donuk * (1.0 - abs(normal.z)) ** 2 + 0.4 * nokta.z / yuk - abs(i) * 0.01 - abs(j) * 0.01
            if en_iyi is None or puan > en_iyi[0]:
                en_iyi = (puan, nokta.copy(), normal.copy(), yon)
    print(f"[blender_ciz] makro hedef: {None if en_iyi is None else tuple(round(v, 1) for v in en_iyi[1])}", flush=True)
    if en_iyi is None:
        _kare_cek(sc, kam, bakis, hedef, 85.0, dosya)  # yedek: eski kadraj
        return
    _p, nokta, normal, yon = en_iyi
    mesafe = MAKRO_GENISLIK_MM * MAKRO_LENS / kam.data.sensor_width
    # Kamera yüzey normaliyle bakış arasında (çok yandan bakınca oluklar sıkışır)
    eksen = (-yon * 0.6 + normal * 0.4).normalized()
    konum = nokta + eksen * mesafe
    bpy.ops.object.light_add(type="AREA", location=nokta + normal * 18.0 + Vector((0, 0, 70.0)))
    isik = bpy.context.active_object
    isik.data.energy = 15000.0
    isik.data.size = 22.0
    isik.data.color = (1.0, 0.97, 0.92)
    isik.rotation_euler = (nokta - isik.location).to_track_quat("-Z", "Y").to_euler()
    try:
        _kare_cek(sc, kam, tuple(konum), tuple(nokta), MAKRO_LENS, dosya)
    finally:
        bpy.data.objects.remove(isik, do_unlink=True)


def _donen_video_cek(sc: bpy.types.Scene, obj: bpy.types.Object, cikti_mp4: Path, kare_sayisi: int = 72) -> None:
    sc.render.resolution_x = 1080
    sc.render.resolution_y = 1080
    sc.cycles.samples = min(sc.cycles.samples, 24)

    with tempfile.TemporaryDirectory(prefix="workbench_360_") as tmp:
        tmp_yol = Path(tmp)
        for i in range(kare_sayisi):
            obj.rotation_euler.z = (2.0 * math.pi * i) / kare_sayisi
            sc.render.filepath = str(tmp_yol / f"kare_{i:03d}.png")
            bpy.ops.render.render(write_still=True)
        obj.rotation_euler.z = 0.0

        subprocess.run(
            [
                "ffmpeg", "-y", "-framerate", "24",
                "-i", str(tmp_yol / "kare_%03d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                str(cikti_mp4),
            ],
            check=True,
        )


def main() -> None:
    args = _argumanlari_coz()
    args.cikti.mkdir(parents=True, exist_ok=True)

    _sahneyi_temizle()
    sc = _cycles_ayarla(args.cozunurluk, args.ornek)
    obj, cap, yuk = _stl_yukle_ve_ortala(args.stl)
    if args.etiket:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from renk_etiket import etiketle

        etiketle(obj, str(args.etiket), lambda h: _pla_malzemesi(h, args.katman_mm))
    else:
        mat = _pla_malzemesi(args.renk, args.katman_mm)
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    zemin, _ = _zemin_ve_isiklar(cap, yuk)

    u = cap * 2.15
    hz = yuk * 0.45
    kam = _kamera_kur((u * 0.85, -u * 0.95, yuk * 0.85 + cap * 0.35), (0, 0, hz), 65.0)

    # 1) Stüdyo üç çeyrek açı
    sc.render.film_transparent = False
    _kare_cek(sc, kam, (u * 0.85, -u * 0.95, yuk * 0.85 + cap * 0.35), (0, 0, hz), 65.0, args.cikti / "studyo.png")

    # 2) Yakın plan — katman dokusu (gerçek makro: ~40 mm genişlik → 0.16–0.2 mm katman ≈ 6–8 px)
    _makro_cek(sc, kam, obj, (u * 0.48, -u * 0.52, yuk * 0.62), (0, 0, yuk * 0.52), cap, args.cikti / "yakin.png")

    # 3) Şeffaf arka plan + saf beyaz e-ticaret karesi
    zemin.is_shadow_catcher = True
    sc.render.film_transparent = True
    _kare_cek(sc, kam, (u * 0.85, -u * 0.95, yuk * 0.85 + cap * 0.35), (0, 0, hz), 65.0, args.cikti / "seffaf.png")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=white:s={args.cozunurluk}x{args.cozunurluk}:d=1",
            "-i", str(args.cikti / "seffaf.png"),
            "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto",
            "-frames:v", "1", str(args.cikti / "beyaz.png"),
        ],
        check=True,
    )

    # 4) 360° dönen stüdyo videosu — yalnızca --donen açıkça istenirse (video için Google Flow tercih edilir)
    if args.donen and not args.sadece_kare:
        zemin.is_shadow_catcher = False
        sc.render.film_transparent = False
        kam.location = (u * 0.85, -u * 0.95, yuk * 0.85 + cap * 0.35)
        kam.data.lens = 65.0
        _donen_video_cek(sc, obj, args.cikti / "donen.mp4")


if __name__ == "__main__":
    main()
