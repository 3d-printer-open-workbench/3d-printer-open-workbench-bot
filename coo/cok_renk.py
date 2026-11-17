"""Çok renkli baskı: renklendirilmiş görünümlerden (ön/sol/arka) onarılmış STL'nin yüzeyine renk aktarımı.

Akış (bot `coo/__main__.py → _cok_renk_baslat`):
  1) Renk şeması (ajan, paletteki filamentlerden en fazla 4 renk + hangi parça hangi renk) seçilir.
  2) Qwen-Image-Edit konsept görünümlerini (Hunyuan'ın gördüğü ön/sol/arka) bu düz renklerle boyar (`boyali_*.png`).
  3) BU MODÜL: her görünüm için kamera açısı siluet + gölgelendirme benzerliğiyle bulunur (az/el/ayna), yüz
     merkezleri görünüme izdüşürülür, z-tamponla görünürlük, yüz normaline göre ağırlıklı oylama → her üçgen
     şemadaki en yakın filamente (Lab) atanır; görünmeyen yüzler komşulardan yayılır; çoğunluk süzgeci ve küçük
     renk adaları (baskıda gereksiz renk değişimi) temizlenir.
  4) Çıktılar: `renkli.3mf` (Orca `paint_color` boyamalı girdi), `etiket.npz` (Blender render için), rapor.

    python -m coo.cok_renk <stl> <cikti_klasoru> --renkler '#E2DDC7,#1E1E1E' \
        --gorus on=<boyali_on.png>:<maske_on.png> --gorus sol=... --gorus arka=...
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

from .renk_al import hex_rgb, srgb_lab

IZGARA = 160                 # hizalama için siluet ızgarası
ZBUF = 384                   # görünürlük z-tamponu çözünürlüğü
ORCA_KOD = ["4", "8", "0C", "1C", "2C", "3C", "4C", "5C"]  # paint_color: filament 1..8 (Orca/Bambu 3MF)
L_AGIRLIK = 0.55             # gölgeli görselde açıklık farkı daha az güvenilir


# --- izdüşüm ------------------------------------------------------------------------------------------------
def _eksenler(az: float, el: float):
    """Z-yukarı mesh için kamera eksenleri: sag (u), yukari (v), bakis (kameradan nesneye)."""
    a, e = np.radians(az), np.radians(el)
    bakis = np.array([np.sin(a) * np.cos(e), np.cos(a) * np.cos(e), -np.sin(e)])  # az=0: kamera -Y'de, +Y'ye bakar
    sag = np.array([np.cos(a), -np.sin(a), 0.0])
    yukari = np.cross(sag, bakis)
    return sag, yukari, bakis


def _izdus(p: np.ndarray, az: float, el: float, ayna: bool):
    sag, yukari, bakis = _eksenler(az, el)
    u, v, d = p @ sag, p @ yukari, p @ bakis
    if ayna:
        u = -u
    return u, v, d


def _beyaz_disi(rgb: np.ndarray, esik: float = 22.0) -> np.ndarray:
    """Düz beyaz zeminli görüntüde nesne maskesi (en büyük bileşen, delikler dolu)."""
    from scipy import ndimage

    m = np.linalg.norm(rgb.astype(float) - 255, axis=2) > esik
    m = ndimage.binary_opening(m, iterations=2)
    lab, n = ndimage.label(m)
    if n > 1:
        m = lab == (np.argmax(np.bincount(lab.ravel())[1:]) + 1)
    return ndimage.binary_fill_holes(m)


def _maske_kutu(m: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(m)
    return xs.min(), ys.min(), xs.max(), ys.max()


def _izgaraya(u: np.ndarray, v: np.ndarray, n: int = IZGARA):
    u0, v1 = u.min(), v.max()
    s = (n - 1) / max(u.max() - u0, v1 - v.min(), 1e-9)
    return ((u - u0) * s).astype(int), ((v1 - v) * s).astype(int)


def _hedef_izgara(maske: np.ndarray, n: int = IZGARA) -> np.ndarray:
    x0, y0, x1, y1 = _maske_kutu(maske)
    kes = maske[y0:y1 + 1, x0:x1 + 1]
    h, w = kes.shape
    s = (n - 1) / max(h, w)
    im = Image.fromarray((kes * 255).astype(np.uint8)).resize((max(1, round(w * s)), max(1, round(h * s))), Image.NEAREST)
    g = np.zeros((n, n), bool)
    a = np.asarray(im) > 127
    g[:a.shape[0], :a.shape[1]] = a
    return g


def _siluet(u, v, n=IZGARA):
    from scipy import ndimage

    iu, iv = _izgaraya(u, v, n)
    g = np.zeros((n, n), bool)
    g[np.clip(iv, 0, n - 1), np.clip(iu, 0, n - 1)] = True
    return ndimage.binary_fill_holes(ndimage.binary_closing(g, iterations=2))


def _golge(u, v, d, nrm_isik, n=IZGARA):
    """Basit Lambert gölgelendirme görüntüsü (z-tampon ile ön yüzler)."""
    iu, iv = _izgaraya(u, v, n)
    iu, iv = np.clip(iu, 0, n - 1), np.clip(iv, 0, n - 1)
    z = np.full((n, n), np.inf)
    np.minimum.at(z, (iv, iu), d)
    on = d <= z[iv, iu] + 1e-6
    g = np.zeros((n, n))
    g[iv[on], iu[on]] = nrm_isik[on]
    return g


def hizala(mesh, gorsel_rgb: np.ndarray, maske: np.ndarray, azlar=None, aynalar=(False, True),
           eller=(0, 10, 20, 30)) -> dict:
    """Görünüm görseline en uyan kamera (az, el, ayna) — siluet IoU × (1 + gölge korelasyonu).
    azlar/aynalar: aday kısıtı (ön bulunduktan sonra arka = ön+180, yan = ön±90; ayna önle aynı)."""
    rng = np.random.default_rng(0)
    idx = rng.choice(len(mesh.faces), min(len(mesh.faces), 60000), replace=False)
    c = mesh.triangles_center[idx]
    nr = mesh.face_normals[idx]
    hedef = _hedef_izgara(maske)
    gri = np.asarray(Image.fromarray(gorsel_rgb).convert("L"), np.float64) / 255
    x0, y0, x1, y1 = _maske_kutu(maske)
    kes = gri[y0:y1 + 1, x0:x1 + 1]
    h, w = kes.shape
    s = (IZGARA - 1) / max(h, w)
    gri_iz = np.zeros((IZGARA, IZGARA))
    a = np.asarray(Image.fromarray((kes * 255).astype(np.uint8)).resize((max(1, round(w * s)), max(1, round(h * s)))), np.float64) / 255
    gri_iz[:a.shape[0], :a.shape[1]] = a
    azlar = range(0, 360, 5) if azlar is None else azlar
    en_iyi = {"skor": -1.0}
    for el in eller:
        for az in azlar:
            for ayna in aynalar:
                u, v, d = _izdus(c, az, el, ayna)
                sil = _siluet(u, v)
                iou = float((sil & hedef).sum() / max((sil | hedef).sum(), 1))
                if iou < en_iyi.get("iou", 0) * 0.85:
                    continue
                _, _, bakis = _eksenler(az, el)
                isik = np.clip(-(nr @ bakis), 0, 1)  # kameraya bakan yüz parlak
                gl = _golge(u, v, d, isik)
                ortak = sil & hedef
                kor = 0.0
                if ortak.sum() > 50:
                    x, y = gl[ortak], gri_iz[ortak]
                    if x.std() > 1e-6 and y.std() > 1e-6:
                        kor = float(np.corrcoef(x, y)[0, 1])
                skor = iou * (1 + max(kor, 0))
                if skor > en_iyi["skor"]:
                    en_iyi = {"skor": round(skor, 4), "iou": round(iou, 3), "kor": round(kor, 3),
                              "az": az % 360, "el": el, "ayna": ayna}
    return en_iyi


# --- esnek eşleme -------------------------------------------------------------------------------------------
SATIR = 256


def _satir_kenarlari(x: np.ndarray, satir: np.ndarray, n: int = SATIR) -> tuple[np.ndarray, np.ndarray]:
    """Her yükseklik satırında siluetin sol/sağ kenarı (boş satırlar komşulardan doldurulur)."""
    sol, sag = np.full(n, np.nan), np.full(n, np.nan)
    for r in range(n):
        xs = x[satir == r]
        if len(xs) >= 3:
            sol[r], sag[r] = np.percentile(xs, 1), np.percentile(xs, 99)
    i = np.arange(n)
    ok = ~np.isnan(sol)
    if ok.sum() < 2:
        return np.full(n, np.nanmin(x)), np.full(n, np.nanmax(x))
    return np.interp(i, i[ok], sol[ok]), np.interp(i, i[ok], sag[ok])


def esnek_esle(mesh, hiz: dict, maske: np.ndarray, u: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mesh izdüşümünü görünüm maskesine esneterek oturtur: dikeyde göreli yükseklik (maske kutusu), yatayda
    her yükseklik satırında sol↔sol, sağ↔sağ kenar eşlemesi. Hunyuan modeli görünümlerle aynı oranda olmasa da
    (ör. tepsi daha geniş) parçalar görünümdeki karşılıklarına düşer."""
    H, W = maske.shape
    x0, y0, x1, y1 = _maske_kutu(maske)
    vu, vv, _ = _izdus(mesh.vertices, hiz["az"], hiz["el"], hiz["ayna"])
    vmin, vmax = vv.min(), vv.max()
    def goreli(t):
        return np.clip((vmax - t) / max(vmax - vmin, 1e-9), 0, 1)  # 0 üst, 1 alt
    m_sol, m_sag = _satir_kenarlari(vu, np.minimum((goreli(vv) * SATIR).astype(int), SATIR - 1))
    ys, xs = np.nonzero(maske)
    i_sol, i_sag = _satir_kenarlari(xs.astype(float), np.minimum(((ys - y0) / max(y1 - y0, 1) * SATIR).astype(int), SATIR - 1))
    def yatay(uu, vv):
        g = goreli(vv)
        r = np.minimum((g * SATIR).astype(int), SATIR - 1)
        t = (uu - m_sol[r]) / np.maximum(m_sag[r] - m_sol[r], 1e-6)
        return i_sol[r] + np.clip(t, 0, 1) * (i_sag[r] - i_sol[r])

    # 2. aşama: her (eşlenmiş) sütunda üst↔üst, alt↔alt — şapka, omuz gibi çıkıntılar kendi yüksekliğine oturur
    vpx = yatay(vu, vv)
    sut = lambda x: np.minimum(((x - x0) / max(x1 - x0, 1) * SATIR).clip(0).astype(int), SATIR - 1)  # noqa: E731
    m_ust, m_alt = _satir_kenarlari(-vv, sut(vpx))          # -v: üst kenar küçük değer
    i_ust, i_alt = _satir_kenarlari(ys.astype(float), sut(xs.astype(float)))
    px = yatay(u, v)
    c = sut(px)
    t = (-v - m_ust[c]) / np.maximum(m_alt[c] - m_ust[c], 1e-6)
    py = i_ust[c] + np.clip(t, 0, 1) * (i_alt[c] - i_ust[c])
    return np.clip(np.round(px).astype(int), 0, W - 1), np.clip(np.round(py).astype(int), 0, H - 1)


