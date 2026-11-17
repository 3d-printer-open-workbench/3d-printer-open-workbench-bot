"""Fikir → Konsept → 3B hattı (Telegram `/fikir`).

Akış:
1. `/fikir <tarif>` → ürün klasörü + urun.yaml (durum KONSEPT) açılır; Claude, Chrome'daki
   Google Flow'un en kaliteli görsel modeliyle 4 konsept üretir, en iyi 2-3'ünü indirir.
   Ekran görüntüsü veya link verilirse referans olarak kullanılır (aynı konsept, özgün tasarım).
2. Bot indirilenleri `konsept/flow-N.jpg` olarak toplar ve Patrona butonlarla sunar (Onay ①).
3. Seçilen konsept → `coo/ai3d_mesh.py` (Hunyuan3D) → `coo/ai3d_hazirla.py` (düz taban, saksıysa
   drenaj) → kalite kapısı → Blender render → Telegram (Dilimle / Yeni konsept / İptal).

Bu modül Telegram'a bağlı değildir; `coo/__main__.py` çağırır ve test edilebilir saf işlevler sunar.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import unicodedata
from pathlib import Path
from typing import Any

import yaml

from .ayar import CALISMA_ALANI, COO_KLASORU, PROGRAMLAR_KLASORU, PY_AI3D, PY_CAD, URUNLER_KLASORU

AI3D_PYTHON = PY_AI3D
BLENDER_BETIK = COO_KLASORU / "gorsel" / "blender_ciz.py"
INDIRILEN_KLASORLER = [Path.home() / "İndirilenler", Path.home() / "Downloads"]

VARSAYILAN_YUKSEKLIK_MM = 120.0
DRENAJ_CAP_MM = 6.0
SKU_MAKS = 36  # callback_data 64 bayt sınırı: "fikir:sec:<sku>:<n>"

_SAKSI_KELIMELERI = ("saksı", "saksi", "planter", "kaktüs", "kaktus", "sukulent", "çiçeklik", "ciceklik")
_GORSEL_UZANTI = {".png", ".jpg", ".jpeg", ".webp"}
_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def sku_uret(tarif: str, urunler_klasoru: Path | None = None) -> str:
    """Tariften ASCII, kısa ve benzersiz bir SKU üretir (ör. 'cay-icen-teyze-saksi')."""
    kok = urunler_klasoru or URUNLER_KLASORU
    temiz = re.sub(r"\b\d{2,3}\s*mm\b", " ", tarif, flags=re.I).translate(_TR)
    temiz = unicodedata.normalize("NFKD", temiz).encode("ascii", "ignore").decode().lower()
    kelimeler = re.findall(r"[a-z0-9]+", temiz)
    sku = ""
    for k in kelimeler:
        aday = f"{sku}-{k}" if sku else k
        if len(aday) > SKU_MAKS - 3:
            break
        sku = aday
    sku = sku or "fikir"
    sonuc, i = sku, 2
    while (kok / sonuc).exists():
        sonuc, i = f"{sku}-{i}", i + 1
    return sonuc


def tarif_coz(tarif: str) -> dict[str, Any]:
    """Tariften hedef yüksekliği (ör. '140mm') ve saksı olup olmadığını çıkarır."""
    m = re.search(r"\b(\d{2,3})\s*mm\b", tarif, flags=re.I)
    yukseklik = float(m.group(1)) if m else VARSAYILAN_YUKSEKLIK_MM
    yukseklik = min(max(yukseklik, 30.0), 250.0)
    kucuk = tarif.lower()
    return {"yukseklik_mm": yukseklik, "saksi": any(k in kucuk for k in _SAKSI_KELIMELERI)}


def urun_klasoru_hazirla(
    sku: str, tarif: str, urunler_klasoru: Path | None = None, linkler: list[str] | None = None
) -> Path:
    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    for alt in ("konsept", "model/ai3d", "gorsel", "medya", "uretim"):
        (kok / alt).mkdir(parents=True, exist_ok=True)
    yaml_yolu = kok / "urun.yaml"
    if not yaml_yolu.exists():
        sablon = (urunler_klasoru or URUNLER_KLASORU) / "_sablon" / "urun.yaml"
        veri = yaml.safe_load(sablon.read_text(encoding="utf-8")) if sablon.exists() else {}
        cozum = tarif_coz(tarif)
        veri.update(
            sku=sku,
            ad=tarif[:80],
            kategori="B2C_DEKOR",
            durum="KONSEPT",
            cmo_konsept_ve_ana_prompt=f"Patron fikri (/fikir): {tarif}",
            tasarim_araci="ai3d (Hunyuan3D-2mini) + coo/ai3d_hazirla.py",
        )
        veri["fikir"] = {"tarif": tarif, "yukseklik_mm": cozum["yukseklik_mm"], "saksi": cozum["saksi"]}
        if linkler:
            veri["fikir"]["linkler"] = list(linkler)
        yaml_yolu.write_text(yaml.safe_dump(veri, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return kok


def urun_yaml_guncelle(sku: str, degisiklik: dict[str, Any], urunler_klasoru: Path | None = None) -> None:
    yol = (urunler_klasoru or URUNLER_KLASORU) / sku / "urun.yaml"
    veri = yaml.safe_load(yol.read_text(encoding="utf-8")) if yol.exists() else {}
    veri.update(degisiklik)
    yol.write_text(yaml.safe_dump(veri, allow_unicode=True, sort_keys=False), encoding="utf-8")


def fikir_linkleri_ekle(sku: str, linkler: list[str], urunler_klasoru: Path | None = None) -> None:
    yol = (urunler_klasoru or URUNLER_KLASORU) / sku / "urun.yaml"
    veri = yaml.safe_load(yol.read_text(encoding="utf-8")) if yol.exists() else {}
    fikir = veri.get("fikir") if isinstance(veri.get("fikir"), dict) else {}
    fikir["linkler"] = list(dict.fromkeys([*(fikir.get("linkler") or []), *linkler]))
    veri["fikir"] = fikir
    yol.write_text(yaml.safe_dump(veri, allow_unicode=True, sort_keys=False), encoding="utf-8")


def fikir_bilgisi(sku: str, urunler_klasoru: Path | None = None) -> dict[str, Any]:
    yol = (urunler_klasoru or URUNLER_KLASORU) / sku / "urun.yaml"
    veri = yaml.safe_load(yol.read_text(encoding="utf-8")) if yol.exists() else {}
    fikir = veri.get("fikir") if isinstance(veri.get("fikir"), dict) else {}
    tarif = str(fikir.get("tarif") or veri.get("ad") or sku)
    cozum = tarif_coz(tarif)
    return {
        "tarif": tarif,
        "yukseklik_mm": float(fikir.get("yukseklik_mm") or cozum["yukseklik_mm"]),
        "saksi": bool(fikir.get("saksi", cozum["saksi"])),
        "linkler": [str(u) for u in (fikir.get("linkler") or [])],
    }


URL_DESENI = re.compile(r"https?://[^\s<>\"]+")
_TARAYICI = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


def referans_ayir(metin: str) -> tuple[str, list[str]]:
    """Fikir metninden linkleri ayırır → (linksiz tarif, linkler)."""
    linkler = [u.rstrip(").,;") for u in URL_DESENI.findall(metin or "")]
    tarif = re.sub(r"\s+", " ", URL_DESENI.sub(" ", metin or "")).strip()
    return tarif, linkler


def referans_klasoru(sku: str, urunler_klasoru: Path | None = None) -> Path:
    d = (urunler_klasoru or URUNLER_KLASORU) / sku / "konsept" / "referans"
    d.mkdir(parents=True, exist_ok=True)
    return d


def referans_yolu(sku: str, uzanti: str = ".jpg", urunler_klasoru: Path | None = None) -> Path:
    d = referans_klasoru(sku, urunler_klasoru)
    n = len([p for p in d.iterdir() if p.suffix.lower() in _GORSEL_UZANTI]) + 1
    return d / f"ref-{n}{uzanti}"


def referanslar(sku: str, urunler_klasoru: Path | None = None) -> list[Path]:
    d = (urunler_klasoru or URUNLER_KLASORU) / sku / "konsept" / "referans"
    return sorted(p for p in d.glob("ref-*") if p.suffix.lower() in _GORSEL_UZANTI) if d.exists() else []


def _og_gorsel(html: str, taban: str) -> str | None:
    import urllib.parse

    for desen in (r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',
                  r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
                  r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)'):
        m = re.search(desen, html, flags=re.I)
        if m:
            return urllib.parse.urljoin(taban, m.group(1).replace("&amp;", "&"))
    return None


def linkten_referans(url: str, sku: str, urunler_klasoru: Path | None = None, zaman: float = 20) -> Path | None:
    """Linkteki ürün görselini (og:image) indirir; link doğrudan görselse onu alır. Olmazsa None."""
    import urllib.request

    def al(u: str) -> tuple[bytes, str]:
        req = urllib.request.Request(u, headers={"User-Agent": _TARAYICI, "Accept-Language": "tr,en;q=0.8"})
        with urllib.request.urlopen(req, timeout=zaman) as r:
            return r.read(8_000_000), str(r.headers.get("Content-Type") or "")

    try:
        veri, tur = al(url)
        if not tur.startswith("image/"):
            gorsel = _og_gorsel(veri.decode("utf-8", "ignore"), url)
            if not gorsel:
                return None
            veri, tur = al(gorsel)
        if not tur.startswith("image/") or len(veri) < 5000:
            return None
    except Exception:
        return None
    uzanti = {"image/png": ".png", "image/webp": ".webp"}.get(tur.split(";")[0], ".jpg")
    hedef = referans_yolu(sku, uzanti, urunler_klasoru)
    hedef.write_bytes(veri)
    return hedef


def flow_konsept_istemi(
    sku: str,
    tarif: str,
    saksi: bool,
    revize_notu: str = "",
    referans_gorseller: list[Path] | None = None,
    linkler: list[str] | None = None,
) -> str:
    """Claude'a (Chrome + Google Flow) verilecek görev istemi."""
    saksi_satiri = (
        "It is a flower planter: the top of the character/object must form a wide, clearly open, "
        "deep bowl opening (the pot cavity), at least 55% of the top width. "
        if saksi
        else ""
    )
    revize = f"\nPatron revize notu (istemi buna göre değiştir): {revize_notu}\n" if revize_notu else ""
    refler = [str(p) for p in (referans_gorseller or [])]
    referans = ""
    if refler or linkler:
        referans = (
            "\nREFERANS: Patron bu konsepte benzer bir ürün istiyor.\n"
            + (f"   Referans görseller (yerel dosya): {', '.join(refler)}\n" if refler else "")
            + (f"   Referans linkler: {', '.join(linkler or [])}\n" if linkler else "")
            + "   a) Önce referans görselleri Read ile incele; link varsa YENİ sekmede aç, ürünü incele (sayfada hiçbir "
            "şeye tıklayıp satın alma/giriş yapma). Konseptin özünü çıkar: obje/karakter türü, poz, oranlar, tarz, "
            "hikâye, fonksiyon (saksı/kalemlik vb.).\n"
            "   b) İstemi bu öze göre yaz; referans görseli Flow'a da 'malzeme' (ingredient) olarak yükle ve istemde "
            "'Use the reference image only for the concept, pose and style; create a new original design' de.\n"
            "   c) ÖZGÜNLÜK: aynı konsept/tarz, ama birebir kopya DEĞİL — yüz, kıyafet detayları ve aksesuarlar farklı "
            "olsun; logo, marka, telifli karakter kullanma. Referanstaki ürün başka bir satıcının tasarımıdır.\n"
            "   d) Referans renkli/boyalı olsa da çıktı tek renk mat beyaz olacak (aşağıdaki kurallar geçerli).\n"
        )
    yukleme = (
        "   Referans görseli yüklemek için: önce javascript_tool ile HTMLInputElement.prototype.click'i, type=file "
        "olanları yakalayıp DOM'a ekleyecek ve dialog AÇMAYACAK şekilde yamala; sonra '+' → 'Medya yükle'ye bas, "
        "find ile file-input'u bul, file_upload ile görseli yükle ve isteme ekle. 'Kullanım hakları' onay penceresi "
        "çıkarsa DUR ve `KONSEPT_HATA haklar onayı gerekli` yaz.\n"
        if refler else ""
    )
    return (
        f"Görev: Google Flow'da (Chrome, Patronun PRO oturumu) '{sku}' ürünü için 3B baskı konsept görseli üret.\n"
        f"Patronun Türkçe fikri: \"{tarif or 'referanstaki konsept'}\"{revize}{referans}\n"
        "KALİTE ÖNCELİKLİ: Bu görsel doğrudan 3B modele dönüşecek; görsel ne kadar temiz ve net olursa model o kadar "
        "düzgün olur. Kredi harcamak serbest.\n"
        "1) Fikri İNGİLİZCE tek paragraflık bir görsel istemine çevir. İstemde ŞUNLAR mutlaka olsun:\n"
        "   'Product concept for a 3D-printed object, single object, centered, fully visible with margin, plain pure "
        "white background, 3/4 front view, soft even studio light, crisp sharp details, high resolution.' + fikrin "
        f"özgün tarifi + '{saksi_satiri}Designer vinyl-toy style, smooth rounded chunky forms, all details sculpted "
        "in volume rather than painted, clean readable silhouette, no thin fragile parts (no glasses, no thin "
        "sticks), flat stable base. Entirely one material: unpainted matte warm-white clay, single color, no text, "
        "no logo.'\n"
        "   Mevcut bir markanın, çizgi film karakterinin veya satıcının tasarımını taklit etme; özgün olsun.\n"
        f"2) İstemi `02_Urunler/{sku}/konsept/istem.md` dosyasına yaz (kullandığın modeli de not et).\n"
        "3) Claude in Chrome araçlarını tek ToolSearch ile yükle (file_upload, javascript_tool dahil); "
        "tabs_context_mcp çağır; YENİ sekme aç; https://flow.google.com/ adresine git; 'Yeni proje' ile proje aç.\n"
        "4) Görsel modunda model seçicisini aç ve listedeki EN YÜKSEK KALİTELİ görsel modelini seç (ör. 'Pro' / "
        "'Ultra' / en yeni Nano Banana veya Imagen sürümü; ücretsiz olanı değil, kredi harcasa da). Çıktı adedi x4.\n"
        f"{yukleme}"
        "   İstemi yaz ve gönder. Görseller %100 olana kadar bekle (10 sn aralıklarla, en fazla ~5 dk).\n"
        "5) 4 sonucu Read/ekran görüntüsüyle değerlendir; obje kesik, birden fazla obje, renkli/boyalı, ince kırılgan "
        "parça veya bozuk anatomi olanları ele. En iyi 2-3 tanesini aç → 'Medyayı indir' → '1K Orijinal boyut'. "
        "(2K/4K yükseltme tasarımı iyileştirmez, seçme.) Video ÜRETME.\n"
        "6) Oluşturduğun sekmeleri kapat. Dosyaları taşıma; bot İndirilenler klasöründen kendisi toplar.\n"
        "7) Son yanıtın tek satır olsun: `KONSEPT_HAZIR <indirilen sayı> model=<model adı> kredi=<harcanan>`; "
        "hata varsa `KONSEPT_HATA <kısa neden>`.\n"
        "Kurallar: Giriş/ödeme/abonelik/kredi satın alma ekranlarında hiçbir şeyi onaylama, dur ve KONSEPT_HATA yaz. "
        "Aynı başarısız adımı 3 kereden fazla deneme."
    )


