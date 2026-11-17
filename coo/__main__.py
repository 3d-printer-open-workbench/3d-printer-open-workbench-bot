"""Open Workbench 2. Katman COO — Telegram + Claude Opus 5.5 (CEO/CTO/CMO) + ERP + Yazıcı + Medya Orkestratörü.

Sıfır dış kütüphane bağımlılığıyla (doğrudan standart kütüphane urllib + asyncio ile)
Telegram Bot API, Claude Code CLI (CEO, CTO, CMO ve 18 alt ajan), Elegoo Centauri Carbon (SDCP v3)
ve Open Workbench ERP ile konuşur.

Çalıştırma:
    python3 -m coo
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import json
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from .ayar import (
    KOK,
    B2C_ONERILER_KLASORU,
    CALISMA_ALANI,
    CONFIG_KLASORU,
    HF_HOME,
    PROGRAMLAR_KLASORU,
    PY_AI3D,
    PY_CAD,
    PY_GORSEL,
    VERI_KLASORU,
    HAMMADDE_KLASORU,
    LOG_KLASORU,
    MAGAZA_ADI,
    STUDIO_URL,
    URUNLER_KLASORU,
    VARSAYILAN_CLAUDE_ZAMAN_ASIMI,
    ayarlari_yukle,
)
from .b2c_arge import (
    aday_butonlari,
    aday_durum_guncelle,
    aday_kart_metni,
    gorsel_yolunu_coz,
    katalog_gorseli_olustur,
    paket_id_temizle,
    paket_yukle,
    urun_iskelesi_kur,
)
from .erp_koprusu import ErpKoprusu
from .konsept_hatti import kaynak_fotograf, konsept_ciktilari, konsept_istemi, konsept_kaydet, konseptler
from .pazar_hatti import fiyat_coz, fiyat_onerisi, pazar_istemi, pazar_metni, pazar_oku, pazar_ozeti
from .fikir_hatti import (
    fikir_bilgisi,
    fikir_linkleri_ekle,
    flow_konsept_istemi,
    konsept_gorselleri_topla,
    konsept_yolu,
    linkten_referans,
    mesh_hatti,
    mesh_ozeti,
    onarim_istemi,
    referans_ayir,
    referans_yolu,
    referanslar,
    sku_uret,
    tarif_coz,
    urun_klasoru_hazirla,
    urun_yaml_guncelle,
)
from .kalite_kapisi import kalite_kapisi_calistir
from .kalite_kapisi import rapor_ozeti as kalite_rapor_ozeti
from .magaza_hatti import (
    hazirla_istemi,
    mevcut_gorseller,
    onizleme_metni,
    paket_oku,
    renk_varyantlari,
    yukle_istemi,
    yukleme_dogrula,
    yukleme_oku,
)
from . import cok_renk_hatti, eticaret_denetim, pinterest_hatti, qwen_edit, reels_takvim, studio_hatti
from .renk_paleti import (
    erpden_tohumla,
    kartela_gorseli,
    palet_oku,
    en_yakin,
    erp_eslesmesi,
    erp_filamentleri,
    erp_istek,
    palet_metni,
    palete_ekle,
    secim_istemi,
)
from .renk_hatti import (
    aciklamadan_renk_sku,
    renk_gorselleri_uret,
    urun_renklerini_kaydet,
    urun_renkleri,
)
from .urun_menusu import aktif_urunler, sonraki_butonlari as urun_sonraki_butonlari, urun_karti, urun_listesi_butonlari
from .icerik_hatti import (
    icerik_ozeti,
    kullanim_istemi,
    numune_fotograflari,
    numunesiz_kaynaklar,
    numune_kaydet_yolu,
    renk_hedefleri,
)
from .medya_editoru import tam_medya_paketi_uret, urun_yaml_kalite_guncelle, urun_yaml_oku
from .alim_hatti import aciklama_alim_mi, alim_istemi, alim_oku, dogrula as alim_dogrula
from .alim_hatti import ozet_metni as alim_ozet_metni, sonuc_metni as alim_sonuc_metni, uygula as alim_uygula
from .alim_hatti import ALIM_KLASORU, yeni_alim_klasoru
from .baski_goz import KONTROL_ARALIGI_SN as YZ_KONTROL_ARALIGI_SN, SESSIZ_SN as YZ_SESSIZ_SN
from .baski_goz import kaydet as yz_kaydet, kare_degerlendir as yz_kare_degerlendir, karar_ver as yz_karar_ver
from .baski_goz import ozet_satiri as yz_ozet_satiri
from .baski_rapor import bakim_durumu as rapor_bakim_durumu, bakim_metni as rapor_bakim_metni
from .baski_rapor import bakim_yapildi as rapor_bakim_yapildi, kare_secki as rapor_kare_secki
from .baski_rapor import onerileri_suz as rapor_onerileri_suz, rapor_kaydet, rapor_metni, rapor_oku, rapor_uret
from .baski_rapor import RAPOR_KLASORU, bekleyen_oneriler as rapor_bekleyen_oneriler
from .teklif_hatti import TEKLIF_KLASORU, denetim_istemi as teklif_denetim_istemi, fiyatla as teklif_fiyatla
from .teklif_hatti import kalem_dogrula as teklif_kalem_dogrula, katalog as teklif_katalog
from .teklif_hatti import ozet_metni as teklif_ozet_metni, pdf_html as teklif_pdf_html, pdf_uret as teklif_pdf_uret
from .teklif_hatti import teklif_istemi, teklif_oku, yeni_teklif_klasoru
from .kilavuz import kilavuz_bolumu, kilavuz_dizini
from .magaza_gorsel import hazirla as magaza_gorsel_hazirla
from .uretim_hatti import (
    baski_oncesi_kontrol,
    engel_var,
    fire_grami,
    kontrol_metni,
    kritik_katmanlar,
    riskli_z_listesi,
    tarti_cozumle,
    tarti_ozeti,
)
from .orca_dilim import IZINLI_AYARLAR, ORCA_BIN, baski_analizi, dilimle_3mf, kategori_guncelle, kategori_sec
from .orca_dilim import kategoriler as baski_kategorileri
from .urun_ozet import (
    portfoy_ozet_metni_ve_butonlari,
    tek_urun_ozet_metni,
    urun_asama_analiz_et,
)
from .yazici import (
    gcode_yukle,
    GcodeReferans,
    TimelapseToplayici,
    baski_durdur,
    durum_dosyasi_oku,
    durum_dosyasi_yaz,
    gcode_referans_coz,
    kamera_karesi_al,
    kayit_islendi_isaretle,
    tabla_bos_isaretle,
    yazici_durumu_oku,
)

LOG_KLASORU.mkdir(parents=True, exist_ok=True)
OTURUM_DOSYASI = LOG_KLASORU / "claude_oturumlari.json"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_KLASORU / "coo_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("workbench.coo")


def ekran_var() -> bool:
    """Chrome/Flow için masaüstü oturumu var mı. Bot oturum açılırken (DISPLAY/WAYLAND_DISPLAY içe aktarılmadan)
    başlarsa ortam boş kalıyordu ve Flow işleri 'ekran yok' diye reddediliyordu (2026-11-17); soketten tamamla."""
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return True
    bulundu = False
    if (Path(f"/run/user/{os.getuid()}") / "wayland-0").exists():
        os.environ.setdefault("WAYLAND_DISPLAY", "wayland-0")
        bulundu = True
    if Path("/tmp/.X11-unix/X0").exists():
        os.environ.setdefault("DISPLAY", ":0")
        bulundu = True
    return bulundu


# ============================================================================
# CLAUDE OPUS 5.5 (1. KATMAN CEO / CTO / CMO & 21 AJAN) KÖPRÜSÜ
# ============================================================================

AJAN_KATALOGU: dict[str, tuple[str, str]] = {
    "ceo-orchestrator": ("🎩 CEO (Baş Orkestratör)", "executive"),
    "cto-architect": ("🔧 CTO (Altyapı & Yazılım)", "executive"),
    "cmo-store-director": ("📢 CMO (Pazarlama & Mağaza)", "executive"),
    "trend-researcher": ("🔍 Ar-Ge Müdürü", "product"),
    "feedback-synthesizer": ("💬 Müşteri Geri Bildirim Analizcisi", "product"),
    "experiment-tracker": ("🧪 Deney Takipçisi", "product"),
    "cad-artist": ("🎨 Sanatçı (3B Tasarım)", "design"),
    "visual-storyteller": ("🖼️ Görsel Hikayeci (7 Kare Galeri)", "design"),
    "brand-guardian": ("🛡️ Marka & Kalite Bekçisi", "design"),
    "reels-tiktok-strategist": ("🎬 Reels & TikTok Stratejisti", "marketing"),
    "pinterest-curator": ("📌 Pinterest Küratörü", "marketing"),
    "seo-copywriter": ("✍️ E-Ticaret SEO Yazarı", "marketing"),
    "slicer-engineer": ("⚙️ Üretim & OrcaSlicer Mühendisi", "studio-operations"),
    "finance-tracker": ("📊 Muhasebe & BOM Uzmanı", "studio-operations"),
    "legal-compliance-checker": ("⚖️ Lisans & Telif Denetçisi", "studio-operations"),
    "support-responder": ("🤝 Müşteri & B2B Destek", "studio-operations"),
    "backend-architect": ("💻 ERP & Studio Geliştiricisi", "engineering"),
    "infrastructure-maintainer": ("🛠️ PC & Servis Bakım Uzmanı", "engineering"),
    "mesh-validator": ("📐 STL Mesh & Manifold Denetçisi", "testing"),
    "tool-evaluator": ("🔭 Yeni 3B/AI Araç Avcısı", "testing"),
    "workflow-optimizer": ("⚡ İş Akışı & Test Denetçisi", "testing"),
}

KISA_AJAN_ESLEME: dict[str, str] = {
    "ceo": "ceo-orchestrator",
    "cto": "cto-architect",
    "cmo": "cmo-store-director",
    "arge": "trend-researcher",
    "sanatci": "cad-artist",
    "gorsel": "visual-storyteller",
    "bekci": "brand-guardian",
    "reels": "reels-tiktok-strategist",
    "pinterest": "pinterest-curator",
    "seo": "seo-copywriter",
    "uretim": "slicer-engineer",
    "muhasebe": "finance-tracker",
    "lisans": "legal-compliance-checker",
    "destek": "support-responder",
    "bakim": "infrastructure-maintainer",
}


def _claude_ikili_yolu() -> str | None:
    adaylar = [
        Path.home() / ".local/bin/claude",
        Path("/usr/local/bin/claude"),
        Path("/usr/bin/claude"),
    ]
    for a in adaylar:
        if a.exists() and os.access(a, os.X_OK):
            return str(a)
    return shutil.which("claude")


def _claude_zaman_asimi_al(verilen: int | None = None) -> int:
    if verilen is not None:
        return verilen
    try:
        return int(ayarlari_yukle().claude_zaman_asimi)
    except Exception:
        return VARSAYILAN_CLAUDE_ZAMAN_ASIMI


def _hedef_ajan_coz(ajan_kodu: str) -> str:
    hedef_ajan = KISA_AJAN_ESLEME.get(ajan_kodu.lower(), ajan_kodu.lower())
    if hedef_ajan not in AJAN_KATALOGU:
        return "ceo-orchestrator"
    return hedef_ajan


# Ajan → model (Patron kararı 2026-11-16: verimli yapı, son söz Opus 5.5). `claude -p --agent` ana-oturum ajanında
# ajan dosyasındaki `model:` uygulanmadığı için model burada açıkça verilir. Sonnet çıktıları Patrona gitmeden
# önce `_opus_denetimli` ile Opus 5.5 tarafından denetlenir.
AJAN_MODELLERI: dict[str, str] = {
    "ceo-orchestrator": "opus", "cmo-store-director": "opus", "cto-architect": "opus", "cad-artist": "opus",
    "brand-guardian": "opus", "legal-compliance-checker": "opus", "backend-architect": "opus",
    "trend-researcher": "sonnet", "finance-tracker": "sonnet", "slicer-engineer": "sonnet",
    "infrastructure-maintainer": "sonnet", "seo-copywriter": "sonnet", "visual-storyteller": "sonnet",
    "pinterest-curator": "sonnet", "reels-tiktok-strategist": "sonnet", "support-responder": "sonnet",
    "feedback-synthesizer": "sonnet", "experiment-tracker": "sonnet", "tool-evaluator": "sonnet",
    "workflow-optimizer": "sonnet", "mesh-validator": "sonnet",
}


def _claude_komut_ve_ortam(
    claude_bin: str,
    hedef_ajan: str,
    istem: str,
    *,
    stream_json: bool = False,
    oturum_id: str | None = None,
    model: str | None = None,
) -> tuple[list[str], dict[str, str]]:
    env = os.environ.copy()
    env["PATH"] = f"{Path.home() / '.local/bin'}:{env.get('PATH', '/usr/bin:/bin')}"
    # Ajanlar kökten (CLAUDE.md + .claude/) çalışır; `python3 -m coo.…` her yerden bulunsun.
    env["PYTHONPATH"] = os.pathsep.join(x for x in (str(PROGRAMLAR_KLASORU), env.get("PYTHONPATH", "")) if x)
    env.setdefault("HF_HOME", str(HF_HOME))
    komut = [
        claude_bin,
        "-p",
        "--agent",
        hedef_ajan,
        "--permission-mode",
        os.environ.get("WORKBENCH_CLAUDE_PERMISSION_MODE") or "bypassPermissions",
    ]
    if stream_json:
        komut.extend(["--output-format", "stream-json", "--verbose"])
    if os.environ.get("WORKBENCH_CLAUDE_CHROME", "1") != "0" and ekran_var():
        komut.append("--chrome")
    if oturum_id:
        komut.extend(["--resume", oturum_id])
    model = model or AJAN_MODELLERI.get(hedef_ajan)  # görev bazlı model, yoksa ajanın modeli
    if model:
        komut.extend(["--model", model])
    komut.append(istem)
    return komut, env


def _claude_ciktisini_temizle(cikti: str) -> str:
    temiz_satirlar = [
        s for s in (cikti or "").splitlines() if not s.startswith("Permission deny rule (.claude/settings.json)")
    ]
    return "\n".join(temiz_satirlar).strip()


def _claude_hata_acikla(metin: str) -> str:
    temiz = (metin or "").strip()
    kucuk = temiz.lower()
    if "hit your 5-hour limit" in kucuk or ("rate limit" in kucuk and "resets" in kucuk):
        return (
            f"⏳ *Claude 5 Saatlik Kullanım Kotası Doldu*\n"
            f"• *Sistem yanıtı:* `{temiz}`\n"
            f"• *Ne yapabilirsiniz:* Sıfırlanma saatine kadar acil işleri buradaki Antigravity (Gemini) oturumundan devam ettirebilir, kota yenilenince Telegram'dan `/devam` yazarak tam kaldığı yerden sürdürebilirsiniz."
        )
    return temiz


def _sure_bicimle(saniye: float) -> str:
    sn_top = max(0, int(round(saniye)))
    if sn_top < 60:
        return f"{sn_top} sn"
    dk, sn = divmod(sn_top, 60)
    return f"{dk} dk {sn:02d} sn"


def _arac_ozeti_cikar(arac_adi: str, arac_girdisi: Any) -> str:
    kisa = arac_adi
    if arac_adi.startswith("mcp__"):
        parca = arac_adi.split("__")
        if len(parca) >= 3:
            kisa = f"{parca[1]}:{parca[2]}"
    if arac_adi == "Bash" and isinstance(arac_girdisi, dict):
        komut = str(arac_girdisi.get("command") or "").strip().splitlines()[0:1]
        ilk = komut[0][:34].strip() if komut else ""
        if ilk:
            return f"Bash ({ilk})"
    elif arac_adi in ("Write", "Edit", "Read") and isinstance(arac_girdisi, dict):
        yol = str(arac_girdisi.get("file_path") or "").strip()
        if yol:
            return f"{arac_adi} ({Path(yol).name})"
    return kisa[:42]


def _stream_json_satiri_isle(satir: str, durum: dict[str, Any]) -> None:
    temiz = satir.strip()
    if not temiz:
        return
    try:
        obj = json.loads(temiz)
    except Exception:
        if not temiz.startswith("Permission deny rule (.claude/settings.json)"):
            ham = durum.setdefault("ham_satirlar", [])
            ham.append(temiz)
        return
    if not isinstance(obj, dict):
        return

    sid = obj.get("session_id")
    if isinstance(sid, str) and sid:
        durum["session_id"] = sid

    tip = obj.get("type")
    if tip == "assistant":
        mesaj = obj.get("message") or {}
        icerik = mesaj.get("content")
        if isinstance(icerik, list):
            for parca in icerik:
                if not isinstance(parca, dict):
                    continue
                if parca.get("type") == "tool_use":
                    durum["arac_sayisi"] = int(durum.get("arac_sayisi", 0)) + 1
                    durum["son_arac"] = _arac_ozeti_cikar(str(parca.get("name") or "arac"), parca.get("input"))
                    durum["son_etkinlik"] = time.monotonic()
                elif parca.get("type") == "text":
                    metin = str(parca.get("text") or "").strip()
                    if metin:
                        durum["son_metin"] = metin
    elif tip == "result":
        durum["bitti"] = True
        durum["is_error"] = bool(obj.get("is_error"))
        durum["tur_sayisi"] = int(obj.get("num_turns") or 0)
        sonuc_metin = str(obj.get("result") or "").strip()
        if sonuc_metin:
            durum["sonuc"] = sonuc_metin


def claude_ajan_calistir(
    ajan_kodu: str,
    istem: str,
    zaman_asimi: int | None = None,
    oturum_id: str | None = None,
) -> tuple[bool, str]:
    """Claude Code CLI (-p --agent <ajan>) üzerinden 1. Katman veya 2. Katman ajanını çalıştırır."""
    claude_bin = _claude_ikili_yolu()
    if not claude_bin:
        return False, "Claude CLI (`~/.local/bin/claude`) bulunamadı."

    hedef_ajan = _hedef_ajan_coz(ajan_kodu)
    sinir = _claude_zaman_asimi_al(zaman_asimi)
    komut, env = _claude_komut_ve_ortam(claude_bin, hedef_ajan, istem, oturum_id=oturum_id)
    try:
        sonuc = subprocess.run(
            komut,
            cwd=str(CALISMA_ALANI),
            env=env,
            capture_output=True,
            text=True,
            timeout=sinir if sinir > 0 else None,
        )
        temiz_cikti = _claude_ciktisini_temizle(sonuc.stdout or "")
        hata = (sonuc.stderr or "").strip()
        if sonuc.returncode == 0 and temiz_cikti:
            return True, temiz_cikti
        return False, _claude_hata_acikla(temiz_cikti or hata or f"Claude çıkış kodu: {sonuc.returncode}")
    except subprocess.TimeoutExpired:
        return False, f"⏱️ `{hedef_ajan}` işlemi {_sure_bicimle(sinir)} sınırını aştı."
    except Exception as e:
        return False, f"Claude çalıştırma hatası: {e}"


async def _surec_durdur(proc: asyncio.subprocess.Process | None) -> None:
    if not proc or proc.returncode is not None:
        return
    try:
        proc.terminate()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(proc.wait(), timeout=3.0)
    except Exception:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass


async def claude_ajan_akisi_calistir(
    ajan_kodu: str,
    istem: str,
    zaman_asimi: int | None = None,
    oturum_id: str | None = None,
    gorev_kaydi: dict[str, Any] | None = None,
    ilerleme_cb: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ilerleme_araligi_sn: float = 15.0,
    model: str | None = None,
) -> tuple[bool, str, str | None]:
    """Claude CLI'yi akışlı (stream-json) ve bloklamadan çalıştırır; session_id döner."""
    claude_bin = _claude_ikili_yolu()
    if not claude_bin:
        return False, "Claude CLI (`~/.local/bin/claude`) bulunamadı.", oturum_id

    hedef_ajan = _hedef_ajan_coz(ajan_kodu)
    sinir = _claude_zaman_asimi_al(zaman_asimi)
    komut, env = _claude_komut_ve_ortam(
        claude_bin,
        hedef_ajan,
        istem,
        stream_json=True,
        oturum_id=oturum_id,
        model=model,
    )

    baslangic = time.monotonic()
    durum: dict[str, Any] = {
        "session_id": oturum_id or "",
        "arac_sayisi": 0,
        "son_arac": "",
        "son_metin": "",
        "sonuc": "",
        "ham_satirlar": [],
        "is_error": False,
        "bitti": False,
        "baslangic": baslangic,
        "son_etkinlik": baslangic,
    }

    proc: asyncio.subprocess.Process | None = None
    okuyucu: asyncio.Task[None] | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *komut,
            cwd=str(CALISMA_ALANI),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=16 * 1024 * 1024,
        )
        if gorev_kaydi is not None:
            gorev_kaydi["proc"] = proc

        async def _stdout_oku() -> None:
            assert proc is not None and proc.stdout is not None
            while True:
                satir_bytes = await proc.stdout.readline()
                if not satir_bytes:
                    break
                _stream_json_satiri_isle(satir_bytes.decode("utf-8", errors="replace"), durum)
                if gorev_kaydi is not None:
                    gorev_kaydi["session_id"] = durum.get("session_id") or ""
                    gorev_kaydi["arac_sayisi"] = durum.get("arac_sayisi", 0)
                    gorev_kaydi["son_arac"] = durum.get("son_arac", "")

        okuyucu = asyncio.create_task(_stdout_oku())
        son_bildirim = baslangic

        while not okuyucu.done():
            await asyncio.wait({okuyucu}, timeout=min(1.0, max(0.2, ilerleme_araligi_sn)))
            simdi = time.monotonic()
            gecen = simdi - baslangic
            if sinir > 0 and gecen >= sinir:
                await _surec_durdur(proc)
                okuyucu.cancel()
                sid = str(durum.get("session_id") or "").strip() or None
                adim = int(durum.get("arac_sayisi") or 0)
                return (
                    False,
                    f"⏱️ `{hedef_ajan}` {_sure_bicimle(sinir)} üst sınırına ulaştı ({adim} adım işlendi). "
                    f"Kaldığı yerden devam etmek için `/devam` yazabilir veya aşağıdaki butonu kullanabilirsiniz.",
                    sid,
                )
            if ilerleme_cb and (simdi - son_bildirim) >= ilerleme_araligi_sn and not okuyucu.done():
                son_bildirim = simdi
                durum["gecen_sn"] = gecen
                try:
                    await ilerleme_cb(durum)
                except Exception as exc:
                    log.debug("İlerleme güncelleme uyarısı: %s", exc)

        await okuyucu
        returncode = await proc.wait()
        stderr_metin = ""
        if proc.stderr is not None:
            stderr_bytes = await proc.stderr.read()
            stderr_metin = _claude_ciktisini_temizle(stderr_bytes.decode("utf-8", errors="replace"))

        sid = str(durum.get("session_id") or "").strip() or None
        yanit = _claude_ciktisini_temizle(
            str(durum.get("sonuc") or durum.get("son_metin") or "\n".join(durum.get("ham_satirlar") or []))
        )
        if returncode == 0 and not durum.get("is_error") and yanit:
            return True, yanit, sid
        ham_hata = yanit or stderr_metin or f"Claude çıkış kodu: {returncode}"
        return False, _claude_hata_acikla(ham_hata), sid

    except asyncio.CancelledError:
        await _surec_durdur(proc)
        if okuyucu and not okuyucu.done():
            okuyucu.cancel()
        raise
    except Exception as exc:
        await _surec_durdur(proc)
        sid = str(durum.get("session_id") or "").strip() or None
        return False, f"Claude akış hatası: {exc}", sid


class TelegramIstemci:
    """Standart kütüphane (urllib) tabanlı, sıfır bağımlılıklı Telegram Bot API istemcisi."""

    def __init__(self, token: str) -> None:
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.file_base_url = f"https://api.telegram.org/file/bot{token}"

    def _json_istek(self, metot: str, veri: dict[str, Any], zaman_asimi: float = 35.0) -> dict[str, Any]:
        url = f"{self.base_url}/{metot}"
        govde = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=govde,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=zaman_asimi) as r:
            return json.loads(r.read().decode("utf-8"))

    def _multipart_istek(
        self,
        metot: str,
        alanlar: dict[str, Any],
        dosya_alani: str,
        dosya_adi: str,
        dosya_verisi: bytes,
        zaman_asimi: float = 60.0,
    ) -> dict[str, Any]:
        sinir = f"----WorkbenchBoundary{uuid.uuid4().hex}"
        parcalar: list[bytes] = []

        for k, v in alanlar.items():
            if v is None:
                continue
            deger_str = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
            parcalar.append(
                (
                    f"--{sinir}\r\n"
                    f'Content-Disposition: form-data; name="{k}"\r\n\r\n'
                    f"{deger_str}\r\n"
                ).encode("utf-8")
            )

        mime = mimetypes.guess_type(dosya_adi)[0] or "application/octet-stream"
        parcalar.append(
            (
                f"--{sinir}\r\n"
                f'Content-Disposition: form-data; name="{dosya_alani}"; filename="{dosya_adi}"\r\n'
                f"Content-Type: {mime}\r\n\r\n"
            ).encode("utf-8")
        )
        parcalar.append(dosya_verisi)
        parcalar.append(f"\r\n--{sinir}--\r\n".encode("utf-8"))

        govde = b"".join(parcalar)
        req = urllib.request.Request(
            f"{self.base_url}/{metot}",
            data=govde,
            headers={"Content-Type": f"multipart/form-data; boundary={sinir}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=zaman_asimi) as r:
            return json.loads(r.read().decode("utf-8"))

    def _album_istek(self, chat_id: int, ogeler: list[tuple[Path, str]], zaman_asimi: float = 120.0) -> dict[str, Any]:
        """sendMediaGroup: 2–10 fotoğraf tek albümde (açıklama her karenin altında)."""
        sinir = f"----WorkbenchBoundary{uuid.uuid4().hex}"
        medya = [{"type": "photo", "media": f"attach://f{i}", "caption": a[:1000]} for i, (_, a) in enumerate(ogeler)]
        parcalar = [(f"--{sinir}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n").encode(),
                    (f"--{sinir}\r\nContent-Disposition: form-data; name=\"media\"\r\n\r\n"
                     f"{json.dumps(medya, ensure_ascii=False)}\r\n").encode("utf-8")]
        for i, (yol, _) in enumerate(ogeler):
            mime = mimetypes.guess_type(yol.name)[0] or "image/png"
            parcalar.append((f"--{sinir}\r\nContent-Disposition: form-data; name=\"f{i}\"; filename=\"{yol.name}\"\r\n"
                             f"Content-Type: {mime}\r\n\r\n").encode("utf-8"))
            parcalar.append(yol.read_bytes())
            parcalar.append(b"\r\n")
        parcalar.append(f"--{sinir}--\r\n".encode())
        req = urllib.request.Request(f"{self.base_url}/sendMediaGroup", data=b"".join(parcalar),
                                     headers={"Content-Type": f"multipart/form-data; boundary={sinir}"}, method="POST")
        with urllib.request.urlopen(req, timeout=zaman_asimi) as r:
            return json.loads(r.read().decode("utf-8"))

    async def album_gonder(self, chat_id: int, ogeler: list[tuple[Path, str]]) -> None:
        """Fotoğrafları 10'arlı albümlerle gönderir; tek kalan kare normal fotoğraf olarak gider."""
        for i in range(0, len(ogeler), 10):
            parca = ogeler[i:i + 10]
            if len(parca) == 1:
                await self.foto_gonder(chat_id, parca[0][0].read_bytes(), aciklama=parca[0][1], dosya_adi=parca[0][0].name)
            else:
                await asyncio.to_thread(self._album_istek, chat_id, parca)

    async def mesaj_gonder(
        self,
        chat_id: int,
        metin: str,
        butonlar: list[list[dict[str, str]]] | None = None,
    ) -> dict[str, Any]:
        # Telegram 4096 karakter sınırını aşarsa parçalara böl
        parcalar = [metin[i : i + 3900] for i in range(0, max(len(metin), 1), 3900)]
        son_yanit: dict[str, Any] = {}
        for idx, parca in enumerate(parcalar):
            veri: dict[str, Any] = {
                "chat_id": chat_id,
                "text": parca,
                "parse_mode": "Markdown",
            }
            if butonlar and idx == len(parcalar) - 1:
                veri["reply_markup"] = {"inline_keyboard": butonlar}
            try:
                son_yanit = await asyncio.to_thread(self._json_istek, "sendMessage", veri, 15.0)
            except Exception:
                veri.pop("parse_mode", None)
                son_yanit = await asyncio.to_thread(self._json_istek, "sendMessage", veri, 15.0)
        return son_yanit

    async def mesaj_duzenle(
        self,
        chat_id: int,
        message_id: int | None,
        metin: str,
        butonlar: list[list[dict[str, str]]] | None = None,
    ) -> bool:
        if not message_id:
            return False
        veri: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": metin[:3900],
            "parse_mode": "Markdown",
        }
        if butonlar is not None:
            veri["reply_markup"] = {"inline_keyboard": butonlar}
        try:
            await asyncio.to_thread(self._json_istek, "editMessageText", veri, 10.0)
            return True
        except Exception:
            veri.pop("parse_mode", None)
            try:
                await asyncio.to_thread(self._json_istek, "editMessageText", veri, 10.0)
                return True
            except Exception:
                return False

    async def klavye_temizle(self, chat_id: int, message_id: int | None) -> bool:
        """Hem metin hem fotoğraf mesajlarındaki inline butonları güvenle kaldırır."""
        if not message_id:
            return False
        veri: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": {"inline_keyboard": []},
        }
        try:
            await asyncio.to_thread(self._json_istek, "editMessageReplyMarkup", veri, 10.0)
            return True
        except Exception:
            return False

    def _medya_duzenle(self, chat_id: int, mesaj_id: int, yol: Path, aciklama: str,
                       butonlar: list[list[dict[str, str]]] | None = None) -> dict[str, Any]:
        """Gönderilmiş bir fotoğraf mesajının görselini + açıklamasını + butonlarını yerinde değiştirir."""
        alanlar: dict[str, Any] = {
            "chat_id": chat_id, "message_id": mesaj_id,
            "media": {"type": "photo", "media": "attach://foto", "caption": aciklama[:1000], "parse_mode": "Markdown"},
        }
        if butonlar:
            alanlar["reply_markup"] = {"inline_keyboard": butonlar}
        return self._multipart_istek("editMessageMedia", alanlar, "foto", yol.name, yol.read_bytes(), 30.0)

    async def foto_gonder(
        self,
        chat_id: int,
        foto_verisi: bytes,
        aciklama: str = "",
        butonlar: list[list[dict[str, str]]] | None = None,
        dosya_adi: str = "kamera.jpg",
    ) -> dict[str, Any]:
        alanlar: dict[str, Any] = {"chat_id": chat_id, "caption": aciklama[:1000], "parse_mode": "Markdown"}
        if butonlar:
            alanlar["reply_markup"] = {"inline_keyboard": butonlar}
        try:
            return await asyncio.to_thread(
                self._multipart_istek,
                "sendPhoto",
                alanlar,
                "photo",
                dosya_adi,
                foto_verisi,
                30.0,
            )
        except Exception:
            alanlar.pop("parse_mode", None)
            return await asyncio.to_thread(
                self._multipart_istek,
                "sendPhoto",
                alanlar,
                "photo",
                dosya_adi,
                foto_verisi,
                30.0,
            )

    async def belge_gonder(
        self,
        chat_id: int,
        yol: Path,
        aciklama: str = "",
        butonlar: list[list[dict[str, str]]] | None = None,
    ) -> dict[str, Any]:
        alanlar: dict[str, Any] = {"chat_id": chat_id, "caption": aciklama[:1000]}
        if butonlar:
            alanlar["reply_markup"] = {"inline_keyboard": butonlar}
        return await asyncio.to_thread(self._multipart_istek, "sendDocument", alanlar, "document", yol.name,
                                       yol.read_bytes(), 60.0)

    async def video_gonder(
        self,
        chat_id: int,
        video_yolu: Path,
        aciklama: str = "",
    ) -> dict[str, Any]:
        alanlar: dict[str, Any] = {"chat_id": chat_id, "caption": aciklama[:1000], "parse_mode": "Markdown"}
        veri = video_yolu.read_bytes()
        # yükleme hızı düşük olabilir: MB başına 20 sn, en az 120 sn (60 sn'lik sabit sınır 5 MB Reels'te düşüyordu)
        zaman = max(120.0, len(veri) / 1_000_000 * 20)
        return await asyncio.to_thread(
            self._multipart_istek,
            "sendVideo",
            alanlar,
            "video",
            video_yolu.name,
            veri,
            zaman,
        )

    async def callback_yanitla(self, callback_id: str, metin: str = "") -> None:
        veri: dict[str, Any] = {"callback_query_id": callback_id}
        if metin:
            veri["text"] = metin
        try:
            await asyncio.to_thread(self._json_istek, "answerCallbackQuery", veri, 10.0)
        except Exception:
            pass

    async def dosya_indir(self, file_id: str, hedef_yol: Path) -> bool:
        def _indir() -> bool:
            yanit = self._json_istek("getFile", {"file_id": file_id}, 15.0)
            file_path = (yanit.get("result") or {}).get("file_path")
            if not file_path:
                return False
            url = f"{self.file_base_url}/{file_path}"
            with urllib.request.urlopen(url, timeout=60.0) as r:
                hedef_yol.parent.mkdir(parents=True, exist_ok=True)
                hedef_yol.write_bytes(r.read())
            return True

        return await asyncio.to_thread(_indir)

    async def guncellemeleri_al(self, offset: int, timeout: int = 20) -> list[dict[str, Any]]:
        veri = {
            "offset": offset,
            "timeout": timeout,
            "allowed_updates": ["message", "callback_query"],
        }
        yanit = await asyncio.to_thread(self._json_istek, "getUpdates", veri, float(timeout + 15))
        return yanit.get("result") or []


