"""Yazıcı (Elegoo Centauri Carbon) bağlantı, G-code referans eşleştirme ve timelapse modülü.

Kural: Yazıcıya (PRINTER_IP) asla baskı başlatma komutu gönderilmez.
Yalnızca durum/kamera/dosya listesi okunur; Patron Telegram'dan istediğinde dilimlenmiş G-code yazıcı
belleğine YÜKLENİR (başlatılmaz — Patron yazıcı ekranından/uygulamadan başlatır, Patron onayı 2026-11-16);
kullanıcı çift onay verdiğinde acil durdurma (stop) gönderilir.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
import secrets
import socket
import struct
import subprocess
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .ayar import DURUM_DOSYASI, URUNLER_KLASORU, ayarlari_yukle


@dataclass
class YaziciDurumu:
    bagli: bool = False
    durum_kodu: int = -1
    durum_adi: str = "BAGLI_DEGIL"
    nozul_sicaklik: float = 0.0
    nozul_hedef: float = 0.0
    tabla_sicaklik: float = 0.0
    tabla_hedef: float = 0.0
    dosya_adi: str = ""
    mevcut_katman: int = 0
    toplam_katman: int = 0
    ilerleme_yuzde: float = 0.0
    gecen_saniye: int = 0
    toplam_saniye: int = 0
    hata_mesaji: str = ""


@dataclass
class GcodeReferans:
    ham_dosya_adi: str
    temiz_ad: str
    eslesen_sku: str | None = None
    urun_adi: str = ""
    erp_urun_id: int | None = None
    tahmini_gram: float = 0.0
    tahmini_dakika: int = 0
    kaynak: str = "dosya_adi"
    ilerleme_yuzde: float = 100.0   # yarıda kalan baskıda fire gramı buna göre
    bitis_durumu: str = ""


DURUM_HARITASI = {
    0: "BOSTA",
    1: "HAZIRLANIYOR",
    5: "DURAKLATILIYOR",
    6: "DURAKLATILDI",
    7: "DURDURULUYOR",
    8: "DURDURULDU",
    9: "TAMAMLANDI",
    10: "DOSYA_KONTROL",
    11: "CIHAZ_KONTROL",
    12: "DEVAM_EDIYOR",
    13: "BASKIDA",
    14: "HATA",
    15: "KALIBRASYON",
    16: "ISINIYOR",
    17: " titresim_TESTI",
    18: "BASKI_BASLIYOR",
    19: "KALIBRASYON_BITTI",
    20: "ISINMA_BITTI",
}


def durum_dosyasi_oku() -> dict[str, Any]:
    if not DURUM_DOSYASI.exists():
        return {"tabla_bos": True, "son_baski_dosya": "", "son_baski_zaman": ""}
    try:
        return json.loads(DURUM_DOSYASI.read_text(encoding="utf-8"))
    except Exception:
        return {"tabla_bos": True, "son_baski_dosya": "", "son_baski_zaman": ""}


def durum_dosyasi_yaz(**guncellemeler: Any) -> dict[str, Any]:
    mevcut = durum_dosyasi_oku()
    mevcut.update(guncellemeler)
    DURUM_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
    DURUM_DOSYASI.write_text(json.dumps(mevcut, ensure_ascii=False, indent=2), encoding="utf-8")
    return mevcut


def tabla_bos_isaretle(bos: bool = True) -> dict[str, Any]:
    zaman = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return durum_dosyasi_yaz(tabla_bos=bos, tabla_bos_at=zaman)


from threading import Lock

_KAYIT_ISLEM_KILIDI = Lock()


def kayit_islendi_mi(kayit_id: str) -> bool:
    """Baskı bildirimindeki callback ID'sinin daha önce ERP'ye işlenip işlenmediğini kontrol eder."""
    if not kayit_id:
        return False
    idler = durum_dosyasi_oku().get("islenen_kayit_idler") or []
    return str(kayit_id) in idler


def kayit_islendi_isaretle(kayit_id: str) -> bool:
    """Idempotency kilidi: ilk çağrıda kaydeder ve True döner; yinelenen tıklamada False döner."""
    if not kayit_id:
        return True
    anahtar = str(kayit_id)
    with _KAYIT_ISLEM_KILIDI:
        idler = [str(x) for x in (durum_dosyasi_oku().get("islenen_kayit_idler") or []) if x]
        if anahtar in idler:
            return False
        idler.append(anahtar)
        durum_dosyasi_yaz(islenen_kayit_idler=idler[-100:])
        return True


def _dosya_adindan_sure_ve_gram_ayikla(dosya_adi: str) -> tuple[float, int]:
    """Dosya adındaki '64g', '48.5gr', '2h15m', '135m', '1s30dk' gibi kalıpları çözer."""
    gram = 0.0
    dakika = 0

    m_gram = re.search(r"(?:^|[_\-\s])(\d+(?:[.,]\d+)?)\s*(?:g|gr)(?:$|[_\-\s.])", dosya_adi, re.IGNORECASE)
    if m_gram:
        gram = float(m_gram.group(1).replace(",", "."))

    m_saat_dk = re.search(
        r"(?:^|[_\-\s])(?:(\d+)\s*(?:h|sa|s))?\s*(?:(\d+)\s*(?:m|dk|min))(?:$|[_\-\s.])",
        dosya_adi,
        re.IGNORECASE,
    )
    if m_saat_dk and (m_saat_dk.group(1) or m_saat_dk.group(2)):
        saat = int(m_saat_dk.group(1) or 0)
        dk = int(m_saat_dk.group(2) or 0)
        dakika = saat * 60 + dk
    else:
        m_sadece_saat = re.search(r"(?:^|[_\-\s])(\d+)\s*(?:h|sa)(?:$|[_\-\s.])", dosya_adi, re.IGNORECASE)
        if m_sadece_saat:
            dakika = int(m_sadece_saat.group(1)) * 60

    return gram, dakika


def gcode_basligindan_oku(gcode_yolu: Path) -> tuple[float, int]:
    """Yerel .gcode dosyasının yorum satırlarından gerçek filament gramını ve süreyi okur."""
    if not gcode_yolu.exists() or not gcode_yolu.is_file():
        return 0.0, 0
    gram = 0.0
    dakika = 0
    try:
        with gcode_yolu.open("r", encoding="utf-8", errors="ignore") as f:
            for i, satir in enumerate(f):
                if i > 2000 and satir.startswith("G1 "):
                    break
                if "filament used [g]" in satir:
                    m = re.search(r"=\s*([\d.]+)", satir)
                    if m:
                        gram = float(m.group(1))
                elif "estimated printing time" in satir:
                    saat_m = re.search(r"(\d+)\s*h", satir)
                    dk_m = re.search(r"(\d+)\s*m", satir)
                    sn_m = re.search(r"(\d+)\s*s", satir)
                    toplam_dk = (int(saat_m.group(1)) * 60 if saat_m else 0) + (int(dk_m.group(1)) if dk_m else 0)
                    if sn_m and int(sn_m.group(1)) >= 30:
                        toplam_dk += 1
                    if toplam_dk > 0:
                        dakika = toplam_dk
    except Exception:
        pass
    if gram <= 0 or dakika <= 0:
        # OrcaSlicer özet bloğunu dosyanın SONUNA yazar.
        try:
            with gcode_yolu.open("rb") as f:
                f.seek(max(0, gcode_yolu.stat().st_size - 60000))
                kuyruk = f.read().decode("utf-8", "ignore")
            if gram <= 0 and (m := re.search(r"filament used \[g\]\s*=\s*([\d.]+)", kuyruk)):
                gram = float(m.group(1))
            if dakika <= 0 and (m := re.search(r"estimated printing time[^=]*=\s*(.+)", kuyruk)):
                parca = dict((b, int(d)) for d, b in re.findall(r"(\d+)\s*([dhms])", m.group(1)))
                dakika = parca.get("d", 0) * 1440 + parca.get("h", 0) * 60 + parca.get("m", 0) + (1 if parca.get("s", 0) >= 30 else 0)
        except Exception:
            pass
    return gram, dakika


def _normallestir(metin: str) -> str:
    tr_harita = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    temiz = metin.translate(tr_harita).lower()
    return re.sub(r"[^a-z0-9]+", "-", temiz).strip("-")


def gcode_referans_coz(
    dosya_adi: str,
    erp_urunler: list[dict[str, Any]] | None = None,
    gecen_saniye: int = 0,
) -> GcodeReferans:
    """Yazıcıdaki G-code dosya adından hangi ürünün basıldığını, gramajını ve süresini çözer.

    Eşleştirme sırası:
    1. 02_Urunler/<sku>/ klasör adları ve urun.yaml içindeki sku / ad / gcode_dosyasi
    2. workbench-erp içindeki ürün listesi (sku, name, gcode_path)
    3. Dosya adındaki gram/süre etiketleri + yerel .gcode başlığı
    """
    saf_ad = Path(dosya_adi).name
    govde = re.sub(r"\.(gcode|3mf|stl)$", "", saf_ad, flags=re.IGNORECASE)
    norm_govde = _normallestir(govde)

    gram, dakika = _dosya_adindan_sure_ve_gram_ayikla(govde)
    if dakika == 0 and gecen_saniye > 0:
        dakika = max(1, round(gecen_saniye / 60))

    ref = GcodeReferans(
        ham_dosya_adi=dosya_adi,
        temiz_ad=govde,
        urun_adi=govde.replace("_", " ").replace("-", " ").strip(),
        tahmini_gram=gram,
        tahmini_dakika=dakika,
    )

    # 1) 02_Urunler/<sku> altında eşleştir
    if URUNLER_KLASORU.exists():
        for klasor in sorted(URUNLER_KLASORU.iterdir()):
            if not klasor.is_dir() or klasor.name.startswith("_"):
                continue
            sku = klasor.name
            norm_sku = _normallestir(sku)
            yaml_yolu = klasor / "urun.yaml"
            veri: dict[str, Any] = {}
            if yaml_yolu.exists():
                try:
                    veri = yaml.safe_load(yaml_yolu.read_text(encoding="utf-8")) or {}
                except Exception:
                    veri = {}

            urun_ad = str(veri.get("ad") or sku)
            uretim = veri.get("uretim") or {}
            gcode_yol_str = str(uretim.get("gcode_dosyasi") or "")

            eslesti = False
            if norm_sku and (norm_sku in norm_govde or norm_govde in norm_sku):
                eslesti = True
            elif gcode_yol_str and Path(gcode_yol_str).name.lower() == saf_ad.lower():
                eslesti = True
            elif _normallestir(urun_ad) and _normallestir(urun_ad) in norm_govde:
                eslesti = True

            if eslesti:
                ref.eslesen_sku = sku
                ref.urun_adi = urun_ad
                ref.kaynak = "02_Urunler"
                # Orca'nın gerçek dilimlemesi (coo/orca_dilim → urun.yaml dilimleme.*) önceliklidir.
                dil = veri.get("dilimleme") if isinstance(veri.get("dilimleme"), dict) else {}
                if ref.tahmini_gram <= 0 and dil.get("gercek_gram"):
                    ref.tahmini_gram = float(dil["gercek_gram"])
                if ref.tahmini_dakika <= 0 and dil.get("gercek_sure_dk"):
                    ref.tahmini_dakika = int(dil["gercek_sure_dk"])
                if ref.tahmini_gram <= 0 and uretim.get("tahmini_gram"):
                    ref.tahmini_gram = float(uretim["tahmini_gram"])
                if ref.tahmini_dakika <= 0 and uretim.get("tahmini_sure_dk"):
                    ref.tahmini_dakika = int(uretim["tahmini_sure_dk"])

                # Yerel gcode varsa başlığından oku
                for aday_gcode in sorted((klasor / "uretim").glob("*.gcode"),
                                         key=lambda g: g.stem != sku):  # önce uretim/<sku>.gcode
                    g_gr, g_dk = gcode_basligindan_oku(aday_gcode)
                    if ref.tahmini_gram <= 0 and g_gr > 0:
                        ref.tahmini_gram = g_gr
                    if ref.tahmini_dakika <= 0 and g_dk > 0:
                        ref.tahmini_dakika = g_dk
                break

    # 2) ERP ürün listesinde eşleştir
    if erp_urunler:
        for u in erp_urunler:
            u_sku = str(u.get("sku") or "")
            u_ad = str(u.get("name") or "")
            u_gcode = str(u.get("gcode_path") or "")
            norm_u_sku = _normallestir(u_sku)
            norm_u_ad = _normallestir(u_ad)

            eslesti = False
            if ref.eslesen_sku and norm_u_sku == _normallestir(ref.eslesen_sku):
                eslesti = True
            elif norm_u_sku and norm_u_sku in norm_govde:
                eslesti = True
            elif norm_u_ad and len(norm_u_ad) >= 4 and norm_u_ad in norm_govde:
                eslesti = True
            elif u_gcode and Path(u_gcode).name.lower() == saf_ad.lower():
                eslesti = True

            if eslesti:
                urun_id = u.get("product_id") or u.get("id")
                ref.erp_urun_id = int(urun_id) if urun_id is not None else None
                if not ref.eslesen_sku:
                    ref.eslesen_sku = u_sku or _normallestir(u_ad)
                if u_ad:
                    ref.urun_adi = u_ad
                ref.kaynak = "workbench-erp"
                erp_gram = u.get("total_filament_with_waste_gr") or u.get("total_filament_gr")
                if ref.tahmini_gram <= 0 and erp_gram:
                    ref.tahmini_gram = float(erp_gram)
                if ref.tahmini_dakika <= 0:
                    pt = u.get("print_time") or {}
                    saat = int(pt.get("hours") if isinstance(pt, dict) and pt.get("hours") is not None else (u.get("print_time_hours") or 0))
                    dk = int(pt.get("minutes") if isinstance(pt, dict) and pt.get("minutes") is not None else (u.get("print_time_minutes") or 0))
                    if saat * 60 + dk > 0:
                        ref.tahmini_dakika = saat * 60 + dk
                break

    return ref


def _ws_istemci_cerceve_paketle(metin: str) -> bytes:
    """RFC 6455 istemci -> sunucu maskeli WebSocket metin çerçevesi oluşturur."""
    veri = metin.encode("utf-8")
    maske = os.urandom(4)
    baslik = bytearray([0x81])  # FIN + Text frame
    uz = len(veri)
    if uz < 126:
        baslik.append(0x80 | uz)
    elif uz < 65536:
        baslik.append(0x80 | 126)
        baslik.extend(struct.pack(">H", uz))
    else:
        baslik.append(0x80 | 127)
        baslik.extend(struct.pack(">Q", uz))
    baslik.extend(maske)
    maskeli = bytes(b ^ maske[i % 4] for i, b in enumerate(veri))
    return bytes(baslik) + maskeli


def _ws_cerceveleri_coz(tampon: bytes) -> tuple[list[str], bytes]:
    """Sunucudan gelen maskesiz WebSocket çerçevelerini ayıklar."""
    mesajlar: list[str] = []
    while len(tampon) >= 2:
        ilk_bayt = tampon[0]
        ikinci_bayt = tampon[1]
        opcode = ilk_bayt & 0x0F
        maskeli = bool(ikinci_bayt & 0x80)
        uz = ikinci_bayt & 0x7F
        ofset = 2
        if uz == 126:
            if len(tampon) < 4:
                break
            uz = struct.unpack(">H", tampon[2:4])[0]
            ofset = 4
        elif uz == 127:
            if len(tampon) < 10:
                break
            uz = struct.unpack(">Q", tampon[2:10])[0]
            ofset = 10
        if maskeli:
            ofset += 4
        if len(tampon) < ofset + uz:
            break
        govde = tampon[ofset : ofset + uz]
        tampon = tampon[ofset + uz :]
        if opcode == 1:  # Text frame
            mesajlar.append(govde.decode("utf-8", errors="ignore"))
    return mesajlar, tampon


def _udp_mainboard_id_bul(ip: str, zaman_asimi: float = 1.2) -> str | None:
    """UDP 3000 portuna M99999 göndererek yazıcının MainboardID değerini öğrenir."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(zaman_asimi)
    try:
        s.sendto(b"M99999", (ip, 3000))
        veri, _ = s.recvfrom(4096)
        obj = json.loads(veri.decode("utf-8", errors="ignore"))
        ic = obj.get("Data") if isinstance(obj.get("Data"), dict) else obj
        return str(ic.get("MainboardID") or "") or None
    except Exception:
        return None
    finally:
        s.close()


