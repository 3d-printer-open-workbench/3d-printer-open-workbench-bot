"""Görselden 3B mesh üretimi (Hunyuan3D-2, yalnızca şekil — doku yok).

Bu betik `.venv-ai3d` ortamında çalışır; coo paketinin geri kalanını içe aktarmaz.

Kullanım:
    .venv-ai3d/bin/python coo/ai3d_mesh.py <gorsel.png> <cikti_klasoru> \
        [--model mini|v2|mv] [--sol sol.png --arka arka.png] [--tohumlar 1234,42,777] \
        [--yukseklik-mm 120] [--adim 50] [--octree 380]

Çok tohum: model bir kez yüklenir, her tohum için mesh üretilir; her mesh'in siluet sadakati
(IoU) konsept görselinin siluetiyle ölçülür (açı taraması), en yüksek skorlu olan seçilir.
Çok görüş (`--model mv`): ön görsel + sol + arka görünüm (ör. Qwen ile konseptten üretilmiş) →
arka yüz tahmin edilmez, görülür.

Çıktı: <cikti>/ham.glb, <cikti>/ham.stl (Z=0'a oturtulmuş, mm ölçekli), <cikti>/rapor.json.
Lisans: Tencent Hunyuan 3D 2.0 Community License — Bölge (Territory) AB, Birleşik
Krallık ve Güney Kore hariçtir; çıktılar bu bölgelerde kullanılamaz/dağıtılamaz.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

MODELLER = {
    "mini": ("tencent/Hunyuan3D-2mini", "hunyuan3d-dit-v2-mini"),
    "v2": ("tencent/Hunyuan3D-2", "hunyuan3d-dit-v2-0"),
    "mv": ("tencent/Hunyuan3D-2mv", "hunyuan3d-dit-v2-mv"),
}
IZGARA = 128


def _sigdir(m: np.ndarray, n: int = IZGARA) -> np.ndarray:
    """Maskeyi sınır kutusuna kırpar, en-boy oranını koruyarak n×n tuvale ortalar."""
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return np.zeros((n, n), bool)
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = m.shape
    s = (n - 2) / max(h, w)
    yy = (np.arange(max(1, round(h * s))) / s).astype(int).clip(0, h - 1)
    xx = (np.arange(max(1, round(w * s))) / s).astype(int).clip(0, w - 1)
    k = m[np.ix_(yy, xx)]
    t = np.zeros((n, n), bool)
    oy, ox = (n - k.shape[0]) // 2, (n - k.shape[1]) // 2
    t[oy:oy + k.shape[0], ox:ox + k.shape[1]] = k
    return t


def gorsel_maskesi(rgba) -> np.ndarray:
    return _sigdir(np.asarray(rgba)[:, :, 3] > 128)


def _projeksiyon(v: np.ndarray, az: float, el: float) -> np.ndarray:
    from scipy import ndimage

    a, e = np.radians(az), np.radians(el)
    ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    rx = np.array([[1, 0, 0], [0, np.cos(e), -np.sin(e)], [0, np.sin(e), np.cos(e)]])
    p = v @ (rx @ ry).T
    x, y = p[:, 0], -p[:, 1]
    x0, y0 = x.min(), y.min()
    olcek = 4 * IZGARA / max(x.max() - x0, y.max() - y0, 1e-9)
    ix, iy = ((x - x0) * olcek).astype(int), ((y - y0) * olcek).astype(int)
    g = np.zeros((iy.max() + 1, ix.max() + 1), bool)
    g[iy, ix] = True
    g = ndimage.binary_fill_holes(ndimage.binary_closing(g, iterations=3))
    return _sigdir(g)


def siluet_skoru(mesh, hedef: np.ndarray) -> dict:
    """Mesh'in (glTF, Y-yukarı) en iyi açıdan siluetinin hedef maskeyle IoU'su."""
    v = np.asarray(mesh.vertices)
    if len(v) > 150_000:
        v = v[np.random.default_rng(0).choice(len(v), 150_000, replace=False)]
    en_iyi = {"iou": 0.0, "az": 0, "el": 0}
    for el in (0, 10, 20, 30):
        for az in range(0, 360, 15):
            m = _projeksiyon(v, az, el)
            iou = float((m & hedef).sum() / max((m | hedef).sum(), 1))
            if iou > en_iyi["iou"]:
                en_iyi = {"iou": round(iou, 3), "az": az, "el": el}
    return en_iyi


def _asamali_gpu(pipe, torch) -> None:
    """Bileşenleri yalnızca kullanıldıkları aşamada GPU'ya alır (kütüphanenin cpu_offload'u bozuk).
    Sıra: conditioner (görsel kodlama) → model (difüzyon) → vae (mesh çözme)."""
    gpu = torch.device("cuda")
    pipe.device = gpu
    enc, lat, exp = pipe.encode_cond, pipe.prepare_latents, pipe._export

    def encode_cond(*a, **k):
        pipe.conditioner.to(gpu)
        try:
            return enc(*a, **k)
        finally:
            pipe.conditioner.to("cpu")
            torch.cuda.empty_cache()

    def prepare_latents(*a, **k):
        pipe.model.to(gpu)
        return lat(*a, **k)

    def _export(*a, **k):
        pipe.model.to("cpu")
        torch.cuda.empty_cache()
        pipe.vae.to(gpu)
        try:
            return exp(*a, **k)
        finally:
            pipe.vae.to("cpu")
            torch.cuda.empty_cache()

    pipe.encode_cond, pipe.prepare_latents, pipe._export = encode_cond, prepare_latents, _export


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gorsel", type=Path, help="konsept / ön görünüm")
    ap.add_argument("cikti", type=Path)
    ap.add_argument("--model", choices=MODELLER, default="mini")
    ap.add_argument("--sol", type=Path, help="mv: sol yan görünüm")
    ap.add_argument("--arka", type=Path, help="mv: arka görünüm")
    ap.add_argument("--siluet", type=Path, help="sadakat ölçümü için görsel (vars. ön görsel)")
    ap.add_argument("--yukseklik-mm", type=float, default=120.0, help="Z yüksekliği bu değere ölçeklenir")
    ap.add_argument("--adim", type=int, default=50, help="difüzyon adım sayısı")
    ap.add_argument("--octree", type=int, default=380, help="mesh çözünürlüğü (256 düşük VRAM, 380 detaylı)")
    ap.add_argument("--tohumlar", default="1234", help="virgülle; her biri denenir, en sadık olan seçilir")
    ap.add_argument("--tohum", type=int, help="(eski) tek tohum")
    ap.add_argument("--arkaplan-koru", action="store_true", help="rembg arka plan silmeyi atla")
    args = ap.parse_args()

    import torch
    import trimesh
    from PIL import Image

    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    args.cikti.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    rembg = None

    def hazirla(yol: Path, ad: str):
        nonlocal rembg
        g = Image.open(yol).convert("RGBA")
        if args.arkaplan_koru and np.asarray(g)[:, :, 3].min() < 255:
            return g
        if rembg is None:
            from hy3dgen.rembg import BackgroundRemover
            rembg = BackgroundRemover()
        g = rembg(g.convert("RGB"))
        g.save(args.cikti / f"girdi_{ad}.png")
        return g

    on = hazirla(args.gorsel, "arkaplansiz")
    if args.model == "mv":
        if not (args.sol and args.arka):
            ap.error("--model mv için --sol ve --arka gerekli")
        girdi = {"front": on, "left": hazirla(args.sol, "sol"), "back": hazirla(args.arka, "arka")}
    else:
        girdi = on
    hedef = gorsel_maskesi(hazirla(args.siluet, "siluet") if args.siluet else on)

    repo, alt = MODELLER[args.model]
    torch.cuda.reset_peak_memory_stats()
    # mv (1.1B) + VAE + DINO ≈5 GB; masaüstü 8 GB kartın ~2.7 GB'ını tutuyor → CPU'ya yükle, aşama aşama GPU'ya al.
    kw = {"variant": "fp16", "device": "cpu"} if args.model == "mv" else {}
    pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(repo, subfolder=alt, use_safetensors=True, **kw)
    if args.model == "mv":
        _asamali_gpu(pipe, torch)
    t_yukle = time.time()

    tohumlar = [args.tohum] if args.tohum is not None else [int(x) for x in args.tohumlar.split(",") if x.strip()]
    denemeler, en_iyi = [], None
    for tohum in tohumlar:
        t1 = time.time()
        mesh = pipe(image=girdi, num_inference_steps=args.adim, octree_resolution=args.octree,
                    num_chunks=8000, generator=torch.manual_seed(tohum), output_type="trimesh")[0]
        skor = siluet_skoru(mesh, hedef)
        denemeler.append({"tohum": tohum, **skor, "sure_sn": round(time.time() - t1, 1)})
        print(json.dumps(denemeler[-1]), flush=True)
        if en_iyi is None or skor["iou"] > en_iyi[1]["iou"]:
            en_iyi = (mesh, skor, tohum)
        torch.cuda.empty_cache()
    t_uret = time.time()
    vram_gb = torch.cuda.max_memory_allocated() / 1024**3
    mesh, skor, tohum = en_iyi

    mesh.export(args.cikti / "ham.glb")

    # Baskı hazırlığı: Y-yukarı (glTF) → Z-yukarı, ölçek, Z=0 tabana oturt, XY ortala.
    m = mesh.copy()
    m.apply_transform(trimesh.transformations.rotation_matrix(1.5707963267948966, [1, 0, 0]))
    yuk = float(m.extents[2])
    if yuk > 0:
        m.apply_scale(args.yukseklik_mm / yuk)
    b = m.bounds
    m.apply_translation([-(b[0][0] + b[1][0]) / 2, -(b[0][1] + b[1][1]) / 2, -b[0][2]])
    m.export(args.cikti / "ham.stl")

    rapor = {
        "model": args.model,
        "gorsel": str(args.gorsel),
        "gorusler": {k: str(v) for k, v in (("sol", args.sol), ("arka", args.arka)) if v},
        "sure_sn": {"yukleme": round(t_yukle - t0, 1), "uretim": round(t_uret - t_yukle, 1)},
        "vram_tepe_gb": round(vram_gb, 2),
        "ucgen": int(len(m.faces)),
        "su_gecirmez": bool(m.is_watertight),
        "boyut_mm": [round(float(x), 1) for x in m.extents],
        "siluet": {"secilen_tohum": tohum, **skor, "denemeler": denemeler},
        "parametreler": {"adim": args.adim, "octree": args.octree, "tohumlar": tohumlar},
    }
    (args.cikti / "rapor.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=2))
    print(json.dumps(rapor, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