def konsept_gorselleri_topla(
    sku: str,
    baslangic_epoch: float,
    urunler_klasoru: Path | None = None,
    indirilen_klasorler: list[Path] | None = None,
) -> list[Path]:
    """İndirilenler'de `baslangic_epoch` sonrası gelen görselleri `konsept/flow-N.<ext>` olarak taşır."""
    hedef_dir = (urunler_klasoru or URUNLER_KLASORU) / sku / "konsept"
    hedef_dir.mkdir(parents=True, exist_ok=True)
    adaylar: list[Path] = []
    for klasor in indirilen_klasorler or INDIRILEN_KLASORLER:
        if not klasor.exists():
            continue
        for d in klasor.iterdir():
            if (d.is_file() and d.suffix.lower() in _GORSEL_UZANTI
                    and d.stat().st_mtime >= baslangic_epoch - 2.0):
                adaylar.append(d)
    adaylar.sort(key=lambda p: p.stat().st_mtime)

    mevcut = [int(m.group(1)) for p in hedef_dir.glob("flow-*")
              if (m := re.match(r"flow-(\d+)$", p.stem))]
    n = max(mevcut, default=0)
    tasinanlar: list[Path] = []
    for d in adaylar:
        n += 1
        hedef = hedef_dir / f"flow-{n}{d.suffix.lower()}"
        shutil.move(str(d), hedef)
        tasinanlar.append(hedef)
    return tasinanlar