# --- renk aktarımı ------------------------------------------------------------------------------------------
def _lab_uzaklik(lab: np.ndarray, palet_lab: np.ndarray) -> np.ndarray:
    w = np.array([L_AGIRLIK, 1.0, 1.0])
    return np.linalg.norm((lab[:, None, :] - palet_lab[None, :, :]) * w, axis=2)


def kesin_esle(hiz: dict, maske: np.ndarray, u: np.ndarray, v: np.ndarray, mu: np.ndarray, mv: np.ndarray):
    """Model kendi renderından boyandıysa (bilinen ortografik kamera) eşleme bir benzerlik dönüşümüdür:
    siluet kutusu ↔ maske kutusu (tek ölçek)."""
    H, W = maske.shape
    x0, y0, x1, y1 = _maske_kutu(maske)
    s = ((x1 - x0) / max(mu.max() - mu.min(), 1e-9) + (y1 - y0) / max(mv.max() - mv.min(), 1e-9)) / 2
    px = (u - (mu.max() + mu.min()) / 2) * s + (x0 + x1) / 2
    py = ((mv.max() + mv.min()) / 2 - v) * s + (y0 + y1) / 2
    return np.clip(np.round(px).astype(int), 0, W - 1), np.clip(np.round(py).astype(int), 0, H - 1)