def _sicaklik_cikar(sozluk: dict[str, Any], anahtar: str, hedef_anahtar: str) -> tuple[float, float]:
    ham = sozluk.get(anahtar)
    hedef_ham = sozluk.get(hedef_anahtar)
    mevcut = 0.0
    hedef = 0.0
    if isinstance(ham, (int, float)):
        mevcut = float(ham)
    elif isinstance(ham, list) and len(ham) >= 2:
        hedef = float(ham[0] or 0.0)
        mevcut = float(ham[1] or 0.0)
    if hedef == 0.0 and isinstance(hedef_ham, (int, float)):
        hedef = float(hedef_ham)
    return round(mevcut, 1), round(hedef, 1)


def yazici_durumu_oku(ip: str | None = None, zaman_asimi: float = 4.0) -> YaziciDurumu:
    """Elegoo Centauri Carbon yazıcısının anlık durumunu doğrudan SDCP v3 (WebSocket + UDP) ile okur."""
    hedef_ip = ip or ayarlari_yukle().printer_ip
    if not hedef_ip:
        return YaziciDurumu(hata_mesaji="PRINTER_IP ayarlı değil (.env)")
    mainboard_id = _udp_mainboard_id_bul(hedef_ip, zaman_asimi=1.0)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(zaman_asimi)
    try:
        s.connect((hedef_ip, 3030))
        ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
        istek = (
            f"GET /websocket HTTP/1.1\r\n"
            f"Host: {hedef_ip}:3030\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        s.sendall(istek.encode("ascii"))

        ham = b""
        while b"\r\n\r\n" not in ham:
            parca = s.recv(4096)
            if not parca:
                break
            ham += parca
        _, _, tampon = ham.partition(b"\r\n\r\n")

        # MainboardID biliniyorsa hemen Cmd 0 (GET_PRINTER_STATUS) ve Cmd 320 (GET_PRINT_HISTORY) gönder
        def _komut_gonder(mid: str, cmd: int, data: dict[str, Any]) -> None:
            zarf = {
                "Id": mid,
                "Data": {
                    "Cmd": cmd,
                    "Data": data,
                    "RequestID": secrets.token_hex(8),
                    "MainboardID": mid,
                    "TimeStamp": int(time.time() * 1000),
                    "From": 1,
                },
                "Topic": f"sdcp/request/{mid}",
            }
            s.sendall(_ws_istemci_cerceve_paketle(json.dumps(zarf, separators=(",", ":"))))

        def _durum_iste(mid: str) -> None:
            for cmd, data in ((512, {"TimePeriod": 5000}), (0, {}), (320, {})):
                _komut_gonder(mid, cmd, data)

        istek_gonderildi = False
        detay_istendi = False
        if mainboard_id:
            _durum_iste(mainboard_id)
            istek_gonderildi = True

        bitis = time.time() + zaman_asimi
        status_sozlugu: dict[str, Any] | None = None
        gecmis_dosya_adi: str = ""
        gecmis_sure_sn: int = 0

        while time.time() < bitis:
            mesajlar, tampon = _ws_cerceveleri_coz(tampon)
            for m in mesajlar:
                try:
                    paket = json.loads(m)
                except Exception:
                    continue
                ic_veri = paket.get("Data") if isinstance(paket.get("Data"), dict) else paket
                if not mainboard_id:
                    attr = paket.get("Attributes") or ic_veri.get("Attributes") or {}
                    mid = attr.get("MainboardID") or paket.get("MainboardID") or ic_veri.get("MainboardID")
                    if mid:
                        mainboard_id = str(mid)
                if mainboard_id and not istek_gonderildi:
                    _durum_iste(mainboard_id)
                    istek_gonderildi = True

                st = paket.get("Status") or ic_veri.get("Status")
                if isinstance(st, dict):
                    status_sozlugu = st

                # Cmd 320 yanıtından son TaskId'yi alıp Cmd 321 (detay) iste
                cmd_no = ic_veri.get("Cmd")
                cmd_data = ic_veri.get("Data") if isinstance(ic_veri.get("Data"), dict) else {}
                if cmd_no == 320 and mainboard_id and not detay_istendi:
                    h_list = cmd_data.get("HistoryData") or []
                    if h_list and isinstance(h_list[0], str):
                        _komut_gonder(mainboard_id, 321, {"Id": [h_list[0]]})
                        detay_istendi = True
                elif cmd_no == 321:
                    d_list = cmd_data.get("HistoryDetailList") or []
                    if d_list and isinstance(d_list[0], dict):
                        son_detay = d_list[0]
                        ham_task_ad = str(son_detay.get("TaskName") or "")
                        if ham_task_ad:
                            gecmis_dosya_adi = Path(ham_task_ad).name
                        bas_t = int(son_detay.get("BeginTime") or 0)
                        bit_t = int(son_detay.get("EndTime") or 0)
                        if bit_t > bas_t > 0:
                            gecmis_sure_sn = bit_t - bas_t

            # Hem status hem de dosya adı (veya geçmiş detayı) geldiyse döngüden çık
            if status_sozlugu is not None:
                pi_kontrol = status_sozlugu.get("PrintInfo") or {}
                if pi_kontrol.get("Filename") or gecmis_dosya_adi or not detay_istendi:
                    if pi_kontrol.get("Filename") or gecmis_dosya_adi:
                        break

            s.settimeout(max(0.3, bitis - time.time()))
            try:
                yeni = s.recv(8192)
                if not yeni:
                    break
                tampon += yeni
            except Exception:
                break

        if status_sozlugu is None:
            return YaziciDurumu(
                bagli=True,
                durum_kodu=0,
                durum_adi="BOSTA",
                hata_mesaji="",
            )

        pi = status_sozlugu.get("PrintInfo") if isinstance(status_sozlugu.get("PrintInfo"), dict) else {}
        cur_list = status_sozlugu.get("CurrentStatus") or status_sozlugu.get("CurrenStatus") or []
        pi_status = pi.get("Status")
        if isinstance(pi_status, int) and pi_status > 0:
            kod = pi_status
        elif isinstance(cur_list, list) and cur_list:
            kod = int(cur_list[0])
        else:
            kod = 0

        noz, noz_h = _sicaklik_cikar(status_sozlugu, "TempOfNozzle", "TempTargetNozzle")
        bed, bed_h = _sicaklik_cikar(status_sozlugu, "TempOfHotbed", "TempTargetHotbed")
        dosya = str(pi.get("Filename") or "") or gecmis_dosya_adi
        katman = int(pi.get("CurrentLayer") or 0)
        top_katman = int(pi.get("TotalLayer") or 0)
        gecen = int(float(pi.get("CurrentTicks") or 0))
        toplam = int(float(pi.get("TotalTicks") or 0))
        # Bazı firmware sürümlerinde ticks milisaniye cinsindendir
        if gecen > 100_000 and toplam > 100_000:
            gecen //= 1000
            toplam //= 1000
        if gecen <= 0 and gecmis_sure_sn > 0:
            gecen = gecmis_sure_sn
        ilerleme = float(pi.get("Progress") or 0.0)
        if ilerleme <= 0 and top_katman > 0:
            ilerleme = round((katman / top_katman) * 100.0, 1)

        return YaziciDurumu(
            bagli=True,
            durum_kodu=kod,
            durum_adi=DURUM_HARITASI.get(kod, f"KOD_{kod}"),
            nozul_sicaklik=noz,
            nozul_hedef=noz_h,
            tabla_sicaklik=bed,
            tabla_hedef=bed_h,
            dosya_adi=dosya,
            mevcut_katman=katman,
            toplam_katman=top_katman,
            ilerleme_yuzde=ilerleme,
            gecen_saniye=gecen,
            toplam_saniye=toplam,
        )
    except Exception as e:
        return YaziciDurumu(bagli=False, hata_mesaji=str(e))
    finally:
        try:
            s.close()
        except Exception:
            pass


def kamera_karesi_al(ip: str | None = None, zaman_asimi: float = 5.0) -> bytes | None:
    """Yazıcının MJPEG akışından (3031/video) tek bir JPEG karesi yakalar."""
    hedef_ip = ip or ayarlari_yukle().printer_ip
    url = f"http://{hedef_ip}:3031/video"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=zaman_asimi) as r:
            tampon = bytearray()
            while True:
                parca = r.read(4096)
                if not parca:
                    break
                tampon.extend(parca)
                bas = tampon.find(b"\xff\xd8")
                if bas != -1:
                    bit = tampon.find(b"\xff\xd9", bas + 2)
                    if bit != -1:
                        return bytes(tampon[bas : bit + 2])
                if len(tampon) > 2_000_000:
                    break
    except Exception:
        return None
    return None


