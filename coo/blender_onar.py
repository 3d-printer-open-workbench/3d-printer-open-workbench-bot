"""AI mesh'ini Blender'da basılabilir hale getirir (3B Onarım ajanının deterministik aracı).

Kullanım:
    blender -b -P coo/blender_onar.py -- --girdi a.stl --cikti b.stl --rapor r.json \
        [--min-kalinlik 1.0] [--hazne-duvar 2.0] [--hazne '{"merkez":[x,y],"dip_z":..,"ust_cap_mm":..}'] \
        [--voxel 0.2] [--hedef-ucgen 400000] [--sadece-olc]

Adımlar (Elegoo Centauri Carbon, 0.4 mm nozul):
1. Voxel remesh → kesin su geçirmez, iç kabuklar ve kendini kesen yüzeyler erir.
2. Kopuk parçalar: ana gövdenin %2'sinden küçük adalar silinir (havada basılamaz), büyükler raporlanır.
3. Kalınlık analizi: her köşeden normalin tersine ışın → karşı yüzeye mesafe = et kalınlığı.
   Nozulun basamayacağı ince bölgeler (< min-kalinlik) ve saksı hazne duvarı (< hazne-duvar)
   normal yönünde yerel olarak kalınlaştırılır (iki yüz de yarım fark kadar dışa itilir, yumuşatılarak).
4. Yeniden voxel remesh + decimate → hedef üçgen sayısı. Son ölçüm rapora yazılır.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils.bvhtree import BVHTree


def _arglar():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--girdi", required=True)
    ap.add_argument("--cikti", required=True)
    ap.add_argument("--rapor", required=True)
    ap.add_argument("--min-kalinlik", type=float, default=1.0)
    ap.add_argument("--hazne-duvar", type=float, default=2.0)
    ap.add_argument("--hazne", default="")
    ap.add_argument("--voxel", type=float, default=0.2)
    ap.add_argument("--hedef-ucgen", type=int, default=300_000)
    ap.add_argument("--tur", type=int, default=3)
    ap.add_argument("--sadece-olc", action="store_true")
    return ap.parse_args(argv)


def yukle(yol: str):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.stl_import(filepath=yol)
    obj = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = obj
    return obj


def remesh(obj, voxel: float) -> None:
    obj.data.remesh_voxel_size = voxel
    obj.data.remesh_voxel_adaptivity = 0.0
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.voxel_remesh()


def decimate(obj, hedef: int) -> None:
    n = sum(len(p.vertices) - 2 for p in obj.data.polygons)  # remesh dörtgen üretir; üçgen say
    if n <= hedef:
        return
    mod = obj.modifiers.new("azalt", "DECIMATE")
    mod.ratio = hedef / n
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)


def adalari_temizle(obj, oran: float = 0.02) -> dict:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    gorulen: set[int] = set()
    adalar: list[list] = []
    for v in bm.verts:
        if v.index in gorulen:
            continue
        yigin, ada = [v], []
        gorulen.add(v.index)
        while yigin:
            a = yigin.pop()
            ada.append(a)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in gorulen:
                    gorulen.add(b.index)
                    yigin.append(b)
        adalar.append(ada)
    hacimler = []
    for ada in adalar:
        yuzler = {f for v in ada for f in v.link_faces}
        alt = bmesh.new()
        harita = {}
        for v in ada:
            harita[v] = alt.verts.new(v.co)
        for f in yuzler:
            try:
                alt.faces.new([harita[v] for v in f.verts])
            except ValueError:
                pass
        hacimler.append(abs(alt.calc_volume()))
        alt.free()
    ana = max(hacimler) if hacimler else 0.0
    silinen, kalan_kopuk = 0, []
    for ada, h in zip(adalar, hacimler):
        if h < ana * oran:
            bmesh.ops.delete(bm, geom=list(ada), context="VERTS")
            silinen += 1
        elif h < ana:
            kalan_kopuk.append(round(h / 1000, 2))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return {"ada": len(adalar), "silinen_kucuk_ada": silinen, "kopuk_parca_cm3": kalan_kopuk}


def _diziler(obj):
    me = obj.data
    nv = len(me.vertices)
    co = np.empty(nv * 3, np.float64)
    me.vertices.foreach_get("co", co)
    no = np.empty(nv * 3, np.float64)
    me.vertices.foreach_get("normal", no)
    return co.reshape(-1, 3), no.reshape(-1, 3)


def kalinlik(obj) -> np.ndarray:
    """Her köşe için et kalınlığı (mm); karşı yüz bulunamazsa inf."""
    me = obj.data
    co, no = _diziler(obj)
    polys = [tuple(p.vertices) for p in me.polygons]
    agac = BVHTree.FromPolygons([tuple(c) for c in co], polys, all_triangles=False)
    eps = 0.02
    t = np.full(len(co), np.inf)
    for i in range(len(co)):
        n = no[i]
        hit = agac.ray_cast(tuple(co[i] - n * eps), tuple(-n), 60.0)
        # Yalnız karşı yüz (dış normali ışınla aynı yönde) gerçek et kalınlığıdır; keskin kıvrımlarda yan yüze
        # çarpan ışın sahte "ince" sonucu verir.
        if hit[0] is not None and (hit[1][0] * n[0] + hit[1][1] * n[1] + hit[1][2] * n[2]) < -0.3:
            t[i] = hit[3] + eps
    return t


def hedefler(co: np.ndarray, no: np.ndarray, a) -> np.ndarray:
    h = np.full(len(co), a.min_kalinlik)
    if a.hazne:
        hz = json.loads(a.hazne)
        cx, cy = hz["merkez"]
        r = hz["ust_cap_mm"] / 2
        d = np.hypot(co[:, 0] - cx, co[:, 1] - cy)
        bolge = (d < r + a.hazne_duvar + 3.0) & (co[:, 2] > hz["dip_z"] - a.hazne_duvar - 1.0)
        h[bolge] = np.maximum(h[bolge], a.hazne_duvar)
    return h


def komsuluk(obj) -> list[np.ndarray]:
    me = obj.data
    ed = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", ed)
    ed = ed.reshape(-1, 2)
    return ed


def kalinlastir(obj, a) -> dict:
    co, no = _diziler(obj)
    t = kalinlik(obj)
    h = hedefler(co, no, a)
    eksik = np.where(np.isfinite(t), np.clip((h - t) / 2.0, 0, None), 0.0)
    ince = int((eksik > 0.02).sum())
    if ince == 0:
        return {"ince_kose": 0}
    # Kenar komşuluğu üzerinden yumuşat (ani çıkıntı olmasın), en az kendi eksiği kadar it.
    ed = komsuluk(obj)
    d = eksik.copy()
    for _ in range(4):
        top = np.zeros_like(d)
        say = np.zeros_like(d)
        np.add.at(top, ed[:, 0], d[ed[:, 1]])
        np.add.at(top, ed[:, 1], d[ed[:, 0]])
        np.add.at(say, ed[:, 0], 1)
        np.add.at(say, ed[:, 1], 1)
        d = np.maximum(eksik, (d + top) / (1 + say))
    yeni = co + no * (d * 1.15)[:, None]
    obj.data.vertices.foreach_set("co", yeni.ravel())
    obj.data.update()
    return {"ince_kose": ince, "max_itme_mm": round(float(d.max() * 1.15), 2)}


def olc(obj, a) -> dict:
    co, no = _diziler(obj)
    t = kalinlik(obj)
    h = hedefler(co, no, a)
    sonlu = np.isfinite(t)
    ince = sonlu & (t < h - 0.05)
    rapor = {
        "ucgen": sum(len(p.vertices) - 2 for p in obj.data.polygons),
        "kalinlik_p1_mm": round(float(np.percentile(t[sonlu], 1)), 2) if sonlu.any() else None,
        "ince_kose_yuzde": round(100.0 * ince.sum() / max(len(t), 1), 2),
        "ince_kose": int(ince.sum()),
    }
    if a.hazne:
        hb = h >= a.hazne_duvar
        if (hb & sonlu).any():
            rapor["hazne_duvar_p5_mm"] = round(float(np.percentile(t[hb & sonlu], 5)), 2)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    rapor["manifold"] = all(e.is_manifold for e in bm.edges)
    rapor["hacim_cm3"] = round(abs(bm.calc_volume()) / 1000, 1)
    bm.free()
    rapor["boyut_mm"] = [round(float(x), 1) for x in (co.max(0) - co.min(0))]
    return rapor


def main() -> None:
    a = _arglar()
    t0 = time.time()
    obj = yukle(a.girdi)
    rapor: dict = {"girdi": a.girdi, "hedef": {"min_kalinlik": a.min_kalinlik, "hazne_duvar": a.hazne_duvar}}
    if a.sadece_olc:
        rapor["sonra"] = olc(obj, a)
    else:
        decimate(obj, a.hedef_ucgen)
        rapor["once"] = olc(obj, a)
        remesh(obj, a.voxel)
        rapor["adalar"] = adalari_temizle(obj)
        decimate(obj, a.hedef_ucgen)
        turlar = []
        for _ in range(a.tur):
            s = kalinlastir(obj, a)
            turlar.append(s)
            # Birkaç dağınık köşe kıvrım gürültüsüdür; yeniden remesh'e değmez.
            if s["ince_kose"] <= max(20, len(obj.data.vertices) // 10000):
                break
            remesh(obj, a.voxel)
            decimate(obj, a.hedef_ucgen)
        rapor["kalinlastirma"] = turlar
        rapor["adalar_son"] = adalari_temizle(obj)
        # Taban: remesh tabanı ~voxel kadar yuvarlar; Z=0'a oturt (düzlük ai3d_hazirla'da kesimle sağlandı).
        co, _ = _diziler(obj)
        obj.data.vertices.foreach_set("co", (co - [0, 0, co[:, 2].min()]).ravel())
        obj.data.update()
        rapor["sonra"] = olc(obj, a)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.ops.wm.stl_export(filepath=a.cikti, export_selected_objects=True, ascii_format=False)
    rapor["sure_sn"] = round(time.time() - t0, 1)
    with open(a.rapor, "w", encoding="utf-8") as f:
        json.dump(rapor, f, ensure_ascii=False, indent=2)
    print("ONAR_RAPOR " + json.dumps(rapor, ensure_ascii=False))


if __name__ == "__main__":
    main()