def konsept_yolu(sku: str, no: int, urunler_klasoru: Path | None = None) -> Path | None:
    hedef_dir = (urunler_klasoru or URUNLER_KLASORU) / sku / "konsept"
    for p in hedef_dir.glob(f"flow-{no}.*"):
        if p.suffix.lower() in _GORSEL_UZANTI:
            return p
    return None


def _calistir(komut: list[str], zaman_asimi: int) -> tuple[bool, str]:
    try:
        s = subprocess.run(komut, cwd=str(PROGRAMLAR_KLASORU), capture_output=True, text=True, timeout=zaman_asimi)
    except subprocess.TimeoutExpired:
        return False, f"zaman aşımı ({zaman_asimi} sn): {' '.join(komut[:3])}"
    cikti = (s.stdout or "") + (s.stderr or "")
    return s.returncode == 0, cikti


def _son_json(metin: str) -> dict[str, Any]:
    for satir in reversed(metin.strip().splitlines()):
        satir = satir.strip()
        if satir.startswith("{") and satir.endswith("}"):
            try:
                return json.loads(satir)
            except json.JSONDecodeError:
                continue
    return {}


BLENDER_ONAR = COO_KLASORU / "blender_onar.py"
BLENDER_GORUNUS = COO_KLASORU / "blender_gorunus.py"
MESH_TOHUMLARI = "1234,42,777"
MIN_KALINLIK_MM = 1.0   # 0.4 mm nozul: ≥2 çevre çizgisi
HAZNE_DUVAR_MM = 2.0    # saksı duvarı: su/toprak yükü