def baski_durdur(ip: str | None = None) -> tuple[bool, str]:
    """Yalnızca kullanıcı Telegram'dan çift onay verdiğinde çağrılır (SDCP Cmd 130 STOP_PRINT)."""
    hedef_ip = ip or ayarlari_yukle().printer_ip
    mid = _udp_mainboard_id_bul(hedef_ip, zaman_asimi=1.5)
    if not mid:
        return False, "Yazıcı MainboardID alınamadığı için durdurma komutu gönderilemedi."
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(4.0)
    try:
        s.connect((hedef_ip, 3030))
        ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
        s.sendall(
            (
                f"GET /websocket HTTP/1.1\r\n"
                f"Host: {hedef_ip}:3030\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {ws_key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n\r\n"
            ).encode("ascii")
        )
        s.recv(4096)
        zarf = {
            "Id": mid,
            "Data": {
                "Cmd": 130,
                "Data": {"TaskId": "", "Filename": ""},
                "RequestID": secrets.token_hex(8),
                "MainboardID": mid,
                "TimeStamp": int(time.time() * 1000),
                "From": 1,
            },
            "Topic": f"sdcp/request/{mid}",
        }
        s.sendall(_ws_istemci_cerceve_paketle(json.dumps(zarf, separators=(",", ":"))))
        return True, "Yazıcıya durdurma komutu (SDCP Cmd 130) gönderildi."
    except Exception as e:
        return False, f"Durdurma komutu gönderilemedi: {e}"
    finally:
        try:
            s.close()
        except Exception:
            pass