class CooDurumBellegi:
    def __init__(self) -> None:
        self.bekleyen_baskilar: dict[str, GcodeReferans] = {}
        self.bekleyen_medyalar: dict[str, dict[str, Any]] = {}
        self.bekleyen_b2c_revize: tuple[str, int] | None = None
        self.aktif_muhatap_ajan: str = "ceo-orchestrator"
        self.son_yazici_durum_adi: str = ""
        self.aktif_baski_dosyasi: str = ""
        self.aktif_baski_baslangic_sn: int = 0
        self.timelapse = TimelapseToplayici()
        self.aktif_gorevler: dict[str, dict[str, Any]] = {}
        self.devam_oturumlari: dict[str, dict[str, str]] = {}
        self.son_oturum_anahtari: str = ""
        self.renk_bekleyen_sku: str | None = None  # renk örneği bekleniyor ("" = yalnız palet, sku = ürün)
        self.fikir_albumleri: dict[str, str] = {}  # Telegram media_group_id → referanslı fikir SKU'su
        self.numune_bekleyen_sku: str | None = None  # "📷 Numune Fotoğrafı" sonrası beklenen fotoğraf
        self.renk_secimleri: dict[str, dict[str, Any]] = {}  # sid -> {sku, renkler, secili}
        self.yerel_isler: dict[str, dict[str, Any]] = {}  # GPU/CPU ağır yerel işler (3B, Qwen, Blender, Orca)
        self.kartela: dict[str, set[int]] = {}  # sku -> paletten seçilen renk sıraları (en fazla 4)
        self.studio_bekleyen: dict[str, Any] | None = None  # Studio aracı seçildi, Patronun isteği bekleniyor
        self.cok_renk_not_sku: str | None = None
        self.cok_renk_zorunlu: dict[str, list[dict[str, Any]]] = {}  # sku -> Patronun karteladan seçtiği renkler  # "🔁 Başka şema" sonrası Patronun renk tercihi metni bekleniyor
        self.cok_renk_onceki: dict[str, list[str]] = {}  # sku -> beğenilmeyen şema adları
        self.baski_izleme: dict[str, Any] = {}
        self.alim_bekleniyor: bool = False  # "🧾 Fatura / Alım Gir" sonrası beklenen belge
        self.alim_albumleri: dict[str, Path] = {}  # media_group_id → alım klasörü (çok sayfalı fatura)  # aktif baskı: dosya, sku, plan, gonderilen, son_ilerleme


BELLEK = CooDurumBellegi()
ERP = ErpKoprusu()


def _oturumlari_yukle() -> None:
    if BELLEK.devam_oturumlari or not OTURUM_DOSYASI.exists():
        return
    try:
        veri = json.loads(OTURUM_DOSYASI.read_text(encoding="utf-8"))
        oturumlar = veri.get("oturumlar")
        if isinstance(oturumlar, dict):
            BELLEK.devam_oturumlari.update(oturumlar)
            BELLEK.son_oturum_anahtari = str(veri.get("son_anahtar") or "")
    except Exception:
        pass


