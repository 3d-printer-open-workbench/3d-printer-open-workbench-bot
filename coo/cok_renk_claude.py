"""Çok renk boyama — Claude + Blender (Patron kararı 2026-11-16: boyamayı Qwen değil Claude yapar).

Claude ajanı bu aracı Bash ile kullanır (ortam: PY_AI3D):

  1) parcala — model konum + yüzey yönüne göre ~40 bölgeye ayrılır; her bölge farklı renkte, NUMARALI olarak
     6 açıdan Blender'da render edilir → `parcalar_pano.png` + parça listesi (alan, z aralığı, konum).
       python -m coo.cok_renk_claude parcala <sku> [--hedef 40]

  2) boya — Claude parça→renk atamasını JSON kurallarla verir; renk sınırları iç bükey kıvrımlara oturtulur
     (random walker; `--kesin` ile kapatılır), küçük renk adaları temizlenir,
     Orca boyalı `renkli.3mf` + `etiket.npz` yazılır, Blender 6 yön pano (`boyali_pano.png`) ve stüdyo render alınır.
       python -m coo.cok_renk_claude boya <sku> --renkler '#C0392B,#1E1E1E' --kurallar kurallar.json [--varsayilan 0]

     kurallar.json: sırayla uygulanan liste (sonraki öncekini ezer):
       [{"renk": 1, "parcalar": [3, 7, 12]},
        {"renk": 2, "parcalar": [5], "z_min": 40.0},          # 5. parçanın z ≥ 40 mm kısmı
        {"renk": 0, "z_max": 2.0}]                            # parça vermeden: tüm modelin alt 2 mm'si
       Eksen sınırları (mm, modelin kendi koordinatı): x_min x_max y_min y_max z_min z_max.

Claude her `boya` sonrası `boyali_pano.png`'yi Read ile inceler; yanlış parça varsa kuralları düzeltip tekrar çalıştırır.
"""
from __future__ import annotations

import argparse
import colorsys
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .ayar import COO_KLASORU, URUNLER_KLASORU
from .cok_renk import (_eksenler, _izdus, _komsular, _yay, boyali_3mf, kesin_esle, rastgele_yuruyus, renk_degisimi_tahmini,
                       sinir_yumusat, temizle, uc_kirp)

GORUSLER = ("on", "sag", "arka", "sol", "on_alt", "arka_alt")
GORUS_ADI = {"on": "ön", "sag": "sağ", "arka": "arka", "sol": "sol", "on_alt": "ön-alttan", "arka_alt": "arka-alttan"}
KAMERA_EL, ALT_EL = 25, -20
ZBUF = 512


def klasor(sku: str) -> Path:
    return URUNLER_KLASORU / sku / "model" / "cok_renk"


def _mesh(sku: str):
    import trimesh

    stl = URUNLER_KLASORU / sku / "model" / f"{sku}.stl"
    mesh = trimesh.load(stl, force="mesh")
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    return mesh


def _ayirt_renkler(n: int) -> list[str]:
    """Komşu numaralar bile birbirinden ayırt edilsin: altın oran ton adımı, iki açıklık seviyesi."""
    out = []
    for i in range(n):
        h = (i * 0.61803398875) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.65 if i % 2 else 0.85, 0.95 if i % 3 else 0.75)
        out.append("#%02X%02X%02X" % (int(r * 255), int(g * 255), int(b * 255)))
    return out


# ---------------------------------------------------------------------------------------------- parçalama
def parcala_mesh(mesh, hedef: int = 40, min_pay: float = 0.002, normal_agirlik: float = 0.35) -> np.ndarray:
    """Yüzeyi ~hedef bölgeye ayırır: konum + yüz normali üzerinde k-ortalama (YZ mesh'leri pürüzsüzdür, kıvrımlar
    kapalı sınır oluşturmaz), sonra her kümenin bağlı bileşenleri ayrı bölge olur; küçük bölgeler komşuya katılır.
    Bölge sınırları kaba olabilir — `boya` Claude'un atamasını tohum yapıp sınırları iç bükey kıvrımlara oturtur."""
    import scipy.sparse as sp
    from scipy.cluster.vq import kmeans2
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree

    c, nr, alan = mesh.triangles_center, mesh.face_normals, mesh.area_faces
    olcek = float(np.linalg.norm(np.ptp(mesh.vertices, axis=0)))
    oz = np.hstack([c / olcek, nr * normal_agirlik])
    rng = np.random.default_rng(7)
    ornek = oz[rng.choice(len(oz), size=min(len(oz), 60000), replace=False, p=alan / alan.sum())]
    merkezler, _ = kmeans2(ornek, hedef, minit="++", seed=7, iter=30)
    _, kume = cKDTree(merkezler).query(oz)
    # bağlılık: aynı kümedeki komşu yüzler → bileşen
    adj = mesh.face_adjacency
    ayni = kume[adj[:, 0]] == kume[adj[:, 1]]
    a = adj[ayni]
    n = len(mesh.faces)
    k, bil = connected_components(sp.coo_matrix((np.ones(len(a)), (a[:, 0], a[:, 1])), shape=(n, n)), directed=False)
    b_alan = np.bincount(bil, weights=alan, minlength=k)
    buyuk = np.nonzero(b_alan >= alan.sum() * min_pay)[0]
    # numaralama: üstten alta, sonra soldan sağa (okunur sıra)
    bm = np.array([c[bil == b].mean(0) for b in buyuk]) if len(buyuk) else np.zeros((0, 3))
    sira = buyuk[np.lexsort((bm[:, 0], -np.round(bm[:, 2] / (olcek * 0.08))))] if len(buyuk) else buyuk
    harita = -np.ones(k, int)
    harita[sira] = np.arange(len(sira))
    et = harita[bil]
    if (et < 0).any() and len(sira):
        et = _yay(et, _komsular(mesh), len(sira))
    return et.astype(np.int32)