def gorus_oylari(mesh, gorsel_rgb: np.ndarray, maske: np.ndarray, hiz: dict, palet_lab: np.ndarray,
                 kalan: int | None = None) -> np.ndarray:
    """(yüz sayısı × renk sayısı) ağırlıklı oy matrisi bu görünüm için."""
    c, nr = mesh.triangles_center, mesh.face_normals
    u, v, d = _izdus(c, hiz["az"], hiz["el"], hiz["ayna"])
    _, _, bakis = _eksenler(hiz["az"], hiz["el"])
    bak = -(nr @ bakis)                                    # >0: yüz kameraya dönük
    H, W = maske.shape
    if hiz.get("kesin"):
        mu, mv, _ = _izdus(mesh.vertices, hiz["az"], hiz["el"], hiz["ayna"])
        ix, iy = kesin_esle(hiz, maske, u, v, mu, mv)
    else:
        ix, iy = esnek_esle(mesh, hiz, maske, u, v)
    # görünürlük: z-tampon (yüz merkezleri; mesh izdüşüm uzayında, esnetmeden önce)
    zu, zv = _izgaraya(u, v, ZBUF)
    zu, zv = np.clip(zu, 0, ZBUF - 1), np.clip(zv, 0, ZBUF - 1)
    z = np.full((ZBUF, ZBUF), np.inf)
    np.minimum.at(z, (zv, zu), d)
    olcek = max(np.ptp(mesh.vertices, axis=0)) * 0.012
    gorunur = (d <= z[zv, zu] + olcek) & (bak > 0.12) & maske[iy, ix]
    oy = np.zeros((len(c), len(palet_lab)))
    sinif = siniflandir(gorsel_rgb, maske, palet_lab, kalan=kalan)  # -1: renk sınırına yakın / arka plan
    sec = gorunur & (sinif[iy, ix] >= 0)
    if sec.any():
        oy[np.nonzero(sec)[0], sinif[iy[sec], ix[sec]]] = bak[sec]
    return oy