def _sol_ayna(sol: Path) -> Path:
    """Qwen yan görünümü ürünün sol tarafını gösterir (yüz sağa bakar); Hunyuan3D-2mv 'left' girdisi
    yüzü görüntünün soluna bakan profil bekler → yatay aynala."""
    from PIL import Image, ImageOps

    hedef = sol.with_name("sol_ayna.png")
    ImageOps.mirror(Image.open(sol)).save(hedef)
    return hedef


def onarim_sorunlari(onar: dict[str, Any], hazirlik: dict[str, Any], kalite: dict[str, Any],
                     saksi: bool) -> list[str]:
    """Blender onarımından sonra hâlâ kalan, basılabilirliği bozan sorunlar (boşsa ürün hazır)."""
    son = onar.get("sonra") or {}
    s: list[str] = []
    if not son.get("manifold", False):
        s.append("Mesh su geçirmez değil (manifold olmayan kenarlar).")
    if son.get("ince_kose_yuzde", 0) > 0.3:
        s.append(f"Yüzeyin %{son['ince_kose_yuzde']}'i {MIN_KALINLIK_MM} mm'den ince (nozul basamaz).")
    if saksi and son.get("hazne_duvar_p5_mm") is not None and son["hazne_duvar_p5_mm"] < HAZNE_DUVAR_MM:
        s.append(f"Hazne duvarı ince (p5 {son['hazne_duvar_p5_mm']} mm < {HAZNE_DUVAR_MM} mm).")
    kopuk = (onar.get("adalar_son") or {}).get("kopuk_parca_cm3") or []
    if kopuk:
        s.append(f"Gövdeye bağlı olmayan {len(kopuk)} parça var ({kopuk} cm³) — havada basılamaz.")
    if saksi and not hazirlik.get("hazne"):
        s.append("Saksı istendi ama açık hazne yok.")
    if hazirlik.get("taban_temas_cm2", 0) < 10:
        s.append(f"Taban teması küçük ({hazirlik.get('taban_temas_cm2')} cm²) — devrilme riski.")
    if kalite.get("durum") != "PASS":
        s.extend(f"Kalite kapısı: {h}" for h in kalite.get("hatalar") or [])
    return s