def _sdcp_istek(cmd: int, data: dict[str, Any], ip: str | None = None, zaman_asimi: float = 6.0) -> dict | None:
    """Tek SDCP isteği gönderir ve aynı Cmd'nin yanıt verisini döndürür (yalnız okuma komutları için)."""
    hedef_ip = ip or ayarlari_yukle().printer_ip
    mid = _udp_mainboard_id_bul(hedef_ip, zaman_asimi=1.5)
    if not mid:
        return None
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(zaman_asimi)
    try:
        s.connect((hedef_ip, 3030))
        ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
        s.sendall((f"GET /websocket HTTP/1.1\r\nHost: {hedef_ip}:3030\r\nUpgrade: websocket\r\n"
                   f"Connection: Upgrade\r\nSec-WebSocket-Key: {ws_key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
                   ).encode("ascii"))
        ham = b""
        while b"\r\n\r\n" not in ham:
            parca = s.recv(4096)
            if not parca:
                return None
            ham += parca
        _, _, tampon = ham.partition(b"\r\n\r\n")
        rid = secrets.token_hex(8)
        zarf = {"Id": mid, "Data": {"Cmd": cmd, "Data": data, "RequestID": rid, "MainboardID": mid,
                                    "TimeStamp": int(time.time() * 1000), "From": 1},
                "Topic": f"sdcp/request/{mid}"}
        s.sendall(_ws_istemci_cerceve_paketle(json.dumps(zarf, separators=(",", ":"))))
        bitis = time.time() + zaman_asimi
        while time.time() < bitis:
            mesajlar, tampon = _ws_cerceveleri_coz(tampon)
            for m in mesajlar:
                try:
                    paket = json.loads(m)
                except Exception:
                    continue
                d = paket.get("Data") or {}
                if d.get("Cmd") == cmd and (d.get("RequestID") in (rid, None, "")):
                    return d.get("Data") or {}
            try:
                parca = s.recv(65536)
            except socket.timeout:
                break
            if not parca:
                break
            tampon += parca
        return None
    except Exception:
        return None
    finally:
        try:
            s.close()
        except Exception:
            pass