def siniflandir(rgb: np.ndarray, maske: np.ndarray, palet_lab: np.ndarray, asinma: int = 14,
                uzak_esik: float = 45.0, kalan: int | None = None) -> np.ndarray:
    """Boyalı görünümün her pikselini en yakın filament rengine atar; renk sınırlarından `asinma` piksel içeride
    kalmayanları -1 yapar (sınırlar geometri ile belirlenecek, görüntü ile değil)."""
    from scipy import ndimage

    H, W = maske.shape
    lab = srgb_lab(rgb.reshape(-1, 3))
    uz = _lab_uzaklik(lab, palet_lab)
    en = np.argmin(uz, axis=1).reshape(H, W)
    uzak = (uz.min(axis=1) > uzak_esik).reshape(H, W)  # hiçbir renge benzemeyen (boyanmamış/gri) piksel
    sonuc = np.full((H, W), -1, np.int32)
    for k in range(len(palet_lab)):
        m = (en == k) & maske & ~uzak
        if kalan is not None and k == kalan:
            m = m | (maske & uzak)  # YZ'nin boyamadığı yüzeyler "kalan her şey" rengine
        ic = ndimage.binary_erosion(m, iterations=asinma) if asinma > 0 else m
        sonuc[ic] = k
    return sonuc


def _komsular(mesh):
    import scipy.sparse as sp

    a = mesh.face_adjacency
    n = len(mesh.faces)
    m = sp.coo_matrix((np.ones(len(a) * 2), (np.r_[a[:, 0], a[:, 1]], np.r_[a[:, 1], a[:, 0]])), shape=(n, n)).tocsr()
    return m


