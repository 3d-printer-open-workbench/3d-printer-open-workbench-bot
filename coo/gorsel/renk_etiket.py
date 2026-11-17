"""Blender içinde: cok_renk etiket.npz (yüz merkezi → renk sırası) ile mesh'e renk başına malzeme atar."""
import numpy as np


def etiketle(obj, npz_yolu, malzeme_uret):
    """malzeme_uret(hex) -> bpy Material. Çokgen merkezleri KD-ağaçla etiket merkezlerine eşlenir (yüz sırası
    Blender içe aktarımında değişse de doğru renk)."""
    from mathutils import Vector
    from mathutils.kdtree import KDTree

    v = np.load(npz_yolu)
    merkez, etiket, renkler = v["merkez"], v["etiket"], [str(x) for x in v["renkler"]]
    agac = KDTree(len(merkez))
    for i, c in enumerate(merkez):
        agac.insert(Vector(c.tolist()), i)
    agac.balance()
    me = obj.data
    me.materials.clear()
    for h in renkler:
        me.materials.append(malzeme_uret(h))
    mw = obj.matrix_world
    # betik nesneyi tablaya ortalayıp taşımış olabilir: alt köşeleri hizala (yalnız öteleme yapılır)
    kose = [mw @ Vector(c) for c in obj.bound_box]
    obj_min = Vector((min(k.x for k in kose), min(k.y for k in kose), min(k.z for k in kose)))
    kaydir = Vector(v["kutu"][0].tolist()) - obj_min if "kutu" in v.files else Vector((0, 0, 0))
    idx = np.empty(len(me.polygons), np.int32)
    for p in me.polygons:
        _, i, _ = agac.find(mw @ p.center + kaydir)
        idx[p.index] = etiket[i]
    me.polygons.foreach_set("material_index", idx)
    me.update()
    return renkler
