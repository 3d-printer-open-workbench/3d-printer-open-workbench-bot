"""COO botu yapılandırma ve çalışma alanı yolları."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Dizin düzeni (hepsi ortam değişkeniyle değiştirilebilir; bkz. .env.example):
#   WORKBENCH_ROOT/        depo kökü (varsayılan: bu paketin bir üstü)
#     coo/                 bot paketi
#     config/              orca kategorileri, rehberler, renk paleti, bakım planı
#     veri/                işletme verisi (git dışı)        -> WORKBENCH_DATA
#     ortamlar/            ek Python sanal ortamları (ops.)  -> WORKBENCH_ENVS
#     yz-araclari/         ComfyUI, Hunyuan3D-2, modeller   -> WORKBENCH_AI_TOOLS
PROGRAMLAR_KLASORU = Path(__file__).resolve().parents[1]  # `python -m coo` için PYTHONPATH/cwd
KOK = Path(os.environ.get("WORKBENCH_ROOT") or PROGRAMLAR_KLASORU).expanduser()
CALISMA_ALANI = KOK  # geriye uyum: kök

COO_KLASORU = Path(__file__).resolve().parent
ORTAMLAR_KLASORU = Path(os.environ.get("WORKBENCH_ENVS") or KOK / "ortamlar").expanduser()
VERI_KLASORU = Path(os.environ.get("WORKBENCH_DATA") or KOK / "veri").expanduser()
CONFIG_KLASORU = Path(os.environ.get("WORKBENCH_CONFIG") or KOK / "config").expanduser()
YZ_ARACLARI_KLASORU = Path(os.environ.get("WORKBENCH_AI_TOOLS") or KOK / "yz-araclari").expanduser()
COMFYUI_KLASORU = YZ_ARACLARI_KLASORU / "ComfyUI"
HUNYUAN_KLASORU = YZ_ARACLARI_KLASORU / "Hunyuan3D-2"
HF_HOME = YZ_ARACLARI_KLASORU / "modeller" / "huggingface"
ERP_DB_YOLU = Path(os.environ.get("WORKBENCH_ERP_DB") or VERI_KLASORU / "erp" / "workbench_erp.db").expanduser()

def _yz_gpu_sec() -> None:
    """Yapay zekâ işlerini (ComfyUI/Qwen, Hunyuan3D, Blender) birden çok GPU varsa en çok VRAM'li karta yönlendirir.

    Bu modülü içe aktaran bot ve onun başlattığı tüm alt süreçler (ComfyUI, ajanlar) bu ortamı devralır.
    Elle seçim: WORKBENCH_GPU=<nvidia-smi sırası>; CUDA_VISIBLE_DEVICES zaten verilmişse dokunulmaz.
    """
    if os.environ.get("CUDA_VISIBLE_DEVICES") is not None:
        return
    secim = os.environ.get("WORKBENCH_GPU")
    if secim is None:
        import subprocess

        try:
            cikti = subprocess.run(["nvidia-smi", "--query-gpu=index,pcie.link.width.current,pcie.link.gen.max,"
                                    "memory.total", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=10).stdout
            kartlar = [tuple(int(x) for x in s.split(",")) for s in cikti.strip().splitlines() if s.strip()]
        except Exception:
            return
        if len(kartlar) < 2:
            return
        # en çok VRAM; eşitse daha geniş hat
        secim = str(max(kartlar, key=lambda k: (k[3], k[1], k[2]))[0])
    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"  # nvidia-smi ile aynı sıra
    os.environ["CUDA_VISIBLE_DEVICES"] = secim


_yz_gpu_sec()

# Python ortamları
def _ortam_python(ad: str) -> Path:
    """Ayrı sanal ortam varsa onu, yoksa botun kendi yorumlayıcısını kullanır."""
    aday = ORTAMLAR_KLASORU / ad / "bin" / "python"
    return aday if aday.exists() else Path(sys.executable)


PY_AI3D = _ortam_python(".venv-ai3d")      # Hunyuan3D, trimesh, çok renk, renk ölçümü
PY_CAD = _ortam_python(".venv-cad")        # build123d, kalite kapısı
PY_GORSEL = _ortam_python(".venv-gorsel")  # Qwen stüdyo, Teknik Poster (PIL/numpy)

# İşletme verisi
ONAY_KLASORU = VERI_KLASORU / "00_Onay"
KONSEPT_ARGE_KLASORU = VERI_KLASORU / "01_Konsept_ve_ArGe"
B2C_ONERILER_KLASORU = KONSEPT_ARGE_KLASORU / "B2C_Oneriler"
HAMMADDE_KLASORU = KONSEPT_ARGE_KLASORU / "Hammadde_Arastirmalari"
URUNLER_KLASORU = VERI_KLASORU / "02_Urunler"
MAGAZA_KLASORU = VERI_KLASORU / "03_Magaza"
MUHASEBE_KLASORU = VERI_KLASORU / "04_Muhasebe_ve_Raporlar"
BASKI_KAYITLARI_KLASORU = MUHASEBE_KLASORU / "Baski_Kayitlari"
LOG_KLASORU = COO_KLASORU / "loglar"
DURUM_DOSYASI = COO_KLASORU / "yazici_durum.json"

# Model önbelleği tek yapıda: alt süreçler (Hunyuan3D, Qwen) bunu devralır.
os.environ.setdefault("HF_HOME", str(HF_HOME))

# OrcaSlicer yerel kullanıcı profil dizini (Flatpak ve yerel kurulum destekli)
ORCA_PROCESS_DIZINLERI = [
    Path.home() / ".var/app/com.orcaslicer.OrcaSlicer/config/OrcaSlicer/user/default/process",
    Path.home() / ".config/OrcaSlicer/user/default/process",
    URUNLER_KLASORU / "_sablon" / "uretim",
]

# 0 = üst süre sınırı yok (Patron /iptal veya "🛑 Görevi İptal Et" ile istediği an durdurabilir)
VARSAYILAN_CLAUDE_ZAMAN_ASIMI = 0


def _int_env(anahtar: str, varsayilan: int) -> int:
    ham = os.environ.get(anahtar, "").strip()
    if not ham:
        return varsayilan
    try:
        return int(ham)
    except ValueError:
        return varsayilan


def _env_dosyasi_yukle() -> None:
    """WORKBENCH_ENV_FILE, <kök>/.env veya coo/.env dosyasından ortam değişkenlerini yükler."""
    adaylar = [
        Path(os.environ["WORKBENCH_ENV_FILE"]).expanduser() if os.environ.get("WORKBENCH_ENV_FILE") else None,
        KOK / ".env",
        COO_KLASORU / ".env",
    ]
    for env_yolu in adaylar:
        try:
            if env_yolu is None or not env_yolu.exists():
                continue
            for satir in env_yolu.read_text(encoding="utf-8").splitlines():
                satir = satir.strip()
                if not satir or satir.startswith("#") or "=" not in satir:
                    continue
                anahtar, _, deger = satir.partition("=")
                anahtar = anahtar.strip()
                deger = deger.strip().strip('"').strip("'")
                if anahtar and anahtar not in os.environ:
                    os.environ[anahtar] = deger
        except Exception:
            continue


_env_dosyasi_yukle()  # .env değerleri modül sabitlerinden önce okunsun

# Mağaza kimliği (kullanıcıya görünen metinler, posterler, PDF teklifler)
MAGAZA_ADI = os.environ.get("WORKBENCH_SHOP_NAME") or "Open Workbench"
MAGAZA_URL = (os.environ.get("WORKBENCH_SHOP_URL") or "https://example.com").rstrip("/")
MAGAZA_ALAN_ADI = MAGAZA_URL.split("://", 1)[-1]
PINTEREST_PROFIL = os.environ.get("WORKBENCH_PINTEREST_URL") or ""

# İsteğe bağlı kardeş servisler (3d-printer-open-workbench-erp / -studio)
ERP_URL_VARSAYILAN = (os.environ.get("ERP_URL") or "http://127.0.0.1:8000").rstrip("/")
STUDIO_URL = (os.environ.get("STUDIO_URL") or "http://127.0.0.1:7870").rstrip("/")


@dataclass(frozen=True)
class CooAyar:
    telegram_bot_token: str
    telegram_chat_id: int
    erp_url: str
    printer_ip: str
    workspace: Path
    claude_zaman_asimi: int = VARSAYILAN_CLAUDE_ZAMAN_ASIMI


def ayarlari_yukle() -> CooAyar:
    _env_dosyasi_yukle()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_raw = os.environ.get("TELEGRAM_CHAT_ID", "0")
    try:
        chat_id = int(chat_raw)
    except ValueError:
        chat_id = 0
    zaman_asimi = _int_env("WORKBENCH_CLAUDE_ZAMAN_ASIMI", VARSAYILAN_CLAUDE_ZAMAN_ASIMI)
    if zaman_asimi > 0:
        zaman_asimi = max(60, zaman_asimi)
    return CooAyar(
        telegram_bot_token=token,
        telegram_chat_id=chat_id,
        erp_url=os.environ.get("ERP_URL", "http://127.0.0.1:8000").rstrip("/"),
        printer_ip=os.environ.get("PRINTER_IP", ""),
        workspace=CALISMA_ALANI,
        claude_zaman_asimi=zaman_asimi,
    )
