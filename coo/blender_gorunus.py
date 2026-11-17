"""STL'nin 4 yönden (ön, sağ, arka, sol) hızlı Workbench renderı → yan yana pano. Ajanın/Patronun
modeli her yönden görmesi için.

    blender -b -P coo/blender_gorunus.py -- <girdi.stl> <cikti.png> [--on-aci 0]
"""
import math
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
girdi, cikti = argv[0], argv[1]
on_aci = float(argv[argv.index("--on-aci") + 1]) if "--on-aci" in argv else 0.0
etiket_npz = argv[argv.index("--etiket") + 1] if "--etiket" in argv else None
# --kareler <klasör>: tek tek şeffaf kareler + kamera.json (coo/cok_renk kesin izdüşüm için); --el: kamera yükseklik açısı
kare_klasoru = argv[argv.index("--kareler") + 1] if "--kareler" in argv else None
el_derece = float(argv[argv.index("--el") + 1]) if "--el" in argv else math.degrees(math.atan2(0.6, 3))
alt_el = float(argv[argv.index("--alt-el") + 1]) if "--alt-el" in argv else None  # ek: alttan ön/arka (şapka altı vb.)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.stl_import(filepath=girdi)
obj = bpy.context.selected_objects[0]
bpy.ops.object.shade_smooth()
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "SINGLE"
sc.display.shading.single_color = (0.85, 0.80, 0.72)
if etiket_npz:  # çok renk: renk başına malzeme (coo/cok_renk.py etiket.npz)
    import os as _os
    sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "gorsel"))
    from renk_etiket import etiketle

    def _mat(h):
        m = bpy.data.materials.new(h)
        r, g, b = (int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
        lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
        m.diffuse_color = (lin(r), lin(g), lin(b), 1)
        return m
    etiketle(obj, etiket_npz, _mat)
    sc.display.shading.color_type = "MATERIAL"
sc.display.shading.show_cavity = True
sc.render.resolution_x = sc.render.resolution_y = 640
sc.render.film_transparent = False
sc.world = bpy.data.worlds.new("w")
sc.world.color = (1, 1, 1)
bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
mrk = sum(bb, Vector()) / 8
r = max((b - mrk).length for b in bb)
cam = bpy.data.objects.new("k", bpy.data.cameras.new("k"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.type = "ORTHO"
cam.data.ortho_scale = r * 2.1
kareler = []
if kare_klasoru:
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = 1024
    cam.data.ortho_scale = r * 2.05
kamera = {}
gorus_listesi = [(ad, i, el_derece) for i, ad in enumerate(["on", "sag", "arka", "sol"])]
if kare_klasoru and alt_el is not None:
    gorus_listesi += [("on_alt", 0, alt_el), ("arka_alt", 2, alt_el)]
for ad, i, el in gorus_listesi:
    a = math.radians(on_aci + 90 * i)
    cam.location = mrk + Vector((math.sin(a) * r * 3, -math.cos(a) * r * 3, r * 3 * math.tan(math.radians(el))))
    kamera[ad] = {"az": (-(on_aci + 90 * i)) % 360, "el": el}  # coo/cok_renk._eksenler kuralı
    cam.rotation_euler = (mrk - cam.location).to_track_quat("-Z", "Y").to_euler()
    yol = f"{kare_klasoru}/{ad}.png" if kare_klasoru else f"{cikti}.{ad}.png"
    sc.render.filepath = yol
    bpy.ops.render.render(write_still=True)
    kareler.append(yol)
if kare_klasoru:
    import json  # noqa: E402

    with open(f"{kare_klasoru}/kamera.json", "w") as f:
        json.dump(kamera, f)
    sys.exit(0)
kareler = kareler[:4]
pano = bpy.data.images.new("pano", 640 * 4, 640)
import numpy as np  # noqa: E402

px = np.zeros((640, 640 * 4, 4), np.float32)
for i, y in enumerate(kareler):
    im = bpy.data.images.load(y)
    px[:, i * 640:(i + 1) * 640] = np.array(im.pixels[:]).reshape(640, 640, 4)
pano.pixels = px.ravel()
pano.filepath_raw = cikti
pano.file_format = "PNG"
pano.save()
import os  # noqa: E402

for y in kareler:
    os.remove(y)