def _gorunur_pikseller(mesh, kamera: dict, maske: np.ndarray):
    """Her yüz için (ix, iy, görünür) — modelin kendi ortografik renderına kesin izdüşüm + z-tampon."""
    c, nr = mesh.triangles_center, mesh.face_normals
    az, el = float(kamera["az"]), float(kamera["el"])
    u, v, d = _izdus(c, az, el, False)
    mu, mv, _ = _izdus(mesh.vertices, az, el, False)
    ix, iy = kesin_esle({}, maske, u, v, mu, mv)
    _, _, bakis = _eksenler(az, el)
    bak = -(nr @ bakis)
    span = max(np.ptp(u), np.ptp(v), 1e-9)
    zu = np.clip(((u - u.min()) / span * (ZBUF - 1)).astype(int), 0, ZBUF - 1)
    zv = np.clip(((v - v.min()) / span * (ZBUF - 1)).astype(int), 0, ZBUF - 1)
    z = np.full((ZBUF, ZBUF), np.inf)
    np.minimum.at(z, (zv, zu), d)
    olcek = max(np.ptp(mesh.vertices, axis=0)) * 0.01
    gorunur = (d <= z[zv, zu] + olcek) & (bak > 0.15) & maske[iy, ix]
    return ix, iy, gorunur


def _blender_kareler(stl: Path, npz: Path, hedef: Path) -> bool:
    hedef.mkdir(parents=True, exist_ok=True)
    s = subprocess.run(["blender", "-b", "-P", str(COO_KLASORU / "blender_gorunus.py"), "--", str(stl), str(hedef / "_"),
                        "--kareler", str(hedef), "--el", str(KAMERA_EL), "--alt-el", str(ALT_EL), "--etiket", str(npz)],
                       capture_output=True, text=True, timeout=1200)
    return (hedef / "kamera.json").exists() or bool(print(s.stdout[-800:], s.stderr[-800:]))


def _font(boyut: int):
    for yol in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if Path(yol).exists():
            return ImageFont.truetype(yol, boyut)
    return ImageFont.load_default()