def onarim_istemi(sku: str, sorunlar: list[str], urunler_klasoru: Path | None = None) -> str:
    """Otomatik onarımın çözemediği sorunlar için 3B Onarım ajanı (cad-artist) görevi."""
    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    stl = kok / "model" / f"{sku}.stl"
    py = str(PY_CAD)
    return (
        f"Görev: `{sku}` AI mesh'ini Blender'da basılabilir hale getir (Elegoo Centauri Carbon, 0.4 mm nozul, PLA).\n"
        f"Model: `{stl}` (Z-yukarı, mm, Z=0 düz taban). Konsept: `{kok}/konsept/`. 4 yön görünüm: "
        f"`{kok}/model/ai3d/gorunus.png`. Onarım raporu: `{kok}/model/ai3d/onar.json`.\n"
        "Otomatik onarımdan sonra KALAN sorunlar:\n" + "\n".join(f"- {x}" for x in sorunlar) + "\n\n"
        "KURALLAR:\n"
        "- Yalnız Blender (bpy, `blender -b -P betik.py`) ve trimesh/manifold3d kullan. Ürünün karakterini, "
        "yüzünü, oranlarını ve dış ölçülerini DEĞİŞTİRME; yalnızca sorunlu bölgeye yerel müdahale et "
        "(kalınlaştırma, kopuk parçayı gövdeye köprüleme ya da silme, delik kapatma, taban düzeltme).\n"
        f"- Önce orijinali `{kok}/model/ai3d/onar-oncesi.stl` olarak yedekle.\n"
        f"- Her düzeltmeden sonra ölç: `blender -b -P {BLENDER_ONAR} -- --girdi {stl} --cikti /dev/null "
        f"--rapor {kok}/model/ai3d/onar.json --sadece-olc --min-kalinlik {MIN_KALINLIK_MM} --hazne-duvar "
        f"{HAZNE_DUVAR_MM}` ve `{py} -m coo.kalite_kapisi {stl} --mod b2c`.\n"
        f"- Bitince görünümü yenile: `blender -b -P {BLENDER_GORUNUS} -- {stl} {kok}/model/ai3d/gorunus.png` ve "
        "Read ile kendin bak; bozulma varsa geri al.\n"
        "- En fazla 3 deneme. Son satır tek satır: `ONARIM_TAMAM <kısa özet>` veya `ONARIM_HATA <kalan sorun>`."
    )