def _yay(etiket: np.ndarray, komsu, k: int) -> np.ndarray:
    """-1 etiketli yüzleri komşu çoğunluğuyla doldurur."""
    et = etiket.copy()
    for _ in range(200):
        bos = et < 0
        if not bos.any():
            break
        tek = np.zeros((len(et), k))
        dolu = np.nonzero(~bos)[0]
        tek[dolu, et[dolu]] = 1
        say = komsu @ tek
        aday = bos & (say.sum(1) > 0)
        if not aday.any():
            et[bos] = 0
            break
        et[aday] = np.argmax(say[aday], axis=1)
    return et


def kivrim_agirliklari(mesh, keskinlik: float = 15.0):
    """Yüz komşuluk grafiği; iç bükey kıvrımlarda (parça sınırları) bağ zayıf, düz/dış bükeyde güçlü."""
    import scipy.sparse as sp

    adj = mesh.face_adjacency
    aci = mesh.face_adjacency_angles
    icbukey = ~mesh.face_adjacency_convex
    w = np.where(icbukey, np.exp(-keskinlik * aci), 1.0) + 1e-4
    n = len(mesh.faces)
    return sp.coo_matrix((np.r_[w, w], (np.r_[adj[:, 0], adj[:, 1]], np.r_[adj[:, 1], adj[:, 0]])), shape=(n, n)).tocsr()


def rastgele_yuruyus(mesh, tohum: np.ndarray, k: int) -> np.ndarray:
    """Random walker: tohum (-1 = bilinmiyor) etiketlerini kıvrım ağırlıklı grafikte yayar."""
    import scipy.sparse as sp
    from scipy.sparse.linalg import cg

    A = kivrim_agirliklari(mesh)
    d = np.asarray(A.sum(1)).ravel()
    L = (sp.diags(d) - A).tocsr()
    bil = np.nonzero(tohum < 0)[0]
    tk = np.nonzero(tohum >= 0)[0]
    if len(bil) == 0 or len(tk) == 0:
        return np.where(tohum < 0, 0, tohum)
    Luu = L[bil][:, bil].tocsr()
    Lus = L[bil][:, tk]
    on = sp.diags(1.0 / np.maximum(Luu.diagonal(), 1e-9))
    olas = np.zeros((len(bil), k))
    for j in range(k):
        b = -(Lus @ (tohum[tk] == j).astype(float))
        x, _ = cg(Luu, b, M=on, maxiter=3000, rtol=1e-6) if "rtol" in cg.__code__.co_varnames else cg(Luu, b, M=on, maxiter=3000, tol=1e-6)
        olas[:, j] = x
    et = tohum.copy()
    et[bil] = np.argmax(olas, axis=1)
    return et


def temizle(mesh, etiket: np.ndarray, k: int, min_alan_mm2: float) -> np.ndarray:
    from scipy.sparse.csgraph import connected_components

    komsu = _komsular(mesh)
    et = _yay(etiket, komsu, k)
    iki = (komsu @ komsu + komsu).tocsr()  # 2 halka komşuluk: tırtıklı sınırları düzeltir
    iki.data[:] = 1.0
    for _ in range(6):  # çoğunluk süzgeci (alan ağırlıklı)
        tek = np.zeros((len(et), k))
        tek[np.arange(len(et)), et] = mesh.area_faces
        say = iki @ tek + tek
        yeni = np.argmax(say, axis=1)
        if (yeni == et).all():
            break
        et = yeni
    alan = mesh.area_faces
    for _ in range(3):  # küçük renk adaları → çevresinin rengi
        a = komsu.tocoo()
        ayni = et[a.row] == et[a.col]
        import scipy.sparse as sp

        g = sp.coo_matrix((np.ones(ayni.sum()), (a.row[ayni], a.col[ayni])), shape=komsu.shape)
        n, bilesen = connected_components(g, directed=False)
        b_alan = np.bincount(bilesen, weights=alan, minlength=n)
        kucuk = b_alan[bilesen] < min_alan_mm2
        if not kucuk.any():
            break
        et = _yay(np.where(kucuk, -1, et), komsu, k)
    return et


