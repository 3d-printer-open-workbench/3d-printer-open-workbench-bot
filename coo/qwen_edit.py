"""Qwen-Image-Edit-2511 (Apache 2.0) ile görsel düzenleme — yerel ComfyUI sunucusu üzerinden.

Model: unsloth Qwen-Image-Edit-2511 Q4_K_M GGUF + lightx2v Lightning 4 adım LoRA + Qwen2.5-VL 7B fp8 metin
kodlayıcı (hepsi Apache 2.0). 8 GB GPU'da ComfyUI `--lowvram` ile modelin bir kısmı RAM'de tutulur.

Kullanım (sistem Python'u yeterli, yalnızca HTTP):
  python3 -m coo.qwen_edit --girdi urun.png --cikti out.png --istem "..." [--tohum 7] [--mp 1.0]
ComfyUI kapalıysa başlatır (`WORKBENCH_AI_TOOLS/ComfyUI`, port 8188) ve iş bitince açık bırakır.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .ayar import COMFYUI_KLASORU

COMFY = COMFYUI_KLASORU
ADRES = "http://127.0.0.1:8188"
MODEL = "qwen-image-edit-2511-Q4_K_M.gguf"
LORA = "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"
METIN = "qwen_2.5_vl_7b_fp8_scaled.safetensors"
VAE = "qwen_image_vae.safetensors"


def _istek(yol: str, veri: bytes | None = None, baslik: dict | None = None, zaman: float = 30) -> bytes:
    req = urllib.request.Request(ADRES + yol, data=veri, headers=baslik or {}, method="POST" if veri else "GET")
    with urllib.request.urlopen(req, timeout=zaman) as r:
        return r.read()


def sunucu_hazir() -> bool:
    try:
        _istek("/system_stats", zaman=3)
        return True
    except Exception:
        return False


def _oom_once_ben() -> None:
    """Bellek tükenirse çekirdek önce ComfyUI'yi öldürsün, masaüstünü değil (2026-11-17 oturum çöküşü)."""
    with contextlib.suppress(OSError):
        Path("/proc/self/oom_score_adj").write_text("1000")


def kuyruk_bos() -> bool:
    """ComfyUI'de çalışan ya da bekleyen iş yoksa True; sunucuya ulaşılamazsa False (açılıyor olabilir)."""
    try:
        k = json.loads(_istek("/queue", zaman=5))
    except Exception:
        return False
    return not k.get("queue_running") and not k.get("queue_pending")


def bosta_kapat_kontrol(durum: dict, simdi: float, esik: float = 600) -> bool:
    """Bekçi adımı: ComfyUI kuyruğu `esik` sn boyunca boşsa kapatır ve True döner. `durum` çağrılar arası saklanır."""
    if not comfy_pidleri():
        durum.clear()
        return False
    if not kuyruk_bos() or "son_is" not in durum:
        durum["son_is"] = simdi
        return False
    if simdi - durum["son_is"] >= esik:
        sunucu_kapat()
        durum.clear()
        return True
    return False


def sunucu_baslat(bekle: int = 180) -> None:
    if sunucu_hazir():
        return
    log = open(COMFY / "comfy_workbench.log", "ab")
    subprocess.Popen([str(COMFY / ".venv" / "bin" / "python"), "main.py", "--listen", "127.0.0.1", "--port", "8188",
                      "--lowvram", "--disable-auto-launch"], cwd=str(COMFY), stdout=log, stderr=log,
                     start_new_session=True, preexec_fn=_oom_once_ben)
    for _ in range(bekle):
        if sunucu_hazir():
            return
        time.sleep(1)
    raise RuntimeError("ComfyUI başlatılamadı")


def comfy_pidleri() -> list[int]:
    """Yalnız ComfyUI sunucusunun kendisi: argv[0] python, argv[1] main.py, '--port 8188' ve cwd ComfyUI klasörü.
    `pkill -f` KULLANMA: komut metni '... main.py --listen ... --port 8188' içeren başka süreçleri (ör. bu talimatı
    istem olarak alan Claude ajanı) de öldürüyordu (2026-11-17, e-ticaret denetimi çıkış 137)."""
    pidler = []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            argv = (d / "cmdline").read_bytes().split(b"\0")
            cwd = os.readlink(d / "cwd")
        except OSError:
            continue
        argv = [a.decode(errors="replace") for a in argv if a]
        if (len(argv) >= 2 and Path(argv[0]).name.startswith("python") and argv[1] == "main.py"
                and "8188" in argv and Path(cwd).resolve() == COMFY.resolve()):
            pidler.append(int(d.name))
    return pidler


def sunucu_kapat(bekle: float = 15) -> None:
    """ComfyUI'yi kapatır (≈20 GB RAM'i serbest bırakır); yalnız gerçek ComfyUI süreçlerine sinyal gönderir."""
    pidler = comfy_pidleri()
    for pid in pidler:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGTERM)
    son = time.monotonic() + bekle
    while pidler and time.monotonic() < son:
        pidler = [p for p in pidler if Path(f"/proc/{p}").exists()]
        time.sleep(0.5)
    for pid in pidler:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)