def mesh_hatti(sku: str, konsept_no: int, urunler_klasoru: Path | None = None,
               cok_gorus: bool = True, ilerleme=None) -> dict[str, Any]:
    """Seçilen konseptten basılabilir STL + onarım/kalite raporu + render üretir (bloklayıcı; to_thread ile çağır).

    1) Qwen ile konseptten ön/sol/arka görünüm → Hunyuan3D-2mv (arka yüz görülür; olmazsa tek görüş mini)
    2) 3 tohum, konsept siluetine en sadık mesh seçilir
    3) ai3d_hazirla: düz taban, hazne, drenaj
    4) blender_onar: su geçirmezlik, kopuk parça, ince et / hazne duvarı kalınlaştırma, üçgen azaltma
    5) kalite kapısı + 4 yön görünüm + Blender stüdyo render; kalan sorunlar `onarim_sorunlari`
    """
    from .kalite_kapisi import kalite_kapisi_calistir

    def _ad(metin: str) -> None:
        if ilerleme:
            ilerleme(metin)

    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    gorsel = konsept_yolu(sku, konsept_no, urunler_klasoru)
    if gorsel is None:
        return {"basarili": False, "hata": f"konsept/flow-{konsept_no} bulunamadı"}
    bilgi = fikir_bilgisi(sku, urunler_klasoru)
    ai3d_dir = kok / "model" / "ai3d"
    stl = kok / "model" / f"{sku}.stl"
    ara_stl = ai3d_dir / "hazir.stl"
    t0 = time.time()

    mesh_komut = [str(AI3D_PYTHON), "coo/ai3d_mesh.py", str(gorsel), str(ai3d_dir), "--octree", "380",
                  "--adim", "50", "--tohumlar", MESH_TOHUMLARI, "--yukseklik-mm", str(bilgi["yukseklik_mm"])]
    gorus_notu = "tek görüş (mini)"
    if cok_gorus:
        gd = ai3d_dir / "gorusler"
        _ad("Qwen: ön / sol / arka görünüm")
        ok, cikti = _calistir(["python3", "-m", "coo.ai3d_gorusler", str(gorsel), str(gd)], 1800)
        if ok and all((gd / f"{a}.png").exists() for a in ("on", "sol", "arka")):
            mesh_komut[2] = str(gd / "on.png")
            mesh_komut += ["--model", "mv", "--sol", str(_sol_ayna(gd / "sol.png")), "--arka",
                           str(gd / "arka.png"), "--siluet", str(gorsel)]
            gorus_notu = "çok görüş (ön/sol/arka, Hunyuan3D-2mv)"
        else:
            mesh_komut += ["--model", "mini"]
    else:
        mesh_komut += ["--model", "mini"]
    _ad("Hunyuan3D: 3 tohumla mesh, konsepte en sadık olan")
    ok, cikti = _calistir(mesh_komut, 2400)
    if not ok and "--model" in mesh_komut and "mv" in mesh_komut:
        mesh_komut = [x for x in mesh_komut[:mesh_komut.index("--model")]] + ["--model", "mini"]
        mesh_komut[2] = str(gorsel)
        gorus_notu = "tek görüş (mini; mv başarısız)"
        ok, cikti = _calistir(mesh_komut, 1500)
    if not ok:
        return {"basarili": False, "hata": "mesh üretimi başarısız", "log": cikti[-1500:]}
    mesh_rapor = json.loads((ai3d_dir / "rapor.json").read_text(encoding="utf-8"))

    hazirla_komut = [str(AI3D_PYTHON), "coo/ai3d_hazirla.py", str(ai3d_dir / "ham.stl"), str(ara_stl)]
    if bilgi["saksi"]:
        hazirla_komut += ["--drenaj", str(DRENAJ_CAP_MM)]
    _ad("Baskı hazırlığı: düz taban, hazne")
    ok, cikti = _calistir(hazirla_komut, 600)
    if not ok:
        return {"basarili": False, "hata": "baskı hazırlığı başarısız", "log": cikti[-1500:]}
    hazirlik = _son_json(cikti)

    onar_komut = ["blender", "-b", "-P", str(BLENDER_ONAR), "--", "--girdi", str(ara_stl), "--cikti", str(stl),
                  "--rapor", str(ai3d_dir / "onar.json"), "--min-kalinlik", str(MIN_KALINLIK_MM),
                  "--hazne-duvar", str(HAZNE_DUVAR_MM)]
    if hazirlik.get("hazne"):
        onar_komut += ["--hazne", json.dumps(hazirlik["hazne"])]
    _ad("Blender onarım: kalınlık, kopuk parça, su geçirmezlik")
    ok, cikti = _calistir(onar_komut, 1800)
    if not ok or not stl.exists():
        return {"basarili": False, "hata": "Blender onarımı başarısız", "log": cikti[-1500:]}
    onar = json.loads((ai3d_dir / "onar.json").read_text(encoding="utf-8"))

    _ad("Kalite kapısı + render")
    kalite = kalite_kapisi_calistir(stl, mod="b2c")
    _calistir(["blender", "-b", "-P", str(BLENDER_GORUNUS), "--", str(stl), str(ai3d_dir / "gorunus.png")], 600)
    ok, cikti = _calistir(["blender", "-b", "-P", str(BLENDER_BETIK), "--", "--stl", str(stl),
                           "--cikti", str(kok / "gorsel"), "--renk", "#E8DFD1"], 900)
    render = kok / "gorsel" / "studyo.png"

    sorunlar = onarim_sorunlari(onar, hazirlik, kalite, bilgi["saksi"])
    uyarilar: list[str] = []
    if not ok or not render.exists():
        uyarilar.append("Blender render alınamadı.")
    siluet = mesh_rapor.get("siluet") or {}
    if siluet.get("iou") is not None and siluet["iou"] < 0.90:
        uyarilar.append(f"Konsept siluetine benzerlik düşük (IoU {siluet['iou']}) — konsepti kontrol et.")

    son = onar.get("sonra") or {}
    urun_yaml_guncelle(sku, {
        "durum": "TASARIM",
        "stl_yolu": f"model/{sku}.stl",
        "boyut_mm": dict(zip("xyz", son.get("boyut_mm") or hazirlik.get("boyut_mm", [0, 0, 0]))),
        "kalite_kapisi": {"durum": kalite.get("durum"), "hacim_cm3": kalite.get("hacim_cm3")},
        "ai3d": {"konsept": str(gorsel.relative_to(kok)), "gorus": gorus_notu,
                 "siluet_iou": siluet.get("iou"), "tohum": siluet.get("secilen_tohum"),
                 "hazne": hazirlik.get("hazne"), "drenaj_mm": hazirlik.get("drenaj_mm"),
                 "taban_temas_cm2": hazirlik.get("taban_temas_cm2"),
                 "onarim": {"min_kalinlik_p1_mm": son.get("kalinlik_p1_mm"),
                            "hazne_duvar_p5_mm": son.get("hazne_duvar_p5_mm"),
                            "kalinlastirilan_kose": sum(t.get("ince_kose", 0) for t in onar.get("kalinlastirma") or []),
                            "silinen_ada": (onar.get("adalar") or {}).get("silinen_kucuk_ada", 0),
                            "kalan_sorun": sorunlar},
                 "lisans_notu": "Hunyuan3D çıktısı — AB/UK/Güney Kore'de satılamaz."},
    }, urunler_klasoru)

    return {
        "basarili": True,
        "stl": stl,
        "render": render if render.exists() else None,
        "gorunus": ai3d_dir / "gorunus.png" if (ai3d_dir / "gorunus.png").exists() else None,
        "mesh": mesh_rapor,
        "gorus": gorus_notu,
        "hazirlik": hazirlik,
        "onar": onar,
        "kalite": kalite,
        "sorunlar": sorunlar,
        "uyarilar": uyarilar,
        "sure_sn": round(time.time() - t0),
    }