def _oturum_kaydet(session_id: str | None, ajan: str, ozet: str = "") -> str | None:
    if not session_id:
        return None
    _oturumlari_yukle()
    mevcut_anahtar = next(
        (k for k, v in BELLEK.devam_oturumlari.items() if v.get("session_id") == session_id),
        None,
    )
    anahtar = mevcut_anahtar or uuid.uuid4().hex[:8]
    BELLEK.devam_oturumlari[anahtar] = {
        "session_id": session_id,
        "ajan": ajan,
        "ozet": ozet[:120],
        "tarih": dt.datetime.now().isoformat(timespec="seconds"),
    }
    BELLEK.son_oturum_anahtari = anahtar
    # En fazla son 25 oturumu sakla
    if len(BELLEK.devam_oturumlari) > 25:
        fazla = list(BELLEK.devam_oturumlari.keys())[:-25]
        for k in fazla:
            BELLEK.devam_oturumlari.pop(k, None)
    try:
        OTURUM_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
        OTURUM_DOSYASI.write_text(
            json.dumps(
                {
                    "son_anahtar": BELLEK.son_oturum_anahtari,
                    "oturumlar": BELLEK.devam_oturumlari,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass
    return anahtar


def _oturum_al(anahtar: str | None = None) -> tuple[str, dict[str, str]] | None:
    _oturumlari_yukle()
    hedef = anahtar or BELLEK.son_oturum_anahtari
    if not hedef or hedef not in BELLEK.devam_oturumlari:
        if BELLEK.devam_oturumlari:
            hedef = list(BELLEK.devam_oturumlari.keys())[-1]
        else:
            return None
    return hedef, BELLEK.devam_oturumlari[hedef]


def _ust_yonetim_butonlari() -> list[list[dict[str, str]]]:
    """Ana menü: iş akışına göre (fikir → ürün kartı → üretim/içerik/mağaza)."""
    return [
        [
            {"text": "🔎 Trend Araştır", "callback_data": "trend:baslat"},
            {"text": "💡 Yeni Fikir", "callback_data": "fikir:baslat"},
        ],
        [
            {"text": "📦 Ürünlerim", "callback_data": "menu:urunler"},
            {"text": "🛍️ Trend Vitrini", "callback_data": "b2c:vitrin"},
        ],
        [
            {"text": "🖨️ Yazıcı", "callback_data": "yazici:durum"},
            {"text": "📊 Hat Özeti", "callback_data": "urun:ozet_tumu"},
        ],
        [
            {"text": "🧾 Stok", "callback_data": "menu:stok"},
            {"text": "🗂️ Üretim Kuyruğu", "callback_data": "menu:kuyruk"},
        ],
        [
            {"text": "🎨 Renk Paleti", "callback_data": "renk:liste"},
            {"text": "📸 Renk Ekle", "callback_data": "renk:iste:"},
        ],
        [{"text": "🛠️ Studio Araçları (yazı, tabela, ışık, harita, atölye)", "callback_data": "studio:menu"}],
        [
            {"text": "⚙️ Görevler", "callback_data": "menu:gorevler"},
            {"text": "🤖 Ajanlarla Konuş", "callback_data": "menu:ajanlar"},
        ],
        [{"text": "💼 Teklif Hazırla", "callback_data": "teklif:baslat"},
         {"text": "📖 Kullanım Kılavuzu", "callback_data": "kilavuz:ana"}],
    ]


def _ajan_butonlari() -> list[list[dict[str, str]]]:
    return [
        [
            {"text": "🎩 CEO", "callback_data": "ajan:sec:ceo-orchestrator"},
            {"text": "🔧 CTO", "callback_data": "ajan:sec:cto-architect"},
            {"text": "📢 CMO", "callback_data": "ajan:sec:cmo-store-director"},
        ],
        [{"text": "🤖 Tüm Ajanlar", "callback_data": "ajan:liste"}, {"text": "🏠 Ana Menü", "callback_data": "menu:ana"}],
    ]


BOT_KOMUTLARI = [
    ("menu", "Ana menü"),
    ("trend", "Trend araştır: satan ürünler, fiyatlar, linkler"),
    ("reels", "Reels takvimi: trend fikirleri üret / takvimi aç"),
    ("fikir", "Yeni ürün fikri (metin / ekran görüntüsü / link)"),
    ("konsept", "Konsept kütüphanesi: görsel + Reels stilleri"),
    ("urunler", "Ürünlerim: her ürünün kartı ve işlemleri"),
    ("durum", "Yazıcı durumu ve kamera"),
    ("ozet", "Tüm hat özeti"),
    ("stok", "Filament ve malzeme stoku"),
    ("kuyruk", "Üretim kuyruğu"),
    ("gorevler", "Arka planda çalışan görevler"),
    ("iptal", "Çalışan görevi durdur"),
    ("teklif", "İşletmeye teklif: talep → model → ERP fiyatı → PDF"),
    ("bakim", "Makine bakım durumu ve 'yapıldı' kaydı"),
    ("oneriler", "Bekleyen (ertelenen) dilimleme önerileri"),
    ("kilavuz", "Kullanım kılavuzu: hangi buton ne yapar, ajanlar, maliyet"),
    ("yardim", "Komutlar ve akış"),
]


async def _komutlari_kaydet(tg: "TelegramIstemci") -> None:
    try:
        await asyncio.to_thread(
            tg._json_istek, "setMyCommands",
            {"commands": [{"command": k, "description": a} for k, a in BOT_KOMUTLARI]},
        )
    except Exception as exc:
        log.warning("Telegram komut listesi kaydedilemedi: %s", exc)


async def _urunler_menusu_gonder(tg: "TelegramIstemci", chat_id: int) -> None:
    butonlar = await asyncio.to_thread(urun_listesi_butonlari)
    adet = len(butonlar) - 1
    metin = (f"📦 *Ürünlerim* ({adet})\nBir ürüne dokun → aşamasını ve yapılabilecek işlemleri gör."
             if adet else "📦 Henüz ürün yok. *💡 Yeni Fikir* ile başla.")
    await tg.mesaj_gonder(chat_id, metin, butonlar=butonlar)


def _sonraki_adim_butonlari(sku: str) -> list[list[dict[str, str]]]:
    return urun_sonraki_butonlari(sku)


async def _urun_karti_gonder(tg: "TelegramIstemci", chat_id: int, sku: str) -> None:
    if not (URUNLER_KLASORU / sku).is_dir():
        await tg.mesaj_gonder(chat_id, f"❌ `{sku}` bulunamadı.")
        return
    calisan = [f"{k['ad']}" + (f" ({k.get('adim')})" if k["durum"] == "çalışıyor" and k.get("adim") else " — sırada")
               for k in BELLEK.yerel_isler.values() if k["sku"] == sku]
    calisan += [f"{k.get('unvan', k.get('ajan'))}: {k.get('ozet', '')}"[:80] for k in BELLEK.aktif_gorevler.values()
                if sku in str(k.get("ozet", ""))]
    metin, butonlar, kapak = await asyncio.to_thread(urun_karti, sku, None, calisan)
    if kapak:
        await tg.foto_gonder(chat_id, kapak.read_bytes(), aciklama=metin, butonlar=butonlar, dosya_adi=kapak.name)
    else:
        await tg.mesaj_gonder(chat_id, metin, butonlar=butonlar)


def _mevcut_skulari_listele() -> list[str]:
    if not URUNLER_KLASORU.exists():
        return []
    return [k.name for k in sorted(URUNLER_KLASORU.iterdir()) if k.is_dir() and not k.name.startswith("_")]


async def _urun_ozet_gonder(tg: TelegramIstemci, chat_id: int, sku: str = "") -> None:
    """Tüm portföyün veya tek bir SKU'nun güncel 6 aşamalı ürün özeti kartını gönderir."""
    try:
        erp_urunler = await ERP.urunler()
    except Exception:
        erp_urunler = []

    temiz_sku = sku.strip()
    if temiz_sku:
        metin, onizleme, butonlar = tek_urun_ozet_metni(
            temiz_sku,
            erp_urunler=erp_urunler,
            urunler_klasoru=URUNLER_KLASORU,
        )
        if onizleme and onizleme.is_file():
            try:
                foto_bytes = onizleme.read_bytes()
                if len(metin) <= 950:
                    await tg.foto_gonder(
                        chat_id,
                        foto_bytes,
                        aciklama=metin,
                        butonlar=butonlar,
                        dosya_adi=onizleme.name,
                    )
                    return
                await tg.foto_gonder(
                    chat_id,
                    foto_bytes,
                    aciklama=f"📸 `{temiz_sku}` önizleme",
                    dosya_adi=onizleme.name,
                )
            except Exception:
                pass
        await tg.mesaj_gonder(chat_id, metin, butonlar=butonlar)
        return

    try:
        son_paket = paket_yukle()
    except Exception:
        son_paket = None
    metin, butonlar = portfoy_ozet_metni_ve_butonlari(
        erp_urunler=erp_urunler,
        aktif_gorevler=BELLEK.aktif_gorevler,
        son_paket=son_paket,
        urunler_klasoru=URUNLER_KLASORU,
    )
    await tg.mesaj_gonder(chat_id, metin, butonlar=butonlar)


async def _medya_paketi_gonder(tg: TelegramIstemci, chat_id: int, sku: str, sonuc: Any, **_: Any) -> None:
    """Gerçek kaynaklı Reels kurgusunu gönderir (numuneden Flow/Veo, kullanıcı çekimi, timelapse)."""
    if sonuc.reels_mp4 and sonuc.reels_mp4.exists():
        await tg.video_gonder(chat_id, sonuc.reels_mp4, aciklama=f"🎬 *{sku}* — Reels & TikTok (`1080×1920`, gerçek kaynaklı)")
    else:
        await tg.mesaj_gonder(chat_id, f"ℹ️ `{sku}` için gerçek kaynak (numuneden Flow videosu, çekim, timelapse) yok; "
                                       "ürün tanıtım Reels'i Teknik Poster konseptinden üretilir.",
                              butonlar=[[{"text": "🎨 Teknik Poster Poster + Reels", "callback_data": f"konsept:liste:{sku}"}]])


async def _flow_uretimi_baslat(tg: TelegramIstemci, chat_id: int, sku: str, senaryo_notu: str = "") -> None:
    """Mutabık yöntem: kullanım/yaşam görseli YALNIZ gerçek numune fotoğrafından (Flow) — numune yoksa yönlendir."""
    temiz_sku = sku.strip()
    if not temiz_sku or not (URUNLER_KLASORU / temiz_sku).is_dir():
        await tg.mesaj_gonder(chat_id, f"❌ `{sku}` ürün klasörü bulunamadı.")
        return
    if await asyncio.to_thread(numune_fotograflari, temiz_sku):
        await _kullanim_uret(tg, chat_id, temiz_sku, senaryo_notu)
        return
    await tg.mesaj_gonder(
        chat_id, f"ℹ️ `{temiz_sku}` — kullanım görselleri yalnız *gerçek numune fotoğrafından* üretilir. Numune basılınca "
                 "fotoğrafını gönder; o zamana kadar stüdyo görselleri ve teknik poster kullanılır.",
        butonlar=[[{"text": "📷 Numune Fotoğrafı Gönder", "callback_data": f"numune:iste:{temiz_sku}"}],
                  [{"text": "🏡 Numunesiz Kullanım Görseli (stüdyo karesinden)", "callback_data": f"icerik:kullanimq:{temiz_sku}"}],
                  [{"text": "🛍️ E-ticaret Görselleri", "callback_data": f"icerik:studyo:{temiz_sku}"},
                   {"text": "🎨 Teknik Poster Poster + Reels", "callback_data": f"konsept:liste:{temiz_sku}"}]])


# --- /fikir hattı: Flow konsepti → Patron seçimi (Onay ①) → Hunyuan3D mesh → baskı hazırlığı ---
_GPU_KILIDI = asyncio.Lock()  # Hunyuan3D + Blender aynı 8 GB kartı paylaşır; mesh işleri sırayla.


def _yerel_is_metni(k: dict[str, Any]) -> str:
    if k["durum"] == "sırada":
        onde = [f"{x['ad']} (`{x['sku']}`)" for x in BELLEK.yerel_isler.values() if x["durum"] == "çalışıyor"]
        return (f"🕒 *Sırada:* {k['ad']} — `{k['sku']}`\nÖnce bitmesi gereken: {', '.join(onde) or 'başka bir iş'}\n"
                "_Başlayınca bu mesaj güncellenir._")
    gecen = _sure_bicimle(time.monotonic() - k["baslangic"])
    tahmin = f" (tahmini ~{k['tahmini_dk']} dk)" if k.get("tahmini_dk") else ""
    return (f"⏳ *Çalışıyor:* {k['ad']} — `{k['sku']}`\n• Adım: {k.get('adim') or '…'}\n• Geçen süre: {gecen}{tahmin}\n"
            "_Bu mesaj kendiliğinden güncellenir; bittiğinde haber vereceğim._")


@contextlib.asynccontextmanager
async def _yerel_is(tg: "TelegramIstemci", chat_id: int, sku: str, ad: str, tahmini_dk: int | None = None):
    """Ağır yerel işi GPU sırasına alır ve tek bir canlı durum mesajı tutar (sırada → çalışıyor → bitti).
    Kullanım: `async with _yerel_is(...) as k: k["adim"] = "…"` (to_thread'lere `lambda a: k.__setitem__("adim", a)`)."""
    iid = uuid.uuid4().hex[:6]
    k: dict[str, Any] = {"ad": ad, "sku": sku, "adim": "", "durum": "sırada", "baslangic": time.monotonic(),
                         "tahmini_dk": tahmini_dk}
    BELLEK.yerel_isler[iid] = k
    buton = [[{"text": "📦 Ürün Kartı", "callback_data": f"urunmenu:{sku}"}]]
    if not _GPU_KILIDI.locked():
        k["durum"] = "çalışıyor"
    ilk = await tg.mesaj_gonder(chat_id, _yerel_is_metni(k), butonlar=buton)
    mid = ((ilk or {}).get("result") or {}).get("message_id") if isinstance(ilk, dict) else None
    son_metin = ""

    async def _guncelle() -> None:
        nonlocal son_metin
        while True:
            await asyncio.sleep(15)
            m = _yerel_is_metni(k)
            if mid and m != son_metin:
                with contextlib.suppress(Exception):
                    await tg.mesaj_duzenle(chat_id, mid, m, butonlar=buton)
                son_metin = m

    gorev = asyncio.create_task(_guncelle())
    tamam = False
    try:
        async with _GPU_KILIDI:
            k["durum"], k["baslangic"] = "çalışıyor", time.monotonic()
            yield k
            tamam = True
    finally:
        gorev.cancel()
        BELLEK.yerel_isler.pop(iid, None)
        sure = _sure_bicimle(time.monotonic() - k["baslangic"])
        if mid:
            with contextlib.suppress(Exception):
                await tg.mesaj_duzenle(chat_id, mid, (f"✅ *Bitti:* {ad} — `{sku}` ({sure})" if tamam
                                                       else f"❌ *Yarıda kaldı:* {ad} — `{sku}` ({sure})"), butonlar=buton)


def _fikir_alt_butonlari(sku: str) -> list[list[dict[str, str]]]:
    return [[
        {"text": "🔁 Yeni konsept", "callback_data": f"fikir:yeni:{sku}"},
        {"text": "❌ İptal", "callback_data": f"fikir:iptal:{sku}"},
    ]]


async def _fikir_konsept_baslat(
    tg: TelegramIstemci, chat_id: int, sku: str, tarif: str, revize_notu: str = ""
) -> None:
    chrome_musait = os.environ.get("WORKBENCH_CLAUDE_CHROME", "1") != "0" and ekran_var()
    if not chrome_musait:
        await tg.mesaj_gonder(chat_id, "⚠️ Chrome ekran oturumu erişilebilir değil; Flow konsepti üretilemiyor.")
        return

    baslangic_epoch = time.time()
    refler = await asyncio.to_thread(referanslar, sku)
    linkler = list(((await asyncio.to_thread(fikir_bilgisi, sku)).get("linkler")) or [])
    istem = flow_konsept_istemi(sku, tarif, tarif_coz(tarif)["saksi"], revize_notu,
                                referans_gorseller=refler, linkler=linkler)

    async def _konsept_sonrasi(basarili: bool, yanit: str, devam_anahtari: str | None) -> None:
        yollar = await asyncio.to_thread(konsept_gorselleri_topla, sku, baslangic_epoch)
        if not yollar:
            butonlar = _fikir_alt_butonlari(sku) + _gorev_sonu_butonlari(devam_anahtari)
            await tg.mesaj_gonder(
                chat_id, f"⚠️ `{sku}` için konsept görseli gelmedi.\n\n{(yanit or '')[-800:]}", butonlar=butonlar
            )
            return
        await asyncio.to_thread(urun_yaml_guncelle, sku, {"durum": "KONSEPT_SECIMI"})
        await _konseptleri_gonder(tg, chat_id, sku, yollar)

    await tg.mesaj_gonder(
        chat_id,
        f"💡 *Fikir:* `{sku}`\n• _{tarif or 'referanstaki konsept'}_\n"
        + (f"• Referans: {len(refler)} görsel" + (f", {len(linkler)} link" if linkler else "") + "\n"
           if refler or linkler else "")
        + "• Google Flow'da en kaliteli modelle 4 konsept üretiliyor, en iyileri gelecek (kredi harcayabilir)…",
    )
    _ajan_arka_planda_calistir(
        tg,
        chat_id,
        "cmo-store-director",
        istem,
        gorev_ozeti=f"Flow konsept: {sku}",
        sonraki_islem=_konsept_sonrasi,
    )


TREND_ISTEM_BASLIGI = "🔎 Hangi alanda trend araştırayım?"
FIYAT_ISTEM_BASLIGI = "💰 Satış fiyatını yaz"
TEKLIF_ISTEM_BASLIGI = "💼 Teklif talebini yaz"
TEKLIF_REVIZE_BASLIGI = "✏️ Teklif revize notu"
TARTI_ISTEM_BASLIGI = "⚖️ Numuneyi tart, gramı yaz"


def _trend_istemi(konu: str, pid: str) -> str:
    return (
        f"Patron Telegram'dan '{konu}' konusu için TREND ARAŞTIRMASI istedi (canlı internet).\n"
        "Amaç: işletmemizin üretebileceği, ŞU AN SATAN B2C 3B baskı ürünlerini bulmak. Üretim hattımız: Flow konsept "
        "görseli → Hunyuan3D (organik formlar: figür, karakterli saksı, dekor objesi, vazo, abajur) → Elegoo Centauri "
        "Carbon (256 mm), tek renk mat PLA. İnce/mekanik/çok parçalı ürünler ve lisanslı karakterler UYGUN DEĞİL.\n"
        "1) WebSearch + WebFetch ile Türkiye (Trendyol, Hepsiburada, Etsy TR, Instagram mağazaları) ve global "
        "(Etsy, Pinterest, MakerWorld/Printables popüler) kaynaklarda 4-6 aday bul. Satış sinyali olanları seç: "
        "yorum/favori sayısı, 'çok satan' rozeti, Pinterest kaydetme, MakerWorld indirme.\n"
        "2) DOĞRULUK: Yalnızca açtığın sayfadaki fiyatı ve doğrudan ürün URL'sini yaz; grounding/redirect linki, "
        "tahmini fiyat YAZMA. Lisans: başkasının tasarımını kopyalamayacağız, konsept ilhamı alacağız — 'lisans' "
        "alanına 'İlham (özgün tasarım yapılacak)' veya model dosyası açık lisanslıysa lisans adını yaz.\n"
        "3) Her adayın ürün fotoğrafını `python3 -c \"from pathlib import Path; from coo.b2c_arge import "
        "gorsel_indir; gorsel_indir('<url>', Path('01_Konsept_ve_ArGe/B2C_Oneriler/gorseller/<sku>.jpg'))\"` ile indir.\n"
        f"4) Sonucu `01_Konsept_ve_ArGe/B2C_Oneriler/{pid}.json` dosyasına yaz (`paket_id`, `baslik`, `tarih`, "
        "`adaylar`: [{\"sku\", \"ad\", \"kategori\", \"ozet\" (neden satıyor + bizim farkımız ne olur), "
        "\"kaynak_url\", \"kaynak_platform\", \"rakip_fiyat\", \"satis_sinyali\", \"onerilen_satis_tl\", "
        "\"tahmini_gram\", \"tahmini_saat\", \"tahmini_kar_marji\", \"lisans\", \"cad_rotasi\": \"ai3d\", "
        "\"gorsel_yolu\", \"durum\": \"ONERILDI\"}]).\n"
        f"5) `python3 -m coo.b2c_arge katalog {pid}` komutunu çalıştır. Son satır: `TREND_HAZIR <aday sayısı>`."
    )


def _opus_denetim_istemi(gorev: str, dosyalar: list[str], kurallar: str) -> str:
    return (
        "Görev: SON KALİTE DENETİMİ (Claude Opus 5.5). Daha hızlı bir model (Sonnet) şu işi yaptı: " + gorev + "\n"
        f"Ürettiği dosyalar: {', '.join(f'`{d}`' for d in dosyalar)}\n\n"
        f"Denetim kuralları:\n{kurallar}\n\n"
        "Hatalı/uydurma/eksik kaydı DÜZELT (kaynağı kendin aç ve doğrula) ya da kaldır; doğruysa dokunma. Dosya "
        "şemasını değiştirme. Dosyaya `\"opus_denetim\": {\"sonuc\": \"ONAY|DUZELTILDI|RED\", \"notlar\": [...]}` ekle.\n"
        "Son satır: `DENETIM_ONAY`, `DENETIM_DUZELTILDI <özet>` veya `DENETIM_RED <neden>`."
    )


def _opus_denetimli(tg: TelegramIstemci, chat_id: int, gorev_ozeti: str, denetim_istemi: str,
                    sonraki: Callable[[bool, str, str | None], Awaitable[None]]
                    ) -> Callable[[bool, str, str | None], Awaitable[None]]:
    """Sonnet ajanının çıktısını Patrona gitmeden önce Opus 5.5'e denetletir, sonra asıl adımı çalıştırır."""
    async def _sonra(basarili: bool, yanit: str, devam: str | None) -> None:
        if not basarili:
            await sonraki(basarili, yanit, devam)
            return

        async def _denetim_sonrasi(b2: bool, y2: str, d2: str | None) -> None:
            son = " | ".join((y2 or "").strip().splitlines()[-3:])  # karar satırları (ör. KATEGORI_MEVCUT + DENETIM_*)
            await sonraki(basarili, f"{yanit}\n\n[Opus denetimi] {son[:400]}", devam)

        _ajan_arka_planda_calistir(tg, chat_id, "ceo-orchestrator", denetim_istemi,
                                   gorev_ozeti=f"Opus denetimi: {gorev_ozeti}", sonraki_islem=_denetim_sonrasi,
                                   model="opus")
    return _sonra


async def _trend_arastir(tg: TelegramIstemci, chat_id: int, konu: str) -> None:
    konu = konu.strip() or "çok satan 3D baskı ev dekoru, karakterli saksı ve hediyelik objeler"
    pid = paket_id_temizle(f"{dt.date.today().strftime('%m%d')}-{konu[:18]}")
    await tg.mesaj_gonder(
        chat_id,
        f"🔎 *Trend araştırması* başladı: _{konu}_\nTrendyol, Etsy, Pinterest ve MakerWorld'den satan ürünler, "
        "gerçek fiyatlar ve linkler toplanıyor (birkaç dakika)…",
    )

    async def _sonra(basarili: bool, yanit: str, devam_anahtari: str | None) -> None:
        if not paket_yukle(pid):
            await tg.mesaj_gonder(chat_id, f"⚠️ Trend araştırması tamamlanamadı:\n\n{(yanit or '')[-700:]}",
                                  butonlar=_gorev_sonu_butonlari(devam_anahtari))
            return
        await _b2c_vitrini_gonder(tg, chat_id, pid)

    denetim = _opus_denetim_istemi(
        f"trend araştırması ({konu})", [str(B2C_ONERILER_KLASORU / f"{pid}.json")],
        "- Her adayın URL'si gerçekten o ürün sayfası mı (en az 3 adayı aç); fiyat sayfada görünen fiyat mı?\n"
        "- Görsel o ürüne mi ait; lisans/ilham notu doğru mu? Tekrar eden veya alakasız adayı çıkar.")
    _ajan_arka_planda_calistir(tg, chat_id, "trend-researcher", _trend_istemi(konu, pid),
                               gorev_ozeti=f"Trend: {konu[:40]}",
                               sonraki_islem=_opus_denetimli(tg, chat_id, f"trend {konu[:30]}", denetim, _sonra))


async def _trendden_fikir(tg: TelegramIstemci, chat_id: int, pid: str, idx: int, ek_not: str = "") -> None:
    """Trend vitrinindeki adayı referans (fotoğraf + link) olarak yeni fikir hattına alır."""
    paket = paket_yukle(pid)
    adaylar = (paket or {}).get("adaylar") or []
    if not paket or not 0 <= idx < len(adaylar):
        await tg.mesaj_gonder(chat_id, "❌ Trend adayı bulunamadı.")
        return
    aday = adaylar[idx]
    tarif = str(aday.get("ad") or "trend ürün")
    if ek_not:
        tarif += f" — {ek_not}"
    url = str(aday.get("kaynak_url") or "")
    metin = tarif + (f" {url}" if url.startswith("http") else "")
    await asyncio.to_thread(aday_durum_guncelle, pid, idx, "FIKRE_ALINDI")
    await _yeni_fikir(tg, chat_id, metin, yerel_referans=gorsel_yolunu_coz(aday))


async def _pazar_arastir(tg: TelegramIstemci, chat_id: int, sku: str, sessiz: bool = False) -> None:
    """Benzer ürün fiyatlarını araştırır → pazar/fiyat.json → bant; paket varsa fiyat kararını yeniler."""
    if not sessiz:
        await tg.mesaj_gonder(chat_id, f"💹 `{sku}` için pazar fiyat araştırması başladı (benzer ürünler, gerçek fiyatlar)…")

    async def _sonra(basarili: bool, yanit: str, devam_anahtari: str | None) -> None:
        veri = await asyncio.to_thread(pazar_oku, sku)
        if not veri:
            await tg.mesaj_gonder(chat_id, f"⚠️ `{sku}` pazar araştırması tamamlanamadı.\n\n{(yanit or '')[-500:]}",
                                  butonlar=[[{"text": "💹 Tekrar Dene", "callback_data": f"pazar:arastir:{sku}"}]])
            return
        ozet = pazar_ozeti(veri)
        await asyncio.to_thread(urun_yaml_guncelle, sku, {"pazar": ozet})
        await tg.mesaj_gonder(chat_id, pazar_metni(sku, veri, ozet)[:3900],
                              butonlar=[[{"text": "📦 Ürün Kartı", "callback_data": f"urunmenu:{sku}"}]])
        paket, hatalar = await asyncio.to_thread(paket_oku, sku)
        if paket and not hatalar:
            await _fiyat_karari_uygula_ve_goster(tg, chat_id, sku, paket)

    denetim = _opus_denetim_istemi(
        f"`{sku}` pazar fiyat araştırması", [str(URUNLER_KLASORU / sku / "pazar" / "fiyat.json")],
        "- En az 3 örneğin URL'sini aç: fiyat sayfada aynen var mı, ürün gerçekten benzer mi (benzerlik puanı)?\n"
        "- Yabancı para çevrimi ve kur kaynağı doğru mu? Uydurma/grounding linkli örneği çıkar.")
    _ajan_arka_planda_calistir(tg, chat_id, "trend-researcher", pazar_istemi(sku),
                               gorev_ozeti=f"Pazar fiyatı: {sku}",
                               sonraki_islem=_opus_denetimli(tg, chat_id, f"pazar {sku}", denetim, _sonra))


def _paket_kaydet(sku: str, paket: dict[str, Any]) -> None:
    (URUNLER_KLASORU / sku / "magaza" / "paket.json").write_text(
        json.dumps(paket, ensure_ascii=False, indent=2), encoding="utf-8")


async def _fiyat_karari_uygula_ve_goster(
    tg: TelegramIstemci, chat_id: int, sku: str, paket: dict[str, Any], secilen_tl: float | None = None
) -> None:
    ozet = pazar_ozeti(await asyncio.to_thread(pazar_oku, sku))
    karar = fiyat_onerisi(paket.get("maliyet") or {}, ozet)
    if secilen_tl is not None:
        karar["secilen_tl"] = secilen_tl
        karar["secim"] = "PATRON"
    paket["satis_fiyati_tl"] = karar.get("secilen_tl") or karar["onerilen_tl"]
    paket["fiyat_karari"] = karar
    await asyncio.to_thread(_paket_kaydet, sku, paket)
    butonlar = [[{"text": f"{'✅ ' if s['tl'] == paket['satis_fiyati_tl'] else ''}{s['ad']} {s['tl']:.2f}",
                  "callback_data": f"magaza:fiyat:{sku}:{int(round(s['tl'] * 100))}"}
                 for s in karar["secenekler"]]]
    butonlar.append([{"text": "✏️ Elle Fiyat", "callback_data": f"magaza:elle:{sku}"}]
                    + ([] if ozet else [{"text": "💹 Pazar Araştır", "callback_data": f"pazar:arastir:{sku}"}]))
    butonlar.append([{"text": "🚀 Mağazaya Yükle", "callback_data": f"magaza:yukle:{sku}"},
                     {"text": "🔁 Yeniden Hazırla", "callback_data": f"magaza:hazirla:{sku}"}])
    await tg.mesaj_gonder(chat_id, onizleme_metni(paket), butonlar=butonlar)


FIKIR_ISTEM_BASLIGI = "💡 Ürün fikrini yaz"


async def _linkleri_referansa_al(tg: TelegramIstemci, chat_id: int, sku: str, linkler: list[str]) -> None:
    alinamayan = []
    for url in linkler:
        if not await asyncio.to_thread(linkten_referans, url, sku):
            alinamayan.append(url)
    if alinamayan:
        await tg.mesaj_gonder(
            chat_id,
            f"ℹ️ {len(alinamayan)} linkten ürün görseli otomatik alınamadı; Claude sayfayı Chrome'da açıp inceleyecek. "
            "Daha net sonuç için ürünün ekran görüntüsünü de gönderebilirsin (açıklama: `fikir`).",
        )


async def _yeni_fikir(
    tg: TelegramIstemci, chat_id: int, metin: str, dosya_id: str | None = None, album_id: str | None = None,
    yerel_referans: Path | None = None,
) -> None:
    """Metin (+ link) ve/veya ekran görüntüsünden yeni ürün fikri açar ve konsept üretimini başlatır."""
    tarif, linkler = referans_ayir(metin)
    sku = sku_uret(tarif or "referans konsept")
    await asyncio.to_thread(urun_klasoru_hazirla, sku, tarif or "referans konsept", None, linkler)
    if dosya_id:
        hedef = await asyncio.to_thread(referans_yolu, sku)
        if not await tg.dosya_indir(dosya_id, hedef):
            await tg.mesaj_gonder(chat_id, "❌ Referans görsel indirilemedi.")
            return
    if yerel_referans and yerel_referans.exists():
        hedef = await asyncio.to_thread(referans_yolu, sku, yerel_referans.suffix.lower() or ".jpg")
        await asyncio.to_thread(shutil.copy2, yerel_referans, hedef)
    await _linkleri_referansa_al(tg, chat_id, sku, linkler)
    if album_id:  # albümün diğer fotoğrafları birkaç saniye içinde gelir; sonra başlat
        BELLEK.fikir_albumleri[album_id] = sku

        async def _gecikmeli() -> None:
            await asyncio.sleep(5)
            BELLEK.fikir_albumleri.pop(album_id, None)
            await _fikir_konsept_baslat(tg, chat_id, sku, tarif)

        asyncio.create_task(_gecikmeli())
        return
    await _fikir_konsept_baslat(tg, chat_id, sku, tarif)


async def _fikir_istemi_gonder(tg: TelegramIstemci, chat_id: int) -> None:
    """Yanıt kutusu (force_reply) açar; Patronun bu mesaja yanıtı `/fikir <metin>` olarak işlenir."""
    await asyncio.to_thread(
        tg._json_istek,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": f"{FIKIR_ISTEM_BASLIGI} (yükseklik eklemek istersen sonuna örn. 140mm).\n"
                    "Örnek: kitap okuyan tombul kedi saksı 120mm\n\n"
                    "📎 Referans da verebilirsin: bu mesaja ekran görüntüsü ile yanıt ver (açıklamaya fikri yaz) "
                    "ya da metne link ekle. Aynı konsept, özgün tasarım üretilir.",
            "reply_markup": {"force_reply": True, "input_field_placeholder": "Ürün fikri…"},
        },
    )


async def _konseptleri_gonder(tg: "TelegramIstemci", chat_id: int, sku: str, yollar: list[Path]) -> None:
    for yol in yollar:
        m = re.match(r"flow-(\d+)", yol.stem)
        if not m:
            continue
        no = int(m.group(1))
        await tg.foto_gonder(
            chat_id,
            yol.read_bytes(),
            aciklama=f"🎨 `{sku}` — Konsept {no}",
            butonlar=[[{"text": f"✅ Konsept {no} ile 3B üret", "callback_data": f"fikir:sec:{sku}:{no}"}]],
            dosya_adi=yol.name,
        )
    await tg.mesaj_gonder(
        chat_id,
        f"🟢 *Onay ①* — `{sku}` için bir konsept seç.\n"
        f"Revize için: `/fikir {sku} revize: <ne değişsin>`",
        butonlar=_fikir_alt_butonlari(sku),
    )


async def _fikir_callback(tg: TelegramIstemci, chat_id: int, veri: str) -> None:
    if veri == "fikir:baslat":
        await _fikir_istemi_gonder(tg, chat_id)
        return
    parcalar = veri.split(":")
    eylem = parcalar[1] if len(parcalar) > 1 else ""
    sku = parcalar[2] if len(parcalar) > 2 else ""
    if not sku or not (URUNLER_KLASORU / sku).is_dir():
        await tg.mesaj_gonder(chat_id, f"❌ `{sku}` ürün klasörü bulunamadı.")
        return

    if eylem == "goster":
        yollar = sorted(p for p in (URUNLER_KLASORU / sku / "konsept").glob("flow-*")
                        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
        if not yollar:
            await tg.mesaj_gonder(chat_id, f"⚠️ `{sku}` için kayıtlı konsept görseli yok.")
            return
        await _konseptleri_gonder(tg, chat_id, sku, yollar)
        return

    if eylem == "yeni":
        bilgi = await asyncio.to_thread(fikir_bilgisi, sku)
        await _fikir_konsept_baslat(tg, chat_id, sku, bilgi["tarif"])
        return

    if eylem == "iptal":
        await asyncio.to_thread(urun_yaml_guncelle, sku, {"durum": "IPTAL"})
        await tg.mesaj_gonder(chat_id, f"🗑️ `{sku}` iptal edildi (dosyalar arşiv için duruyor).")
        return

    if eylem == "sec" and len(parcalar) > 3 and parcalar[3].isdigit():
        no = int(parcalar[3])
        if konsept_yolu(sku, no) is None:
            await tg.mesaj_gonder(chat_id, f"❌ `{sku}` konsept {no} dosyası yok.")
            return
        sira = " (GPU meşgul, sıraya alındı)" if _GPU_KILIDI.locked() else ""
        if not (URUNLER_KLASORU / sku / "pazar" / "fiyat.json").exists():
            await _pazar_arastir(tg, chat_id, sku, sessiz=True)
        await tg.mesaj_gonder(
            chat_id,
            f"⏳ `{sku}` — Konsept {no} → 3B model{sira}\n"
            "• Qwen ön/yan/arka görünüm → Hunyuan3D-2mv (3 tohum, konsepte en sadık olan) → düz taban/drenaj\n"
            "• Blender onarım: su geçirmezlik, ince et/hazne duvarı kalınlaştırma, kopuk parça → kalite kapısı (~20 dk)\n"
            "• Paralelde 💹 pazar fiyat araştırması (benzer ürünler) yapılıyor",
        )
        async with _yerel_is(tg, chat_id, sku, "3B model (Qwen görünüm → Hunyuan3D → Blender onarım)", 20) as k:
            sonuc = await asyncio.to_thread(mesh_hatti, sku, no, None, True, lambda a: k.__setitem__("adim", a))
        if not sonuc.get("basarili"):
            log_kuyrugu = str(sonuc.get("log") or "")[-700:]
            await tg.mesaj_gonder(
                chat_id,
                f"❌ `{sku}` 3B üretim hatası: {sonuc.get('hata')}\n```\n{log_kuyrugu}\n```",
                butonlar=_fikir_alt_butonlari(sku),
            )
            return
        butonlar = _sonraki_adim_butonlari(sku) + _fikir_alt_butonlari(sku)
        baslik = f"🧊 *{sku}* — basılabilir 3B model hazır\n"
        render = sonuc.get("render")
        if render:
            await tg.foto_gonder(
                chat_id, render.read_bytes(), aciklama=baslik + mesh_ozeti(sonuc), butonlar=butonlar,
                dosya_adi="studyo.png",
            )
        else:
            await tg.mesaj_gonder(chat_id, baslik + mesh_ozeti(sonuc), butonlar=butonlar)
        if sonuc.get("gorunus"):
            await tg.foto_gonder(chat_id, sonuc["gorunus"].read_bytes(),
                                 aciklama=f"🔄 `{sku}` — ön · sağ · arka · sol", dosya_adi="gorunus.png")
        if sonuc.get("sorunlar"):
            await _onarim_ajani(tg, chat_id, sku, sonuc["sorunlar"])
        return

    await tg.mesaj_gonder(chat_id, f"❓ Bilinmeyen fikir işlemi: `{veri}`")


async def _onarim_ajani(tg: TelegramIstemci, chat_id: int, sku: str, sorunlar: list[str]) -> None:
    """Otomatik Blender onarımının çözemediği sorunları 3B Onarım ajanına (cad-artist) verir; bitince
    yeniden ölçüp 4 yön görünümü gönderir."""
    async def _sonra(basarili: bool, yanit: str, devam_anahtari: str | None) -> None:
        stl = URUNLER_KLASORU / sku / "model" / f"{sku}.stl"
        kalite = await asyncio.to_thread(kalite_kapisi_calistir, stl, "b2c")
        gorunus = URUNLER_KLASORU / sku / "model" / "ai3d" / "gorunus.png"
        son = (yanit or "").strip().splitlines()[-1:] or [""]
        metin = (f"🛠️ `{sku}` onarım ajanı: `{son[0][:200]}`\n{kalite_rapor_ozeti(kalite)}")
        if gorunus.exists():
            await tg.foto_gonder(chat_id, gorunus.read_bytes(), aciklama=metin[:1000], dosya_adi="gorunus.png",
                                 butonlar=[[{"text": "⚙️ Dilimle → 3MF", "callback_data": f"orca:analiz:{sku}"}]])
        else:
            await tg.mesaj_gonder(chat_id, metin)

    await tg.mesaj_gonder(chat_id, f"🛠️ `{sku}` — otomatik onarım sonrası {len(sorunlar)} sorun kaldı; "
                                   "3B Onarım ajanı Blender'da düzeltiyor.")
    _ajan_arka_planda_calistir(tg, chat_id, "cad-artist", onarim_istemi(sku, sorunlar),
                               gorev_ozeti=f"{sku} Blender onarım", sonraki_islem=_sonra)


# --- Mağaza hattı: Hazırla (fire sor → ERP fiyat + SEO + paket.json) → Önizleme → Yükle (Chrome/İkas) ---
async def _magaza_callback(tg: TelegramIstemci, chat_id: int, veri: str) -> None:
    parcalar = veri.split(":")
    eylem = parcalar[1] if len(parcalar) > 1 else ""
    sku = parcalar[2] if len(parcalar) > 2 else ""
    kok = URUNLER_KLASORU / sku
    if not sku or not kok.is_dir():
        await tg.mesaj_gonder(chat_id, f"❌ `{sku}` ürün klasörü bulunamadı.")
        return

    if eylem == "hazirla":
        onay = str((await asyncio.to_thread(urun_yaml_oku, sku)).get("icerik_onayi") or "")
        if onay != "ONAYLANDI":
            await tg.mesaj_gonder(
                chat_id, f"🟡 `{sku}` içerikleri henüz onaylanmadı (Onay ②). Önce görselleri incele.",
                butonlar=[[{"text": "📋 Onaya Sun", "callback_data": f"icerik:sun:{sku}"},
                           {"text": "🛍️ E-ticaret Görselleri", "callback_data": f"icerik:studyo:{sku}"}]],
            )
            return
        if not (kok / "uretim" / f"{sku}.gcode").exists():
            await tg.mesaj_gonder(
                chat_id, f"⚠️ `{sku}` henüz dilimlenmedi; fiyat gerçek G-code'dan hesaplanır.",
                butonlar=[[{"text": "⚙️ Dilimle → 3MF", "callback_data": f"orca:analiz:{sku}"}]],
            )
            return
        await tg.mesaj_gonder(
            chat_id,
            f"🧮 `{sku}` için *fire oranı* (hatalı baskı payı) kaç olsun?",
            butonlar=[[{"text": f"%{n}", "callback_data": f"magaza:fire:{sku}:{n}"} for n in (5, 10, 15)]],
        )
        return

    if eylem == "fire" and len(parcalar) > 3 and parcalar[3].isdigit():
        fire = int(parcalar[3])
        (kok / "magaza").mkdir(exist_ok=True)
        eski = kok / "magaza" / "paket.json"
        if eski.exists():
            eski.unlink()

        async def _hazirla_sonrasi(basarili: bool, yanit: str, devam_anahtari: str | None) -> None:
            paket, hatalar = await asyncio.to_thread(paket_oku, sku)
            yeniden = [[{"text": "🔁 Yeniden Hazırla", "callback_data": f"magaza:hazirla:{sku}"}]]
            if hatalar or paket is None:
                await tg.mesaj_gonder(
                    chat_id,
                    f"⚠️ `{sku}` mağaza paketi tamamlanamadı:\n• " + "\n• ".join(hatalar)
                    + f"\n\n{(yanit or '')[-500:]}",
                    butonlar=yeniden + _gorev_sonu_butonlari(devam_anahtari),
                )
                return
            await asyncio.to_thread(urun_yaml_guncelle, sku, {"durum": "PATRON_ONAYINDA",
                                                             "magaza_paketi": "magaza/paket.json"})
            try:
                hg = await asyncio.to_thread(magaza_gorsel_hazirla, sku)
                kapak = kok / hg["gorseller"][0]["dosya"]
                await tg.mesaj_gonder(chat_id, f"🖼️ `{sku}` mağaza görselleri hazır: {len(hg['gorseller'])} galeri"
                                               + (f" + {sum(len(v['gorseller']) for v in hg['varyantlar'])} varyant"
                                                  if hg["varyantlar"] else "")
                                               + f" görseli, `{hg['kare_px']}×{hg['kare_px']}` kare JPG, alt metinli.")
            except Exception as exc:  # noqa: BLE001 — görsel hazırlığı paketi engellemesin
                log.warning("Mağaza görsel hazırlığı: %s", exc)
                kapak = kok / paket["gorseller"][0]
            await tg.foto_gonder(chat_id, kapak.read_bytes(), aciklama=f"🖼️ Kapak — `{sku}`", dosya_adi=kapak.name)
            await _fiyat_karari_uygula_ve_goster(tg, chat_id, sku, paket)

        _ajan_arka_planda_calistir(
            tg, chat_id, "cmo-store-director", hazirla_istemi(sku, fire),
            gorev_ozeti=f"Mağaza paketi: {sku}", sonraki_islem=_hazirla_sonrasi,
        )
        return

    if eylem == "fiyat" and len(parcalar) > 3 and parcalar[3].isdigit():
        paket, hatalar = await asyncio.to_thread(paket_oku, sku)
        if paket is None:
            await tg.mesaj_gonder(chat_id, "❌ Paket yok; önce Mağazaya Hazırla.")
            return
        await _fiyat_karari_uygula_ve_goster(tg, chat_id, sku, paket, secilen_tl=int(parcalar[3]) / 100)
        return

    if eylem == "elle":
        await asyncio.to_thread(
            tg._json_istek, "sendMessage",
            {"chat_id": chat_id, "text": f"{FIYAT_ISTEM_BASLIGI} [{sku}] (TL, kargo hariç; örn. 499,90)",
             "reply_markup": {"force_reply": True, "input_field_placeholder": "499,90"}},
        )
        return

    if eylem == "yukle":
        paket, hatalar = await asyncio.to_thread(paket_oku, sku)
        if hatalar or paket is None:
            await tg.mesaj_gonder(chat_id, "❌ Paket geçersiz, yüklenmedi:\n• " + "\n• ".join(hatalar))
            return
        onceki = await asyncio.to_thread(yukleme_oku, sku)
        if onceki and onceki.get("durum") == "YUKLENDI":
            await tg.mesaj_gonder(chat_id, f"ℹ️ `{sku}` zaten yüklü: {onceki.get('urun_linki')}")
            return

        async def _yukle_sonrasi(basarili: bool, yanit: str, devam_anahtari: str | None) -> None:
            kayit = await asyncio.to_thread(yukleme_oku, sku)
            if not kayit or kayit.get("durum") != "YUKLENDI":
                await tg.mesaj_gonder(
                    chat_id, f"⚠️ `{sku}` İkas'a yüklenemedi.\n\n{(yanit or '')[-700:]}",
                    butonlar=_gorev_sonu_butonlari(devam_anahtari),
                )
                return
            await asyncio.to_thread(urun_yaml_guncelle, sku, {"durum": "SATISTA", "ikas": kayit})
            ekran = kok / "magaza" / "ikas-ekran.png"
            metin = f"✅ *{sku}* İkas'ta yayında\n• {kayit.get('urun_linki')}\n• Panel: {kayit.get('panel_linki')}"
            dog = await asyncio.to_thread(yukleme_dogrula, sku)
            if dog.get("tamam"):
                sb = dog.get("sayfa") or {}
                metin += (f"\n🔎 *Doğrulama:* yayındaki sayfa paketle birebir — ad, fiyat `{min(sb.get('fiyatlar') or [0])} TL`, "
                          f"`{sb.get('gorsel')}` görsel, `{sb.get('teklif')}` seçenek")
            else:
                metin += "\n⚠️ *Doğrulama farkları:*\n" + "\n".join(f"• {x}" for x in dog.get("farklar") or [])
            if ekran.exists():
                await tg.foto_gonder(chat_id, ekran.read_bytes(), aciklama=metin, dosya_adi=ekran.name)
            else:
                await tg.mesaj_gonder(chat_id, metin)

        await tg.mesaj_gonder(chat_id, f"🚀 `{sku}` İkas'a yükleniyor (Chrome)…")
        _ajan_arka_planda_calistir(
            tg, chat_id, "cmo-store-director", yukle_istemi(sku),
            gorev_ozeti=f"İkas yükleme: {sku}", sonraki_islem=_yukle_sonrasi,
        )
        return

    await tg.mesaj_gonder(chat_id, f"❓ Bilinmeyen mağaza işlemi: `{veri}`")


# --- Renk hattı: ekran görüntüsü → aday bölgeler → YZ hangi bölge filament → piksel ölçümü → palet / ürün renkleri ---
def _renk_butonlari(sid: str) -> list[list[dict[str, str]]]:
    kayit = BELLEK.renk_secimleri.get(sid) or {}
    satirlar = []
    for i, r in enumerate(kayit.get("renkler") or []):
        isaret = "✅" if i in kayit.get("secili", set()) else "▫️"
        satirlar.append([{"text": f"{isaret} {i + 1}. {r['ad']} {r['hex']}", "callback_data": f"renk:sec:{sid}:{i}"}])
    alt = [{"text": "➕ Palete Ekle", "callback_data": f"renk:palet:{sid}"}]
    if kayit.get("sku"):
        alt.append({"text": "➕🎨 Palete Ekle + Ürün Görselleri", "callback_data": f"renk:uret:{sid}"})
    satirlar.append(alt)
    satirlar.append([{"text": "❌ Vazgeç", "callback_data": f"renk:iptal:{sid}"}])
    return satirlar


def _renk_klasoru(sku: str | None) -> Path:
    damga = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    if sku:
        return URUNLER_KLASORU / sku / "konsept" / f"renk-{damga}"
    return VERI_KLASORU / "01_Konsept_ve_ArGe" / "renk_ornekleri" / damga


async def _renk_ornegi_isle(tg: TelegramIstemci, chat_id: int, dosya_id: str, sku: str | None, not_: str = "") -> None:
    """Renk örneği (ekran görüntüsü/fotoğraf). Doğruluk: YZ yalnız hangi numaralı bölgenin filament olduğunu
    seçer; HEX bölgenin piksellerinden ölçülür (coo/renk_al.py). sku verilirse sonunda ürün renk görselleri."""
    if sku and not (URUNLER_KLASORU / sku / "model" / f"{sku}.stl").exists():
        await tg.mesaj_gonder(chat_id, f"⚠️ `{sku}` için 3B model henüz yok; renk yalnız palete eklenecek.")
        sku = None
    klasor = _renk_klasoru(sku)
    klasor.mkdir(parents=True, exist_ok=True)
    ornek = klasor / "ornek.jpg"
    if not await tg.dosya_indir(dosya_id, ornek):
        await tg.mesaj_gonder(chat_id, "❌ Fotoğraf indirilemedi.")
        return
    s = await asyncio.to_thread(
        subprocess.run, [str(PY_AI3D), "-m", "coo.renk_al", "adaylar", str(ornek), str(klasor)],
        cwd=str(PROGRAMLAR_KLASORU), capture_output=True, text=True, timeout=300,
    )
    if s.returncode != 0 or not (klasor / "isaretli.png").exists():
        await tg.mesaj_gonder(chat_id, f"❌ Görsel bölgelere ayrılamadı:\n```\n{(s.stderr or s.stdout)[-500:]}\n```")
        return
    filamentler = await asyncio.to_thread(erp_filamentleri, ayarlari_yukle().erp_url)

    async def _secimden_sonra(basarili: bool, _yanit: str, _oturum: str | None) -> None:
        secim_yolu = klasor / "secim.json"
        if not secim_yolu.exists():
            await tg.mesaj_gonder(chat_id, "❌ Renk bölgesi seçilemedi (ajan sonucu yazmadı). Örneği tekrar gönderin.")
            return
        secim = json.loads(secim_yolu.read_text(encoding="utf-8"))
        if not secim.get("renkler"):
            await tg.mesaj_gonder(chat_id, f"⚠️ Görselde filament/ürün rengi bulunamadı. {secim.get('neden', '')}")
            return
        o = await asyncio.to_thread(
            subprocess.run, [str(PY_AI3D), "-m", "coo.renk_al", "olc", str(ornek), str(klasor),
                             json.dumps(secim, ensure_ascii=False)],
            cwd=str(PROGRAMLAR_KLASORU), capture_output=True, text=True, timeout=300,
        )
        olcum_yolu = klasor / "olcum.json"
        if o.returncode != 0 or not olcum_yolu.exists():
            await tg.mesaj_gonder(chat_id, f"❌ Renk ölçülemedi:\n```\n{(o.stderr or o.stdout)[-500:]}\n```")
            return
        olcum = json.loads(olcum_yolu.read_text(encoding="utf-8"))
        renkler = [r for r in olcum["renkler"] if r.get("hex")]
        satirlar = []
        for i, r in enumerate(renkler, start=1):
            yakin, de = await asyncio.to_thread(en_yakin, r["hex"])
            erp = erp_eslesmesi(r, filamentler)
            if erp:
                r["erp_filament_id"] = erp["id"]
            ek = f" · paletteki en yakın: {yakin['ad']} `{yakin['hex']}` (ΔE {de})" if yakin else ""
            erp_ek = (f"\n   ERP: {erp.get('brand')} {erp.get('color_name')} — kayıtlı `{erp.get('color_hex')}`"
                      if erp else "")
            satirlar.append(f"{i}. *{r['ad']}* `{r['hex']}` — güven {r['guven']}{ek}{erp_ek}")
        sid = uuid.uuid4().hex[:6]
        BELLEK.renk_secimleri[sid] = {"sku": sku, "renkler": renkler, "secili": set(range(len(renkler))),
                                      "kaynak": str(ornek.relative_to(KOK)) if ornek.is_relative_to(KOK) else str(ornek)}
        await tg.foto_gonder(
            chat_id, Path(olcum["onizleme"]).read_bytes(),
            aciklama=(f"🎨 {secim.get('urun') or 'Renk örneği'} — ölçülen renkler (sol: görseldeki bölge, orta: "
                      "ölçülen renk)\n" + "\n".join(satirlar)
                      + "\n\n_HEX, seçilen bölgenin piksellerinden ölçüldü (parlama/gölge atıldı). Ekran ve "
                        "fotoğraf ışığı gerçek filamentten biraz farklı olabilir._")[:1020],
            butonlar=_renk_butonlari(sid), dosya_adi="renkler.png",
        )

    await tg.mesaj_gonder(chat_id, "🔎 Görseldeki filament/ürün bölgeleri belirleniyor (arayüz, kutu, gölge ayıklanıyor)…")
    _ajan_arka_planda_calistir(
        tg, chat_id, "visual-storyteller", secim_istemi(klasor, filamentler, not_), model="opus",
        gorev_ozeti="Renk örneği: filament bölgesini seç", sonraki_islem=_secimden_sonra,
    )


async def _renk_callback(tg: TelegramIstemci, chat_id: int, veri: str, mesaj: dict[str, Any]) -> None:
    parcalar = veri.split(":")
    eylem = parcalar[1] if len(parcalar) > 1 else ""

    if eylem == "iste":
        sku = parcalar[2] if len(parcalar) > 2 and parcalar[2] else None
        BELLEK.renk_bekleyen_sku = sku or ""
        await tg.mesaj_gonder(
            chat_id,
            "📸 Renk örneği gönder: filament ürün sayfasının ekran görüntüsü ya da filament/baskı fotoğrafı.\n"
            "Filamentin bulunduğu bölgeyi seçip rengini piksellerden ölçeceğim; site arayüzü ve gölgeler sayılmaz."
            + (f"\n_Sonra `{sku}` ürününün renk görsellerini de üretebilirim._" if sku else "")
            + "\n_Kısayol: fotoğraf açıklamasına `palet` (yalnız palet) ya da `renk <sku>` yaz._",
        )
        return
    if eylem == "liste":
        await tg.mesaj_gonder(chat_id, f"🎨 *Renk paleti*\n{palet_metni()}\n\n✅ ölçülmüş · ⚠️ tahmini (ekran görüntüsü gönder)",
                              butonlar=[[{"text": "📸 Renk Ekle", "callback_data": "renk:iste:"}]])
        return

    sid = parcalar[2] if len(parcalar) > 2 else ""
    kayit = BELLEK.renk_secimleri.get(sid)
    if not kayit:
        await tg.mesaj_gonder(chat_id, "⚠️ Bu renk seçimi süresi doldu (bot yeniden başlamış olabilir); örneği tekrar gönder.")
        return

    if eylem == "sec" and len(parcalar) > 3 and parcalar[3].isdigit():
        kayit["secili"] ^= {int(parcalar[3])}
        mesaj_id = mesaj.get("message_id")
        if mesaj_id:
            await asyncio.to_thread(
                tg._json_istek, "editMessageReplyMarkup",
                {"chat_id": chat_id, "message_id": mesaj_id, "reply_markup": {"inline_keyboard": _renk_butonlari(sid)}},
            )
        return
    if eylem == "iptal":
        BELLEK.renk_secimleri.pop(sid, None)
        await tg.mesaj_gonder(chat_id, "Renk örneği iptal edildi.")
        return

    if eylem == "erp" and len(parcalar) > 3 and parcalar[3].isdigit():
        r = kayit["renkler"][int(parcalar[3])]
        try:
            yanit = await asyncio.to_thread(erp_istek, "PATCH", f"/api/filaments/{r['erp_filament_id']}/renk",
                                            {"color_hex": r["hex"], "kaynak": kayit.get("kaynak")})
            await tg.mesaj_gonder(chat_id, f"✅ ERP güncellendi: *{r['ad']}* `{yanit.get('eski_hex')}` → `{r['hex']}`")
        except Exception as exc:
            await tg.mesaj_gonder(chat_id, f"❌ ERP güncellenemedi: {exc}")
        return

    if eylem in ("palet", "uret"):
        secilenler = [kayit["renkler"][i] for i in sorted(kayit["secili"])]
        if not secilenler:
            await tg.mesaj_gonder(chat_id, "⚠️ Önce en az bir renk seç.")
            return
        eklenen = [await asyncio.to_thread(palete_ekle, r, kayit.get("kaynak", "")) for r in secilenler]
        satir = "\n".join(f"• *{e['ad']}* `{e['hex']}`" + (f" (önceki `{e['eski_hex']}`)" if e.get("eski_hex") else "")
                          for e in eklenen)
        erp_butonlari = [
            [{"text": f"🔄 ERP'de {r['ad']} → {r['hex']}", "callback_data": f"renk:erp:{sid}:{kayit['renkler'].index(r)}"}]
            for r in secilenler if r.get("erp_filament_id")
        ]
        await tg.mesaj_gonder(chat_id, f"✅ Palete eklendi:\n{satir}" + (
            "\n\nBu renkler ERP'deki filamentlerle eşleşti; stok kaydındaki renk kodunu da düzelteyim mi?"
            if erp_butonlari else ""), butonlar=erp_butonlari or None)
        if eylem == "palet" or not kayit.get("sku"):
            return
        sku = kayit["sku"]
        adlar = ", ".join(f"{r['ad']} {r['hex']}" for r in secilenler)
        await tg.mesaj_gonder(chat_id, f"🎨 `{sku}` görselleri üretiliyor: {adlar} (renk başına ~1–2 dk)…")
        basarili: list[dict[str, Any]] = []
        for r in secilenler:
            async with _yerel_is(tg, chat_id, sku, f"Renk render'ı: {r['ad']}", 2) as k:
                k["adim"] = "Blender render"
                sonuc = await asyncio.to_thread(renk_gorselleri_uret, sku, r)
            if not sonuc.get("basarili"):
                await tg.mesaj_gonder(chat_id, f"❌ {r['ad']} {r['hex']}: {sonuc.get('hata')}")
                continue
            basarili.append(sonuc)
            onizleme = URUNLER_KLASORU / sku / sonuc["klasor"] / "studyo.png"
            if onizleme.exists():
                await tg.foto_gonder(chat_id, onizleme.read_bytes(), aciklama=f"🎨 `{sku}` — *{r['ad']}* `{r['hex']}`",
                                     dosya_adi=f"{sonuc['slug']}.png")
        if not basarili:
            return
        tum = await asyncio.to_thread(urun_renklerini_kaydet, sku, basarili)
        await tg.mesaj_gonder(
            chat_id,
            f"✅ `{sku}` renkleri kaydedildi ({len(tum)} renk: {', '.join(r['ad'] for r in tum)}).\n"
            "⚠️ Bu renklerde filamentin olduğundan emin ol — mağazada her renk ayrı varyant olarak açılır.",
            butonlar=[[{"text": "📸 Stüdyo Görselleri", "callback_data": f"icerik:studyo:{sku}"}],
                      [{"text": "🛒 Mağazaya Hazırla", "callback_data": f"magaza:hazirla:{sku}"},
                       {"text": "🎨 Başka Renk Ekle", "callback_data": f"renk:iste:{sku}"}]],
        )
        BELLEK.renk_secimleri.pop(sid, None)
        return

    await tg.mesaj_gonder(chat_id, f"❓ Bilinmeyen renk işlemi: `{veri}`")


# --- İçerik hattı: YZ boş sahne + Blender ürün → yaşam görselleri, Veo video, Reels/Pin/metin (numune gerekmez) ---
ICERIK_REVIZE_BASLIGI = "✏️ İçerik revize notu"


async def _icerik_onaya_sun(tg: TelegramIstemci, chat_id: int, sku: str) -> None:
    """Onay ②: e-ticaret galerisi (mağaza sırasıyla), Pinterest Pin ve Reels'i Patrona sunar."""
    kok = URUNLER_KLASORU / sku
    galeri = await asyncio.to_thread(mevcut_gorseller, sku)
    if not galeri:
        await tg.mesaj_gonder(chat_id, f"❌ `{sku}` için sunulacak görsel yok.")
        return
    await tg.mesaj_gonder(chat_id, f"📋 *ONAY — `{sku}` içerikleri* ({len(galeri)} e-ticaret görseli + Pin + Reels)")
    for i, rel in enumerate(galeri, start=1):
        yol = kok / rel
        await tg.foto_gonder(chat_id, yol.read_bytes(), aciklama=f"🛒 E-ticaret {i}/{len(galeri)} — `{rel}`",
                             dosya_adi=yol.name)
    varyantlar = await asyncio.to_thread(renk_varyantlari, sku)
    for v in varyantlar[1:]:  # ilk renk galeride; diğer renklerin İkas varyant görselleri
        for rel in v.get("gorseller") or []:
            yol = kok / rel
            await tg.foto_gonder(chat_id, yol.read_bytes(), aciklama=f"🎨 Varyant *{v['deger']}* — `{rel}`",
                                 dosya_adi=yol.name)
    for poster in sorted((kok / "gorsel" / "konsept").glob("*-3x4.png")):
        await tg.foto_gonder(chat_id, poster.read_bytes(), aciklama=f"🎨 Teknik Poster poster (galeri ölçü görseli + Pinterest) — "
                             f"`{poster.stem}`", dosya_adi=poster.name)
    gonderilemeyen = []
    videolar = [(v, f"🎬 Konsept Reels — `{v.stem}`") for v in sorted((kok / "medya").glob("konsept-*-reels.mp4"))]
    if (kok / "medya" / "reels-son.mp4").exists():
        videolar.append((kok / "medya" / "reels-son.mp4", "🎬 Reels / TikTok (9:16) — numune/çekim kaynaklı"))
    for video, aciklama in videolar:
        try:  # bir videonun yüklenememesi onay mesajını düşürmesin
            await tg.video_gonder(chat_id, video, aciklama=aciklama)
        except Exception as e:
            log.warning("Onay videosu gönderilemedi (%s): %s", video.name, e)
            gonderilemeyen.append(f"medya/{video.name}")
    ozet = await asyncio.to_thread(icerik_ozeti, sku)
    notlar = []
    if gonderilemeyen:
        notlar.append("⚠️ Telegram'a yüklenemedi (dosya klasörde hazır): " + ", ".join(f"`{g}`" for g in gonderilemeyen))
    if ozet.get("eski"):
        notlar.append("⛔ Geçerli renk modelinden ESKİ içerik (ürünün eski rengini gösterir, yeniden üretilmeli): "
                      + ", ".join(f"`{g}`" for g in ozet["eski"]))
    if ozet["video_red"]:
        notlar.append("⚠️ Numuneden Veo videosu ürünü değiştirdiği için reddedildi.")
    if not list((kok / "gorsel" / "konsept").glob("*-3x4.png")):
        notlar.append("⚠️ Teknik Poster poster yok — galeride ölçü/malzeme görseli ve Pinterest Pin eksik (adım 6).")
    if not ozet["kullanim"]:
        notlar.append("ℹ️ Kullanım görseli yok (numune basılınca eklenir).")
    await asyncio.to_thread(urun_yaml_guncelle, sku, {"icerik_onayi": "BEKLIYOR"})
    await tg.mesaj_gonder(
        chat_id,
        f"🟡 *Onay ②* — `{sku}` görsellerinin kalitesini değerlendir.\n"
        "_Stüdyo kareleri basılacak 3B modelin render'ından Qwen ile çekildi (geometri/renk denetimli); ölçü ve "
        "malzeme teknik posternde gerçek veriden basıldı._\n" + "\n".join(notlar),
        butonlar=[
            [{"text": "✅ Onayla", "callback_data": f"icerik:onay:{sku}"},
             {"text": "✏️ Not ile Revize", "callback_data": f"icerik:revize:{sku}"}],
            [{"text": "🔁 E-ticaret Görsellerini Yenile", "callback_data": f"icerik:yenile:{sku}"},
             {"text": "❌ Reddet", "callback_data": f"icerik:red:{sku}"}],
        ],
    )


async def _icerik_callback(tg: TelegramIstemci, chat_id: int, veri: str) -> None:
    parcalar = veri.split(":", 2)
    eylem, sku = (parcalar[1], parcalar[2]) if len(parcalar) == 3 else ("", "")
    if not sku or not (URUNLER_KLASORU / sku).is_dir():
        await tg.mesaj_gonder(chat_id, f"❌ `{sku}` ürün klasörü bulunamadı.")
        return
    if eylem == "uret":  # geriye dönük: numune varsa kullanım (Flow), yoksa stüdyo
        if await asyncio.to_thread(numune_fotograflari, sku):
            await _kullanim_uret(tg, chat_id, sku)
        else:
            await _studyo_uret(tg, chat_id, sku)
    elif eylem == "studyo":
        await _studyo_uret(tg, chat_id, sku)
    elif eylem == "yenile":
        await _studyo_uret(tg, chat_id, sku, tohum_degistir=True)
    elif eylem == "kullanim":
        await _kullanim_uret(tg, chat_id, sku)
    elif eylem == "kullanimq":
        await _kullanim_uret(tg, chat_id, sku, numunesiz=True)
    elif eylem == "sun":
        await _icerik_onaya_sun(tg, chat_id, sku)
    elif eylem == "onay":
        await asyncio.to_thread(urun_yaml_guncelle, sku, {"icerik_onayi": "ONAYLANDI"})
        await tg.mesaj_gonder(chat_id, f"✅ `{sku}` görselleri onaylandı.", butonlar=_sonraki_adim_butonlari(sku))
    elif eylem == "red":
        await asyncio.to_thread(urun_yaml_guncelle, sku, {"icerik_onayi": "REDDEDILDI"})
        await tg.mesaj_gonder(chat_id, f"❌ `{sku}` içerikleri reddedildi. Yeniden üretmek için:",
                              butonlar=[[{"text": "🔁 E-ticaret Görsellerini Yenile", "callback_data": f"icerik:yenile:{sku}"}]])
    elif eylem == "revize":
        await asyncio.to_thread(
            tg._json_istek, "sendMessage",
            {"chat_id": chat_id, "text": f"{ICERIK_REVIZE_BASLIGI} [{sku}]: ne değişsin? "
                                         "(ör. 'sahne daha aydınlık, pencere önü, ürün daha büyük')",
             "reply_markup": {"force_reply": True, "input_field_placeholder": "Revize notu…"}},
        )
    else:
        await tg.mesaj_gonder(chat_id, f"❓ Bilinmeyen içerik işlemi: `{veri}`")


AI3D_PY = PY_AI3D
KONSEPT_ISTEM_BASLIGI = "🎨 Yeni konsept istemi"


async def _konsept_uret(tg: TelegramIstemci, chat_id: int, sku: str, konsept: dict) -> None:
    """Flow (Chrome) ile konsept görsel (3:4 + 9:16) ve Veo Reels; sonuçlar Telegram'a."""
    if not ekran_var():
        await tg.mesaj_gonder(chat_id, "⚠️ Chrome ekran oturumu yok; Flow çalıştırılamıyor.")
        return
    if not await asyncio.to_thread(kaynak_fotograf, sku):
        await tg.mesaj_gonder(chat_id, f"⚠️ `{sku}` için konsepte girecek ürün görseli yok — önce *5. E-ticaret görselleri* "
                                       "(Qwen) üretilmeli; poster ürünün gerçek görselinden yapılır.",
                              butonlar=[[{"text": "🛍️ E-ticaret Görselleri", "callback_data": f"icerik:studyo:{sku}"}]])
        return
    await tg.mesaj_gonder(chat_id, f"🎨 `{sku}` — *{konsept['baslik']}* konsepti Flow'da üretiliyor "
                                   "(3:4 poster + 9:16 + Reels, ~10 dk, kredi harcar)…")

    async def _sonra(basarili: bool, yanit: str, devam_anahtari: str | None) -> None:
        c = await asyncio.to_thread(konsept_ciktilari, sku, konsept["ad"])
        if not c["poster"] and not c["dikey"]:
            await tg.mesaj_gonder(chat_id, f"⚠️ Konsept görseli gelmedi.\n\n{(yanit or '')[-600:]}",
                                  butonlar=_gorev_sonu_butonlari(devam_anahtari))
            return
        for anahtar, etiket in (("poster", "3:4 poster (galeri / Pinterest)"), ("dikey", "9:16 (Reels / Story)")):
            if c[anahtar]:
                await tg.foto_gonder(chat_id, c[anahtar].read_bytes(), dosya_adi=c[anahtar].name,
                                     aciklama=f"🎨 {konsept['baslik']} — {etiket}")
        if c["reels"]:
            await tg.video_gonder(chat_id, c["reels"], aciklama=f"🎬 {konsept['baslik']} — Reels")
        son = (yanit or "").strip().splitlines()[-1:] or [""]
        await tg.mesaj_gonder(
            chat_id, f"✅ Konsept hazır. `{son[0][:200]}`",
            butonlar=[[{"text": "🔁 Tekrar Üret", "callback_data": f"konsept:liste:{sku}"},
                       {"text": "📋 Onaya Sun", "callback_data": f"icerik:sun:{sku}"}],
                      [{"text": "📦 Ürün Kartı", "callback_data": f"urunmenu:{sku}"}]])

    _ajan_arka_planda_calistir(tg, chat_id, "cmo-store-director", konsept_istemi(sku, konsept),
                               gorev_ozeti=f"Konsept {konsept['ad']}: {sku}", sonraki_islem=_sonra)


async def _studyo_uret(tg: TelegramIstemci, chat_id: int, sku: str, tohum_degistir: bool = False) -> None:
    """E-ticaret stüdyo görselleri: her renk için kapak-beyaz / krem-fon / koyu-fon (Qwen-Image-Edit) +
    ≥2 renkte vitrin karesi (renkler-birlikte)."""
    renkler = await asyncio.to_thread(urun_renkleri, sku)
    if not await asyncio.to_thread(renk_hedefleri, sku):
        await tg.mesaj_gonder(chat_id, f"⚠️ `{sku}` için önce renk kararı gerekli (görseller o renkte çekilir).")
        await _kartela_ac(tg, chat_id, sku)
        return
    tohum = str(int(time.time()) % 100000) if tohum_degistir else "7"
    vitrin = len(renkler) >= 2
    await tg.mesaj_gonder(
        chat_id,
        f"📸 `{sku}` stüdyo görselleri üretiliyor: {max(1, len(renkler))} renk × 3 kare"
        + (" + tüm renkler vitrin karesi" if vitrin else "") + f" (≈{max(1, len(renkler)) * 3 + vitrin} dk)…",
    )
    komut = [str(PY_GORSEL), "-m", "coo.studyo_qwen", sku, "--tohum", tohum] + (["--vitrin"] if vitrin else [])
    async with _yerel_is(tg, chat_id, sku, "E-ticaret görselleri (Qwen stüdyo)", max(1, len(renkler)) * 3 + vitrin) as k:
        k["adim"] = "Qwen: kapak (beyaz) · krem fon · koyu fon"
        sonuc = await asyncio.to_thread(
            subprocess.run, komut, cwd=str(PROGRAMLAR_KLASORU), capture_output=True, text=True, timeout=5400
        )
    try:
        rapor = json.loads((sonuc.stdout or "").strip().splitlines()[-1])
    except Exception:
        rapor = {"basarili": False, "hata": (sonuc.stderr or "")[-600:]}

    satirlar: list[str] = []
    if rapor.get("basarili"):
        for r in rapor.get("renkler") or []:
            for c in r.get("cekimler") or []:
                if c.get("basarili"):
                    satirlar.append(f"{'✅' if c['gecti'] else '⚠️'} {r.get('slug') or 'varsayılan'}/{c['ad']}: "
                                    f"geometri {c['geometri']:.2f} • renk sapması {c['renk_sapma']:.1f}")
                else:
                    satirlar.append(f"❌ {r.get('slug')}/{c['ad']}: {str(c.get('hata'))[:120]}")
        v = rapor.get("vitrin") or {}
        if v.get("basarili"):
            satirlar.append(f"{'✅' if v['gecti'] else '⚠️'} vitrin ({', '.join(v['renkler'])}): "
                            f"geometri {v['geometri']:.2f} • renk sapması {v['renk_sapma']:.1f}")
        elif vitrin:
            satirlar.append(f"❌ vitrin: {str(v.get('hata'))[:120]}")
    else:
        await tg.mesaj_gonder(chat_id, f"⚠️ Qwen stüdyo hatası:\n`{str(rapor.get('hata'))[-300:]}`",
                              butonlar=[[{"text": "🔁 Tekrar Dene", "callback_data": f"icerik:studyo:{sku}"}]])
        return
    if not satirlar:
        await tg.mesaj_gonder(chat_id, f"❌ `{sku}` stüdyo görselleri üretilemedi.")
        return
    await tg.mesaj_gonder(
        chat_id,
        "🔍 *Otomatik ölçüm* (geometri: Blender modeliyle kenar örtüşmesi • renk sapması: filament tonundan fark)\n"
        + "\n".join(f"• {x}" for x in satirlar),
    )
    await _studyo_denetle(tg, chat_id, sku)


async def _studyo_denetle(tg: TelegramIstemci, chat_id: int, sku: str, not_: str = "") -> None:
    """Claude her kareyi kaynak render'la karşılaştırır (şekil, renk, gölge/hale, fon); kusurluyu yeniden ürettirir
    (kare başına en fazla 5) → albüm + onay butonları (Patron kararı 2026-11-16)."""
    eticaret_denetim.denetim_yolu(sku).unlink(missing_ok=True)
    await tg.mesaj_gonder(chat_id, f"🧐 `{sku}` — Claude kareleri tek tek denetliyor; gölge/hale, renk veya şekil hatası "
                                   "olan kareyi yeniden ürettiriyor (kare başına en fazla 5 deneme, ~5–20 dk).")

    async def _sonra(_ok: bool, yanit: str, devam: str | None) -> None:
        await _studyo_onaya_sun(tg, chat_id, sku, yanit)

    _ajan_arka_planda_calistir(tg, chat_id, "brand-guardian", eticaret_denetim.istem(sku, not_=not_), model="opus",
                               gorev_ozeti=f"E-ticaret denetimi: {sku}", sonraki_islem=_sonra)


async def _studyo_onaya_sun(tg: TelegramIstemci, chat_id: int, sku: str, yanit: str = "") -> None:
    sonuc = await asyncio.to_thread(eticaret_denetim.sonuc_oku, sku) or {}
    kararlar = {k.get("yol"): k for k in sonuc.get("kareler") or []}
    kareler = await asyncio.to_thread(eticaret_denetim.kare_listesi, sku)
    if not kareler:
        await tg.mesaj_gonder(chat_id, f"❌ `{sku}` için e-ticaret karesi bulunamadı.")
        return
    ogeler, kalan = [], []
    for k in kareler:
        d = kararlar.get(k["yol"], {})
        isaret = {"gecti": "✅", "kaldi": "⚠️"}.get(d.get("karar"), "•")
        if d.get("karar") == "kaldi":
            kalan.append(f"{k['kare']} ({k.get('renk_ad') or ''})")
        ogeler.append((Path(k["yol"]), f"{isaret} {k['kare']} — {k.get('renk_ad') or ''}"
                                       + (f" · {d.get('deneme')}. deneme" if d.get("deneme") else "")
                                       + (f"\n{d.get('not')}" if d.get("not") else "")))
    try:
        await tg.album_gonder(chat_id, ogeler)
    except Exception as e:
        log.warning("E-ticaret albümü gönderilemedi: %s", e)
        for yol, aciklama in ogeler:
            with contextlib.suppress(Exception):
                await tg.foto_gonder(chat_id, yol.read_bytes(), aciklama=aciklama, dosya_adi=yol.name)
    yanit_temiz = "\n".join(sat for sat in (yanit or "").splitlines()
                             if not sat.startswith("Ignoring ") and "trust dialog" not in sat).strip()
    ozet = sonuc.get("ozet") or ("⚠️ Claude denetimi yarıda kaldı, kareler DENETLENMEDİ. "
                                 "'✏️ Not ile Düzelt' ile denetimi yeniden başlatın."
                                 + (f"\n{yanit_temiz[-300:]}" if yanit_temiz else ""))
    await asyncio.to_thread(urun_yaml_guncelle, sku, {"studyo_onayi": "BEKLIYOR"})
    await tg.mesaj_gonder(
        chat_id,
        f"🟡 *E-ticaret görselleri onayı* — `{sku}`\n🧐 {ozet}"
        + (f"\n⚠️ 5 denemede düzelmeyen: {', '.join(kalan)}" if kalan else ""),
        butonlar=[[{"text": "✅ Onayla", "callback_data": f"studyo:onay:{sku}"},
                   {"text": "✏️ Not ile Düzelt", "callback_data": f"studyo:revize:{sku}"}],
                  [{"text": "🔁 Hepsini Yeniden Üret", "callback_data": f"icerik:yenile:{sku}"},
                   {"text": "📦 Ürün Kartı", "callback_data": f"urunmenu:{sku}"}]],
    )


async def _pin_callback(tg: TelegramIstemci, chat_id: int, veri: str) -> None:
    """📌 Pinterest: hazırla (ajan yazar) → önizleme + onay → paylaş (ajan Chrome'da yayınlar). Patron kararı 2026-11-17."""
    _, eylem, sku = veri.split(":", 2)
    if not (URUNLER_KLASORU / sku).is_dir():
        await tg.mesaj_gonder(chat_id, f"❌ `{sku}` ürün klasörü bulunamadı.")
        return
    if eylem == "hazirla":
        if not await asyncio.to_thread(pinterest_hatti.uygun_mu, sku):
            await tg.mesaj_gonder(chat_id, f"⚠️ `{sku}` için pin görseli yok — önce teknik poster ya da e-ticaret görselleri.",
                                  butonlar=_sonraki_adim_butonlari(sku))
            return
        pinterest_hatti.pin_yolu(sku).unlink(missing_ok=True)
        await tg.mesaj_gonder(chat_id, f"📌 `{sku}` — pin hazırlanıyor (görsel, başlık, açıklama, pano)…")

        async def _hazir(_ok: bool, yanit: str, devam: str | None) -> None:
            pin = await asyncio.to_thread(pinterest_hatti.oku, sku)
            if not pin or pin.get("durum") != "HAZIR" or not Path(str(pin.get("gorsel"))).exists():
                await tg.mesaj_gonder(chat_id, "❌ Pin hazırlanamadı.\n" + (yanit or "")[-400:])
                return
            metin = (f"📌 *Pinterest önizleme* — `{sku}`\n*{pin.get('baslik')}*\n{pin.get('aciklama')}\n\n"
                     f"Pano: _{pin.get('pano')}_\nBağlantı: {pin.get('link')}\n"
                     + ("🤖 'Yapay zeka ile değiştirildi' olarak işaretlenecek." if pin.get("yz_isareti") else ""))
            await tg.foto_gonder(chat_id, Path(str(pin["gorsel"])).read_bytes(), aciklama=metin[:1000],
                                 dosya_adi=Path(str(pin["gorsel"])).name,
                                 butonlar=[[{"text": "✅ Pinterest'te Paylaş", "callback_data": f"pin:paylas:{sku}"}],
                                           [{"text": "🔁 Yeniden Hazırla", "callback_data": f"pin:hazirla:{sku}"},
                                            {"text": "❌ Vazgeç", "callback_data": f"pin:iptal:{sku}"}]])

        _ajan_arka_planda_calistir(tg, chat_id, "pinterest-curator", pinterest_hatti.hazirla_istemi(sku),
                                   gorev_ozeti=f"Pinterest pin hazırlığı: {sku}", sonraki_islem=_hazir)
    elif eylem == "paylas":
        pin = await asyncio.to_thread(pinterest_hatti.oku, sku)
        if not pin or pin.get("durum") != "HAZIR":
            await tg.mesaj_gonder(chat_id, "⚠️ Onaylanacak hazır pin yok.",
                                  butonlar=[[{"text": "📌 Pin Hazırla", "callback_data": f"pin:hazirla:{sku}"}]])
            return
        await tg.mesaj_gonder(chat_id, f"📌 `{sku}` — Pinterest'te yayınlanıyor (Chrome)…")

        async def _bitti(_ok: bool, yanit: str, devam: str | None) -> None:
            son = await asyncio.to_thread(pinterest_hatti.oku, sku) or {}
            if son.get("durum") == "PAYLASILDI":
                await asyncio.to_thread(urun_yaml_guncelle, sku, {"pinterest": {"pin_url": son.get("pin_url"),
                                                                              "tarih": son.get("tarih"),
                                                                              "pano": son.get("pano")}})
                await tg.mesaj_gonder(chat_id, f"✅ Pin yayında: {son.get('pin_url')}", butonlar=_sonraki_adim_butonlari(sku))
            else:
                await tg.mesaj_gonder(chat_id, f"❌ Pin yayınlanamadı: {son.get('hata') or (yanit or '')[-300:]}",
                                      butonlar=[[{"text": "🔁 Tekrar Dene", "callback_data": f"pin:paylas:{sku}"}]])

        _ajan_arka_planda_calistir(tg, chat_id, "pinterest-curator", pinterest_hatti.paylas_istemi(sku),
                                   gorev_ozeti=f"Pinterest paylaşımı: {sku}", sonraki_islem=_bitti)
    elif eylem == "iptal":
        pinterest_hatti.pin_yolu(sku).unlink(missing_ok=True)
        await tg.mesaj_gonder(chat_id, "Pin iptal edildi; Pinterest'e bir şey gönderilmedi.")


STUDYO_REVIZE_BASLIGI = "✏️ E-ticaret görsel notu"


async def _studyo_callback(tg: TelegramIstemci, chat_id: int, veri: str) -> None:
    _, eylem, sku = veri.split(":", 2)
    if not (URUNLER_KLASORU / sku).is_dir():
        await tg.mesaj_gonder(chat_id, f"❌ `{sku}` ürün klasörü bulunamadı.")
        return
    if eylem == "onay":
        await asyncio.to_thread(urun_yaml_guncelle, sku, {"studyo_onayi": "ONAYLANDI"})
        await tg.mesaj_gonder(chat_id, f"✅ `{sku}` e-ticaret görselleri onaylandı.", butonlar=_sonraki_adim_butonlari(sku))
    elif eylem == "revize":
        await asyncio.to_thread(
            tg._json_istek, "sendMessage",
            {"chat_id": chat_id, "text": f"{STUDYO_REVIZE_BASLIGI} [{sku}]: hangi karede ne düzelsin? "
                                         "(ör. 'mavi kapakta gölge çok koyu', 'krem fonda pencere gölgesi olmasın')",
             "reply_markup": {"force_reply": True, "input_field_placeholder": "Düzeltme notu…"}})
    elif eylem == "sun":
        await _studyo_onaya_sun(tg, chat_id, sku)


async def _numune_kaydet(tg: TelegramIstemci, chat_id: int, dosya_id: str, sku: str) -> None:
    if not sku or not (URUNLER_KLASORU / sku).is_dir():
        await tg.mesaj_gonder(chat_id, f"❌ `{sku}` ürün klasörü bulunamadı.")
        return
    hedef = await asyncio.to_thread(numune_kaydet_yolu, sku)
    if not await tg.dosya_indir(dosya_id, hedef):
        await tg.mesaj_gonder(chat_id, "❌ Fotoğraf indirilemedi.")
        return
    adet = len(await asyncio.to_thread(numune_fotograflari, sku))
    await tg.mesaj_gonder(
        chat_id,
        f"📷 `{sku}` numune fotoğrafı kaydedildi (`{hedef.name}`, toplam {adet}).\n"
        "Başka açıdan da gönderebilirsin. Hazır olunca kullanım görsellerini üret:",
        butonlar=[[{"text": "🏡 Kullanım Görselleri (Flow)", "callback_data": f"icerik:kullanim:{sku}"}],
                  [{"text": "📷 Bir Numune Daha", "callback_data": f"numune:iste:{sku}"},
                   {"text": "📦 Ürün Kartı", "callback_data": f"urunmenu:{sku}"}]],
    )


async def _kullanim_uret(tg: TelegramIstemci, chat_id: int, sku: str, revize_notu: str = "",
                         numunesiz: bool = False) -> None:
    """Flow ile kullanım görselleri + Veo video → Reels → Onay ②. Kaynak gerçek numune fotoğrafı; numunesiz=True
    (Patron seçeneği): ürünün Qwen stüdyo karesi, sıkı sadakat kontrolüyle (`kullanim-q-*`)."""
    if numunesiz:
        if not await asyncio.to_thread(numunesiz_kaynaklar, sku):
            await tg.mesaj_gonder(chat_id, f"⚠️ `{sku}` için önce *5. E-ticaret görselleri* gerekli (kullanım görseli "
                                           "ürünün stüdyo karesinden yapılır).",
                                  butonlar=[[{"text": "🛍️ E-ticaret Görselleri", "callback_data": f"icerik:studyo:{sku}"}]])
            return
    elif not await asyncio.to_thread(numune_fotograflari, sku):
        BELLEK.numune_bekleyen_sku = sku
        await tg.mesaj_gonder(chat_id, f"📷 `{sku}` için önce numune fotoğrafı gönder (kullanım görselleri gerçek "
                                       "fotoğraftan üretilir).")
        return

    async def _sonrasi(basarili: bool, yanit: str, devam_anahtari: str | None) -> None:
        kullanimlar = sorted((URUNLER_KLASORU / sku / "gorsel").glob("kullanim-*"))
        if not kullanimlar:
            await tg.mesaj_gonder(chat_id, f"⚠️ `{sku}` kullanım görseli üretilemedi.\n\n{(yanit or '')[-700:]}",
                                  butonlar=_gorev_sonu_butonlari(devam_anahtari))
            return
        try:
            await asyncio.to_thread(tam_medya_paketi_uret, sku, None)
        except Exception as exc:
            log.exception("Medya paketi hatası (%s)", sku)
            await tg.mesaj_gonder(chat_id, f"⚠️ Reels/Pin kurgusu hata verdi: {exc}")
        await _icerik_onaya_sun(tg, chat_id, sku)

    await tg.mesaj_gonder(chat_id, f"🏡 `{sku}` — {'stüdyo karesinden (numunesiz, deneme)' if numunesiz else 'numune fotoğrafından'} "
                                   "Flow kullanım görselleri + video üretiliyor… (~10–15 dk, Flow: görsel 0, video ~20 kredi)"
                                   + ("\n_Ürün değişirse görsel elenir; onay ekranında yine sen karar verirsin._" if numunesiz else ""))
    _ajan_arka_planda_calistir(
        tg, chat_id, "cmo-store-director", kullanim_istemi(sku, revize_notu=revize_notu, numunesiz=numunesiz),
        gorev_ozeti=f"Kullanım görselleri: {sku}", sonraki_islem=_sonrasi,
    )


def _metinden_sku_bul(metin: str) -> str | None:
    if not metin:
        return None
    kucuk = metin.lower()
    for sku in _mevcut_skulari_listele():
        if sku.lower() in kucuk:
            return sku
        veri = urun_yaml_oku(sku)
        ad = str(veri.get("ad") or "").lower()
        if ad and len(ad) >= 4 and ad in kucuk:
            return sku
    return None


def _baski_sonu_butonlari(kayit_id: str, sku: str | None) -> list[list[dict[str, str]]]:
    satirlar = [
        [
            {"text": "🏠 Hobi / Kişisel", "callback_data": f"baski:HOBI:{kayit_id}"},
            {"text": "🧪 İş: Numune", "callback_data": f"baski:IS_NUMUNE:{kayit_id}"},
        ],
        [
            {"text": "📦 İş: Sipariş", "callback_data": f"baski:IS_SIPARIS:{kayit_id}"},
            {"text": "🎁 Hediye / Tanıtım", "callback_data": f"baski:HEDIYE:{kayit_id}"},
        ],
        [{"text": "🗑️ Hatalı / Fire", "callback_data": f"baski:FIRE:{kayit_id}"}],
    ]
    if sku:
        satirlar.append(
            [
                {"text": "🏡 Kullanım Görseli (numuneden)", "callback_data": f"flow:uret:{sku}"},
                {"text": "🎬 Reels / Kurgu", "callback_data": f"medya:uret:{sku}"},
            ]
        )
    satirlar.append([{"text": "🧹 Tabla Boşaltıldı", "callback_data": "tabla:bos"}])
    return satirlar


def _metinden_gorselleri_bul(metin: str, max_adet: int = 3) -> list[Path]:
    """Ajan yanıtında geçen mevcut görsel yollarını (.png/.jpg) çalışma alanı sınırları içinde bulur."""
    adaylar = re.findall(r"(?:[A-Za-z0-9_./-]+\.(?:png|jpg|jpeg|webp))", metin or "", flags=re.IGNORECASE)
    kok = CALISMA_ALANI.resolve()
    bulunan: list[Path] = []
    gorulen: set[Path] = set()
    for ham in adaylar:
        p = Path(ham)
        if not p.is_absolute():
            p = CALISMA_ALANI / ham if (CALISMA_ALANI / ham).exists() else VERI_KLASORU / ham
        try:
            cozulmus = p.resolve()
        except Exception:
            continue
        if cozulmus in gorulen or not str(cozulmus).startswith(str(kok)):
            continue
        if cozulmus.exists() and cozulmus.is_file():
            gorulen.add(cozulmus)
            bulunan.append(cozulmus)
            if len(bulunan) >= max_adet:
                break
    return bulunan


async def _mesaj_yanit_gorsellerini_gonder(tg: TelegramIstemci, chat_id: int, yanit: str) -> None:
    for img_yol in _metinden_gorselleri_bul(yanit):
        try:
            await tg.foto_gonder(
                chat_id,
                img_yol.read_bytes(),
                aciklama=f"🖼️ `{img_yol.relative_to(CALISMA_ALANI)}`",
                dosya_adi=img_yol.name,
            )
        except Exception as exc:
            log.warning("Yanıt görseli gönderilemedi (%s): %s", img_yol, exc)


def _gorev_sonu_butonlari(
    devam_anahtari: str | None = None,
    ek_satirlar: list[list[dict[str, str]]] | None = None,
) -> list[list[dict[str, str]]]:
    satirlar: list[list[dict[str, str]]] = []
    if devam_anahtari:
        satirlar.append([{"text": "▶️ Kaldığı Yerden Devam Et", "callback_data": f"gorev:devam:{devam_anahtari}"}])
    if ek_satirlar:
        satirlar.extend(ek_satirlar)
    satirlar.extend(_ust_yonetim_butonlari())
    return satirlar


def _ajan_arka_planda_calistir(
    tg: TelegramIstemci,
    chat_id: int,
    ajan_kodu: str,
    istem: str,
    *,
    zaman_asimi: int | None = None,
    oturum_id: str | None = None,
    gorev_ozeti: str = "",
    sonraki_islem: Callable[[bool, str, str | None], Awaitable[None]] | None = None,
    model: str | None = None,
) -> str:
    """Claude ajan görevini arka planda başlatır; polling döngüsünü bloklamaz ve canlı ilerleme gösterir.
    model: görev bazlı model ("opus"/"sonnet"); verilmezse ajan dosyasındaki model kullanılır."""
    hedef_ajan = _hedef_ajan_coz(ajan_kodu)
    BELLEK.aktif_muhatap_ajan = hedef_ajan
    unvan, _ = AJAN_KATALOGU[hedef_ajan]
    gorev_id = uuid.uuid4().hex[:6]
    ozet_kisa = (gorev_ozeti or istem).strip().replace("\n", " ")[:70]

    async def _yurut() -> None:
        kayit = BELLEK.aktif_gorevler[gorev_id]
        kayit["task"] = asyncio.current_task()
        baslangic = time.monotonic()
        durum_msg_id: int | None = None
        iptal_buton = [[{"text": "🛑 Görevi İptal Et", "callback_data": f"gorev:iptal:{gorev_id}"}]]

        try:
            ilk_mesaj = await tg.mesaj_gonder(
                chat_id,
                f"⏳ *{unvan}* (`{hedef_ajan}`) çalışıyor...\n"
                f"• *Görev:* `{gorev_id}` — _{ozet_kisa}_\n"
                f"• _(Bot yanıt verirken diğer komutları ve yazıcıyı kullanmaya devam edebilirsiniz.)_",
                butonlar=iptal_buton,
            )
            durum_msg_id = (ilk_mesaj.get("result") or {}).get("message_id")
        except Exception as exc:
            log.warning("Görev başlangıç mesajı gönderilemedi (%s): %s", gorev_id, exc)

        async def _ilerleme_guncelle(durum: dict[str, Any]) -> None:
            if not durum_msg_id:
                return
            sure = _sure_bicimle(float(durum.get("gecen_sn") or (time.monotonic() - baslangic)))
            adim = int(durum.get("arac_sayisi") or 0)
            son_arac = str(durum.get("son_arac") or "düşünüyor")
            await tg.mesaj_duzenle(
                chat_id,
                durum_msg_id,
                f"⏳ *{unvan}* (`{hedef_ajan}`) çalışıyor...\n"
                f"• *Görev:* `{gorev_id}` • *Süre:* `{sure}` • *Adım:* `{adim}`\n"
                f"• *Son İşlem:* `{son_arac}`",
                butonlar=iptal_buton,
            )

        try:
            basarili, yanit, sid = await claude_ajan_akisi_calistir(
                hedef_ajan,
                istem,
                zaman_asimi=zaman_asimi,
                oturum_id=oturum_id,
                gorev_kaydi=kayit,
                ilerleme_cb=_ilerleme_guncelle,
                model=model,
            )
            gecen = _sure_bicimle(time.monotonic() - baslangic)
            adim = int(kayit.get("arac_sayisi") or 0)
            devam_anahtari = _oturum_kaydet(sid, hedef_ajan, ozet_kisa)

            if durum_msg_id:
                durum_rozet = "✅" if basarili else "⚠️"
                durum_yazi = "tamamlandı" if basarili else "uyarı / süre sonu ile durdu"
                await tg.mesaj_duzenle(
                    chat_id,
                    durum_msg_id,
                    f"{durum_rozet} *{unvan}* (`{hedef_ajan}`) {durum_yazi} (`{gecen}` • `{adim} adım`).",
                    butonlar=[],
                )

            if sonraki_islem is not None:
                await sonraki_islem(basarili, yanit, devam_anahtari)
                return

            baslik = f"*{unvan} Yanıtı* (`{gecen}`):\n\n" if basarili else f"⚠️ *{unvan} Uyarısı* (`{gecen}`):\n\n"
            butonlar = _gorev_sonu_butonlari(devam_anahtari if not basarili else None)
            await tg.mesaj_gonder(chat_id, baslik + yanit, butonlar=butonlar)
            await _mesaj_yanit_gorsellerini_gonder(tg, chat_id, yanit)

        except asyncio.CancelledError:
            gecen = _sure_bicimle(time.monotonic() - baslangic)
            sid = str(kayit.get("session_id") or "").strip() or None
            devam_anahtari = _oturum_kaydet(sid, hedef_ajan, ozet_kisa)
            if durum_msg_id:
                await tg.mesaj_duzenle(
                    chat_id,
                    durum_msg_id,
                    f"🛑 *{unvan}* (`{hedef_ajan}`) iptal edildi (`{gecen}`).",
                    butonlar=[],
                )
            butonlar = _gorev_sonu_butonlari(devam_anahtari)
            await tg.mesaj_gonder(
                chat_id,
                f"🛑 Görev `{gorev_id}` iptal edildi (`{gecen}`)."
                + ("\nKaldığı yerden devam etmek isterseniz `/devam` kullanabilirsiniz." if devam_anahtari else ""),
                butonlar=butonlar,
            )
            raise
        except Exception as exc:
            log.exception("Arka plan ajan görevi hatası (%s)", gorev_id)
            await tg.mesaj_gonder(chat_id, f"❌ `{hedef_ajan}` görevi (`{gorev_id}`) hata verdi: {exc}")
        finally:
            BELLEK.aktif_gorevler.pop(gorev_id, None)

    BELLEK.aktif_gorevler[gorev_id] = {
        "id": gorev_id,
        "ajan": hedef_ajan,
        "unvan": unvan,
        "ozet": ozet_kisa,
        "baslangic": time.monotonic(),
        "arac_sayisi": 0,
        "son_arac": "başlatılıyor",
        "session_id": oturum_id or "",
        "proc": None,
        "task": None,
    }
    t = asyncio.create_task(_yurut())
    BELLEK.aktif_gorevler[gorev_id]["task"] = t
    return gorev_id


async def _claude_ajana_sor_ve_yanitla(
    tg: TelegramIstemci,
    chat_id: int,
    ajan_kodu: str,
    istem: str,
    zaman_asimi: int | None = None,
    oturum_id: str | None = None,
) -> None:
    _ajan_arka_planda_calistir(
        tg,
        chat_id,
        ajan_kodu,
        istem,
        zaman_asimi=zaman_asimi,
        oturum_id=oturum_id,
    )


async def _b2c_vitrini_gonder(tg: TelegramIstemci, chat_id: int, paket_id: str | None = None) -> None:
    paket = paket_yukle(paket_id)
    if not paket or not (paket.get("adaylar") or []):
        await tg.mesaj_gonder(
            chat_id,
            "📭 Henüz kayıtlı bir B2C ürün öneri paketi yok.\n"
            "Canlı internet araştırması başlatmak için:\n`/b2c minimalist masaüstü ürünleri` yazabilirsiniz.",
            butonlar=_ust_yonetim_butonlari(),
        )
        return

    pid = str(paket.get("paket_id") or "")
    katalog_yolu = await asyncio.to_thread(katalog_gorseli_olustur, paket)
    if katalog_yolu.exists():
        await tg.foto_gonder(
            chat_id,
            katalog_yolu.read_bytes(),
            aciklama=f"🛍️ *{paket.get('baslik', 'B2C Ürün Önerileri')}* (`{pid}`)\nBeğendiğin ürünü *💡 Bu Konseptle Fikir* ile referans alıp özgün konsept üretimine başlatabilirsin:",
            dosya_adi=katalog_yolu.name,
        )

    adaylar = paket.get("adaylar") or []
    gosterilen = 0
    for idx, aday in enumerate(adaylar):
        if str(aday.get("durum") or "").upper() == "ELENDI":
            continue
        metin = aday_kart_metni(aday, idx, pid)
        butonlar = aday_butonlari(pid, idx)
        foto_yolu = gorsel_yolunu_coz(aday)
        if foto_yolu:
            await tg.foto_gonder(
                chat_id,
                foto_yolu.read_bytes(),
                aciklama=metin[:1000],
                dosya_adi=foto_yolu.name,
                butonlar=butonlar,
            )
        else:
            await tg.mesaj_gonder(chat_id, metin, butonlar=butonlar)
        gosterilen += 1
        if gosterilen >= 6:
            break


async def _b2c_aday_gelistir(
    tg: TelegramIstemci,
    chat_id: int,
    paket_id: str,
    idx: int,
    ek_not: str = "",
) -> None:
    try:
        aday, urun_dir, arge_md = urun_iskelesi_kur(paket_id, idx, ek_not=ek_not)
    except Exception as exc:
        await tg.mesaj_gonder(chat_id, f"❌ Ürün iskeleti kurulamadı: {exc}")
        return

    sku = urun_dir.name
    ad = str(aday.get("ad") or sku)
    stl_yolu = urun_dir / "model" / f"{sku}.stl"
    gorsel_dir = urun_dir / "gorsel"

    await tg.mesaj_gonder(
        chat_id,
        f"🚀 *B2C Ürün Geliştirme Başlatıldı:* *{ad}* (`{sku}`)\n"
        f"• *Ar-Ge Dosyası:* `{arge_md.relative_to(CALISMA_ALANI)}`\n"
        f"• *Aşamalar:* Endüstriyel CAD (`build123d` / `BOSL2` / `Blender`) → `kalite_kapisi.py --mod b2c` → Cycles GPU Render → OrcaSlicer Profili",
    )

    istem = (
        f"Seçilen B2C ürünü geliştir ve fiziksel üretime hazır hale getir:\n"
        f"- SKU: {sku}\n"
        f"- Ürün Adı: {ad}\n"
        f"- Referans Kaynak: {aday.get('kaynak_url', '')} ({aday.get('ozet', '')})\n"
        f"- CAD Rotası: {aday.get('cad_rotasi', 'build123d')}\n"
        + (f"- Patron Notu / Revizyon: {ek_not}\n" if ek_not else "")
        + f"\nZORUNLU KURALLAR:\n"
        f"1) B2C üründe workbench-studio maker (container/photo_stand vb.) kaba 2B ekstrüzyonları KESİNLİKLE YASAKTIR. "
        f"Pahlı (fillet/chamfer), geçme toleranslı (0.25mm), ergonomik ve premium gerçek endüstriyel CAD modeli üret.\n"
        f"2) Kullanılacak araçlar: {PY_CAD} (build123d) veya openscad (BOSL2) veya blender -b (bpy/bmesh).\n"
        f"3) Çıktı STL dosyasını mutlaka `02_Urunler/{sku}/model/{sku}.stl` olarak kaydet.\n"
        f"4) Ardından `{PY_CAD} -m coo.kalite_kapisi {URUNLER_KLASORU}/{sku}/model/{sku}.stl --mod b2c` komutunu çalıştır; RED verirse modeli düzelt.\n"
        f"5) `blender -b -P coo/gorsel/blender_ciz.py -- --stl 02_Urunler/{sku}/model/{sku}.stl --cikti 02_Urunler/{sku}/gorsel --sadece-kare` ile `studyo.png` ve `beyaz.png` üret.\n"
        f"6) `python3 -m coo.orca_profil --sku {sku}` ile dilimleme profilini üret ve `02_Urunler/{sku}/urun.yaml` içindeki boyutları güncelle."
    )

    async def _cad_sonrasi(basarili: bool, yanit: str, devam_anahtari: str | None) -> None:
        durum_metni = yanit
        kalite_gecti = False
        if stl_yolu.exists():
            kapisi = await asyncio.to_thread(kalite_kapisi_calistir, stl_yolu, "b2c")
            await asyncio.to_thread(urun_yaml_kalite_guncelle, sku, stl_yolu, kapisi)
            kalite_gecti = kapisi.get("durum") == "PASS"
            durum_metni = f"{kalite_rapor_ozeti(kapisi)}\n\n{yanit}"

        nihai_basari = basarili and kalite_gecti
        if basarili and stl_yolu.exists() and not kalite_gecti:
            baslik = f"🔴 *{ad} (`{sku}`) Kalite Kapısı RED — Revize Gerekli:*\n\n"
        elif nihai_basari:
            baslik = f"✅ *{ad} (`{sku}`) Geliştirme Raporu:*\n\n"
        else:
            baslik = f"⚠️ *{ad} (`{sku}`) Uyarısı:*\n\n"

        revize_buton = {"text": "✏️ Revize İste", "callback_data": f"b2c:revize:{paket_id_temizle(paket_id)}:{idx}"}
        if kalite_gecti:
            ek_satirlar = [[{"text": f"⚙️ {sku} Orca Profil", "callback_data": f"orca:analiz:{sku}"}, revize_buton]]
        else:
            ek_satirlar = [[revize_buton]]

        butonlar = _gorev_sonu_butonlari(
            devam_anahtari if not nihai_basari else None,
            ek_satirlar=ek_satirlar,
        )
        await tg.mesaj_gonder(chat_id, baslik + durum_metni, butonlar=butonlar)

        for dosya_adi in ("studyo.png", "beyaz.png", "yakin.png"):
            f_yol = gorsel_dir / dosya_adi
            if f_yol.exists():
                await tg.foto_gonder(
                    chat_id,
                    f_yol.read_bytes(),
                    aciklama=f"🖼️ *{ad}* (`{sku}`) — `{dosya_adi}`",
                    dosya_adi=f_yol.name,
                )

    _ajan_arka_planda_calistir(
        tg,
        chat_id,
        "cad-artist",
        istem,
        gorev_ozeti=f"B2C CAD: {ad} ({sku})",
        sonraki_islem=_cad_sonrasi,
    )


async def baski_bitti_sorusu_gonder(
    tg: TelegramIstemci,
    chat_id: int,
    dosya_adi: str,
    gecen_saniye: int = 0,
    ilerleme_yuzde: float = 100.0,
    bitis_durumu: str = "TAMAMLANDI",
    izleme: dict[str, Any] | None = None,
) -> GcodeReferans:
    """Baskı tamamlandığında G-code dosya adından ürünü eşleştirir ve Telegram'dan 4 seçenek sorar;
    ardından tüm baskıyı YZ'ye inceletip dilimleme / bakım önerili raporu gönderir."""
    erp_urunler = await ERP.urunler()
    ref = gcode_referans_coz(dosya_adi, erp_urunler=erp_urunler, gecen_saniye=gecen_saniye)
    ref.ilerleme_yuzde = float(ilerleme_yuzde or 100.0)
    ref.bitis_durumu = bitis_durumu
    # mp4_derle kareleri siler → rapor için seçkiyi önce al
    tl_klasor = URUNLER_KLASORU / (ref.eslesen_sku or "_genel_baski") / "medya" / "timelapse_kareler"
    secki = await asyncio.to_thread(
        lambda: [p.read_bytes() for p in rapor_kare_secki(sorted(tl_klasor.glob("kare_*.jpg")))])
    timelapse_yolu = await asyncio.to_thread(BELLEK.timelapse.mp4_derle, ref.eslesen_sku)

    kayit_id = uuid.uuid4().hex[:10]
    BELLEK.bekleyen_baskilar[kayit_id] = ref
    durum_dosyasi_yaz(
        tabla_bos=False,
        son_baski_dosya=dosya_adi,
        son_baski_sku=ref.eslesen_sku or "",
        son_baski_zaman=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        bekleyen_kayit_id=kayit_id,
    )

    saat = ref.tahmini_dakika // 60
    dk = ref.tahmini_dakika % 60
    sure_str = f"{saat} sa {dk} dk" if ref.tahmini_dakika > 0 else "Bilinmiyor"
    gram_str = f"~{ref.tahmini_gram:.1f} g" if ref.tahmini_gram > 0 else "Dosya adında belirtilmemiş"
    timelapse_not = f"\n🎥 *İç Kamera Timelapse:* `{timelapse_yolu.name}` hazır" if timelapse_yolu else ""

    yarim = ref.ilerleme_yuzde < 99.5
    metin = (
        (f"⚠️ *Baskı yarıda kaldı* (`{bitis_durumu}`, %{ref.ilerleme_yuzde:.0f})\n"
         f"_Fire seçilirse yalnız harcanan ~{fire_grami(ref.tahmini_gram, ref.ilerleme_yuzde)} g düşülür._\n\n"
         if yarim else f"🏁 *Baskı Tamamlandı!*\n\n")
        + ""
        f"• *G-Code Dosyası:* `{ref.ham_dosya_adi}`\n"
        f"• *Eşleşen Ürün:* *{ref.urun_adi}* (`{ref.eslesen_sku or 'genel-baski'}`)\n"
        f"• *Süre & Gramaj:* `{sure_str}` • `{gram_str}`"
        f"{timelapse_not}\n\n"
        f"❓ *Bu baskı ne içindi? Lütfen seçin (ERP ve stok buna göre işlenecek):*"
    )

    butonlar = _baski_sonu_butonlari(kayit_id, ref.eslesen_sku)
    kare = await asyncio.to_thread(kamera_karesi_al)
    if kare:
        await tg.foto_gonder(chat_id, kare, aciklama=metin, butonlar=butonlar)
    else:
        await tg.mesaj_gonder(chat_id, metin, butonlar=butonlar)
    if secki:
        asyncio.create_task(_guvenli(_baski_raporu_gonder(tg, chat_id, ref, secki + ([kare] if kare else []),
                                                          izleme or {}, gecen_saniye)))
    return ref


async def _guvenli(coro: Awaitable[None]) -> None:
    try:
        await coro
    except Exception as exc:  # noqa: BLE001 — arka plan raporu ana akışı bozmasın
        log.warning("Arka plan görevi hatası: %s", exc)


async def _makine_saati() -> float:
    m = next((x for x in await ERP.makineler() if int(x.get("id", 0)) == 1), {})
    return float(m.get("total_worked_hours") or 0.0)


def _kategori_ve_ayarlar(urun: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    from .orca_dilim import _ORTAK_WORKBENCH, duzlestir, TABAN_PROSES

    dil = urun.get("dilimleme") if isinstance(urun.get("dilimleme"), dict) else {}
    kat = dil.get("kategori") or urun.get("baski_kategorisi") or (kategori_sec(urun, "")[0] if urun else None)
    katlar = baski_kategorileri()
    if kat not in katlar:
        return None, {}
    try:
        taban = duzlestir(TABAN_PROSES)
    except Exception:  # noqa: BLE001
        taban = {}
    ayarlar = {k: taban.get(k) for k in IZINLI_AYARLAR if taban.get(k) is not None}
    ayarlar.update(_ORTAK_WORKBENCH)
    ayarlar.update(katlar[kat].get("ayarlar") or {})
    return kat, ayarlar


async def _baski_raporu_gonder(tg: TelegramIstemci, chat_id: int, ref: GcodeReferans, kareler: list[bytes],
                               izleme: dict[str, Any], gecen_saniye: int) -> None:
    urun = await asyncio.to_thread(urun_yaml_oku, ref.eslesen_sku) if ref.eslesen_sku else {}
    kat, ayarlar = await asyncio.to_thread(_kategori_ve_ayarlar, urun or {})
    dil = (urun or {}).get("dilimleme") if isinstance((urun or {}).get("dilimleme"), dict) else {}
    saat = await _makine_saati()
    takili = await _takili_filament()
    baglam = {
        "urun": ref.urun_adi, "sku": ref.eslesen_sku, "bitis": ref.bitis_durumu,
        "ilerleme_yuzde": round(ref.ilerleme_yuzde), "dilimleme_kategorisi": kat, "mevcut_ayarlar": ayarlar,
        "destek": dil.get("destek_gerekli"), "destek_nedeni": dil.get("destek_nedeni"),
        "tahmini_sure_dk": dil.get("gercek_sure_dk") or ref.tahmini_dakika or None,
        "gercek_sure_dk": round(gecen_saniye / 60) if gecen_saniye else None,
        "filament": (f"{takili.get('brand', '')} {takili.get('material_type', '')} {takili.get('color_name', '')}"
                     if takili else dil.get("filament")),
        "yz_kontrol_gecmisi": [{k: x.get(k) for k in ("durum", "sorun", "guven", "aciklama")}
                               for x in (izleme.get("yz_gecmis") or [])][-12:],
        "patron_yanlis_alarm": bool(izleme.get("sessiz_bitis")),
        "bakim_durumu": rapor_bakim_durumu(saat), "makine": f"Elegoo Centauri Carbon, toplam {saat:.1f} sa (ERP)",
    }
    rapor = await asyncio.to_thread(rapor_uret, kareler, baglam)
    oneriler = rapor_onerileri_suz(rapor, ayarlar) if kat else []
    rapor.update(sku=ref.eslesen_sku, kategori=kat, oneriler=oneriler, baglam=baglam)
    rid = await asyncio.to_thread(rapor_kaydet, rapor)
    butonlar: list[list[dict[str, str]]] = []
    if oneriler and kat:
        butonlar.append([{"text": f"⚙️ Uygula ('{kat}')", "callback_data": f"rapor:uygula:{rid}"},
                         {"text": "⏳ Şimdi Değil", "callback_data": f"rapor:ertele:{rid}"}])
    acil = [b for b in rapor_bakim_durumu(saat) if b["durum"] in ("GECIKTI", "YAKLASTI")]
    butonlar += [[{"text": f"🛠️ Yapıldı: {b['is'][:28]}", "callback_data": f"bakim:yap:{b['anahtar']}"}] for b in acil[:3]]
    butonlar.append([{"text": "🛠️ Bakım Durumu", "callback_data": "bakim:liste"}])
    await tg.mesaj_gonder(chat_id, rapor_metni(rapor, oneriler, kat), butonlar=butonlar)


async def _alim_belgesi_al(tg: TelegramIstemci, chat_id: int, dosya_id: str, pdf_mu: bool,
                           album_id: str | None, aciklama: str) -> None:
    """Fatura / alım listesi belgesini kaydeder; albümün tüm sayfaları gelince finans ajanını başlatır."""
    if album_id and album_id in BELLEK.alim_albumleri:
        klasor = BELLEK.alim_albumleri[album_id]
        n = len(list(klasor.glob("sayfa-*")))
        await tg.dosya_indir(dosya_id, klasor / f"sayfa-{n + 1:02d}{'.pdf' if pdf_mu else '.jpg'}")
        return
    BELLEK.alim_bekleniyor = False
    klasor = await asyncio.to_thread(yeni_alim_klasoru)
    if album_id:
        BELLEK.alim_albumleri[album_id] = klasor
    await tg.dosya_indir(dosya_id, klasor / f"sayfa-01{'.pdf' if pdf_mu else '.jpg'}")
    not_ = re.sub(r"^\s*/?(fatura|al[ıi]m|filament|malzeme)\b[:\s]*", "", aciklama or "", flags=re.I).strip()
    await tg.mesaj_gonder(chat_id, "🧾 Alım belgesi alındı — finans ajanı okuyor, kalemleri ERP ile eşleştiriyor… "
                                   "(ERP'ye senin onayından önce hiçbir şey yazılmaz)")
    if album_id:
        await asyncio.sleep(6)  # çok sayfalı faturanın diğer sayfaları gelsin
        BELLEK.alim_albumleri.pop(album_id, None)
    filamentler, malzemeler = await ERP.filamentler(), await ERP.malzemeler()

    async def _sonra(basarili: bool, yanit: str, devam_anahtari: str | None) -> None:
        await _alim_ozeti_gonder(tg, chat_id, klasor, yanit)

    _ajan_arka_planda_calistir(tg, chat_id, "finance-tracker", alim_istemi(klasor, filamentler, malzemeler, not_),
                               gorev_ozeti=f"Alım belgesi {klasor.name}",
                               sonraki_islem=_opus_denetimli(tg, chat_id, f"alım {klasor.name}", _alim_denetim(klasor), _sonra))


def _alim_denetim(klasor: Path) -> str:
    belgeler = [str(p) for p in sorted(klasor.glob("sayfa-*"))]
    return _opus_denetim_istemi(
        "alım belgesini (fatura/liste) okuyup ERP kalemlerine eşleştirdi", [str(klasor / "alim.json")] + belgeler,
        "- Belgeyi KENDİN oku: her satırın miktarı, birim fiyatı, toplamı ve genel toplam alim.json ile aynı mı?\n"
        "- Filament miktarı gram, fiyat TL/kg (KDV dahil) mi; eşleştirme (marka+tür+renk) doğru mu? ERP'ye yazma.")


async def _alim_ozeti_gonder(tg: TelegramIstemci, chat_id: int, klasor: Path, yanit: str = "") -> None:
    veri, hatalar = await asyncio.to_thread(alim_oku, klasor)
    if veri is None:
        await tg.mesaj_gonder(chat_id, f"⚠️ Belge okunamadı: {', '.join(hatalar)}\n`{(yanit or '')[-300:]}`")
        return
    filamentler, malzemeler = await ERP.filamentler(), await ERP.malzemeler()
    try:
        onceki = await ERP._get(f"/api/alimlar?limit=500")
    except Exception:  # noqa: BLE001
        onceki = []
    engel, uyari = alim_dogrula(veri, filamentler, malzemeler, onceki)
    metin = alim_ozet_metni(veri, filamentler, malzemeler, engel, uyari)
    butonlar = ([[{"text": "✅ ERP'ye İşle", "callback_data": f"alim:isle:{klasor.name}"},
                  {"text": "❌ İptal", "callback_data": f"alim:iptal:{klasor.name}"}]] if not engel else
                [[{"text": "🔁 Yeniden Oku", "callback_data": f"alim:oku:{klasor.name}"},
                  {"text": "❌ İptal", "callback_data": f"alim:iptal:{klasor.name}"}]])
    await tg.mesaj_gonder(chat_id, metin[:4000], butonlar=butonlar)


async def _alim_callback(tg: TelegramIstemci, chat_id: int, veri: str, mesaj: dict[str, Any]) -> None:
    parca = veri.split(":", 2)
    eylem = parca[1] if len(parca) > 1 else ""
    if eylem == "bekle":
        BELLEK.alim_bekleniyor = True
        await tg.mesaj_gonder(chat_id, "🧾 Faturanın / alım listesinin *fotoğrafını veya PDF'ini* gönder (çok sayfalıysa "
                                       "albüm olarak). İstersen açıklamaya not ekle: `fatura Trendyol siparişi`.")
        return
    klasor = ALIM_KLASORU / (parca[2] if len(parca) > 2 else "")
    if not re.fullmatch(r"\d{8}-\d{6}", klasor.name) or not klasor.is_dir():
        await tg.mesaj_gonder(chat_id, "❌ Alım kaydı bulunamadı.")
        return
    await tg.klavye_temizle(chat_id, mesaj.get("message_id"))
    if eylem == "iptal":
        (klasor / "IPTAL").write_text("Patron iptal etti\n", encoding="utf-8")
        await tg.mesaj_gonder(chat_id, "🗑️ Alım iptal edildi; ERP'ye bir şey yazılmadı.")
        return
    if eylem == "oku":
        filamentler, malzemeler = await ERP.filamentler(), await ERP.malzemeler()

        async def _sonra(basarili: bool, yanit: str, devam_anahtari: str | None) -> None:
            await _alim_ozeti_gonder(tg, chat_id, klasor, yanit)

        _ajan_arka_planda_calistir(tg, chat_id, "finance-tracker", alim_istemi(klasor, filamentler, malzemeler),
                                   gorev_ozeti=f"Alım belgesi {klasor.name} (yeniden)",
                                   sonraki_islem=_opus_denetimli(tg, chat_id, f"alım {klasor.name}",
                                                                 _alim_denetim(klasor), _sonra))
        return
    if eylem == "isle":
        if (klasor / "sonuc.json").exists():
            await tg.mesaj_gonder(chat_id, "ℹ️ Bu alım zaten ERP'ye işlendi.")
            return
        veri_, _ = await asyncio.to_thread(alim_oku, klasor)
        filamentler, malzemeler = await ERP.filamentler(), await ERP.malzemeler()
        try:
            onceki = await ERP._get("/api/alimlar?limit=500")
        except Exception:  # noqa: BLE001
            onceki = []
        engel, _ = alim_dogrula(veri_ or {}, filamentler, malzemeler, onceki)
        if veri_ is None or engel:
            await tg.mesaj_gonder(chat_id, "⛔ İşlenmedi:\n• " + "\n• ".join(engel or ["alim.json yok"]))
            return
        sonuc = await asyncio.to_thread(alim_uygula, veri_, ERP.base_url, f"telegram:{klasor.name}")
        (klasor / "sonuc.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8")
        uyarilar = await ERP.kritik_stok_kontrol()
        await tg.mesaj_gonder(chat_id, alim_sonuc_metni(sonuc)
                              + ("\n\n🚨 " + "\n🚨 ".join(uyarilar) if uyarilar else ""),
                              butonlar=[[{"text": "🧾 Stok", "callback_data": "menu:stok"}]])


def rapor_kaydet_uzerine(rid: str, rapor: dict[str, Any]) -> None:
    (RAPOR_KLASORU / f"{rid}.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")


async def _bakim_listesi_gonder(tg: TelegramIstemci, chat_id: int) -> None:
    saat = await _makine_saati()
    durum = await asyncio.to_thread(rapor_bakim_durumu, saat)
    butonlar = [[{"text": f"🛠️ Yapıldı: {b['is'][:30]}", "callback_data": f"bakim:yap:{b['anahtar']}"}] for b in durum]
    await tg.mesaj_gonder(chat_id, rapor_bakim_metni(durum, saat), butonlar=butonlar)


async def _rapor_bakim_callback(tg: TelegramIstemci, chat_id: int, veri: str, mesaj: dict[str, Any]) -> None:
    parca = veri.split(":", 2)
    tur, eylem, arg = parca[0], parca[1] if len(parca) > 1 else "", parca[2] if len(parca) > 2 else ""
    if tur == "bakim" and eylem == "liste":
        await _bakim_listesi_gonder(tg, chat_id)
        return
    if tur == "bakim" and eylem == "yap":
        saat = await _makine_saati()
        try:
            kalem = await asyncio.to_thread(rapor_bakim_yapildi, arg, saat)
        except ValueError as exc:
            await tg.mesaj_gonder(chat_id, f"❌ {exc}")
            return
        await tg.mesaj_gonder(chat_id, f"✅ Kaydedildi: *{kalem.get('is')}* — makine `{saat:.1f} sa`. "
                                       f"Sonraki: `{saat + float(kalem.get('aralik_saat') or 0):.0f} sa`.")
        return
    rapor = await asyncio.to_thread(rapor_oku, arg) if re.fullmatch(r"\d{8}-\d{6}", arg) else None
    if not rapor:
        await tg.mesaj_gonder(chat_id, "❌ Rapor bulunamadı.")
        return
    oneriler, kat = rapor.get("oneriler") or [], rapor.get("kategori")
    if eylem == "ertele":
        await tg.klavye_temizle(chat_id, mesaj.get("message_id"))
        if rapor.get("uygulandi"):
            await tg.mesaj_gonder(chat_id, "ℹ️ Bu öneriler zaten uygulanmıştı.")
            return
        rapor["ertelendi"] = time.strftime("%Y-%m-%d %H:%M")
        await asyncio.to_thread(rapor_kaydet_uzerine, arg, rapor)
        await tg.mesaj_gonder(chat_id, f"⏳ Şimdilik uygulanmadı — `{kat}` ayarları aynı. Öneri bekleyenlerde duruyor; "
                                       "istediğin an `/oneriler` ile uygulayabilirsin. Sonraki baskılarda yine "
                                       "önerilebilir.")
        return
    if eylem == "uygula":
        if rapor.get("uygulandi"):
            await tg.mesaj_gonder(chat_id, "ℹ️ Bu rapordaki öneriler zaten uygulandı.")
            return
        katlar = await asyncio.to_thread(baski_kategorileri)
        etkilenen = (katlar.get(kat) or {}).get("baslik", kat)
        satir = "\n".join(f"• `{o['ayar']}`: {o['mevcut']} → *{o['onerilen']}*" for o in oneriler)
        await tg.mesaj_gonder(
            chat_id, f"⚠️ *{etkilenen}* kategorisi değişecek — bu kategorideki TÜM ürünlerin sonraki dilimlemesini "
                     f"etkiler:\n{satir}\n\nOnaylıyor musun?",
            butonlar=[[{"text": "✅ Evet, uygula", "callback_data": f"rapor:evet:{arg}"},
                       {"text": "⏳ Şimdi Değil", "callback_data": f"rapor:ertele:{arg}"}]])
        return
    if eylem == "evet":
        if rapor.get("uygulandi"):
            await tg.mesaj_gonder(chat_id, "ℹ️ Zaten uygulandı.")
            return
        await tg.klavye_temizle(chat_id, mesaj.get("message_id"))
        try:
            sonuc = await asyncio.to_thread(kategori_guncelle, kat, {o["ayar"]: o["onerilen"] for o in oneriler},
                                            None, True, f"YZ baskı raporu {arg}")
        except ValueError as exc:
            await tg.mesaj_gonder(chat_id, f"❌ Uygulanamadı: {exc}")
            return
        rapor["uygulandi"] = sonuc
        await asyncio.to_thread(rapor_kaydet_uzerine, arg, rapor)
        sku = rapor.get("sku")
        await tg.mesaj_gonder(
            chat_id, f"✅ `{kat}` kategorisi güncellendi: " + ", ".join(f"{k}={v}" for k, v in sonuc["yeni"].items())
            + "\nYeni ayarlar bir sonraki dilimlemede geçerli.",
            butonlar=[[{"text": "⚙️ Yeniden Dilimle", "callback_data": f"orca:analiz:{sku}"}]] if sku else None)


async def _teklif_baslat(tg: TelegramIstemci, chat_id: int, talep: str, klasor: Path | None = None,
                         revize: str = "") -> None:
    """Teklif: Sonnet ajanı modelleyip ölçer → Opus denetler → bot ERP ile fiyatlar → PDF."""
    if klasor is None:
        klasor = await asyncio.to_thread(yeni_teklif_klasoru)
        (klasor / "talep.txt").write_text(talep, encoding="utf-8")
    katalog_l = await asyncio.to_thread(teklif_katalog, URUNLER_KLASORU)
    malzemeler = await ERP.malzemeler()
    await tg.mesaj_gonder(chat_id, f"💼 Teklif hazırlanıyor (`{klasor.name}`): kalemler gerçek modele çevrilip "
                                   "dilimleniyor → Opus denetimi → ERP fiyatı → PDF. (~5–15 dk)")

    async def _denetim_sonrasi(basarili: bool, yanit: str, devam: str | None) -> None:
        await _teklif_fiyatla_gonder(tg, chat_id, klasor)

    async def _olcum_sonrasi(basarili: bool, yanit: str, devam: str | None) -> None:
        if teklif_oku(klasor) is None:
            await tg.mesaj_gonder(chat_id, f"⚠️ Teklif kalemleri oluşturulamadı.\n`{(yanit or '')[-400:]}`",
                                  butonlar=[[{"text": "✏️ Revize / Tekrar", "callback_data": f"teklif:revize:{klasor.name}"}]])
            return
        _ajan_arka_planda_calistir(tg, chat_id, "ceo-orchestrator", teklif_denetim_istemi(talep, klasor),
                                   gorev_ozeti=f"Teklif denetimi {klasor.name}", sonraki_islem=_denetim_sonrasi,
                                   model="opus")

    _ajan_arka_planda_calistir(tg, chat_id, "cad-artist", teklif_istemi(talep, klasor, katalog_l, malzemeler, revize),
                               gorev_ozeti=f"Teklif modelleme {klasor.name}", sonraki_islem=_olcum_sonrasi,
                               model="sonnet")


async def _teklif_fiyatla_gonder(tg: TelegramIstemci, chat_id: int, klasor: Path) -> None:
    t = await asyncio.to_thread(teklif_oku, klasor)
    hatalar = teklif_kalem_dogrula(t or {})
    revize_btn = [[{"text": "✏️ Revize", "callback_data": f"teklif:revize:{klasor.name}"}]]
    if t is None or hatalar or (t.get("denetim") or {}).get("sonuc") == "RED":
        notlar = hatalar + [f"Opus: {n}" for n in ((t or {}).get("denetim") or {}).get("notlar") or []]
        await tg.mesaj_gonder(chat_id, "⛔ Teklif fiyatlanmadı:\n• " + "\n• ".join(notlar or ["teklif.json yok"]),
                              butonlar=revize_btn)
        return
    takili = await _takili_filament()
    try:
        f = await asyncio.to_thread(teklif_fiyatla, t, ERP.base_url, takili.get("id") if takili else None, True)
    except Exception as exc:  # noqa: BLE001
        await tg.mesaj_gonder(chat_id, f"❌ ERP fiyatlama hatası: {exc}", butonlar=revize_btn)
        return
    no = f"TEKLIF-{klasor.name}"
    (klasor / "fiyat.json").write_text(json.dumps(f, ensure_ascii=False, indent=2), encoding="utf-8")
    pdf = klasor / f"{no}.pdf"
    ok = await asyncio.to_thread(teklif_pdf_uret, teklif_pdf_html(t, f, no), pdf)
    butonlar = [[{"text": "✅ Müşteriye Gönderildi", "callback_data": f"teklif:onay:{klasor.name}"},
                 {"text": "✏️ Revize", "callback_data": f"teklif:revize:{klasor.name}"}]]
    await tg.mesaj_gonder(chat_id, teklif_ozet_metni(t, f, no), butonlar=butonlar)
    if ok:
        await tg.belge_gonder(chat_id, pdf, aciklama=f"📄 {no} — müşteriye gönderilecek PDF")


async def _teklif_callback(tg: TelegramIstemci, chat_id: int, veri: str) -> None:
    parca = veri.split(":", 2)
    eylem = parca[1] if len(parca) > 1 else ""
    if eylem == "baslat":
        await asyncio.to_thread(
            tg._json_istek, "sendMessage",
            {"chat_id": chat_id, "text": f"{TEKLIF_ISTEM_BASLIGI}: müşteri, ürünler, ölçü, adet, renk, yazı metni "
                                         "(örn. 'Kahve Durağı kafe — 120 cm 'Hoş Geldiniz' duvar yazısı mat yeşil + "
                                         "30 adet QR menü standı')",
             "reply_markup": {"force_reply": True, "input_field_placeholder": "Müşteri — ürünler, ölçü, adet"}})
        return
    klasor = TEKLIF_KLASORU / (parca[2] if len(parca) > 2 else "")
    if not re.fullmatch(r"\d{8}-\d{6}", klasor.name) or not klasor.is_dir():
        await tg.mesaj_gonder(chat_id, "❌ Teklif bulunamadı.")
        return
    if eylem == "revize":
        await asyncio.to_thread(
            tg._json_istek, "sendMessage",
            {"chat_id": chat_id, "text": f"{TEKLIF_REVIZE_BASLIGI} [{klasor.name}]: neyi değiştirelim? "
                                         "(adet, ölçü, renk, kalem ekle/çıkar, indirim…)",
             "reply_markup": {"force_reply": True}})
        return
    if eylem == "onay":
        (klasor / "GONDERILDI").write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
        await tg.mesaj_gonder(chat_id, f"✅ `{klasor.name}` müşteriye gönderildi olarak işaretlendi.")


async def _takili_filament() -> dict[str, Any] | None:
    """ERP'de makine 1'e gerçekten takılı filament (tanımlı değilse None — ilk makarayı varsaymaz)."""
    makineler = await ERP.makineler()
    fid = next((m.get("loaded_filament_id") for m in makineler if int(m.get("id", 0)) == 1), None)
    if not fid:
        return None
    return next((f for f in await ERP.filamentler() if int(f.get("id", 0)) == int(fid)), None)


async def _baski_kontrolu(sku: str) -> list[dict[str, Any]]:
    urun = await asyncio.to_thread(urun_yaml_oku, sku)
    d = await asyncio.to_thread(yazici_durumu_oku)
    tabla = bool(durum_dosyasi_oku().get("tabla_bos", True))
    return baski_oncesi_kontrol(urun, await _takili_filament(), tabla, d.durum_adi)


async def _yaziciya_yukle(tg: TelegramIstemci, chat_id: int, sku: str) -> None:
    gcode = URUNLER_KLASORU / sku / "uretim" / f"{sku}.gcode"
    if not gcode.exists():
        await tg.mesaj_gonder(chat_id, f"❌ `{sku}` için dilimlenmiş G-code yok; önce ⚙️ Dilimle.")
        return
    kontrol = await _baski_kontrolu(sku)
    await tg.mesaj_gonder(chat_id, f"📤 `{sku}` yazıcı belleğine yükleniyor (baskı BAŞLATILMAZ)…")
    ok, mesaj = await asyncio.to_thread(gcode_yukle, gcode, f"{sku}.gcode")
    son = ("\n\n⛔ *Başlatmadan önce yukarıdaki engelleri gider.*" if engel_var(kontrol)
           else "\n\n▶️ Yazıcı ekranında *Dosyalar → " + f"{sku}.gcode* → Başlat. Başladığında ilk katman ve "
                "riskli katmanlarda kamera fotoğrafı göndereceğim.")
    await tg.mesaj_gonder(chat_id, f"{'✅' if ok else '❌'} {mesaj}\n\n*Baskı öncesi kontrol:*\n"
                                   f"{kontrol_metni(kontrol)}" + (son if ok else ""),
                          butonlar=[[{"text": "🔄 Kontrolü Yenile", "callback_data": f"yazici:kontrol:{sku}"}]])


def _yz_kategori_istemi(sku: str, urun: dict, mevcut: dict) -> str:
    ozet = "\n".join(f"- `{k}` ({v.get('baslik')}): {v.get('aciklama')} — {v.get('ayarlar')}" for k, v in mevcut.items())
    izinli = ", ".join(f"{k}{'∈' + str(sorted(v[1])) if v[0] == 'secim' else f' [{v[1]}–{v[2]}]'}"
                       for k, v in IZINLI_AYARLAR.items())
    return (
        f"Görev: `{sku}` ürünü için en kaliteli baskıyı verecek BASKI KATEGORİSİ belirle "
        "(Elegoo Centauri Carbon, 0.4 mm nozul, PLA Matte).\n"
        f"Ürün: `{URUNLER_KLASORU / sku}/urun.yaml` (ad, tarif, boyut, kalite_kapisi), model "
        f"`{URUNLER_KLASORU / sku}/model/{sku}.stl`, görseller `{URUNLER_KLASORU / sku}/gorsel/`.\n"
        f"Mevcut kategoriler:\n{ozet}\n\n"
        "1) Ürünü incele (geometri: ince detay, geniş düz yüz, yazı/harf, dayanım ihtiyacı, boyut).\n"
        "2) Mevcut bir kategori gerçekten uygunsa YENİ EKLEME; son satır: `KATEGORI_MEVCUT <anahtar>`.\n"
        "3) Değilse ürün TÜRÜNE (tek ürüne değil, benzer ürün ailesine) göre yeni kategori ekle:\n"
        f"   `cd {PROGRAMLAR_KLASORU} && python3 -m coo.orca_dilim kategori-ekle '<json>'` — json: "
        '{"anahtar":"kisa_ad","baslik":"…","aciklama":"…","anahtar_kelimeler":["…"],"ayarlar":{…},'
        '"gerekce":"neden bu ayarlar"}\n'
        f"   Yalnız şu ayarlar ve aralıklar kabul edilir: {izinli}. Destek ayarı YAZMA (katman analizi "
        "otomatik ekler). KATEGORI_HATA dönerse düzeltip tekrar dene (en fazla 3).\n"
        "   Son satır: `KATEGORI_TAMAM <anahtar>`.\n"
        "Yazıcıya iş gönderme, baskı başlatma; yalnızca kategori dosyasına ekle."
    )


# --- Studio araçları: Patron seçer + yazar → Claude (cad-artist) Studio'yu MCP ile kullanır → önizleme + 3MF ---
async def _studio_callback(tg: TelegramIstemci, chat_id: int, veri: str) -> None:
    parca = veri.split(":")
    eylem = parca[1] if len(parca) > 1 else "menu"
    try:
        kat = await asyncio.to_thread(studio_hatti.katalog)
    except Exception as exc:
        await tg.mesaj_gonder(chat_id, f"❌ Studio'ya ulaşılamadı (workbench-studio servisi): {exc}")
        return
    if eylem == "menu":
        await tg.mesaj_gonder(
            chat_id, "🛠️ *Studio Araçları* — aracı seç, ne istediğini yaz; Claude Studio'yu kullanarak dosyayı üretir "
                     "(önizleme + ölçü/gram + 3MF).",
            butonlar=[[{"text": f"{a['label']}", "callback_data": f"studio:aile:{a['key']}"}] for a in kat["aileler"]]
            + [[{"text": "🏠 Ana Menü", "callback_data": "menu:ana"}]])
        return
    if eylem == "aile":
        aile = parca[2]
        urunler = [u for u in kat["urunler"] if u.get("family") == aile]
        dugme = [{"text": u["label"][:30], "callback_data": f"studio:sec:{u['id']}"} for u in urunler]
        await tg.mesaj_gonder(chat_id, "Hangi araç?", butonlar=[dugme[i:i + 2] for i in range(0, len(dugme), 2)]
                              + [[{"text": "⬅️ Geri", "callback_data": "studio:menu"}]])
        return
    if eylem == "sec":
        pid = parca[2]
        u = next((x for x in kat["urunler"] if x["id"] == pid), None)
        if not u:
            await tg.mesaj_gonder(chat_id, "❌ Araç bulunamadı.")
            return
        BELLEK.studio_bekleyen = {"pid": pid, "etiket": u["label"], "ekler": []}
        await tg.mesaj_gonder(
            chat_id, f"📝 *{u['label']}* — ne istiyorsun? Ölçü, yazı, renk, montaj gibi bildiklerini yaz; eksikleri "
                     f"uygun değerlerle tamamlayıp sana söylerim.\n_{studio_hatti.ORNEKLER.get(pid, 'ör. ölçü, renk, metin')}_\n"
                     "Logo ya da referans görsel varsa önce fotoğraf olarak gönder, sonra isteği yaz.",
            butonlar=[[{"text": "❌ Vazgeç", "callback_data": "studio:iptal"}]])
        return
    if eylem == "iptal":
        BELLEK.studio_bekleyen = None
        await tg.mesaj_gonder(chat_id, "Studio isteği iptal edildi.")
        return
    if eylem == "revize":
        iid = parca[2]
        b = await asyncio.to_thread(studio_hatti.is_bilgisi, iid)
        if not b:
            await tg.mesaj_gonder(chat_id, "⚠️ Bu iş bulunamadı.")
            return
        BELLEK.studio_bekleyen = {"pid": b["pid"], "etiket": b.get("etiket", b["pid"]), "ekler": [], "onceki": iid}
        await tg.mesaj_gonder(chat_id, "✏️ Ne değişsin? (ör. _yazıyı 80 cm yap, rengi kırmızı yap, vida deliği ekle_)",
                              butonlar=[[{"text": "❌ Vazgeç", "callback_data": "studio:iptal"}]])
        return
    if eylem == "orca":
        b = await asyncio.to_thread(studio_hatti.is_bilgisi, parca[2])
        proje = Path(str((b.get("sonuc") or {}).get("proje_3mf") or ""))
        if not proje.is_file():
            await tg.mesaj_gonder(chat_id, "❌ 3MF bulunamadı.")
            return
        subprocess.Popen([ORCA_BIN, str(proje)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        await tg.mesaj_gonder(chat_id, f"🖥️ `{proje.name}` bilgisayarda OrcaSlicer'da açılıyor.")


async def _studio_uret(tg: TelegramIstemci, chat_id: int, talep: str) -> None:
    bek = BELLEK.studio_bekleyen or {}
    BELLEK.studio_bekleyen = None
    pid, etiket = bek["pid"], bek["etiket"]
    onceki = None
    if bek.get("onceki"):
        ob = await asyncio.to_thread(studio_hatti.is_bilgisi, bek["onceki"])
        onceki = {"job_dir": (ob.get("sonuc") or {}).get("job_dir"), "talep": ob.get("talep", "")}
    iid, klasor = await asyncio.to_thread(studio_hatti.yeni_is, pid)
    await asyncio.to_thread(studio_hatti.is_guncelle, iid, etiket=etiket, talep=talep, onceki=bek.get("onceki"))
    ekler = [Path(x) for x in bek.get("ekler") or []]

    async def _sonra(_ok: bool, _yanit: str, oturum: str | None) -> None:
        sonuc = await asyncio.to_thread(studio_hatti.sonuc_oku, klasor)
        if not sonuc or not sonuc.get("basarili"):
            await tg.mesaj_gonder(chat_id, f"❌ Studio üretimi tamamlanmadı: {(sonuc or {}).get('hata') or 'ajan sonuç yazmadı'}",
                                  butonlar=[[{"text": "✏️ Tekrar Dene / Değiştir", "callback_data": f"studio:revize:{iid}"},
                                             {"text": "🛠️ Studio", "callback_data": "studio:menu"}]])
            return
        await asyncio.to_thread(studio_hatti.is_guncelle, iid, sonuc=sonuc)
        metin = (f"🛠️ *{etiket}* hazır\n{sonuc.get('ozet', '')}"
                 + ("\n_Varsayımlar: " + "; ".join(sonuc.get("varsayimlar") or []) + "_" if sonuc.get("varsayimlar") else ""))
        butonlar = [[{"text": "✏️ Değiştir", "callback_data": f"studio:revize:{iid}"},
                     {"text": "🖥️ Orca'da Aç", "callback_data": f"studio:orca:{iid}"}],
                    [{"text": "🛠️ Başka Araç", "callback_data": "studio:menu"}]]
        oniz = Path(str(sonuc.get("onizleme") or ""))
        if oniz.is_file():
            await tg.foto_gonder(chat_id, oniz.read_bytes(), aciklama=metin[:1000], butonlar=butonlar, dosya_adi=oniz.name)
        else:
            await tg.mesaj_gonder(chat_id, metin, butonlar=butonlar)
        proje = Path(str(sonuc.get("proje_3mf") or ""))
        if proje.is_file():
            await tg.belge_gonder(chat_id, proje, aciklama=f"📦 {etiket} — 3MF (OrcaSlicer projesi)")

    await tg.mesaj_gonder(chat_id, f"🛠️ *{etiket}* — Claude Studio araçlarıyla üretiyor (~2–5 dk)…")
    _ajan_arka_planda_calistir(tg, chat_id, "cad-artist",
                               studio_hatti.istem(pid, etiket, talep, klasor, ekler, onceki),
                               gorev_ozeti=f"Studio {etiket}: {talep[:40]}", sonraki_islem=_sonra)


MAKS_KARTELA = 4


def _kartela_butonlari(sku: str) -> list[list[dict[str, str]]]:
    palet = palet_oku()
    sec = BELLEK.kartela.get(sku, set())
    dugmeler = [{"text": ("✅ " if i in sec else "") + f"{i + 1}. {r.get('ad')}"[:28], "callback_data": f"kartela:sec:{sku}:{i}"}
                for i, r in enumerate(palet)]
    satirlar = [dugmeler[i:i + 3] for i in range(0, len(dugmeler), 3)]
    n = len(sec)
    if n >= 1:
        satirlar.append([{"text": f"⚪ Tek renk ({'bu renk' if n == 1 else f'{n} renk varyantı'})", "callback_data": f"kartela:tek:{sku}"}])
    if n >= 2:
        satirlar.append([{"text": f"🎨 Bu {n} renkle çok renkli tasarla", "callback_data": f"kartela:cok:{sku}"}])
    satirlar.append([{"text": "🤖 YZ çok renk önersin", "callback_data": f"kartela:yz:{sku}"},
                     {"text": "📸 Kartelaya renk ekle", "callback_data": "renk:iste:"}])
    satirlar.append([{"text": "📦 Ürün Kartı", "callback_data": f"urunmenu:{sku}"}])
    return satirlar


def _kartela_metni(sku: str) -> str:
    palet = palet_oku()
    sec = sorted(BELLEK.kartela.get(sku, set()))
    secilen = ", ".join(f"{palet[i].get('ad')} `{palet[i].get('hex')}`" for i in sec if i < len(palet)) or "—"
    from .renk_paleti import delta_e

    benzer = [f"{palet[a].get('ad')} ≈ {palet[b].get('ad')}" for x, a in enumerate(sec) for b in sec[x + 1:]
              if a < len(palet) and b < len(palet) and delta_e(palet[a]["hex"], palet[b]["hex"]) < 18]
    if benzer:
        secilen += "\n⚠️ Çok benzer (baskıda ayırt edilmez): " + ", ".join(benzer)
    return (f"🎨 *Adım 3 — Renk* · `{sku}`\nKarteladan en fazla {MAKS_KARTELA} renk seç (dokun = seç/kaldır).\n"
            f"Seçili: {secilen}\n\n"
            "• *⚪ Tek renk* — ürün tek filamentle basılır; birden çok seçersen her biri ayrı mağaza varyantı olur.\n"
            "• *🎨 Çok renkli tasarla* — Claude seçtiğin renkleri Blender'da parçalara boyar (şapka, gövde, taban…), "
            "6 açıdan denetleyip onayına getirir.\n"
            "• *🤖 YZ önersin* — renkleri de Claude seçer.\n"
            "_~ işaretli renklerin kodu tahmini. Düzeltmek için bilgisayarda slider'lı kartela: "
            f"{STUDIO_URL}/kartela (ya da ekran görüntüsü gönder)._")


async def _kartela_ac(tg: TelegramIstemci, chat_id: int, sku: str, mesaj_id: int | None = None) -> None:
    if not palet_oku():
        await asyncio.to_thread(erpden_tohumla, erp_filamentleri(ayarlari_yukle().erp_url))
    yol = await asyncio.to_thread(kartela_gorseli, URUNLER_KLASORU / sku / "konsept" / "kartela.png", BELLEK.kartela.get(sku, set()))
    if mesaj_id:  # aynı mesajı güncelle (görsel + butonlar)
        with contextlib.suppress(Exception):
            await asyncio.to_thread(tg._medya_duzenle, chat_id, mesaj_id, yol, _kartela_metni(sku), _kartela_butonlari(sku))
            return
    await tg.foto_gonder(chat_id, yol.read_bytes(), aciklama=_kartela_metni(sku), butonlar=_kartela_butonlari(sku),
                         dosya_adi="kartela.png")


async def _kartela_callback(tg: TelegramIstemci, chat_id: int, veri: str, mesaj: dict[str, Any]) -> None:
    parca = veri.split(":")
    eylem, sku = parca[1], parca[2]
    palet = palet_oku()
    sec = BELLEK.kartela.setdefault(sku, set())
    if eylem == "ac":
        await _kartela_ac(tg, chat_id, sku)
        return
    if eylem == "sec":
        i = int(parca[3])
        if i in sec:
            sec.discard(i)
        elif len(sec) >= MAKS_KARTELA:
            await tg.mesaj_gonder(chat_id, f"⚠️ En fazla {MAKS_KARTELA} renk seçebilirsin (yazıcıda {MAKS_KARTELA} filament yuvası var).")
            return
        else:
            sec.add(i)
        await _kartela_ac(tg, chat_id, sku, mesaj.get("message_id"))
        return
    secilen = [palet[i] for i in sorted(sec) if i < len(palet)]
    if eylem == "tek":
        if not secilen:
            await tg.mesaj_gonder(chat_id, "⚠️ Önce karteladan en az bir renk seç.")
            return
        await asyncio.to_thread(urun_yaml_guncelle, sku, {"cok_renk": {"karar": "tek", "tarih": dt.date.today().isoformat()}})
        basarili = []
        for r in secilen:
            renk = {"ad": r.get("ad"), "hex": r.get("hex")}
            async with _yerel_is(tg, chat_id, sku, f"Renk render'ı: {renk['ad']}", 2) as k:
                k["adim"] = "Blender render"
                sonuc = await asyncio.to_thread(renk_gorselleri_uret, sku, renk)
            if sonuc.get("basarili"):
                basarili.append(sonuc)
            else:
                await tg.mesaj_gonder(chat_id, f"❌ {renk['ad']}: {sonuc.get('hata')}")
        if basarili:
            await asyncio.to_thread(urun_renklerini_kaydet, sku, basarili)
        BELLEK.kartela.pop(sku, None)
        await tg.mesaj_gonder(chat_id, f"✅ Renk kararı: tek renk — {', '.join(r.get('ad') for r in secilen)}.",
                              butonlar=_sonraki_adim_butonlari(sku))
        return
    if eylem == "cok":
        if len(secilen) < 2:
            await tg.mesaj_gonder(chat_id, "⚠️ Çok renk için karteladan en az 2 renk seç.")
            return
        await _cok_renk_baslat(tg, chat_id, sku, zorunlu=secilen)
        return
    if eylem == "yz":
        await _cok_renk_baslat(tg, chat_id, sku)
        return


async def _cok_renk_baslat(tg: TelegramIstemci, chat_id: int, sku: str, not_: str = "",
                           zorunlu: list[dict[str, Any]] | None = None, _deneme: int = 0) -> None:
    """Çok renk (Patron kararı 2026-11-16): Claude ajanı şemayı seçer, modeli Blender'da numaralı parçalara
    göre kendisi boyar, 6 açıdan denetler ve doğru olana kadar düzeltir (coo/cok_renk_claude.py) → Patron onayı."""
    k = cok_renk_hatti.klasor(sku)
    k.mkdir(parents=True, exist_ok=True)
    for ad in ("sema.json", "sema_son.json", "rapor.json", "boyali_pano.png"):
        (k / ad).unlink(missing_ok=True)
    palet = await asyncio.to_thread(palet_oku)

    async def _boyamadan_sonra(_ok: bool, yanit: str, devam: str | None) -> None:
        rapor_yolu, sema_yolu = k / "rapor.json", k / "sema_son.json"
        if not (rapor_yolu.exists() and sema_yolu.exists() and (k / "renkli.3mf").exists()):
            await tg.mesaj_gonder(chat_id, "❌ Claude çok renk boyamayı tamamlayamadı.\n" + (yanit or "")[-500:],
                                  butonlar=[[{"text": "🔁 Tekrar Dene", "callback_data": f"cokrenk:yeni:{sku}"},
                                             {"text": "⚪ Tek Renk Dilimle", "callback_data": f"cokrenk:tek:{sku}"}]])
            return
        sema = json.loads(sema_yolu.read_text(encoding="utf-8"))
        rapor = json.loads(rapor_yolu.read_text(encoding="utf-8"))
        paylar = rapor.get("alan_yuzde") or []
        satir = "\n".join(f"• *{x.get('ad')}* `{x.get('hex')}` — {x.get('parcalar', '')} (%{paylar[i] if i < len(paylar) else '?'})"
                          for i, x in enumerate(sema.get("renkler") or []))
        uyari = "\n".join(f"⚠️ {u}" for u in rapor.get("uyarilar") or [])
        metin = (f"🎨 *{sku}* — çok renk: *{sema.get('ad', '')}* (Claude, Blender, {sema.get('tur', '?')} tur denetim)\n{satir}\n"
                 f"_{sema.get('gerekce', '')}_\n🔍 {sema.get('denetim', '')}" + (f"\n{uyari}" if uyari else "")
                 + "\n\nOnaylarsan bu renklerle çok filamentli 3MF dilimlenir; gram, süre ve renk değişimi gelir.")
        pano = k / "boyali_pano.png"
        if pano.exists():
            await tg.foto_gonder(chat_id, pano.read_bytes(), aciklama=f"🎨 `{sku}` — 6 açı (ön, sağ, arka, sol, alttan)",
                                 dosya_adi="cok-renk-pano.png")
        butonlar = [[{"text": "✅ Onayla → Çok Renk 3MF", "callback_data": f"cokrenk:onay:{sku}"}],
                    [{"text": "🔁 Başka Renk Şeması", "callback_data": f"cokrenk:yeni:{sku}"},
                     {"text": "⚪ Tek Renk Dilimle", "callback_data": f"cokrenk:tek:{sku}"}]]
        foto = k / "render" / "studyo.png"
        if foto.exists():
            await tg.foto_gonder(chat_id, foto.read_bytes(), aciklama=metin[:1020], butonlar=butonlar, dosya_adi="cok-renk-studyo.png")
        else:
            await tg.mesaj_gonder(chat_id, metin, butonlar=butonlar)

    await tg.mesaj_gonder(chat_id, f"🎨 `{sku}` — Claude renk şemasını seçip modeli Blender'da boyuyor"
                                   + (f" ({', '.join(r.get('ad') for r in zorunlu)})" if zorunlu else " (paletten en fazla 4 renk)")
                                   + ". Her turda 6 açıdan kendisi denetliyor, doğru olana kadar düzeltiyor (~10–20 dk).")
    BELLEK.cok_renk_zorunlu[sku] = zorunlu or []
    _ajan_arka_planda_calistir(
        tg, chat_id, "cad-artist",
        cok_renk_hatti.claude_boyama_istemi(sku, palet, not_, BELLEK.cok_renk_onceki.get(sku), zorunlu=zorunlu),
        model="opus", gorev_ozeti=f"Çok renk (Claude+Blender): {sku}", sonraki_islem=_boyamadan_sonra,
    )


async def _cok_renk_callback(tg: TelegramIstemci, chat_id: int, veri: str) -> None:
    _, eylem, sku = veri.split(":", 2)
    k = cok_renk_hatti.klasor(sku)
    if eylem == "onay":
        sema_yolu = k / "sema_son.json"
        if not sema_yolu.exists() or not (k / "renkli.3mf").exists():
            await tg.mesaj_gonder(chat_id, "⚠️ Onaylanacak çok renk sonucu yok; yeniden hazırlıyorum.")
            await _cok_renk_baslat(tg, chat_id, sku)
            return
        sema = json.loads(sema_yolu.read_text(encoding="utf-8"))
        await asyncio.to_thread(urun_yaml_guncelle, sku, {"cok_renk": {
            "karar": "onay", "sema": sema.get("ad"), "girdi_3mf": "model/cok_renk/renkli.3mf",
            "renkler": [{"ad": r.get("ad"), "hex": r.get("hex"), "parcalar": r.get("parcalar")} for r in sema.get("renkler") or []],
            "tarih": dt.date.today().isoformat()}})
        await tg.mesaj_gonder(chat_id, f"✅ Çok renk onaylandı: *{sema.get('ad')}*. Şimdi çok filamentli dilimleme…")
        await _dilimleme_ozeti_gonder(tg, chat_id, sku)
    elif eylem == "tek":
        await asyncio.to_thread(urun_yaml_guncelle, sku, {"cok_renk": {"karar": "tek", "tarih": dt.date.today().isoformat()}})
        await _dilimleme_ozeti_gonder(tg, chat_id, sku)
    elif eylem == "yeni":
        son = k / "sema_son.json"
        if son.exists():
            BELLEK.cok_renk_onceki.setdefault(sku, []).append(json.loads(son.read_text(encoding="utf-8")).get("ad", ""))
        BELLEK.cok_renk_not_sku = sku
        await tg.mesaj_gonder(chat_id, "✏️ Renk tercihini yaz (ör. _şapka siyah, kıyafet kırmızı, tepsi ahşap_) ya da "
                                       "*devam* yaz — yeni bir şema önereyim.")
    elif eylem == "baslat":
        await _cok_renk_baslat(tg, chat_id, sku)


async def _dilimleme_ozeti_gonder(tg: TelegramIstemci, chat_id: int, sku: str, kategori: str | None = None) -> None:
    """Ürüne göre baskı kategorisi seçer, katman katman ada/sarkma analizi yapar (gerekirse yalnız tabladan
    ağaç destek), seçilen renkle Orca CLI'da gerçek dilimleme yapar → uretim/<sku>.3mf + tabla önizlemesi."""
    stl = URUNLER_KLASORU / sku / "model" / f"{sku}.stl"
    if not stl.exists():
        await tg.mesaj_gonder(chat_id, f"❌ `{sku}` için `model/{sku}.stl` yok; önce tasarım tamamlanmalı.")
        return
    urun = await asyncio.to_thread(urun_yaml_oku, sku)
    katlar = await asyncio.to_thread(baski_kategorileri)
    if kategori and kategori in katlar:
        kat, neden = kategori, "Patron seçimi"
    else:
        kat, neden = kategori_sec(urun, sku)
    bilgi = katlar[kat]
    proses = bilgi["proses"]
    katman = float((bilgi.get("ayarlar") or {}).get("layer_height", 0.2))
    renkler = [r for r in (urun.get("renkler") or []) if isinstance(r, dict) and not r.get("cok_renk")]
    renk = renkler[0] if renkler and isinstance(renkler[0], dict) else {}
    cr = urun.get("cok_renk") if isinstance(urun.get("cok_renk"), dict) else {}
    boyama = None
    if cr.get("karar") == "onay":
        if not await asyncio.to_thread(cok_renk_hatti.guncel_mi, sku):
            await tg.mesaj_gonder(chat_id, "♻️ 3B model renk onayından sonra değişmiş; renkleri yeni modele yeniden aktarıyorum.")
            await _cok_renk_baslat(tg, chat_id, sku, not_="Önceki onaylı şema: " + ", ".join(
                f"{r.get('ad')} {r.get('hex')} ({r.get('parcalar')})" for r in cr.get("renkler") or []) + " — aynısını uygula.")
            return
        boyama = {"girdi_3mf": str(URUNLER_KLASORU / sku / cr["girdi_3mf"]), "renkler": [r["hex"] for r in cr["renkler"]]}
    elif not cr.get("karar") and not renkler:
        await tg.mesaj_gonder(chat_id, f"🎨 `{sku}` dilimlemeden önce renk kararı gerekli (3MF'e filament rengi yazılır).")
        await _kartela_ac(tg, chat_id, sku)
        return
    await tg.mesaj_gonder(chat_id, f"⚙️ `{sku}` — kategori *{bilgi.get('baslik')}* (`{proses}`, {neden})\n"
                                   "Katman analizi → OrcaSlicer dilimleme… (~2–6 dk)")
    async with _yerel_is(tg, chat_id, sku, "Dilimleme (katman analizi → OrcaSlicer)", 6) as k:
        k["adim"] = "katman katman ada/sarkma analizi"
        analiz = await asyncio.to_thread(baski_analizi, stl, katman)
        k["adim"] = "OrcaSlicer dilimleme" + (" (çok renk)" if boyama else "")
        sonuc = await asyncio.to_thread(dilimle_3mf, sku, proses, destek=bool(analiz.get("destek_gerekli")),
                                        renk_hex=renk.get("hex"), boyama=boyama)
    if not sonuc.get("basarili"):
        await tg.mesaj_gonder(
            chat_id, f"❌ Dilimleme başarısız: {sonuc.get('hata')}\n```\n{str(sonuc.get('log') or '')[-600:]}\n```"
        )
        return
    tek = None
    if boyama:  # fiyat kararı için tek renk karşılaştırması (aynı ayarlarla)
        async with _yerel_is(tg, chat_id, sku, "Tek renk karşılaştırma dilimi", 3) as k:
            k["adim"] = "OrcaSlicer (yalnız gram/süre için)"
            tek = await asyncio.to_thread(dilimle_3mf, sku, proses, destek=bool(analiz.get("destek_gerekli")),
                                          renk_hex=(cr.get("renkler") or [{}])[-1].get("hex"), _sadece_ozet=True)
    sn = int(sonuc.get("sure_sn") or 0)
    gram = sonuc.get("gram")
    dil = urun.get("dilimleme") if isinstance(urun.get("dilimleme"), dict) else {}
    dil.update(
        kategori=kat, proses=proses, filament=sonuc["filament"], renk_hex=renk.get("hex"),
        cok_renk=bool(boyama), filament_gram=sonuc.get("filament_gram"), renk_degisimi=sonuc.get("renk_degisimi"),
        katman_mm=katman, gercek_gram=gram, gercek_sure_dk=round(sn / 60),
        destek_gerekli=bool(sonuc.get("destek")), destek_nedeni=analiz.get("neden") or "",
        havada_parca=analiz.get("ada_sayisi", 0),
        riskli_z_mm=riskli_z_listesi(analiz),
    )
    await asyncio.to_thread(
        urun_yaml_guncelle,
        sku,
        {"dilimleme": dil, "proje_3mf_yolu": f"uretim/{sku}.3mf", "gcode_yolu": f"uretim/{sku}.gcode",
         "durum": "URETIM_HAZIR"},
    )
    a = bilgi.get("ayarlar") or {}
    destek_satiri = (f"🌳 *Ağaç destek (yalnız tabladan):* {analiz.get('neden')}" if sonuc.get("destek")
                     else "✅ *Desteksiz:* havada başlayan parça yok")
    if analiz.get("hata"):
        destek_satiri = f"⚠️ Katman analizi yapılamadı ({analiz['hata'][:120]}); desteksiz dilimlendi — Orca'da kontrol et."
    metin = (
        f"✅ *{sku}* — baskıya hazır\n\n"
        f"• *Kategori:* {bilgi.get('baslik')} (`{proses}`)\n"
        f"• *Ayar:* katman `{katman} mm`, duvar `{a.get('wall_loops', '3')}`, dolgu `{a.get('sparse_infill_density', '15%')}`"
        f", dikiş `{a.get('seam_position', 'aligned')}`, ütü `{a.get('ironing_type', 'top')}`\n"
        f"• {destek_satiri}\n"
        f"• *Filament:* `{sonuc['filament']}`" + (
            "\n" + "\n".join(f"   {i + 1}. {r.get('ad')} `{r.get('hex')}` — "
                              f"{(sonuc.get('filament_gram') or [None] * 9)[i] if i < len(sonuc.get('filament_gram') or []) else '?'} g"
                              for i, r in enumerate(cr.get("renkler") or [])) + f"\n   🔁 Renk değişimi: *{sonuc.get('renk_degisimi')}*"
            if boyama else (f" — {renk.get('ad')} `{renk.get('hex')}`" if renk else "")) + "\n"
        + (f"• *Tek renge göre:* +{round(gram - tek['gram'])} g, +{(sn - int(tek['sure_sn'] or 0)) // 60} dk "
           f"(tek renk {tek['gram']} g)\n" if tek and tek.get("basarili") and gram and tek.get("gram") else "")
        + f"• *Orca gerçek dilimleme:* `{gram} g` • `{sn // 3600} sa {sn % 3600 // 60} dk`\n"
        f"• *Proje:* `02_Urunler/{sku}/uretim/{sku}.3mf`"
    )
    kat_butonlari = [{"text": ("✓ " if k == kat else "") + str(v.get("baslik", k)).split("/")[0].strip()[:18],
                      "callback_data": f"orca:kat:{sku}:{i}"} for i, (k, v) in enumerate(katlar.items())]
    butonlar = [
        [{"text": "📤 Yazıcıya Yükle (başlatmaz)", "callback_data": f"yazici:yukle:{sku}"},
         {"text": "🖥️ Orca'da Aç", "callback_data": f"orca:ac:{sku}"}],
        *[kat_butonlari[i:i + 3] for i in range(0, len(kat_butonlari), 3)],
        [{"text": "🧩 YZ: Bu Ürüne Yeni Kategori", "callback_data": f"orca:yzkat:{sku}"}],
        [{"text": "🎨 Rengi Değiştir (kartela)", "callback_data": f"kartela:ac:{sku}"}],
    ]
    butonlar = _sonraki_adim_butonlari(sku) + butonlar
    oniz = sonuc.get("onizleme")
    if oniz and Path(oniz).exists():
        await tg.foto_gonder(chat_id, Path(oniz).read_bytes(), aciklama=metin, butonlar=butonlar,
                             dosya_adi="tabla.png")
    else:
        await tg.mesaj_gonder(chat_id, metin, butonlar=butonlar)


async def _yz_kategori(tg: TelegramIstemci, chat_id: int, sku: str) -> None:
    urun = await asyncio.to_thread(urun_yaml_oku, sku)
    mevcut = await asyncio.to_thread(baski_kategorileri)

    async def _sonra(basarili: bool, yanit: str, devam_anahtari: str | None) -> None:
        bulunan = list(re.finditer(r"KATEGORI_(TAMAM|MEVCUT)\s+([a-z0-9_]+)", yanit or ""))
        m = bulunan[-1] if bulunan else None  # son söz Opus denetiminin
        katlar = await asyncio.to_thread(baski_kategorileri)
        if not m or m.group(2) not in katlar:
            await tg.mesaj_gonder(chat_id, f"⚠️ `{sku}` için kategori eklenemedi.\n`{(yanit or '')[-300:]}`")
            return
        k = katlar[m.group(2)]
        yeni = m.group(1) == "TAMAM"
        await tg.mesaj_gonder(
            chat_id,
            (f"🧩 Yeni kategori eklendi: *{k.get('baslik')}* (`{k['proses']}`)\n• {k.get('aciklama')}\n"
             f"• Ayarlar: `{k.get('ayarlar')}`\n• Gerekçe: {k.get('gerekce', '')}" if yeni else
             f"🧩 Mevcut kategori uygun bulundu: *{k.get('baslik')}*") + "\nŞimdi bu kategoriyle dilimleniyor…")
        await _dilimleme_ozeti_gonder(tg, chat_id, sku, kategori=m.group(2))

    denetim = _opus_denetim_istemi(
        f"`{sku}` için baskı kategorisi seçti/ekledi", [str(CONFIG_KLASORU / "orca" / "kategoriler.yaml")],
        "- Eklenen kategori varsa ayarları ürün tipi için mantıklı mı (0.4 nozul, PLA)? Gereksiz yere yeni kategori "
        "açıldıysa ve mevcut biri uygunsa yenisini sil ve son satırda o mevcut anahtarı `KATEGORI_MEVCUT <anahtar>` "
        "olarak da yaz.")
    _ajan_arka_planda_calistir(tg, chat_id, "slicer-engineer", _yz_kategori_istemi(sku, urun, mevcut),
                               gorev_ozeti=f"{sku} baskı kategorisi",
                               sonraki_islem=_opus_denetimli(tg, chat_id, f"kategori {sku}", denetim, _sonra))


async def _medya_indir_ve_kurgula(
    tg: TelegramIstemci,
    chat_id: int,
    dosya_id: str,
    video_mu: bool,
    sku: str,
    aciklama: str = "",
) -> None:
    medya_klasoru = URUNLER_KLASORU / sku / "medya"
    medya_klasoru.mkdir(parents=True, exist_ok=True)
    hedef_dosya = medya_klasoru / ("kullanici-cekim.mp4" if video_mu else "kullanici-foto.jpg")

    await tg.mesaj_gonder(
        chat_id,
        f"⏳ `{sku}` için medya indiriliyor ve **Reels (9:16) + Pinterest Pin (2:3)** kurgulanıyor...",
    )

    ok = await tg.dosya_indir(dosya_id, hedef_dosya)
    if not ok:
        await tg.mesaj_gonder(chat_id, "❌ Medya dosyası Telegram'dan indirilemedi.")
        return

    kanca_baslik: str | None = None
    temiz_aciklama = re.sub(
        r"(bundan\s+i[çc]erik\s+[üu]ret|i[çc]erik\s+[üu]ret|" + re.escape(sku) + r")",
        "",
        aciklama,
        flags=re.IGNORECASE,
    ).strip(" -:,.")
    if len(temiz_aciklama) >= 6:
        kanca_baslik = temiz_aciklama

    sonuc = await asyncio.to_thread(tam_medya_paketi_uret, sku, kanca_baslik)
    await tg.mesaj_gonder(
        chat_id,
        f"✅ *`{sku}` Sosyal Medya ve E-Ticaret Paketi Hazır!*\n"
        f"• *Kaydedilen Çekim:* `02_Urunler/{sku}/medya/{hedef_dosya.name}`\n"
        f"• *Paylaşım Metinleri:* `02_Urunler/{sku}/medya/paylasim-metinleri.md`",
    )

    await _medya_paketi_gonder(tg, chat_id, sku, sonuc)


async def _yazici_durum_gonder(tg: TelegramIstemci, chat_id: int) -> None:
    d = await asyncio.to_thread(yazici_durumu_oku)
    yerel = durum_dosyasi_oku()
    tabla_etiket = "✅ Boş (Yeni baskıya hazır)" if yerel.get("tabla_bos", True) else "⚠️ Dolu (Parça tablada)"
    if not d.bagli:
        await tg.mesaj_gonder(
            chat_id,
            f"🔌 *Yazıcı Bağlantısı Yok*\n• *Durum:* `{d.hata_mesaji or 'Ulaşılamıyor'}`\n• *Tabla:* {tabla_etiket}",
        )
        return

    gecen_dk = d.gecen_saniye // 60
    toplam_dk = d.toplam_saniye // 60
    ozet = (
        f"🖨️ *Elegoo Centauri Carbon — {d.durum_adi}*\n"
        f"• *Son/Aktif Dosya:* `{d.dosya_adi or '-'}`\n"
        f"• *İlerleme:* `%{d.ilerleme_yuzde:.1f}` (Katman `{d.mevcut_katman}/{d.toplam_katman}`)\n"
        f"• *Süre:* `{gecen_dk} dk / {toplam_dk} dk`\n"
        f"• *Nozul:* `{d.nozul_sicaklik:.1f}°C` (Hedef: `{d.nozul_hedef:.0f}°C`)\n"
        f"• *Tabla:* `{d.tabla_sicaklik:.1f}°C` (Hedef: `{d.tabla_hedef:.0f}°C`)\n"
        f"• *Tabla Durumu:* {tabla_etiket}"
    )
    butonlar = [[{"text": "🧹 Tabla Boşaltıldı", "callback_data": "tabla:bos"}]]
    if d.durum_adi == "BASKIDA":
        butonlar.append([{"text": "🛑 Baskıyı Durdur", "callback_data": "hata:durdur"}])
    elif d.durum_adi == "TAMAMLANDI" and d.dosya_adi:
        butonlar.append([{"text": "🧾 Son Baskıyı Muhasebeleştir", "callback_data": "baski:sor"}])

    kare = await asyncio.to_thread(kamera_karesi_al)
    if kare:
        await tg.foto_gonder(chat_id, kare, aciklama=ozet, butonlar=butonlar)
    else:
        await tg.mesaj_gonder(chat_id, ozet, butonlar=butonlar)


async def mesaj_isle(tg: TelegramIstemci, mesaj: dict[str, Any], yetkili_chat_id: int) -> None:
    chat_id = int((mesaj.get("chat") or {}).get("id") or 0)
    if yetkili_chat_id and chat_id != yetkili_chat_id:
        return

    # 1) Video / Fotoğraf kontrolü ("bundan içerik üret")
    aciklama = str(mesaj.get("caption") or "").strip()
    dosya_id: str | None = None
    video_mu = True
    if "video" in mesaj:
        dosya_id = mesaj["video"].get("file_id")
        video_mu = True
    elif "animation" in mesaj:
        dosya_id = mesaj["animation"].get("file_id")
        video_mu = True
    elif "document" in mesaj and str(mesaj["document"].get("mime_type") or "").startswith("video/"):
        dosya_id = mesaj["document"].get("file_id")
        video_mu = True
    elif "photo" in mesaj and mesaj["photo"]:
        dosya_id = mesaj["photo"][-1].get("file_id")
        video_mu = False
    elif "document" in mesaj and str(mesaj["document"].get("mime_type") or "").startswith("image/"):
        dosya_id = mesaj["document"].get("file_id")  # sıkıştırılmadan gönderilen ekran görüntüsü
        video_mu = False
    elif "document" in mesaj and str(mesaj["document"].get("mime_type") or "") == "application/pdf":
        dosya_id = mesaj["document"].get("file_id")  # fatura / alım belgesi (PDF)
        video_mu = False
    pdf_mu = "document" in mesaj and str(mesaj["document"].get("mime_type") or "") == "application/pdf"

    album_id = str(mesaj.get("media_group_id") or "") or None
    if dosya_id and not video_mu and (pdf_mu or aciklama_alim_mi(aciklama) or BELLEK.alim_bekleniyor
                                      or (album_id and album_id in BELLEK.alim_albumleri)):
        await _alim_belgesi_al(tg, chat_id, dosya_id, pdf_mu, album_id, aciklama)
        return
    if dosya_id and not video_mu and album_id and album_id in BELLEK.fikir_albumleri:
        hedef = await asyncio.to_thread(referans_yolu, BELLEK.fikir_albumleri[album_id])
        await tg.dosya_indir(dosya_id, hedef)
        return
    yanitlanan_metin = str((mesaj.get("reply_to_message") or {}).get("text") or "")
    m_fikir = re.match(r"^\s*/?fikir\b[:\s]*(.*)$", aciklama, flags=re.I | re.S)
    if dosya_id and not video_mu and (m_fikir or yanitlanan_metin.startswith(FIKIR_ISTEM_BASLIGI)):
        await _yeni_fikir(tg, chat_id, (m_fikir.group(1) if m_fikir else aciklama).strip(), dosya_id, album_id)
        return

    renk_sku = aciklamadan_renk_sku(aciklama) if not video_mu else None
    m_numune = re.match(r"^\s*numune\s+([a-z0-9-]+)\s*$", aciklama, flags=re.I) if not video_mu else None
    if dosya_id and not video_mu and (m_numune or BELLEK.numune_bekleyen_sku):
        hedef_sku = (m_numune.group(1).lower() if m_numune else BELLEK.numune_bekleyen_sku) or ""
        BELLEK.numune_bekleyen_sku = None
        await _numune_kaydet(tg, chat_id, dosya_id, hedef_sku)
        return

    m_palet = re.match(r"^\s*(palet|renk)\b\s*(.*)$", aciklama, flags=re.I | re.S) if not video_mu else None
    if dosya_id and not video_mu and BELLEK.studio_bekleyen:
        hedef = studio_hatti.IS_KLASORU / "ekler" / f"{uuid.uuid4().hex[:8]}{'.pdf' if pdf_mu else '.jpg'}"
        hedef.parent.mkdir(parents=True, exist_ok=True)
        if await tg.dosya_indir(dosya_id, hedef):
            BELLEK.studio_bekleyen.setdefault("ekler", []).append(str(hedef))
            if aciklama.strip():
                await _studio_uret(tg, chat_id, aciklama.strip())
            else:
                await tg.mesaj_gonder(chat_id, "📎 Eklendi. Şimdi isteğini yaz (ölçü, yazı, renk…).")
        return
    if dosya_id and not video_mu and (renk_sku or m_palet or BELLEK.renk_bekleyen_sku is not None):
        hedef_sku = renk_sku or BELLEK.renk_bekleyen_sku or None
        BELLEK.renk_bekleyen_sku = None
        not_ = (m_palet.group(2).strip() if m_palet and not renk_sku else "")
        await _renk_ornegi_isle(tg, chat_id, dosya_id, hedef_sku, not_)
        return

    if dosya_id:
        eslesen_sku = _metinden_sku_bul(aciklama)
        skular = _mevcut_skulari_listele()
        if not eslesen_sku and len(skular) == 1:
            eslesen_sku = skular[0]
        elif not eslesen_sku and not skular:
            eslesen_sku = "genel-urun"

        if eslesen_sku:
            await _medya_indir_ve_kurgula(tg, chat_id, dosya_id, video_mu, eslesen_sku, aciklama)
            return

        medya_kayit_id = uuid.uuid4().hex[:8]
        BELLEK.bekleyen_medyalar[medya_kayit_id] = {
            "dosya_id": dosya_id,
            "video_mu": video_mu,
            "aciklama": aciklama,
        }
        butonlar = [[{"text": f"📦 {s}", "callback_data": f"medya:sec:{medya_kayit_id}:{s}"}] for s in skular[:8]]
        await tg.mesaj_gonder(
            chat_id,
            "🎬 Gönderdiğiniz çekimi hangi ürünün klasörüne kaydedip **Reels / TikTok / Pinterest** kurgusunu başlatayım?",
            butonlar=butonlar,
        )
        return

    metin = str(mesaj.get("text") or "").strip()
    yanitlanan = str((mesaj.get("reply_to_message") or {}).get("text") or "")
    if metin and not metin.startswith("/") and yanitlanan.startswith(FIKIR_ISTEM_BASLIGI):
        metin = f"/fikir {metin}"
    if metin and not metin.startswith("/") and yanitlanan.startswith(KONSEPT_ISTEM_BASLIGI):
        try:
            k = await asyncio.to_thread(konsept_kaydet, metin)
        except ValueError as exc:
            await tg.mesaj_gonder(chat_id, f"❌ {exc}")
            return
        await tg.mesaj_gonder(chat_id, f"✅ Konsept kaydedildi: *{k['baslik']}* (`{k['yol'].name}`).\n"
                                       "Ürün kartında 🎨 Konsept Görsel + Reels ile kullanabilirsin.")
        return
    if metin and not metin.startswith("/") and yanitlanan.startswith(TREND_ISTEM_BASLIGI):
        metin = f"/trend {metin}"
    if metin and not metin.startswith("/") and yanitlanan.startswith(TEKLIF_ISTEM_BASLIGI):
        await _teklif_baslat(tg, chat_id, metin)
        return
    if metin and not metin.startswith("/") and yanitlanan.startswith(TEKLIF_REVIZE_BASLIGI):
        m_id = re.search(r"\[(\d{8}-\d{6})\]", yanitlanan)
        klasor = TEKLIF_KLASORU / m_id.group(1) if m_id else None
        if not (klasor and klasor.is_dir()):
            await tg.mesaj_gonder(chat_id, "❌ Teklif bulunamadı.")
            return
        talep = (klasor / "talep.txt").read_text(encoding="utf-8") if (klasor / "talep.txt").exists() else metin
        await _teklif_baslat(tg, chat_id, talep, klasor=klasor, revize=metin)
        return
    if metin and not metin.startswith("/") and yanitlanan.startswith(TARTI_ISTEM_BASLIGI):
        m_sku = re.search(r"\[([a-z0-9_-]+)\]", yanitlanan)
        g = tarti_cozumle(metin)
        if not (m_sku and g and (URUNLER_KLASORU / m_sku.group(1)).is_dir()):
            await tg.mesaj_gonder(chat_id, "❌ Gram anlaşılamadı. Örnek: 268,4")
            return
        urun = await asyncio.to_thread(urun_yaml_oku, m_sku.group(1))
        dil = urun.get("dilimleme") if isinstance(urun.get("dilimleme"), dict) else {}
        dil["gercek_numune_gram"] = g
        await asyncio.to_thread(urun_yaml_guncelle, m_sku.group(1), {"dilimleme": dil})
        await tg.mesaj_gonder(chat_id, f"`{m_sku.group(1)}` " + tarti_ozeti(g, float(dil.get("gercek_gram") or 0)))
        return
    if metin and not metin.startswith("/") and yanitlanan.startswith(FIYAT_ISTEM_BASLIGI):
        m_sku = re.search(r"\[([a-z0-9-]+)\]", yanitlanan)
        tl = fiyat_coz(metin)
        paket, _ = await asyncio.to_thread(paket_oku, m_sku.group(1)) if m_sku else (None, [])
        if not (m_sku and tl and paket):
            await tg.mesaj_gonder(chat_id, "❌ Fiyat anlaşılamadı veya paket yok. Örnek: 499,90")
            return
        taban = float((paket.get("maliyet") or {}).get("basa_bas_tl") or 0)
        if tl < taban:
            await tg.mesaj_gonder(chat_id, f"⚠️ {tl:.2f} TL başa baş fiyatın ({taban:.2f} TL) altında; kaydedilmedi.")
            return
        await _fiyat_karari_uygula_ve_goster(tg, chat_id, m_sku.group(1), paket, secilen_tl=tl)
        return
    if metin and not metin.startswith("/") and yanitlanan.startswith(STUDYO_REVIZE_BASLIGI):
        m_sku = re.search(r"\[([a-z0-9-]+)\]", yanitlanan)
        if m_sku and (URUNLER_KLASORU / m_sku.group(1)).is_dir():
            await _studyo_denetle(tg, chat_id, m_sku.group(1), not_=metin)
            return
    if metin and not metin.startswith("/") and yanitlanan.startswith(ICERIK_REVIZE_BASLIGI):
        m_sku = re.search(r"\[([a-z0-9-]+)\]", yanitlanan)
        if m_sku and (URUNLER_KLASORU / m_sku.group(1)).is_dir():
            await asyncio.to_thread(urun_yaml_guncelle, m_sku.group(1), {"icerik_revize_notu": metin})
            # İçerik notu kullanım görseli/Reels içindir (stüdyo karelerinin kendi revizesi var). Numune yoksa
            # stüdyo karesinden (numunesiz) üret — eskiden burada stüdyo kareleri yeniden üretiliyor, not kayboluyordu.
            numune_var = await asyncio.to_thread(numune_fotograflari, m_sku.group(1))
            await _kullanim_uret(tg, chat_id, m_sku.group(1), revize_notu=metin, numunesiz=not numune_var)
            return
    if not metin:
        return

    parcalar = metin.split()
    komut = parcalar[0].lower().split("@")[0]
    argumanlar = parcalar[1:]
    arg_metin = " ".join(argumanlar).strip()

    if komut == "/teklif":
        if arg_metin:
            await _teklif_baslat(tg, chat_id, arg_metin)
        else:
            await _teklif_callback(tg, chat_id, "teklif:baslat")
        return

    if komut == "/oneriler":
        bekleyen = await asyncio.to_thread(rapor_bekleyen_oneriler)
        if not bekleyen:
            await tg.mesaj_gonder(chat_id, "✅ Bekleyen dilimleme önerisi yok.")
            return
        satirlar, butonlar = ["⚙️ *Bekleyen dilimleme önerileri*"], []
        for b in bekleyen:
            ozet = ", ".join(f"{o['ayar']} → {o['onerilen']}" for o in b["oneriler"])
            tarih = f"{b['rid'][6:8]}.{b['rid'][4:6]} {b['rid'][9:11]}:{b['rid'][11:13]}"
            satirlar.append(f"• `{tarih}` {b.get('sku') or ''} (`{b['kategori']}`): {ozet}"
                            + (" — ⏳ ertelendi" if b.get("ertelendi") else ""))
            butonlar.append([{"text": f"⚙️ Uygula {tarih} ({b['kategori']})", "callback_data": f"rapor:uygula:{b['rid']}"}])
        await tg.mesaj_gonder(chat_id, "\n".join(satirlar)[:3900], butonlar=butonlar)
        return

    if komut == "/bakim":
        await _bakim_listesi_gonder(tg, chat_id)
        return

    if komut == "/kilavuz":
        k_metin, k_butonlar = kilavuz_dizini()
        await tg.mesaj_gonder(chat_id, k_metin, butonlar=k_butonlar)
        return

    if komut in ("/start", "/yardim", "/menu"):
        yardim = (
            f"🏭 *{MAGAZA_ADI}*\n\n"
            "*Akış:* 🔎 Trend → 💡 Fikir → 🎨 Konsept seç (Onay ①) → 🧊 3B model + 💹 Pazar fiyatı → "
            "⚙️ Dilimle (3MF) → 🎨 Renk → 🎬 Görsel & İçerik → 📋 Onay ② → 🛒 Mağazaya Hazırla (fiyat seçimi) "
            "→ 🚀 Yükle\n\n"
            "Her ürünün işlemleri *📦 Ürünlerim* içindeki ürün kartında.\n"
            "Komutlar: /trend /fikir /urunler /durum /ozet /stok /kuyruk /gorevler /iptal\n"
            "📖 Ayrıntılı anlatım: /kilavuz\n"
            "_Düz mesaj yazarsan aktif ajana gider (🤖 Ajanlarla Konuş)._"
        )
        await tg.mesaj_gonder(chat_id, yardim, butonlar=_ust_yonetim_butonlari())

    elif komut == "/urunler":
        await _urunler_menusu_gonder(tg, chat_id)

    elif komut in ("/ceo", "/cto", "/cmo"):
        hedef_ajan = KISA_AJAN_ESLEME[komut.lstrip("/")]
        BELLEK.aktif_muhatap_ajan = hedef_ajan
        unvan, _ = AJAN_KATALOGU[hedef_ajan]
        if not arg_metin:
            await tg.mesaj_gonder(
                chat_id,
                f"✅ Aktif konuşma muhatabınız *{unvan}* olarak ayarlandı.\n"
                f"Şimdi doğrudan mesajınızı yazabilirsiniz (veya `{komut} <mesajınız>` şeklinde gönderebilirsiniz).",
                butonlar=_ust_yonetim_butonlari(),
            )
            return
        await _claude_ajana_sor_ve_yanitla(tg, chat_id, hedef_ajan, arg_metin)

    elif komut in ("/ajan", "/ajanlar"):
        if not argumanlar:
            satirlar = ["🤖 *21 Uzman Ajan Kadrosu (`.claude/agents/`)*\n"]
            for kod, (unvan, dept) in AJAN_KATALOGU.items():
                satirlar.append(f"• `{kod}` — {unvan} _({dept})_")
            satirlar.append("\n💡 Bir ajana doğrudan emir vermek için:\n`/ajan <ajan-kodu> <mesajınız>`\nveya aşağıdan seçin:")
            await tg.mesaj_gonder(chat_id, "\n".join(satirlar), butonlar=_ust_yonetim_butonlari())
            return
        secilen = argumanlar[0].lower()
        gorev = " ".join(argumanlar[1:]).strip()
        if not gorev:
            hedef = KISA_AJAN_ESLEME.get(secilen, secilen)
            if hedef in AJAN_KATALOGU:
                BELLEK.aktif_muhatap_ajan = hedef
                unvan, _ = AJAN_KATALOGU[hedef]
                await tg.mesaj_gonder(chat_id, f"✅ Aktif muhatabınız *{unvan}* (`{hedef}`) oldu. Mesajınızı yazabilirsiniz.")
                return
        await _claude_ajana_sor_ve_yanitla(tg, chat_id, secilen, gorev or "Durum raporu ver.")

    elif komut == "/durum":
        await _yazici_durum_gonder(tg, chat_id)

    elif komut == "/tabla":
        tabla_bos_isaretle(True)
        await tg.mesaj_gonder(chat_id, "🧹 Tabla **boş ve yeni baskıya hazır** olarak işaretlendi.")

    elif komut in ("/ozet", "/durumlar"):
        await _urun_ozet_gonder(tg, chat_id, arg_metin)

    elif komut == "/flow":
        if not argumanlar:
            skular = _mevcut_skulari_listele()
            if not skular:
                await tg.mesaj_gonder(chat_id, "Kullanım: `/flow <sku> [senaryo notu]`")
                return
            butonlar = [[{"text": f"🌊 {s}", "callback_data": f"flow:uret:{s[:48]}"}] for s in skular[:8]]
            await tg.mesaj_gonder(
                chat_id,
                "Hangi ürün için numune fotoğrafından Flow kullanım görselleri + 9:16 video üreteyim?",
                butonlar=butonlar,
            )
            return
        sku = argumanlar[0].strip()
        senaryo_notu = " ".join(argumanlar[1:]).strip()
        await _flow_uretimi_baslat(tg, chat_id, sku, senaryo_notu)

    elif komut == "/stok":
        filamentler = await ERP.filamentler()
        malzemeler = await ERP.malzemeler()
        uyarilar = await ERP.kritik_stok_kontrol()
        satirlar = ["📊 *ERP Stok ve Hammadde Durumu*\n"]
        if filamentler:
            satirlar.append("*🧵 Filamentler:*")
            for f in filamentler:
                satirlar.append(
                    f"• `#{f.get('id')}` {f.get('brand', '')} {f.get('material_type', '')} {f.get('color_name', '')}: "
                    f"*{f.get('remaining_weight_gr', 0):.0f} g* · {f.get('price_per_kg_tl', 0):.0f} TL/kg"
                )
        else:
            satirlar.append("• *Filament:* ERP'de kayıtlı filament yok.")
        if malzemeler:
            satirlar.append("\n*📦 Ambalaj & Yardımcı Malzemeler:*")
            for m in malzemeler:
                satirlar.append(f"• {m.get('name', '')}: *{m.get('stock_quantity', 0)} {m.get('unit', 'adet')}*")
        if uyarilar:
            satirlar.append("\n🚨 *Kritik Stok Uyarıları:*")
            for u in uyarilar:
                satirlar.append(f"• {u}")
        butonlar = [[{"text": "🧾 Fatura / Alım Gir", "callback_data": "alim:bekle"}]] + [
            [{"text": f"🔄 Makineye Tak: {f.get('brand', '')} {f.get('color_name', '')}", "callback_data": f"fil:tak:{f.get('id')}"}]
            for f in filamentler[:6]
        ]
        await tg.mesaj_gonder(chat_id, "\n".join(satirlar), butonlar=butonlar)

    elif komut == "/kuyruk":
        kuyruk = await ERP.kuyruk()
        if not kuyruk:
            await tg.mesaj_gonder(chat_id, "📭 ERP üretim kuyruğunda bekleyen veya üretimde olan iş yok.")
            return
        satirlar = ["📋 *ERP Üretim Kuyruğu*\n"]
        for k in kuyruk[:15]:
            satirlar.append(
                f"• `#{k.get('id')}` *{k.get('product_name') or k.get('notes') or 'Üretim'}* "
                f"— Durum: `{k.get('status')}` • Adet: `{k.get('quantity', 1)}`"
            )
        await tg.mesaj_gonder(chat_id, "\n".join(satirlar))

    elif komut == "/dilimle":
        if not argumanlar:
            skular = _mevcut_skulari_listele()
            if not skular:
                await tg.mesaj_gonder(chat_id, "Kullanım: `/dilimle <sku>` (Örn: `/dilimle kase-chawan`)")
                return
            butonlar = [[{"text": f"⚙️ {s}", "callback_data": f"orca:analiz:{s}"}] for s in skular[:8]]
            await tg.mesaj_gonder(chat_id, "Hangi ürünü OrcaSlicer ile dilimleyip 3MF hazırlayayım?", butonlar=butonlar)
            return
        await _dilimleme_ozeti_gonder(tg, chat_id, argumanlar[0].strip())

    elif komut == "/hammadde":
        sorgu = arg_metin
        if not sorgu:
            await tg.mesaj_gonder(
                chat_id,
                "Kullanım: `/hammadde <aranacak malzeme>`\nÖrnek: `/hammadde mat pla krem 1.75mm fiyat performans`",
            )
            return
        HAMMADDE_KLASORU.mkdir(parents=True, exist_ok=True)
        simdi = dt.datetime.now()
        tarih_str = simdi.strftime("%Y-%m-%d")
        slug = re.sub(r"[^a-z0-9]+", "-", sorgu.lower()).strip("-")[:40] or "hammadde"
        rapor_yolu = HAMMADDE_KLASORU / f"{tarih_str}-{slug}.md"
        talep_dosyasi = HAMMADDE_KLASORU / "bekleyen_talepler.json"
        talepler = []
        if talep_dosyasi.exists():
            try:
                talepler = json.loads(talep_dosyasi.read_text(encoding="utf-8"))
            except Exception:
                talepler = []
        talepler.append(
            {
                "id": uuid.uuid4().hex[:8],
                "sorgu": sorgu,
                "tarih": simdi.isoformat(timespec="seconds"),
                "durum": "BEKLIYOR",
                "hedef_dosya": str(rapor_yolu.relative_to(ayarlari_yukle().workspace)),
            }
        )
        talep_dosyasi.write_text(json.dumps(talepler, ensure_ascii=False, indent=2), encoding="utf-8")
        await tg.mesaj_gonder(
            chat_id,
            f"🧾 *Hammadde Fiyat/Performans Araştırma Talebi Kaydedildi (`{sorgu}`)*\n"
            f"Şimdi `finance-tracker` (Muhasebe Ekibi) ajanını çalıştırıyorum...",
        )
        await _claude_ajana_sor_ve_yanitla(
            tg,
            chat_id,
            "finance-tracker",
            f"Kullanıcı Telegram'dan '{sorgu}' için fiyat/performans hammadde araştırması istedi. "
            f"Sonucu {rapor_yolu.relative_to(ayarlari_yukle().workspace)} dosyasına kaydet ve özetini paylaş.",
        )

    elif komut == "/fikir":
        if not arg_metin:
            await _fikir_istemi_gonder(tg, chat_id)
            return
        revize = re.match(r"^([a-z0-9-]+)\s+revize:\s*(.+)$", arg_metin, flags=re.I | re.S)
        if revize and (URUNLER_KLASORU / revize.group(1)).is_dir():
            sku, notu = revize.group(1), revize.group(2).strip()
            notu, yeni_linkler = referans_ayir(notu)
            bilgi = await asyncio.to_thread(fikir_bilgisi, sku)
            if yeni_linkler:
                await asyncio.to_thread(fikir_linkleri_ekle, sku, yeni_linkler)
                await _linkleri_referansa_al(tg, chat_id, sku, yeni_linkler)
            await asyncio.to_thread(urun_yaml_guncelle, sku, {"revize_notu": notu})
            await _fikir_konsept_baslat(tg, chat_id, sku, bilgi["tarif"], revize_notu=notu)
            return
        await _yeni_fikir(tg, chat_id, arg_metin)

    elif komut == "/konsept":
        liste = await asyncio.to_thread(konseptler)
        await tg.mesaj_gonder(
            chat_id, "🎨 *Konsept kütüphanesi*\n" + ("\n".join(f"• *{k['baslik']}* — {k['aciklama']}" for k in liste)
                                                  or "Henüz konsept yok.")
            + "\n\nÜrüne uygulamak: ürün kartı → 🎨 Konsept Görsel + Reels",
            butonlar=[[{"text": "➕ Yeni Konsept Ekle", "callback_data": "konsept:ekle"}]])

    elif komut == "/reels":
        if arg_metin.lower() in ("takvim", "ac", "aç"):
            await tg.mesaj_gonder(chat_id, f"🗓️ Reels takvimi: {reels_takvim.SAYFA}")
            return
        istek = await asyncio.to_thread(reels_takvim.istek_ekle, "yeni_fikirler", arg_metin, None, 7)
        await tg.mesaj_gonder(chat_id, f"🎬 7 trend Reels fikri sıraya alındı{(' (tema: ' + arg_metin + ')') if arg_metin else ''}. "
                                       f"Claude trendleri araştırıp takvime yerleştirecek (~5–10 dk).\n"
                                       f"Takvim: {reels_takvim.SAYFA}\n_(`/reels takvim` yalnız bağlantıyı verir.)_")
        return

    elif komut == "/trend":
        if not arg_metin:
            await asyncio.to_thread(
                tg._json_istek, "sendMessage",
                {"chat_id": chat_id, "text": f"{TREND_ISTEM_BASLIGI}\nÖrnek: karakterli saksılar • masaüstü dekor • "
                 "anneler günü hediyelik • genel", "reply_markup": {"force_reply": True,
                                                                   "input_field_placeholder": "Konu…"}},
            )
            return
        await _trend_arastir(tg, chat_id, "" if arg_metin.lower() == "genel" else arg_metin)

    elif komut == "/b2c":
        if not arg_metin or arg_metin.lower() in ("liste", "vitrin") or (B2C_ONERILER_KLASORU / f"{paket_id_temizle(arg_metin)}.json").exists():
            hedef_pid = None if (not arg_metin or arg_metin.lower() in ("liste", "vitrin")) else arg_metin
            await _b2c_vitrini_gonder(tg, chat_id, hedef_pid)
            return

        await _trend_arastir(tg, chat_id, arg_metin)

    elif komut == "/gelistir":
        if not arg_metin:
            await tg.mesaj_gonder(
                chat_id,
                "Kullanım:\n"
                "• `/gelistir <no>` — Son B2C öneri paketindeki numaralı ürünü geliştir (ör: `/gelistir 1`)\n"
                "• `/gelistir <paket_id>:<idx>` — Belirli paketten ürün geliştir\n"
                "• `/gelistir <ürün fikri>` — Yeni ürünü doğrudan `build123d`/Blender ile başlat",
            )
            return
        if ":" in arg_metin and arg_metin.split(":", 1)[1].strip().isdigit():
            pid_raw, idx_raw = arg_metin.split(":", 1)
            await _b2c_aday_gelistir(tg, chat_id, pid_raw.strip(), max(0, int(idx_raw.strip()) - 1))
            return
        if arg_metin.strip().isdigit():
            paket = paket_yukle()
            if not paket:
                await tg.mesaj_gonder(chat_id, "❌ Kayıtlı B2C öneri paketi bulunamadı. Önce `/b2c` çalıştırın.")
                return
            await _b2c_aday_gelistir(tg, chat_id, str(paket["paket_id"]), max(0, int(arg_metin.strip()) - 1))
            return
        await _claude_ajana_sor_ve_yanitla(
            tg,
            chat_id,
            "cad-artist",
            f"Yeni B2C endüstriyel ürün fikrini sıfırdan geliştir (Studio 2B ekstrüzyonu KULLANMA; build123d/BOSL2/Blender bpy kullan, `coo.kalite_kapisi --mod b2c` ve Cycles `studyo.png` üret): {arg_metin}",
        )

    elif komut in ("/islemler", "/gorevler"):
        if BELLEK.yerel_isler:
            yerel = ["🖥️ *Bu bilgisayarda çalışan / sıradaki işler:*"] + [
                ("⏳ " if k["durum"] == "çalışıyor" else "🕒 ") + f"{k['ad']} — `{k['sku']}`"
                + (f" • {k.get('adim')}" if k["durum"] == "çalışıyor" and k.get("adim") else "")
                + (f" • {_sure_bicimle(time.monotonic() - k['baslangic'])}" if k["durum"] == "çalışıyor" else " • sırada")
                for k in BELLEK.yerel_isler.values()]
            await tg.mesaj_gonder(chat_id, "\n".join(yerel))
        elif not BELLEK.aktif_gorevler:
            await tg.mesaj_gonder(chat_id, "🖥️ Bilgisayarda şu an çalışan 3B / görsel / dilimleme işi yok.")
        if not BELLEK.aktif_gorevler:
            son = _oturum_al()
            ek_not = ""
            butonlar = _ust_yonetim_butonlari()
            if son:
                anahtar, kayit = son
                ek_not = f"\n\n💡 Son tamamlanan/yarıda kalan oturum: `{kayit.get('ajan')}` — _{kayit.get('ozet', '')}_"
                butonlar = _gorev_sonu_butonlari(anahtar)
            await tg.mesaj_gonder(
                chat_id,
                "📭 Şu anda arka planda çalışan uzun bir ajan görevi yok." + ek_not,
                butonlar=butonlar,
            )
            return
        satirlar = ["⚙️ *Arka Planda Çalışan Aktif Ajan Görevleri:*\n"]
        butonlar = []
        simdi = time.monotonic()
        for gid, k in list(BELLEK.aktif_gorevler.items()):
            sure = _sure_bicimle(simdi - float(k.get("baslangic") or simdi))
            satirlar.append(
                f"• `{gid}` — *{k.get('unvan', k.get('ajan'))}* (`{sure}` • `{k.get('arac_sayisi', 0)} adım`)\n"
                f"  Son: `{k.get('son_arac', '')}` • _{k.get('ozet', '')}_"
            )
            butonlar.append([{"text": f"🛑 İptal Et: {gid}", "callback_data": f"gorev:iptal:{gid}"}])
        await tg.mesaj_gonder(chat_id, "\n".join(satirlar), butonlar=butonlar)

    elif komut == "/iptal":
        if not BELLEK.aktif_gorevler:
            await tg.mesaj_gonder(chat_id, "📭 İptal edilecek çalışan bir arka plan görevi yok.")
            return
        hedef_ids = [arg_metin] if arg_metin and arg_metin in BELLEK.aktif_gorevler else list(BELLEK.aktif_gorevler.keys())
        durdurulan: list[str] = []
        for gid in hedef_ids:
            kayit = BELLEK.aktif_gorevler.get(gid)
            if not kayit:
                continue
            await _surec_durdur(kayit.get("proc"))
            task = kayit.get("task")
            if task and not task.done():
                task.cancel()
            durdurulan.append(gid)
        await tg.mesaj_gonder(
            chat_id,
            f"🛑 İptal isteği gönderildi: {', '.join(f'`{g}`' for g in durdurulan)}" if durdurulan else "❌ Görev ID bulunamadı.",
        )

    elif komut == "/devam":
        son = _oturum_al()
        if not son:
            await tg.mesaj_gonder(chat_id, "❌ Devam edilecek kayıtlı bir ajan oturumu bulunamadı.")
            return
        anahtar, kayit = son
        devam_istem = arg_metin or "Kaldığın yerden devam et, eksik adımları tamamla ve sonucu özetle."
        _ajan_arka_planda_calistir(
            tg,
            chat_id,
            str(kayit.get("ajan") or "ceo-orchestrator"),
            devam_istem,
            oturum_id=str(kayit.get("session_id") or ""),
            gorev_ozeti=f"Devam ({anahtar}): {kayit.get('ozet', '')}",
        )

    elif komut == "/baskibitti":
        dosya_adi = arg_metin
        gecen_sn = 0
        if not dosya_adi:
            d = await asyncio.to_thread(yazici_durumu_oku)
            dosya_adi = d.dosya_adi or durum_dosyasi_oku().get("son_baski_dosya") or "numune_urun_60g_120m.gcode"
            gecen_sn = d.gecen_saniye
        await baski_bitti_sorusu_gonder(tg, chat_id, dosya_adi, gecen_saniye=gecen_sn)

    else:
        if BELLEK.studio_bekleyen:
            await _studio_uret(tg, chat_id, metin.strip())
            return
        if BELLEK.cok_renk_not_sku:
            sku_cr, BELLEK.cok_renk_not_sku = BELLEK.cok_renk_not_sku, None
            await _cok_renk_baslat(tg, chat_id, sku_cr, "" if metin.strip().lower() == "devam" else metin.strip(),
                                   zorunlu=BELLEK.cok_renk_zorunlu.get(sku_cr) or None)
            return
        if BELLEK.bekleyen_b2c_revize:
            pid, idx = BELLEK.bekleyen_b2c_revize
            BELLEK.bekleyen_b2c_revize = None
            aday_durum_guncelle(pid, idx, "REVIZE", revize_notu=metin)
            await _trendden_fikir(tg, chat_id, pid, idx, ek_not=metin)
            return

        # Düz metin mesajları: Başında "cto", "cmo", "ceo" varsa ilgili ajana, yoksa aktif muhatap ajana yönlendir!
        kucuk = metin.lower()
        hedef = BELLEK.aktif_muhatap_ajan
        if kucuk.startswith("cto ") or kucuk.startswith("cto:"):
            hedef = "cto-architect"
            metin = metin[4:].strip()
        elif kucuk.startswith("cmo ") or kucuk.startswith("cmo:"):
            hedef = "cmo-store-director"
            metin = metin[4:].strip()
        elif kucuk.startswith("ceo ") or kucuk.startswith("ceo:"):
            hedef = "ceo-orchestrator"
            metin = metin[4:].strip()
        await _claude_ajana_sor_ve_yanitla(tg, chat_id, hedef, metin)


async def callback_isle(tg: TelegramIstemci, cb: dict[str, Any], yetkili_chat_id: int) -> None:
    cb_id = str(cb.get("id") or "")
    veri = str(cb.get("data") or "")
    mesaj = cb.get("message") or {}
    chat_id = int((mesaj.get("chat") or {}).get("id") or yetkili_chat_id)
    if yetkili_chat_id and chat_id != yetkili_chat_id:
        return

    await tg.callback_yanitla(cb_id)

    if veri == "menu:ana":
        await tg.mesaj_gonder(chat_id, "🏠 *Ana Menü*", butonlar=_ust_yonetim_butonlari())
        return
    if veri == "menu:urunler":
        await _urunler_menusu_gonder(tg, chat_id)
        return
    if veri == "menu:ajanlar":
        await tg.mesaj_gonder(chat_id, "🤖 Hangi ajanla konuşmak istersin? Seçtikten sonra düz mesaj yaz.",
                              butonlar=_ajan_butonlari())
        return
    if veri in ("menu:stok", "menu:kuyruk", "menu:gorevler"):
        komut_adi = {"menu:stok": "/stok", "menu:kuyruk": "/kuyruk", "menu:gorevler": "/gorevler"}[veri]
        await mesaj_isle(tg, {"chat": {"id": chat_id}, "text": komut_adi}, yetkili_chat_id)
        return
    if veri.startswith("urunmenu:"):
        await _urun_karti_gonder(tg, chat_id, veri.split(":", 1)[1])
        return

    if veri.startswith("teklif:"):
        await _teklif_callback(tg, chat_id, veri)
        return

    if veri.startswith("alim:"):
        await _alim_callback(tg, chat_id, veri, mesaj)
        return

    if veri.startswith("kilavuz:"):
        k_metin, k_butonlar = kilavuz_bolumu(veri.split(":", 1)[1])
        await tg.mesaj_gonder(chat_id, k_metin, butonlar=k_butonlar)
        return

    if veri == "trend:baslat":
        await mesaj_isle(tg, {"chat": {"id": chat_id}, "text": "/trend"}, yetkili_chat_id)
        return

    if veri.startswith("pazar:"):
        parca = veri.split(":")
        if len(parca) == 3 and (URUNLER_KLASORU / parca[2]).is_dir():
            if parca[1] == "goster":
                veri_p = await asyncio.to_thread(pazar_oku, parca[2])
                await tg.mesaj_gonder(chat_id, pazar_metni(parca[2], veri_p, pazar_ozeti(veri_p))[:3900],
                                      butonlar=[[{"text": "🔁 Yeniden Araştır", "callback_data": f"pazar:arastir:{parca[2]}"}]])
            else:
                await _pazar_arastir(tg, chat_id, parca[2])
        return

    if veri == "konsept:ekle":
        await asyncio.to_thread(
            tg._json_istek, "sendMessage",
            {"chat_id": chat_id, "text": f"{KONSEPT_ISTEM_BASLIGI}\nİlk satır: konsept adı. Altına: istemin tamamı.",
             "reply_markup": {"force_reply": True, "input_field_placeholder": "Konsept adı + istem"}},
        )
        return
    if veri.startswith("konsept:editoryal:"):  # eski buton: teknik föy reddedildi → Teknik Poster
        veri = "konsept:liste:" + veri.split(":", 2)[2]

    if veri.startswith("konsept:liste:"):
        sku = veri.split(":", 2)[2]
        liste = await asyncio.to_thread(konseptler)
        butonlar = [[{"text": f"🎨 {k['baslik'][:40]}", "callback_data": f"konsept:uret:{sku}:{i}"}]
                    for i, k in enumerate(liste)]
        butonlar.append([{"text": "➕ Yeni Konsept Ekle", "callback_data": "konsept:ekle"}])
        await tg.mesaj_gonder(chat_id, f"🎨 `{sku}` için hangi konsept? (Flow, en kaliteli model; kredi harcar)\n"
                              + "\n".join(f"• *{k['baslik']}* — {k['aciklama']}" for k in liste), butonlar=butonlar)
        return
    if veri.startswith("konsept:uret:"):
        _, _, sku, no = veri.split(":", 3)
        liste = await asyncio.to_thread(konseptler)
        if not no.isdigit() or int(no) >= len(liste) or not (URUNLER_KLASORU / sku).is_dir():
            await tg.mesaj_gonder(chat_id, "❌ Konsept veya ürün bulunamadı.")
            return
        await _konsept_uret(tg, chat_id, sku, liste[int(no)])
        return
    if veri.startswith("fikir:"):
        await _fikir_callback(tg, chat_id, veri)
        return

    if veri.startswith("magaza:"):
        await _magaza_callback(tg, chat_id, veri)
        return

    if veri.startswith("renk:"):
        await _renk_callback(tg, chat_id, veri, mesaj)
        return

    if veri.startswith("icerik:"):
        await _icerik_callback(tg, chat_id, veri)
        return

    if veri.startswith("studyo:"):
        await _studyo_callback(tg, chat_id, veri)
        return

    if veri.startswith("pin:"):
        await _pin_callback(tg, chat_id, veri)
        return

    if veri.startswith("numune:iste:"):
        sku = veri.split(":", 2)[2]
        BELLEK.numune_bekleyen_sku = sku
        await tg.mesaj_gonder(chat_id, f"📷 `{sku}` numune fotoğrafını gönder (gün ışığında, sade zeminde, ürün "
                                       "kadrajın ortasında). Kısayol: açıklamaya `numune " + sku + "` yaz.")
        return

    if veri.startswith("ajan:sec:"):
        secilen = veri.split(":", 2)[2]
        if secilen in AJAN_KATALOGU:
            BELLEK.aktif_muhatap_ajan = secilen
            unvan, _ = AJAN_KATALOGU[secilen]
            await tg.mesaj_gonder(
                chat_id,
                f"🗣️ Aktif muhatabınız *{unvan}* (`{secilen}`) olarak değiştirildi.\n"
                f"Doğrudan mesajınızı yazıp gönderebilirsiniz.",
                butonlar=_ust_yonetim_butonlari(),
            )
        return

    if veri == "ajan:liste":
        satirlar = ["🤖 *21 Uzman Ajan Kadrosu*\n"]
        for kod, (unvan, dept) in AJAN_KATALOGU.items():
            satirlar.append(f"• `{kod}` — {unvan} _({dept})_")
        satirlar.append("\nBir ajana bağlanmak için `/ajan <kod>` yazabilirsiniz.")
        await tg.mesaj_gonder(chat_id, "\n".join(satirlar), butonlar=_ust_yonetim_butonlari())
        return

    if veri.startswith("gorev:iptal:"):
        gid = veri.split(":", 2)[2]
        kayit = BELLEK.aktif_gorevler.get(gid)
        if not kayit:
            await tg.mesaj_gonder(chat_id, f"ℹ️ Görev `{gid}` zaten tamamlanmış veya listede yok.")
            return
        await _surec_durdur(kayit.get("proc"))
        task = kayit.get("task")
        if task and not task.done():
            task.cancel()
        return

    if veri.startswith("gorev:devam:"):
        anahtar = veri.split(":", 2)[2]
        bulunan = _oturum_al(anahtar)
        if not bulunan:
            await tg.mesaj_gonder(chat_id, "❌ Devam edilecek oturum kaydı bulunamadı.")
            return
        _, kayit = bulunan
        _ajan_arka_planda_calistir(
            tg,
            chat_id,
            str(kayit.get("ajan") or "ceo-orchestrator"),
            "Kaldığın yerden devam et, eksik adımları tamamla ve sonucu özetle.",
            oturum_id=str(kayit.get("session_id") or ""),
            gorev_ozeti=f"Devam ({anahtar}): {kayit.get('ozet', '')}",
        )
        return

    if veri == "b2c:vitrin":
        await _b2c_vitrini_gonder(tg, chat_id)
        return

    if veri == "urun:ozet_tumu":
        await _urun_ozet_gonder(tg, chat_id)
        return

    if veri.startswith("urun:ozet:"):
        sku = veri.split(":", 2)[2].strip()
        await _urun_ozet_gonder(tg, chat_id, sku)
        return

    if veri.startswith("b2c:gelistir:"):
        parcalar = veri.split(":", 3)
        if len(parcalar) == 4 and parcalar[3].isdigit():
            await _trendden_fikir(tg, chat_id, parcalar[2], int(parcalar[3]))
        return

    if veri.startswith("b2c:revize:"):
        parcalar = veri.split(":", 3)
        if len(parcalar) == 4 and parcalar[3].isdigit():
            pid, idx = parcalar[2], int(parcalar[3])
            BELLEK.bekleyen_b2c_revize = (pid, idx)
            await tg.mesaj_gonder(
                chat_id,
                f"✏️ *Revize Notu Bekleniyor* (`{pid}` • Aday #{idx + 1})\n"
                "Bu üründen farklı olarak ne istiyorsun (tarz, boyut, kullanım)? Bir sonraki mesajda yaz; "
                "notla birlikte konsept üretimine başlayacağım.",
            )
        return

    if veri.startswith("b2c:ele:"):
        parcalar = veri.split(":", 3)
        if len(parcalar) == 4 and parcalar[3].isdigit():
            pid, idx = parcalar[2], int(parcalar[3])
            aday = aday_durum_guncelle(pid, idx, "ELENDI")
            ad = (aday or {}).get("ad") or f"Aday #{idx + 1}"
            await tg.mesaj_gonder(chat_id, f"🗑️ *{ad}* B2C aday listesinden elendi (`ELENDI`).")
        return

    if veri == "yazici:durum":
        await _yazici_durum_gonder(tg, chat_id)
        return

    if veri == "baski:sor":
        d = await asyncio.to_thread(yazici_durumu_oku)
        dosya_adi = d.dosya_adi or durum_dosyasi_oku().get("son_baski_dosya") or "baski.gcode"
        await baski_bitti_sorusu_gonder(tg, chat_id, dosya_adi, gecen_saniye=d.gecen_saniye)
        return

    if veri.startswith("baski:"):
        parcalar = veri.split(":", 2)
        if len(parcalar) == 3:
            _, senaryo, kayit_id = parcalar
            if not kayit_islendi_isaretle(kayit_id):
                await tg.klavye_temizle(chat_id, mesaj.get("message_id"))
                await tg.mesaj_gonder(chat_id, f"ℹ️ `{kayit_id}` numaralı baskı kararı zaten ERP'ye işlendi.")
                return
            await tg.klavye_temizle(chat_id, mesaj.get("message_id"))
            ref = BELLEK.bekleyen_baskilar.get(kayit_id)
            if not ref:
                yerel = durum_dosyasi_oku()
                son_dosya = yerel.get("son_baski_dosya") or "baski.gcode"
                ref = gcode_referans_coz(son_dosya, erp_urunler=await ERP.urunler())

            if senaryo == "FIRE" and ref.ilerleme_yuzde < 99.5:
                ref.tahmini_gram = fire_grami(ref.tahmini_gram, ref.ilerleme_yuzde)
            sonuc = await ERP.baski_sonucu_isle(senaryo=senaryo, ref=ref)
            BELLEK.bekleyen_baskilar.pop(kayit_id, None)
            if senaryo == "IS_NUMUNE" and ref.eslesen_sku:
                await asyncio.to_thread(
                    tg._json_istek, "sendMessage",
                    {"chat_id": chat_id, "text": f"{TARTI_ISTEM_BASLIGI} [{ref.eslesen_sku}] (destekler temizlenmiş, g)",
                     "reply_markup": {"force_reply": True, "input_field_placeholder": "268,4"}},
                )

            metin = f"*{sonuc.baslik}*\n\n{sonuc.ozet_mesaj}"
            if sonuc.kritik_stok_uyarilari:
                metin += "\n\n🚨 *Kritik Stok Uyarısı:*\n" + "\n".join(f"• {u}" for u in sonuc.kritik_stok_uyarilari)

            ek_butonlar = [[{"text": "🧹 Tabla Boşaltıldı", "callback_data": "tabla:bos"}]]
            if ref.eslesen_sku:
                ek_butonlar[0].insert(0, {"text": "🎬 Kliple Reels Üret", "callback_data": f"medya:uret:{ref.eslesen_sku}"})
            await tg.mesaj_gonder(chat_id, metin, butonlar=ek_butonlar)
        return

    if veri == "tabla:bos":
        tabla_bos_isaretle(True)
        await tg.mesaj_gonder(chat_id, "🧹 Tabla **boş ve yeni baskıya hazır** olarak işaretlendi.")
        return

    if veri == "hata:durdur":
        butonlar = [
            [
                {"text": "⚠️ EVET, Baskıyı Durdur", "callback_data": "durdur:evet"},
                {"text": "Vazgeç", "callback_data": "durdur:iptal"},
            ]
        ]
        await tg.mesaj_gonder(chat_id, "⚠️ *Emin misiniz?* Yazıcıdaki aktif baskı durdurulacak.", butonlar=butonlar)
        return

    if veri == "durdur:evet":
        basarili, m = await asyncio.to_thread(baski_durdur)
        await tg.mesaj_gonder(chat_id, f"{'🛑' if basarili else '❌'} {m}")
        return

    if veri == "durdur:iptal":
        await tg.mesaj_gonder(chat_id, "✅ Baskıya devam ediliyor.")
        return

    if veri.startswith("flow:uret:"):
        sku = veri.split(":", 2)[2]
        await _flow_uretimi_baslat(tg, chat_id, sku)
        return

    if veri.startswith(("medya:taslak:", "medya:uret:")):  # yalnız gerçek kaynaklı Reels kurgusu
        sku = veri.split(":", 2)[2]
        async with _yerel_is(tg, chat_id, sku, "Reels kurgusu (gerçek kaynaklar)", 2) as k:
            k["adim"] = "numuneden Flow videosu / çekim / timelapse kurgulanıyor"
            sonuc = await asyncio.to_thread(tam_medya_paketi_uret, sku, None)
        await _medya_paketi_gonder(tg, chat_id, sku, sonuc)
        return

    if veri.startswith("medya:sec:"):
        _, _, medya_kayit_id, sku = veri.split(":", 3)
        kayit = BELLEK.bekleyen_medyalar.pop(medya_kayit_id, None)
        if not kayit:
            await tg.mesaj_gonder(chat_id, "⚠️ Medya oturumu zaman aşımına uğradı, lütfen videoyu tekrar gönderin.")
            return
        await _medya_indir_ve_kurgula(tg, chat_id, kayit["dosya_id"], kayit["video_mu"], sku, kayit.get("aciklama", ""))
        return

    if veri.startswith("studio:"):
        await _studio_callback(tg, chat_id, veri)
        return

    if veri.startswith("kartela:"):
        await _kartela_callback(tg, chat_id, veri, mesaj)
        return

    if veri.startswith("cokrenk:"):
        await _cok_renk_callback(tg, chat_id, veri)
        return

    if veri.startswith("orca:analiz:"):
        sku = veri.split(":", 2)[2]
        await _dilimleme_ozeti_gonder(tg, chat_id, sku)
        return

    if veri.startswith("orca:kat:"):
        _, _, sku, idx = veri.split(":", 3)
        katlar = list(await asyncio.to_thread(baski_kategorileri))
        if idx.isdigit() and int(idx) < len(katlar):
            await asyncio.to_thread(urun_yaml_guncelle, sku, {"baski_kategorisi": katlar[int(idx)]})
            await _dilimleme_ozeti_gonder(tg, chat_id, sku, kategori=katlar[int(idx)])
        return

    if veri.startswith("yazici:yukle:"):
        await _yaziciya_yukle(tg, chat_id, veri.split(":", 2)[2])
        return

    if veri.startswith("yazici:kontrol:"):
        k = await _baski_kontrolu(veri.split(":", 2)[2])
        await tg.mesaj_gonder(chat_id, "*Baskı öncesi kontrol:*\n" + kontrol_metni(k))
        return

    if veri.startswith("rapor:") or veri.startswith("bakim:"):
        await _rapor_bakim_callback(tg, chat_id, veri, mesaj)
        return

    if veri == "yz:sessiz":
        iz = BELLEK.baski_izleme
        iz["sessiz_bitis"] = time.monotonic() + YZ_SESSIZ_SN
        if iz.get("dosya") and iz.get("yz_gecmis"):
            await asyncio.to_thread(yz_kaydet, iz["dosya"], {**iz["yz_gecmis"][-1], "patron": "yanlis_alarm"})
        await tg.klavye_temizle(chat_id, mesaj.get("message_id"))
        await tg.mesaj_gonder(chat_id, "👍 Not edildi (yanlış alarm olarak kaydedildi); YZ uyarıları 20 dk sessiz.")
        return

    if veri == "izle:tamam":
        await tg.klavye_temizle(chat_id, mesaj.get("message_id"))
        return

    if veri.startswith("orca:yzkat:"):
        await _yz_kategori(tg, chat_id, veri.split(":", 2)[2])
        return

    if veri.startswith("orca:ac:"):
        sku = veri.split(":", 2)[2]
        proje = URUNLER_KLASORU / sku / "uretim" / f"{sku}.3mf"
        if not proje.exists():
            await tg.mesaj_gonder(chat_id, f"❌ `{proje.name}` yok; önce dilimleyin.")
            return
        subprocess.Popen(
            [ORCA_BIN, str(proje)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True
        )
        await tg.mesaj_gonder(chat_id, f"🖥️ `{proje.name}` bilgisayarda OrcaSlicer'da açılıyor.")
        return

    if veri.startswith("fil:tak:"):
        fil_id = int(veri.split(":", 2)[2])
        ok = await ERP.makine_filament_degistir(fil_id)
        await tg.mesaj_gonder(
            chat_id,
            f"✅ Makinedeki aktif filament `#{fil_id}` olarak güncellendi." if ok else "❌ Filament güncellenemedi.",
        )


AKTIF_DURUMLAR = {"BASKIDA", "DURAKLATILIYOR", "DURAKLATILDI", "DEVAM_EDIYOR", "DURDURULUYOR", "ISINIYOR",
                  "BASKI_BASLIYOR", "ISINMA_BITTI", "KALIBRASYON", "KALIBRASYON_BITTI", "DOSYA_KONTROL",
                  "CIHAZ_KONTROL"}
BITIS_DURUMLARI = {"TAMAMLANDI", "BOSTA", "DURDURULDU", "HATA"}


async def _yz_degerlendir(iz: dict[str, Any], d: Any, kare: bytes) -> dict[str, Any]:
    """Kareyi Gemini ile değerlendirir, geçmişe ve baskı kaydına yazar."""
    baglam = {"urun": iz.get("urun_adi") or iz.get("sku") or d.dosya_adi, "katman": d.mevcut_katman,
              "toplam_katman": d.toplam_katman, "ilerleme": round(d.ilerleme_yuzde), "destek": iz.get("destek"),
              "renk": iz.get("renk")}
    sonuc = await asyncio.to_thread(yz_kare_degerlendir, kare, baglam, iz.get("onceki_kare"), iz.get("referans"))
    iz["onceki_kare"] = kare
    iz["son_yz"] = time.monotonic()
    if sonuc.get("durum") != "BILINMIYOR":
        iz.setdefault("yz_gecmis", []).append(sonuc)
    await asyncio.to_thread(yz_kaydet, d.dosya_adi, sonuc, kare if sonuc.get("durum") in ("SUPHELI", "HATA") else None)
    return sonuc


async def _baski_izle(tg: TelegramIstemci, chat_id: int, d: Any, kare: bytes | None = None) -> None:
    """Baskı sürerken: başlangıçta kontrol uyarıları, ilk katman + riskli katmanlarda kamera fotoğrafı ve
    düzenli aralıkla YZ (Gemini) hata kontrolü. Bot asla kendisi durdurmaz; Patrona sorar."""
    iz = BELLEK.baski_izleme
    if iz.get("dosya") != d.dosya_adi:
        ref = gcode_referans_coz(d.dosya_adi)
        urun = await asyncio.to_thread(urun_yaml_oku, ref.eslesen_sku) if ref.eslesen_sku else {}
        iz.clear()
        plan = kritik_katmanlar(urun or {}, d.toplam_katman)
        # Bot baskı ortasında yeniden başladıysa geçmiş katmanların fotoğrafını toplu gönderme.
        gecmis = {n for n, _ in plan if d.mevcut_katman > n + 3}
        dil = (urun or {}).get("dilimleme") if isinstance((urun or {}).get("dilimleme"), dict) else {}
        oniz = URUNLER_KLASORU / str(ref.eslesen_sku) / "uretim" / f"{ref.eslesen_sku}-tabla.png"
        iz.update(dosya=d.dosya_adi, sku=ref.eslesen_sku, gonderilen=gecmis, plan=plan,
                  urun_adi=ref.urun_adi, destek=bool(dil.get("destek_gerekli")),
                  renk=dil.get("renk_hex") or "", referans=oniz.read_bytes() if ref.eslesen_sku and oniz.exists() else None,
                  son_yz=0.0, yz_gecmis=[], sessiz_bitis=0.0, uyari_sayisi=0)
        if ref.eslesen_sku:
            k = baski_oncesi_kontrol(urun, await _takili_filament(), True, "")
            sorunlar = [m for m in k if m["durum"] != "ok"]
            if sorunlar:
                await tg.mesaj_gonder(
                    chat_id, f"🖨️ `{ref.eslesen_sku}` baskısı başladı — dikkat:\n{kontrol_metni(sorunlar)}",
                    butonlar=[[{"text": "✅ Sorun Yok, Devam", "callback_data": "izle:tamam"},
                               {"text": "🛑 Durdur", "callback_data": "hata:durdur"}]])
    iz["son_ilerleme"] = d.ilerleme_yuzde
    btn = [[{"text": "✅ İyi, Devam", "callback_data": "izle:tamam"},
            {"text": "🛑 Durdur", "callback_data": "hata:durdur"}]]
    for n, aciklama in iz.get("plan") or []:
        if n in iz["gonderilen"] or d.mevcut_katman < n:
            continue
        iz["gonderilen"].add(n)
        kare = kare or await asyncio.to_thread(kamera_karesi_al)
        metin = (f"📸 `{iz.get('sku') or d.dosya_adi}` — katman {d.mevcut_katman}/{d.toplam_katman} "
                 f"(%{d.ilerleme_yuzde:.0f})\n{aciklama}")
        if kare:
            sonuc = await _yz_degerlendir(iz, d, kare)
            await tg.foto_gonder(chat_id, kare, aciklama=f"{metin}\n{yz_ozet_satiri(sonuc)}"[:1000], butonlar=btn,
                                 dosya_adi="katman.jpg")
        else:
            await tg.mesaj_gonder(chat_id, metin + "\n_(kamera karesi alınamadı)_", butonlar=btn)
        return  # aynı turda tek fotoğraf / tek YZ çağrısı

    # Düzenli YZ kontrolü
    if not kare or time.monotonic() - float(iz.get("son_yz") or 0) < YZ_KONTROL_ARALIGI_SN:
        return
    onceki_gecmis = list(iz.get("yz_gecmis") or [])
    sonuc = await _yz_degerlendir(iz, d, kare)
    sebep = yz_karar_ver(sonuc, onceki_gecmis)
    if not sebep or time.monotonic() < float(iz.get("sessiz_bitis") or 0):
        return
    iz["uyari_sayisi"] = int(iz.get("uyari_sayisi") or 0) + 1
    baslik = ("🚨 *Olası baskı hatası*" if sebep == "hata" else "⚠️ *Şüpheli görüntü (2 ardışık kontrol)*")
    await tg.foto_gonder(
        chat_id, kare,
        aciklama=(f"{baslik} — `{iz.get('sku') or d.dosya_adi}`\nkatman {d.mevcut_katman}/{d.toplam_katman} "
                  f"(%{d.ilerleme_yuzde:.0f})\n{yz_ozet_satiri(sonuc)}\n_Bot durdurmaz; karar senin._")[:1000],
        butonlar=[[{"text": "🛑 Durdur", "callback_data": "hata:durdur"},
                   {"text": "✅ Sorun Yok (20 dk sessiz)", "callback_data": "yz:sessiz"}]],
        dosya_adi="yz-uyari.jpg")


async def reels_dongusu(tg: TelegramIstemci, chat_id: int) -> None:
    """Reels takvimi: Studio sayfasından/`/reels`'ten gelen Claude işlerini sırayla çalıştırır, her sabah 10:00'da
    günün planını gönderir (Patron isteği 2026-11-17)."""
    await asyncio.to_thread(reels_takvim.yarim_kalanlari_sifirla)
    izlenen: dict[str, str] = {}  # istek_id → gorev_id
    hatirlatma = reels_takvim.klasor() / "son_hatirlatma"
    while True:
        try:
            for istek_id, gorev_id in list(izlenen.items()):
                if gorev_id not in BELLEK.aktif_gorevler:  # iptal/hata: sonraki_islem çağrılmadı
                    await asyncio.to_thread(reels_takvim.istek_bitir, istek_id, "hata")
                    izlenen.pop(istek_id, None)
            istek = await asyncio.to_thread(reels_takvim.siradaki_istek)
            if istek and chat_id:
                async def _sonra(_ok: bool, yanit: str, _devam: str | None, istek: dict = istek) -> None:
                    izlenen.pop(istek["id"], None)
                    islenen = await asyncio.to_thread(reels_takvim.gelen_birlestir, istek)
                    await asyncio.to_thread(reels_takvim.istek_bitir, istek["id"], "tamam" if islenen else "hata")
                    if not islenen:
                        await tg.mesaj_gonder(chat_id, "⚠️ Reels fikirleri takvime yazılamadı.\n" + (yanit or "")[-400:])
                        return
                    satirlar = "\n".join(f"• {f.get('tarih') or 'tarihsiz'} — {f.get('baslik')}" for f in islenen)
                    baslik = "✏️ Reels fikri revize edildi" if istek["tur"] == "revize" else f"🎬 {len(islenen)} yeni Reels fikri takvimde"
                    await tg.mesaj_gonder(chat_id, f"{baslik}:\n{satirlar}\n\nSenaryo ve talimatlar: {reels_takvim.SAYFA}")

                izlenen[istek["id"]] = _ajan_arka_planda_calistir(
                    tg, chat_id, "reels-tiktok-strategist", await asyncio.to_thread(reels_takvim.istem, istek),
                    gorev_ozeti=("Reels revize" if istek["tur"] == "revize" else f"{istek['adet']} trend Reels fikri"),
                    sonraki_islem=_sonra)
            simdi = dt.datetime.now()
            if chat_id and simdi.hour >= 10 and (not hatirlatma.exists() or hatirlatma.read_text().strip() != simdi.date().isoformat()):
                hatirlatma.parent.mkdir(parents=True, exist_ok=True)
                hatirlatma.write_text(simdi.date().isoformat())
                bugun = await asyncio.to_thread(reels_takvim.bugunun_fikirleri)
                if bugun:
                    await tg.mesaj_gonder(chat_id, reels_takvim.hatirlatma_metni(bugun))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Reels döngüsü uyarısı: %s", exc)
        await asyncio.sleep(20)


async def yazici_gozcu_dongusu(tg: TelegramIstemci, chat_id: int) -> None:
    """Her 30 saniyede bir yazıcıyı kontrol eder; baskıda timelapse + kritik katman fotoğrafları,
    bitince (tamamlandı/durduruldu/hata) 4'lü soruyu sorar."""
    while True:
        try:
            if chat_id:
                d = await asyncio.to_thread(yazici_durumu_oku)
                if d.bagli:
                    BELLEK.son_yazici_durum_adi = d.durum_adi

                    if d.durum_adi in AKTIF_DURUMLAR and d.dosya_adi:
                        BELLEK.aktif_baski_dosyasi = d.dosya_adi
                        if d.gecen_saniye > 0:
                            BELLEK.aktif_baski_baslangic_sn = d.gecen_saniye
                    if d.durum_adi == "BASKIDA":
                        kare = await asyncio.to_thread(kamera_karesi_al)
                        if kare and BELLEK.aktif_baski_dosyasi:
                            ref = gcode_referans_coz(BELLEK.aktif_baski_dosyasi)
                            await asyncio.to_thread(
                                BELLEK.timelapse.kare_ekle,
                                BELLEK.aktif_baski_dosyasi,
                                ref.eslesen_sku,
                                kare,
                            )
                        try:
                            await _baski_izle(tg, chat_id, d, kare)
                        except Exception as e:  # izleme hatası baskı sonu kaydını engellemesin
                            log.warning("Katman izleme hatası: %s", e)
                    elif BELLEK.aktif_baski_dosyasi and d.durum_adi in BITIS_DURUMLARI:
                        biten_dosya = d.dosya_adi or BELLEK.aktif_baski_dosyasi or "baski.gcode"
                        gecen_sn = d.gecen_saniye or BELLEK.aktif_baski_baslangic_sn
                        ilerleme = 100.0 if d.durum_adi == "TAMAMLANDI" else float(
                            BELLEK.baski_izleme.get("son_ilerleme") or d.ilerleme_yuzde or 100.0)
                        BELLEK.aktif_baski_dosyasi = ""
                        BELLEK.aktif_baski_baslangic_sn = 0
                        izleme = dict(BELLEK.baski_izleme)
                        BELLEK.baski_izleme.clear()
                        await baski_bitti_sorusu_gonder(tg, chat_id, biten_dosya, gecen_saniye=gecen_sn,
                                                        ilerleme_yuzde=ilerleme, bitis_durumu=d.durum_adi,
                                                        izleme=izleme)
        except Exception as e:
            log.warning("Yazıcı gözcü hatası: %s", e)
        await asyncio.sleep(30.0)


async def _guncelleme_isleyici_guvenli(coro: Awaitable[None]) -> None:
    try:
        await coro
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.exception("Telegram güncelleme işleme hatası: %s", exc)


async def comfy_bekci_dongusu() -> None:
    """ComfyUI (Qwen) iş bitince açık kalırsa ~18 GB RAM tutuyor; 2026-11-17 11:47'de masaüstünü çökertti.
    Kuyruğu 10 dk boş kalan sunucuyu kapatır."""
    durum: dict[str, float] = {}
    while True:
        try:
            if await asyncio.to_thread(qwen_edit.bosta_kapat_kontrol, durum, time.time()):
                log.info("ComfyUI 10 dk boşta kaldı; kapatıldı (RAM serbest).")
        except Exception as exc:  # bekçi asla botu düşürmesin
            log.warning("ComfyUI bekçisi: %s", exc)
        await asyncio.sleep(60)


async def ana_dongu() -> None:
    ayar = ayarlari_yukle()
    if not ayar.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN bulunamadı!")
    if not ayar.telegram_chat_id:
        # Güvenlik: sohbet kimliği olmadan bot herkese açık olur (ajanlar araç izniyle çalışır) — başlatma.
        raise RuntimeError("TELEGRAM_CHAT_ID ayarlı değil! Botu yalnız kendi sohbetinize kilitlemek için .env'e yazın.")

    tg = TelegramIstemci(ayar.telegram_bot_token)
    log.info("COO Telegram Botu (v2.1 — Claude Opus 5.5 Köprülü) başlatıldı (Chat ID: %s)", ayar.telegram_chat_id)

    await _komutlari_kaydet(tg)
    gozcu_gorev = asyncio.create_task(yazici_gozcu_dongusu(tg, ayar.telegram_chat_id))
    reels_gorev = asyncio.create_task(reels_dongusu(tg, ayar.telegram_chat_id))
    comfy_gorev = asyncio.create_task(comfy_bekci_dongusu())
    takip_gorevleri: set[asyncio.Task[None]] = set()
    offset = 0

    def _guncelleme_planla(coro: Awaitable[None]) -> None:
        t = asyncio.create_task(_guncelleme_isleyici_guvenli(coro))
        takip_gorevleri.add(t)
        t.add_done_callback(takip_gorevleri.discard)

    try:
        while True:
            try:
                guncellemeler = await tg.guncellemeleri_al(offset=offset, timeout=20)
                for u in guncellemeler:
                    offset = int(u["update_id"]) + 1
                    if "message" in u:
                        _guncelleme_planla(mesaj_isle(tg, u["message"], ayar.telegram_chat_id))
                    elif "callback_query" in u:
                        _guncelleme_planla(callback_isle(tg, u["callback_query"], ayar.telegram_chat_id))
            except urllib.error.HTTPError as e:
                if e.code == 409:
                    log.warning("Telegram 409 Conflict; 5 sn bekleniyor...")
                    await asyncio.sleep(5.0)
                else:
                    log.warning("Telegram HTTP hatası (%s): %s", e.code, e)
                    await asyncio.sleep(3.0)
            except TimeoutError:
                log.debug("Telegram long-poll zaman aşımı; tekrar bağlanılıyor.")
                await asyncio.sleep(0.5)
            except Exception as e:
                neden = getattr(e, "reason", None)
                if isinstance(neden, TimeoutError) or "timed out" in str(e).lower():
                    log.debug("Telegram polling okuma zaman aşımı (%s); devam ediliyor.", e)
                    await asyncio.sleep(0.5)
                else:
                    log.warning("Polling döngüsü uyarısı: %s", e)
                    await asyncio.sleep(3.0)
    finally:
        gozcu_gorev.cancel()
        reels_gorev.cancel()
        comfy_gorev.cancel()


def main() -> None:
    asyncio.run(ana_dongu())


if __name__ == "__main__":
    main()