def yazici_dosyalari(ip: str | None = None) -> list[dict[str, Any]] | None:
    """Yazıcı yerel belleğindeki dosyalar (SDCP Cmd 258, salt okuma)."""
    d = _sdcp_istek(258, {"Url": "/local/"}, ip)
    if d is None:
        return None
    return list(d.get("FileList") or [])


def gcode_yukle(gcode: Path, hedef_ad: str | None = None, ip: str | None = None,
                parca_boyutu: int = 1024 * 1024) -> tuple[bool, str]:
    """Dilimlenmiş G-code'u yazıcının yerel belleğine yükler (SDCP HTTP /uploadFile/upload).
    BASKI BAŞLATMAZ. Yazıcı baskıdayken yüklemez."""
    import hashlib
    import uuid as _uuid

    hedef_ip = ip or ayarlari_yukle().printer_ip
    if not gcode.exists():
        return False, f"G-code yok: {gcode}"
    d = yazici_durumu_oku(hedef_ip)
    if not d.bagli:
        return False, "Yazıcıya bağlanılamadı."
    if d.durum_adi == "BASKIDA":
        return False, "Yazıcı şu an baskıda; yükleme baskı bitince yapılmalı."
    ad = hedef_ad or gcode.name
    veri = gcode.read_bytes()
    md5 = hashlib.md5(veri).hexdigest()
    kimlik = _uuid.uuid4().hex
    for ofset in range(0, len(veri), parca_boyutu):
        parca = veri[ofset:ofset + parca_boyutu]
        sinir = _uuid.uuid4().hex
        alanlar = {"S-File-MD5": md5, "Check": "1", "Offset": str(ofset), "Uuid": kimlik,
                   "TotalSize": str(len(veri))}
        govde = b"".join(
            f"--{sinir}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
            for k, v in alanlar.items())
        govde += (f"--{sinir}\r\nContent-Disposition: form-data; name=\"File\"; filename=\"{ad}\"\r\n"
                  "Content-Type: application/octet-stream\r\n\r\n").encode() + parca + f"\r\n--{sinir}--\r\n".encode()
        istek = urllib.request.Request(f"http://{hedef_ip}:3030/uploadFile/upload", data=govde, method="POST",
                                       headers={"Content-Type": f"multipart/form-data; boundary={sinir}"})
        try:
            with urllib.request.urlopen(istek, timeout=60) as r:
                yanit = r.read().decode("utf-8", "ignore")
        except Exception as e:
            return False, f"Yükleme hatası (ofset {ofset}): {e}"
        try:
            j = json.loads(yanit)
        except json.JSONDecodeError:
            j = {}
        if j and not (j.get("success") or str(j.get("code")) in ("000000", "0")):
            return False, f"Yazıcı yüklemeyi reddetti: {yanit[:200]}"
    liste = None
    for _ in range(8):  # yazıcı yeni dosyayı birkaç saniyede dizinler
        time.sleep(2)
        liste = yazici_dosyalari(hedef_ip)
        if liste is not None and any(str(f.get("name", "")).endswith("/" + ad) for f in liste):
            break
    else:
        if liste is not None:
            return False, f"Yükleme bitti ama `{ad}` 16 sn içinde yazıcı dosya listesinde görünmedi."
    return True, f"`{ad}` yazıcı belleğine yüklendi ({len(veri) / 1e6:.1f} MB). Baskıyı yazıcıdan başlatın."