def mesh_ozeti(sonuc: dict[str, Any]) -> str:
    h = sonuc.get("hazirlik") or {}
    k = sonuc.get("kalite") or {}
    b = h.get("boyut_mm") or [0, 0, 0]
    satirlar = [
        f"• *Boyut:* `{b[0]}×{b[1]}×{b[2]} mm` • *Hacim:* `{h.get('hacim_cm3')} cm³`",
        f"• *Kalite kapısı:* `{k.get('durum', '?')}` • *Su geçirmez:* `{'Evet' if h.get('su_gecirmez') else 'HAYIR'}`",
        f"• *Taban teması:* `{h.get('taban_temas_cm2')} cm²`",
    ]
    hz = h.get("hazne")
    if hz:
        satirlar.append(f"• *Hazne:* `Ø{hz['ust_cap_mm']} mm`, `{hz['derinlik_mm']} mm` derin"
                        + (f" • *Drenaj:* `Ø{h.get('drenaj_mm')} mm`" if h.get("drenaj_mm") else ""))
    o = (sonuc.get("onar") or {})
    if o:
        son = o.get("sonra") or {}
        kal = sum(t.get("ince_kose", 0) for t in o.get("kalinlastirma") or [])
        satirlar.append(f"• *Blender onarım:* en ince et `{son.get('kalinlik_p1_mm')} mm`"
                        + (f", hazne duvarı `{son.get('hazne_duvar_p5_mm')} mm`" if son.get("hazne_duvar_p5_mm") else "")
                        + f", kalınlaştırılan nokta `{kal}`, `{son.get('ucgen')}` üçgen")
    m = (sonuc.get("mesh") or {}).get("siluet") or {}
    if sonuc.get("gorus"):
        satirlar.append(f"• *3B kaynak:* {sonuc['gorus']}" + (f" • konsept benzerliği `{m.get('iou')}`" if m else ""))
    satirlar.append(f"• *Süre:* `{sonuc.get('sure_sn')} sn`")
    for u in sonuc.get("sorunlar") or []:
        satirlar.append(f"🛠️ {u}")
    for u in sonuc.get("uyarilar") or []:
        satirlar.append(f"⚠️ {u}")
    return "\n".join(satirlar)