def gorsel_yukle(yol: Path) -> str:
    sinir = uuid.uuid4().hex
    govde = (f"--{sinir}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{yol.name}\"\r\n"
             "Content-Type: image/png\r\n\r\n").encode() + yol.read_bytes() + \
        f"\r\n--{sinir}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{sinir}--\r\n".encode()
    yanit = json.loads(_istek("/upload/image", govde, {"Content-Type": f"multipart/form-data; boundary={sinir}"}))
    return yanit["name"]


def workflow(girdi_adi: str, istem: str, tohum: int, mp: float, adim: int = 4) -> dict:
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": MODEL}},
        "2": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": LORA, "strength_model": 1.0}},
        "3": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["2", 0], "shift": 3.1}},
        "4": {"class_type": "CFGNorm", "inputs": {"model": ["3", 0], "strength": 1.0}},
        "5": {"class_type": "CLIPLoader", "inputs": {"clip_name": METIN, "type": "qwen_image"}},
        "6": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "7": {"class_type": "LoadImage", "inputs": {"image": girdi_adi}},
        "8": {"class_type": "ImageScaleToTotalPixels",
              "inputs": {"image": ["7", 0], "upscale_method": "lanczos", "megapixels": mp, "resolution_steps": 16}},
        "9": {"class_type": "TextEncodeQwenImageEditPlus",
              "inputs": {"clip": ["5", 0], "prompt": istem, "vae": ["6", 0], "image1": ["8", 0]}},
        "10": {"class_type": "TextEncodeQwenImageEditPlus",
               "inputs": {"clip": ["5", 0], "prompt": "", "vae": ["6", 0], "image1": ["8", 0]}},
        "11": {"class_type": "VAEEncode", "inputs": {"pixels": ["8", 0], "vae": ["6", 0]}},
        "12": {"class_type": "KSampler",
               "inputs": {"model": ["4", 0], "seed": tohum, "steps": adim, "cfg": 1.0, "sampler_name": "euler",
                          "scheduler": "simple", "positive": ["9", 0], "negative": ["10", 0],
                          "latent_image": ["11", 0], "denoise": 1.0}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["6", 0]}},
        "14": {"class_type": "SaveImage", "inputs": {"images": ["13", 0], "filename_prefix": "workbench_qwen"}},
    }


def duzenle(girdi: Path, cikti: Path, istem: str, tohum: int = 7, mp: float = 1.0, zaman_asimi: int = 1800,
            deneme: int = 2) -> dict:
    """ComfyUI başka bir iş tarafından kapatılırsa (bağlantı reddi) sunucuyu yeniden açıp bir kez daha dener."""
    import urllib.error

    son: dict = {}
    for _ in range(max(1, deneme)):
        try:
            return _duzenle(girdi, cikti, istem, tohum, mp, zaman_asimi)
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            son = {"basarili": False, "hata": f"ComfyUI bağlantısı koptu: {e}"}
            time.sleep(5)
    return son


def _duzenle(girdi: Path, cikti: Path, istem: str, tohum: int, mp: float, zaman_asimi: int) -> dict:
    sunucu_baslat()
    t0 = time.time()
    ad = gorsel_yukle(girdi)
    istemci = uuid.uuid4().hex
    yanit = json.loads(_istek("/prompt", json.dumps({"prompt": workflow(ad, istem, tohum, mp),
                                                       "client_id": istemci}).encode(),
                              {"Content-Type": "application/json"}))
    if yanit.get("node_errors"):
        return {"basarili": False, "hata": json.dumps(yanit["node_errors"], ensure_ascii=False)[:800]}
    pid = yanit["prompt_id"]
    while time.time() - t0 < zaman_asimi:
        gecmis = json.loads(_istek(f"/history/{pid}"))
        if pid in gecmis:
            kayit = gecmis[pid]
            durum = kayit.get("status", {})
            if durum.get("status_str") == "error":
                mesajlar = [m for m in durum.get("messages", []) if m[0] == "execution_error"]
                return {"basarili": False, "hata": json.dumps(mesajlar, ensure_ascii=False)[:1200]}
            for cikis in kayit.get("outputs", {}).values():
                for img in cikis.get("images", []):
                    q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img["subfolder"],
                                                "type": img["type"]})
                    cikti.parent.mkdir(parents=True, exist_ok=True)
                    cikti.write_bytes(_istek(f"/view?{q}", zaman=60))
                    return {"basarili": True, "cikti": str(cikti), "sure_sn": round(time.time() - t0, 1)}
        time.sleep(2)
    return {"basarili": False, "hata": f"zaman aşımı ({zaman_asimi} sn)"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kapat", action="store_true", help="yalnız ComfyUI sunucusunu kapat ve çık")
    ap.add_argument("--girdi", type=Path)
    ap.add_argument("--cikti", type=Path)
    ap.add_argument("--istem")
    ap.add_argument("--tohum", type=int, default=7)
    ap.add_argument("--mp", type=float, default=1.0)
    a = ap.parse_args()
    if a.kapat:
        sunucu_kapat()
        return
    if not (a.girdi and a.cikti and a.istem):
        ap.error("--girdi, --cikti ve --istem gerekli")
    print(json.dumps(duzenle(a.girdi, a.cikti, a.istem, a.tohum, a.mp), ensure_ascii=False))


if __name__ == "__main__":
    main()