class TimelapseToplayici:
    """Baskı süresince yazıcı iç kamerasından kare toplar ve baskı bitince MP4 yapar."""

    def __init__(self) -> None:
        self.aktif_dosya: str = ""
        self.kare_klasoru: Path | None = None
        self.kare_sayaci: int = 0

    def kare_ekle(self, dosya_adi: str, sku: str | None, jpeg_veri: bytes) -> Path | None:
        hedef_sku = sku or "_genel_baski"
        klasor = URUNLER_KLASORU / hedef_sku / "medya" / "timelapse_kareler"
        isaret_yolu = klasor / ".aktif_dosya"
        if dosya_adi != self.aktif_dosya or self.kare_klasoru != klasor:
            self.aktif_dosya = dosya_adi
            self.kare_klasoru = klasor
            klasor.mkdir(parents=True, exist_ok=True)
            onceki = isaret_yolu.read_text(encoding="utf-8").strip() if isaret_yolu.exists() else ""
            if onceki != dosya_adi:
                # Yeni bir baskı başladığında önceki yarım/eski kareleri temizle
                for eski in klasor.glob("kare_*.jpg"):
                    eski.unlink(missing_ok=True)
                isaret_yolu.write_text(dosya_adi, encoding="utf-8")
                self.kare_sayaci = 0
            else:
                mevcutlar = sorted(klasor.glob("kare_*.jpg"))
                if mevcutlar:
                    try:
                        son_no = int(mevcutlar[-1].stem.split("_")[-1])
                        self.kare_sayaci = son_no + 1
                    except ValueError:
                        self.kare_sayaci = len(mevcutlar)
                else:
                    self.kare_sayaci = 0

        kare_yolu = klasor / f"kare_{self.kare_sayaci:05d}.jpg"
        kare_yolu.write_bytes(jpeg_veri)
        self.kare_sayaci += 1
        return kare_yolu

    def mp4_derle(self, sku: str | None) -> Path | None:
        hedef_sku = sku or "_genel_baski"
        medya_klasoru = URUNLER_KLASORU / hedef_sku / "medya"
        kare_klasoru = medya_klasoru / "timelapse_kareler"
        if not kare_klasoru.exists():
            return None
        kareler = sorted(kare_klasoru.glob("kare_*.jpg"))
        if len(kareler) < 3:
            return None

        cikti_mp4 = medya_klasoru / "timelapse.mp4"
        fps = max(12, min(24, len(kareler) // 4)) if len(kareler) >= 24 else 6
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-framerate", str(fps),
                    "-pattern_type", "glob",
                    "-i", str(kare_klasoru / "kare_*.jpg"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                    str(cikti_mp4),
                ],
                check=True,
                capture_output=True,
            )
            # Video başarıyla derlendikten sonra kareleri ve işaretçiyi sıfırla
            for kare in kareler:
                kare.unlink(missing_ok=True)
            (kare_klasoru / ".aktif_dosya").unlink(missing_ok=True)
            self.aktif_dosya = ""
            self.kare_sayaci = 0
            return cikti_mp4
        except Exception:
            return None