# --- çıktılar -----------------------------------------------------------------------------------------------
def boyali_3mf(mesh, etiket: np.ndarray, hedef: Path) -> Path:
    v = "".join(f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in mesh.vertices)
    t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}" paint_color="{ORCA_KOD[e]}"/>'
                for (a, b, c), e in zip(mesh.faces, etiket))
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             f'<resources><object id="1" type="model"><mesh><vertices>{v}</vertices><triangles>{t}</triangles>'
             '</mesh></object></resources><build><item objectid="1"/></build></model>')
    with zipfile.ZipFile(hedef, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.'
                   'openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/'
                   'vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/'
                   'vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.'
                   'openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" '
                   'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr("3D/3dmodel.model", model)
    return hedef


TABAN_BANT_MM = 3.0
TABAN_ESIK = 0.6


def taban_kontrolu(z: np.ndarray, etiket: np.ndarray, taban: list[int], alan: np.ndarray | None = None,
                   bant_mm: float = TABAN_BANT_MM) -> float | None:
    """Şemada taban/tepsi olarak tanımlı renk(ler)in modelin alt bandındaki alan payı (0–1). Bant boşsa None."""
    alt = z <= float(z.min()) + bant_mm
    if not alt.any():
        return None
    w = alan[alt] if alan is not None else np.ones(int(alt.sum()))
    return float(w[np.isin(etiket[alt], taban)].sum() / max(w.sum(), 1e-9))


def taban_duzelt(mesh, etiket: np.ndarray, taban: list[int], alt_mm: float = 1.0, zemin_mm: float = 15.0) -> np.ndarray:
    """Taban/tepsi rengine ait olması gereken yanlış boyalı adaları düzeltir: taban dışı bir rengin, o rengin en büyük
    (ana parça) bileşeni OLMAYAN ve tablaya değen (z ≤ alt_mm) ya da tamamen alt bölgede (z ≤ zemin_mm) kalan
    bağlı bölgeleri taban rengine alınır. YZ'nin tepsi duvarına/zeminine taşırdığı figür rengini temizler."""
    from trimesh.graph import connected_components

    if not taban:
        return etiket
    etiket = etiket.copy()
    z = mesh.triangles_center[:, 2] - mesh.bounds[0, 2]
    alan = mesh.area_faces
    adj = mesh.face_adjacency
    hedef = taban[0]
    for lab in np.unique(etiket):
        if lab in taban:
            continue
        ids = np.where(etiket == lab)[0]
        ic = np.isin(adj[:, 0], ids) & np.isin(adj[:, 1], ids)
        bilesenler = sorted(connected_components(adj[ic], nodes=ids), key=lambda c: -alan[c].sum())
        for c in bilesenler[1:]:
            c = np.asarray(c)
            if z[c].min() <= alt_mm or z[c].max() <= zemin_mm:
                etiket[c] = hedef
    return etiket


def renklendir(stl: Path, cikti: Path, renkler: list[str], gorusler: dict[str, tuple[Path, Path | None]],
               min_alan_mm2: float = 40.0, kamera: dict[str, dict] | None = None,
               kod_renkleri: list[str] | None = None, kalan: int | None = None,
               taban: list[int] | None = None) -> dict:
    """kamera: {görünüm: {az, el}} verilirse görünümler modelin KENDİ renderlarıdır → kesin izdüşüm (arama yok)."""
    import trimesh

    cikti.mkdir(parents=True, exist_ok=True)
    mesh = trimesh.load(stl, force="mesh")
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    # sınıflandırma: görüntüde boyanan KOD renkleri (verilmişse), etiket i → renkler[i] filamenti
    palet_lab = srgb_lab(np.array([hex_rgb(h) for h in (kod_renkleri or renkler)]))
    kod_paylari: dict[str, list[float]] = {}
    oy = np.zeros((len(mesh.faces), len(renkler)))
    hizalar = {}
    # ön önce: serbest arama; diğerleri Qwen'in kamera dönüşüne göre kısıtlı (ön/arka siluetleri ayna simetriği
    # olduğundan serbest aramada arka görünüm öne oturabiliyor)
    sira = sorted(gorusler, key=lambda a: {"on": 0, "arka": 1}.get(a, 2))
    on_hiz: dict | None = None
    on_oy: np.ndarray | None = None
    for ad in sira:
        boyali, maske_yol = gorusler[ad]
        rgba = np.asarray(Image.open(boyali).convert("RGBA"))
        rgb = rgba[:, :, :3]
        if kamera and ad in kamera:
            m = _beyaz_disi(rgb)  # Qwen boyarken kadrajı az kaydırabilir: maskeyi boyalı görüntünün kendisinden al
            if maske_yol and m.sum() < 1000:
                m = np.asarray(Image.open(maske_yol).convert("RGBA").resize((rgb.shape[1], rgb.shape[0])))[:, :, 3] > 127
        elif maske_yol:
            m = np.asarray(Image.open(maske_yol).convert("RGBA").resize((rgb.shape[1], rgb.shape[0])))[:, :, 3] > 127
        elif rgba[:, :, 3].min() < 255:
            m = rgba[:, :, 3] > 127
        else:  # düz beyaz arka plan
            m = np.linalg.norm(rgb.astype(float) - 255, axis=2) > 18
        if kamera and ad in kamera:
            hiz = {"az": float(kamera[ad]["az"]), "el": float(kamera[ad]["el"]), "ayna": False, "kesin": True, "iou": 1.0}
            if ad == "on":
                on_hiz = hiz
        elif on_hiz is None:
            hiz = hizala(mesh, rgb, m)
            if ad == "on":
                on_hiz = hiz
        else:
            # Qwen görünümleri aynı nesnenin etrafında aynı yükseklikte kamera dönüşüyle üretildi:
            # arka = ön+180°, yan = ön±90° (hangisi siluete uyuyorsa); kamera yüksekliği önle aynı.
            a0, ay = on_hiz["az"], (on_hiz["ayna"],)
            azlar = [a0 + 180] if ad == "arka" else [a0 + 90, a0 - 90]
            hiz = hizala(mesh, rgb, m, azlar=azlar, aynalar=ay, eller=(on_hiz["el"],))
        hizalar[ad] = hiz
        if hiz.get("iou", 0) < 0.40:
            continue  # bu görünüm modele hiç oturmadı; oy vermesin
        o = gorus_oylari(mesh, rgb, m, hiz, palet_lab, kalan)
        sinif = siniflandir(rgb, m, palet_lab, asinma=0)
        kod_paylari[ad] = [round(float((sinif == i).sum() / max(m.sum(), 1) * 100), 1) for i in range(len(renkler))]
        iou = hiz.get("iou", 0)
        if ad != "on" and iou < 0.65 and on_oy is not None:
            o[on_oy.sum(1) > 0] = 0  # zayıf oturan görünüm: yalnız önden görülmeyen yüzeylere tohum versin
        oy += o * min(1.0, iou / 0.75) ** 3
        if ad == "on":
            on_oy = o
    top = oy.sum(1)
    guven = np.where(top > 0, oy.max(1) / np.maximum(top, 1e-9), 0)
    tohum = np.where((top > 0.15) & (guven >= 0.8), np.argmax(oy, axis=1), -1)  # kesin yüzler
    gorulen = float((tohum >= 0).mean())
    etiket = rastgele_yuruyus(mesh, tohum, len(renkler))
    etiket = temizle(mesh, etiket, len(renkler), min_alan_mm2)
    if taban:
        etiket = taban_duzelt(mesh, etiket, taban)
    alan = mesh.area_faces
    paylar = [round(float(alan[etiket == i].sum() / alan.sum() * 100), 1) for i in range(len(renkler))]
    np.savez_compressed(cikti / "etiket.npz", merkez=mesh.triangles_center.astype(np.float32), etiket=etiket.astype(np.int8),
                        renkler=np.array(renkler), kutu=mesh.bounds.astype(np.float32))
    mesh.export(cikti / "renkli.stl")
    boyali_3mf(mesh, etiket, cikti / "renkli.3mf")
    rapor = {"basarili": True, "renkler": renkler, "alan_yuzde": paylar, "gorulen_yuzey_yuzde": round(gorulen * 100, 1),
             "hizalama": hizalar, "ucgen": int(len(mesh.faces)), "renkli_3mf": str(cikti / "renkli.3mf"),
             "etiket": str(cikti / "etiket.npz")}
    toplam_pay = [max(p[i] for p in kod_paylari.values()) if kod_paylari else 0 for i in range(len(renkler))]
    eksik = [renkler[i] for i, p in enumerate(toplam_pay) if p < 0.5]
    rapor_ek = {"kod_paylari": kod_paylari, "eksik_renkler": eksik}
    uyarilar = [f"{a} görünümü modele oturmadı (IoU {h.get('iou')})" for a, h in hizalar.items() if h.get("iou", 0) < 0.40]
    kullanilmayan = [renkler[i] for i, p in enumerate(paylar) if p < 0.5]
    if kullanilmayan:
        uyarilar.append(f"Neredeyse hiç kullanılmayan renk(ler): {', '.join(kullanilmayan)}")
    if eksik:
        uyarilar.append("Boyanmış görünümlerde hiç bulunmayan renk(ler): " + ", ".join(eksik)
                        + " — YZ bu parçayı boyamadı; şemayı yenile.")
    if taban:
        tk = taban_kontrolu(mesh.triangles_center[:, 2], etiket, taban, mesh.area_faces)
        rapor_ek["taban_payi"] = tk
        if tk is not None and tk < TABAN_ESIK:
            adlar = ", ".join(renkler[i] for i in taban if i < len(renkler))
            uyarilar.append(f"Taban/tepsi şemadaki renge ({adlar}) boyanmadı — alt {TABAN_BANT_MM:g} mm'nin yalnız "
                            f"%{tk * 100:.0f}'i bu renkte; YZ parçaları karıştırdı. ONAYLAMA, yeniden boyat.")
    rapor.update(rapor_ek)
    rapor["uyarilar"] = uyarilar
    (cikti / "rapor.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    return rapor


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stl", type=Path)
    ap.add_argument("cikti", type=Path)
    ap.add_argument("--renkler", required=True, help="virgülle HEX listesi (en fazla 4)")
    ap.add_argument("--gorus", action="append", required=True, help="ad=boyali.png[:maske.png]")
    ap.add_argument("--min-alan", type=float, default=40.0, help="mm²; daha küçük renk adaları çevresine katılır")
    ap.add_argument("--kamera", type=Path, default=None, help="blender_gorunus --kareler kamera.json (kesin izdüşüm)")
    ap.add_argument("--kalan", type=int, default=None, help="boyanmamış yüzeylerin gideceği renk sırası (0 tabanlı)")
    ap.add_argument("--taban", default="", help="şemada taban/tepsi olan renk sıraları (virgülle) — alt bant denetimi")
    ap.add_argument("--kod-renkleri", default="", help="Qwen'in boyadığı parça kodu renkleri (renkler ile aynı sırada)")
    a = ap.parse_args()
    renkler = [h.strip().upper() for h in a.renkler.split(",") if h.strip()]
    if not 1 <= len(renkler) <= 4:
        raise SystemExit("1–4 renk verilmeli")
    gorusler = {}
    for g in a.gorus:
        ad, yollar = g.split("=", 1)
        parca = yollar.split(":")
        gorusler[ad] = (Path(parca[0]), Path(parca[1]) if len(parca) > 1 and parca[1] else None)
    kamera = json.loads(a.kamera.read_text()) if a.kamera else None
    kodlar = [h.strip().upper() for h in a.kod_renkleri.split(",") if h.strip()] or None
    taban = [int(x) for x in a.taban.split(",") if x.strip()] or None
    print(json.dumps(renklendir(a.stl, a.cikti, renkler, gorusler, a.min_alan, kamera, kodlar, a.kalan, taban),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