def _pano(kareler: Path, mesh, etiket: np.ndarray | None, hedef: Path, numara: bool) -> Path:
    kamera = json.loads((kareler / "kamera.json").read_text(encoding="utf-8"))
    hucre, karolar = 640, []
    f_no, f_baslik = _font(22), _font(26)
    for ad in GORUSLER:
        yol = kareler / f"{ad}.png"
        if not yol.exists() or ad not in kamera:
            continue
        rgba = Image.open(yol).convert("RGBA")
        maske = np.asarray(rgba)[:, :, 3] > 127
        zemin = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(zemin, rgba).convert("RGB")
        if numara and etiket is not None:
            ix, iy, gor = _gorunur_pikseller(mesh, kamera[ad], maske)
            ciz = ImageDraw.Draw(img)
            yerler = []
            for p in np.unique(etiket[gor]):
                s = gor & (etiket == p)
                if s.sum() < 25:
                    continue
                px, py = np.median(ix[s]), np.median(iy[s])
                # median parçanın dışında kalabilir (halka şekli): parçaya ait en yakın piksel
                j = np.argmin((ix[s] - px) ** 2 + (iy[s] - py) ** 2)
                px, py = int(ix[s][j]), int(iy[s][j])
                if any(abs(px - a) < 26 and abs(py - b) < 20 for a, b in yerler):
                    continue
                yerler.append((px, py))
                t = str(int(p))
                w = ciz.textlength(t, font=f_no)
                ciz.rounded_rectangle((px - w / 2 - 5, py - 14, px + w / 2 + 5, py + 14), 6, fill="white", outline="black", width=2)
                ciz.text((px - w / 2, py - 13), t, fill="black", font=f_no)
        img = img.resize((hucre, int(img.height * hucre / img.width)))
        ImageDraw.Draw(img).text((12, 8), GORUS_ADI.get(ad, ad), fill="black", font=f_baslik)
        karolar.append(img)
    h = max(k.height for k in karolar)
    pano = Image.new("RGB", (hucre * 3, h * 2), "white")
    for i, k in enumerate(karolar[:6]):
        pano.paste(k, ((i % 3) * hucre, (i // 3) * h))
    pano.save(hedef)
    return hedef


def parcala(sku: str, hedef: int = 40) -> dict:
    k = klasor(sku)
    k.mkdir(parents=True, exist_ok=True)
    mesh = _mesh(sku)
    et = parcala_mesh(mesh, hedef)
    n = int(et.max()) + 1
    npz = k / "parcalar.npz"
    np.savez_compressed(npz, merkez=mesh.triangles_center.astype(np.float32), etiket=et.astype(np.int16),
                        renkler=np.array(_ayirt_renkler(n)), kutu=mesh.bounds.astype(np.float32))
    stl = k / "parcala.stl"
    mesh.export(stl)
    kareler = k / "parca_kareler"
    if not _blender_kareler(stl, npz, kareler):
        return {"basarili": False, "hata": "Blender parça renderı alınamadı"}
    pano = _pano(kareler, mesh, et, k / "parcalar_pano.png", numara=True)
    alan, c = mesh.area_faces, mesh.triangles_center
    lo, hi = mesh.bounds
    liste = []
    for p in range(n):
        s = et == p
        cz = c[s]
        liste.append({"parca": p, "alan_yuzde": round(float(alan[s].sum() / alan.sum() * 100), 2),
                      "z_mm": [round(float(cz[:, 2].min()), 1), round(float(cz[:, 2].max()), 1)],
                      "merkez_mm": [round(float(x), 1) for x in cz.mean(0)]})
    rapor = {"basarili": True, "parca_sayisi": n, "pano": str(pano), "model_kutusu_mm": [lo.round(1).tolist(), hi.round(1).tolist()],
             "parcalar": liste}
    (k / "parcalar.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    return rapor


# ---------------------------------------------------------------------------------------------- boyama
def kurallari_uygula(etiket_parca: np.ndarray, merkez: np.ndarray, kurallar: list[dict], varsayilan: int,
                     renk_sayisi: int) -> np.ndarray:
    renk = np.full(len(etiket_parca), int(varsayilan), np.int64)
    for kural in kurallar:
        r = int(kural["renk"])
        if not 0 <= r < renk_sayisi:
            raise ValueError(f"geçersiz renk indeksi {r} (0..{renk_sayisi - 1})")
        sec = np.ones(len(renk), bool)
        if kural.get("parcalar") is not None:
            sec &= np.isin(etiket_parca, [int(x) for x in kural["parcalar"]])
        for i, eksen in enumerate("xyz"):
            if f"{eksen}_min" in kural:
                sec &= merkez[:, i] >= float(kural[f"{eksen}_min"])
            if f"{eksen}_max" in kural:
                sec &= merkez[:, i] <= float(kural[f"{eksen}_max"])
        renk[sec] = r
    return renk


def boya(sku: str, renkler: list[str], kurallar: list[dict], varsayilan: int = 0, min_alan_mm2: float = 25.0,
         studyo: bool = True, kesin: bool = False, sadelestir: bool = True) -> dict:
    k = klasor(sku)
    p_yol = k / "parcalar.npz"
    if not p_yol.exists():
        return {"basarili": False, "hata": "önce `parcala` çalıştır"}
    mesh = _mesh(sku)
    parca = np.load(p_yol)["etiket"].astype(np.int64)
    if len(parca) != len(mesh.faces):
        return {"basarili": False, "hata": "model parçalamadan sonra değişmiş — `parcala`yı yeniden çalıştır"}
    renkler = [h.upper() for h in renkler][:4]
    kaba = kurallari_uygula(parca, mesh.triangles_center, kurallar, varsayilan, len(renkler))
    if kesin:
        et = kaba
    else:
        # sınır iyileştirme: renk sınırına 3 halka yakın yüzler bilinmiyor sayılır, random walker kıvrım ağırlıklı
        # grafikte (iç bükey kenarlar zayıf bağ) bunları doldurur → sınır en yakın gerçek parça çizgisine oturur
        # Eksen kesimi (aynı bölge içinde z/x/y sınırı, ör. taban z=20.5) düz kalır: yürüyüş yalnız bölge
        # sınırlarında çalışır, yoksa düz kesim tırtıklanır ve sınır katmanlara yayılır (fazla renk değişimi).
        komsu = _komsular(mesh)
        tohum = kaba.copy()
        a = komsu.tocoo()
        farkli = kaba[a.row] != kaba[a.col]
        bolge = farkli & (parca[a.row] != parca[a.col])
        sinir = np.zeros(len(kaba), bool)
        sinir[a.row[bolge]] = True
        for _ in range(3):
            sinir = sinir | (komsu @ sinir.astype(float) > 0)
        eksen = np.zeros(len(kaba), bool)
        eksen[a.row[farkli & ~bolge]] = True
        eksen = eksen | (komsu @ eksen.astype(float) > 0)
        tohum[sinir & ~eksen] = -1
        et = rastgele_yuruyus(mesh, tohum, len(renkler))
    et = temizle(mesh, et, len(renkler), min_alan_mm2)
    if not kesin:
        et = sinir_yumusat(mesh, et, len(renkler))  # dişli/yırtık sınır → düzgün eğri (yüz–kask gibi kıvrımsız sınırlar)
    degisim_once = renk_degisimi_tahmini(mesh, et)
    kirpilan: list[dict] = []
    if sadelestir:
        et, kirpilan = uc_kirp(mesh, et, len(renkler))
    np.savez_compressed(k / "etiket.npz", merkez=mesh.triangles_center.astype(np.float32), etiket=et.astype(np.int8),
                        renkler=np.array(renkler), kutu=mesh.bounds.astype(np.float32))
    mesh.export(k / "renkli.stl")
    boyali_3mf(mesh, et, k / "renkli.3mf")
    kareler = k / "boyali_kareler"
    if not _blender_kareler(k / "renkli.stl", k / "etiket.npz", kareler):
        return {"basarili": False, "hata": "Blender boyalı render alınamadı"}
    pano = _pano(kareler, mesh, None, k / "boyali_pano.png", numara=False)
    if studyo:
        subprocess.run(["blender", "-b", "-P", str(COO_KLASORU / "gorsel" / "blender_ciz.py"), "--", "--stl", str(k / "renkli.stl"),
                        "--cikti", str(k / "render"), "--etiket", str(k / "etiket.npz"), "--cozunurluk", "1280", "--ornek", "40"],
                       capture_output=True, text=True, timeout=1500)
    alan = mesh.area_faces
    paylar = [round(float(alan[et == i].sum() / alan.sum() * 100), 1) for i in range(len(renkler))]
    rapor = {"basarili": True, "yontem": "claude-blender", "renkler": renkler, "alan_yuzde": paylar, "kurallar": kurallar,
             "varsayilan": varsayilan, "renk_degisimi_tahmini": renk_degisimi_tahmini(mesh, et),
             "renk_degisimi_sadelestirmeden": degisim_once, "uc_kirpma": kirpilan, "pano": str(pano), "renkli_3mf": str(k / "renkli.3mf"),
             "studyo": str(k / "render" / "studyo.png") if (k / "render" / "studyo.png").exists() else None,
             "uyarilar": [f"{renkler[i]} neredeyse hiç kullanılmıyor (%{p})" for i, p in enumerate(paylar) if p < 0.5]}
    (k / "rapor.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    return rapor


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    alt = ap.add_subparsers(dest="komut", required=True)
    p1 = alt.add_parser("parcala")
    p1.add_argument("sku")
    p1.add_argument("--hedef", type=int, default=40, help="en fazla büyük parça sayısı (küçükse daha ince bölünür)")
    p2 = alt.add_parser("boya")
    p2.add_argument("sku")
    p2.add_argument("--renkler", required=True, help="#RRGGBB,… (en fazla 4, filament sırası)")
    p2.add_argument("--kurallar", required=True, help="kurallar.json yolu ya da JSON metni")
    p2.add_argument("--varsayilan", type=int, default=0, help="kurala girmeyen yüzlerin renk indeksi")
    p2.add_argument("--studyo-yok", action="store_true", help="stüdyo render alma (hızlı deneme)")
    p2.add_argument("--kesin", action="store_true", help="sınırı kıvrıma oturtma; kuralları birebir uygula (eksen kesimleri için)")
    p2.add_argument("--sadelestirme-yok", action="store_true",
                    help="renk uçlarını kırpma (varsayılan: ince uç şeritler komşu renge verilir → az renk değişimi)")
    a = ap.parse_args()
    if a.komut == "parcala":
        print(json.dumps(parcala(a.sku, a.hedef), ensure_ascii=False))
    else:
        metin = Path(a.kurallar).read_text(encoding="utf-8") if Path(a.kurallar).exists() else a.kurallar
        print(json.dumps(boya(a.sku, a.renkler.split(","), json.loads(metin), a.varsayilan, studyo=not a.studyo_yok, kesin=a.kesin,
                              sadelestir=not a.sadelestirme_yok),
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
