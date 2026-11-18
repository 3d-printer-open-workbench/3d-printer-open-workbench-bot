"""🗑️ Ürün Sil ve 🧹 Klasör Temizliği (Patron isteği 2026-11-18).

"satışta olmayan onaylanmamış ürünlerden seçerek silebileyim ve PC'de bulunan klasörü istediğim zaman
temizleyebileyim: arşive alınmış ürünlerin kaynak dosyalarının silinmesi, onaylanmamış görsellerin temizlenmesi gibi."

Temel kural: EMİN OLUNAMAYAN HİÇBİR DOSYA SİLİNMEZ. Silme = masaüstü çöp kutusuna taşıma (`gio trash`; gio yoksa
`veri/99_Cop/<tarih>/` altına taşıma) — geri alınabilir. Tarama işlevleri saf ve klasör parametrelidir (dosyaya
dokunmaz); yalnız `cope_tasi` / `urun_sil` / `temizle` dosya taşır.

Silme kuralları (yollar ürün klasörüne göre glob):
- (a) `arsiv` — durumu IPTAL (🗄️ Arşivle) ürünlerde `ARSIV_ARA_DESENLER`.
- (b) `gorsel` — tüm ürünlerde `RED_GORSEL_DESENLER` + seçilmemiş konsept adayları (yalnız `urun.yaml > ai3d.konsept`
  bir seçim kaydediyorsa ve son STL varsa; seçilen korunur).
- (c) `video` — Video_Atölyesi `*/renders/*` dosyaları: AYNI İÇERİKLİ (boyut + SHA-256) kopyası `veri/` altında
  (ürün medya/ klasörü, serbest_reels) bulunanlar. Kopyası olmayan render silinmez.
- (c) `npm` — Video_Atölyesi `node_modules/` ve proje önbellekleri (`.hyperframes/`, `.media/`): `npm ci` ile geri gelir.

Her durumda KORUNAN (aday olsa bile listeye girmez): `KORUNAN_DESENLER`, `urun.yaml` içinde geçen her göreli yol,
`magaza/gorseller.json` (dosya + kaynak), `magaza/paket.json` görselleri, `gorsel/denetim.json` kareleri,
`medya/pinterest/pin.json` görseli, Reels denetim kayıtlarındaki videolar; son `MIN_YAS_SN` içinde değişmiş dosyalar
(çalışan iş olabilir) ve şu an iş çalışan ürünler.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import fnmatch
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable

import yaml

from .ayar import KOK, MAGAZA_KLASORU, URUNLER_KLASORU, VERI_KLASORU

GIZLI_KLASORLER = {"_sablon", "_genel_baski", "_ozel_baski"}
VIDEO_ATOLYESI = KOK / "Video_Atölyesi"
COP_KLASORU = VERI_KLASORU / "99_Cop"
REELS_DENETIM_KLASORU = MAGAZA_KLASORU / "reels_denetim"
MIN_YAS_SN = 6 * 3600  # son 6 saatte değişen dosya çalışan bir işe ait olabilir → dokunma

# (a) Arşivlenmiş ürün: kaynak/ara dosyalar ("{sku}" ürün adıyla değiştirilir)
ARSIV_ARA_DESENLER: tuple[str, ...] = (
    "model/ai3d/**",                 # Hunyuan3D ara çıktıları: ham/hazir STL, GLB, Qwen görünümleri, girdi kareleri
    "model/cok_renk/parcala.stl",    # çok renk ara mesh'leri ve etiket dizileri
    "model/cok_renk/renkli.stl",
    "model/cok_renk/*.npz",
    "model/cok_renk/parcalar_pano.png",
    "model/cok_renk/parca_kareler/**",
    "model/cok_renk/boyali_kareler/**",
    "model/cok_renk/_yedek_*/**",
    "model/sanal_test/**",           # sanal kullanım testi kareleri/betikleri
    "model/*_RED.*",                 # reddedilmiş model sürümleri
    "gorsel/sahne/qwen-tmp/**",      # Qwen ara kareleri
    "gorsel/sahne/eski/**",
    "gorsel/konsept/eski/**",
    "medya/*-red.mp4",
    "medya/*-red[0-9]*.mp4",
    "medya/*-ham.mp4",
    "**/*.blend",
    "**/*.blend1",
    "**/*.bak-*",
    "konsept/kartela.png",           # kartela önizlemesi (her açılışta yeniden çizilir)
)

# (b) Tüm ürünlerde: onaylanmamış / reddedilmiş / yerini yenisine bırakmış görsel ve videolar
RED_GORSEL_DESENLER: tuple[str, ...] = (
    "gorsel/sahne/qwen-tmp/**",      # Qwen aday kareleri (tohum denemeleri) ve girdi render'ları; son kare studyo-ic/'de
    "gorsel/sahne/eski/**",          # yeniden üretimde yerini yenisine bırakan kullanım görselleri
    "gorsel/konsept/eski/**",        # eski teknik posterleri
    "medya/*-red.mp4",               # sadakat denetiminden kalan (reddedilen) videolar
    "medya/*-red[0-9]*.mp4",
)
KONSEPT_ADAY_DESENI = "konsept/flow-*"

# Her durumda korunur ("{sku}" ürün adıyla değiştirilir)
KORUNAN_DESENLER: tuple[str, ...] = (
    "urun.yaml",
    "magaza/**",
    "model/{sku}.stl",
    "uretim/{sku}.3mf",
    "uretim/{sku}.gcode",
    "uretim/*-tabla.png",
    "model/cok_renk/renkli.3mf",
    "model/cok_renk/sema*.json",
    "model/cok_renk/rapor.json",
    "model/cok_renk/kurallar.json",
    "model/cok_renk/render/**",      # onaylı çok renk render'ı ve e-ticaret kareleri
    "gorsel/renkler/**",             # tek renk render'ları ve e-ticaret kareleri
    "gorsel/*.png",                  # ana render'lar (beyaz/studyo/yakin/seffaf) ve kullanım görselleri
    "gorsel/konsept/*-3x4.png",      # geçerli teknik poster
    "gorsel/konsept/*-9x16.png",
    "gorsel/numune-*",               # gerçek numune fotoğrafları
    "konsept/referans/**",
    "konsept/istem.md",
    "medya/pinterest/**",
    "medya/reels-son.mp4",
    "pazar/**",
)

VIDEO_ONBELLEK_KLASORLERI = (".hyperframes", ".media")

KATEGORILER: dict[str, tuple[str, str]] = {
    "arsiv": ("🗄️ Arşivlenen ürünlerin ara dosyaları",
              "Hunyuan/ComfyUI ara çıktıları, çok renk ara mesh'leri, sanal test, reddedilen model sürümleri"),
    "gorsel": ("🖼️ Onaylanmamış / reddedilmiş görseller",
               "Qwen aday kareleri, eski poster/kullanım görselleri, reddedilen videolar, seçilmeyen konseptler"),
    "video": ("🎞️ Video Atölyesi: ürüne kopyalanmış render'lar",
              "Aynısı ürünün medya/ klasöründe duran render kopyaları (ürün kopyası korunur)"),
    "npm": ("📦 Video Atölyesi: node_modules + önbellek",
            "Yeniden oluşturulabilir; HyperFrames Reels'ten önce `npm ci` ile geri kurulur"),
}

_YOL_DESENI = re.compile(r"(?:^|[\s'\"(;:,])((?:model|gorsel|medya|konsept|uretim|magaza|pazar)/[^\s'\"),;]+)")


# --- yardımcılar -------------------------------------------------------------------------------------
def _yaml(kok: Path) -> dict[str, Any]:
    yol = kok / "urun.yaml"
    if not yol.exists():
        return {}
    try:
        v = yaml.safe_load(yol.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return v if isinstance(v, dict) else {}


def _json(yol: Path) -> Any:
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def boyut(yol: Path) -> int:
    """Dosya ya da klasör boyutu (bayt; sembolik bağlar izlenmez)."""
    if yol.is_symlink() or yol.is_file():
        try:
            return yol.lstat().st_size
        except OSError:
            return 0
    toplam = 0
    for p in yol.rglob("*"):
        try:
            if p.is_symlink() or p.is_file():
                toplam += p.lstat().st_size
        except OSError:
            continue
    return toplam


def boyut_metni(bayt: int) -> str:
    for birim, b in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if bayt >= b:
            return f"{bayt / b:.1f} {birim}".replace(".", ",")
    return f"{bayt} B"


def _eslesir(rel: str, desenler: Iterable[str], sku: str) -> bool:
    for d in desenler:
        d = d.replace("{sku}", sku)
        if d.endswith("/**"):
            if rel.startswith(d[:-2]):
                return True
        elif d.startswith("**/"):
            if fnmatch.fnmatchcase(Path(rel).name, d[3:]):
                return True
        elif fnmatch.fnmatchcase(rel, d) and rel.count("/") == d.count("/"):
            return True
    return False


def _dosyalar(kok: Path) -> list[Path]:
    return sorted(p for p in kok.rglob("*") if p.is_file() and not p.is_symlink())


def _yaml_yollari(veri: Any) -> set[str]:
    """urun.yaml'daki her metinden ürün köküne göre göreli yolları çıkarır (ör. 'model/v1_kisa_RED.stl')."""
    bulunan: set[str] = set()
    if isinstance(veri, dict):
        for v in veri.values():
            bulunan |= _yaml_yollari(v)
    elif isinstance(veri, list):
        for v in veri:
            bulunan |= _yaml_yollari(v)
    elif isinstance(veri, str):
        bulunan |= {m.rstrip(".") for m in _YOL_DESENI.findall(veri)}
    return bulunan


def korunan_yollar(kok: Path, reels_klasoru: Path | None = None) -> set[str]:
    """Ürün klasöründe kayıtlarla 'onaylı/seçili/kullanılıyor' olduğu bilinen göreli yollar."""
    sku = kok.name
    k: set[str] = set(_yaml_yollari(_yaml(kok)))

    def _rel(deger: Any) -> None:
        if not isinstance(deger, str) or not deger:
            return
        p = Path(deger)
        if p.is_absolute():
            try:
                k.add(str(p.resolve().relative_to(kok.resolve())))
            except ValueError:
                return
        else:
            k.add(deger)

    g = _json(kok / "magaza" / "gorseller.json") or {}
    for x in (g.get("gorseller") or []) if isinstance(g, dict) else []:
        if isinstance(x, dict):
            _rel(x.get("dosya"))
            _rel(x.get("kaynak"))
    for v in (g.get("varyantlar") or []) if isinstance(g, dict) else []:
        for x in (v.get("gorseller") or []) if isinstance(v, dict) else []:
            if isinstance(x, dict):
                _rel(x.get("dosya"))
                _rel(x.get("kaynak"))
            else:
                _rel(x)
    p = _json(kok / "magaza" / "paket.json") or {}
    if isinstance(p, dict):
        for x in p.get("gorseller") or []:
            _rel(x)
        for v in p.get("varyantlar") or []:
            for x in (v.get("gorseller") or []) if isinstance(v, dict) else []:
                _rel(x)
    d = _json(kok / "gorsel" / "denetim.json") or {}
    for x in (d.get("kareler") or []) if isinstance(d, dict) else []:
        if isinstance(x, dict):
            _rel(x.get("yol"))
    pin = _json(kok / "medya" / "pinterest" / "pin.json") or {}
    if isinstance(pin, dict):
        _rel(pin.get("gorsel"))
    rk = reels_klasoru or REELS_DENETIM_KLASORU
    if rk.exists():
        for yol in rk.glob("*.json"):
            r = _json(yol) or {}
            if isinstance(r, dict) and (r.get("kaynak") or {}).get("sku") == sku:
                _rel(r.get("video"))
                _rel(r.get("yeni_video"))
    return {x.lstrip("./") for x in k} | {f"model/{sku}.stl"}


def _aday(yol: Path, kat: str, neden: str) -> dict[str, Any]:
    return {"yol": yol, "boyut": boyut(yol), "kat": kat, "neden": neden}


# --- tarama -----------------------------------------------------------------------------------------
def urun_adaylari(kok: Path, simdi: float | None = None, min_yas_sn: int = MIN_YAS_SN,
                  reels_klasoru: Path | None = None) -> list[dict[str, Any]]:
    """Tek ürün klasörü için (a) arsiv ve (b) gorsel adayları."""
    sku = kok.name
    v = _yaml(kok)
    arsiv = str(v.get("durum") or "") == "IPTAL"
    korunan = korunan_yollar(kok, reels_klasoru)
    simdi = time.time() if simdi is None else simdi
    secili_konsept = str(((v.get("ai3d") or {}) if isinstance(v.get("ai3d"), dict) else {}).get("konsept") or "")
    konsept_secimi_kesin = bool(secili_konsept) and (kok / secili_konsept).exists() and (kok / "model" / f"{sku}.stl").exists()
    adaylar = []
    for p in _dosyalar(kok):
        rel = p.relative_to(kok).as_posix()
        if (rel in korunan or any(k.endswith("/") and rel.startswith(k) for k in korunan)
                or _eslesir(rel, KORUNAN_DESENLER, sku)):
            continue
        try:
            if simdi - p.stat().st_mtime < min_yas_sn:
                continue
        except OSError:
            continue
        if _eslesir(rel, RED_GORSEL_DESENLER, sku):
            adaylar.append(_aday(p, "arsiv" if arsiv else "gorsel", "reddedilmiş / ara görsel"))
        elif (konsept_secimi_kesin and fnmatch.fnmatchcase(rel, KONSEPT_ADAY_DESENI) and rel.count("/") == 1
              and rel != secili_konsept):
            adaylar.append(_aday(p, "arsiv" if arsiv else "gorsel", f"seçilmeyen konsept (seçilen: {secili_konsept})"))
        elif arsiv and _eslesir(rel, ARSIV_ARA_DESENLER, sku):
            adaylar.append(_aday(p, "arsiv", "arşivlenen ürünün ara dosyası"))
    return adaylar


def _sha256(yol: Path) -> str:
    h = hashlib.sha256()
    with yol.open("rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()


def video_adaylari(atolye: Path | None = None, veri: Path | None = None, simdi: float | None = None,
                   min_yas_sn: int = MIN_YAS_SN) -> list[dict[str, Any]]:
    """(c) Video_Atölyesi: kopyası veri/ altında duran render'lar ('video') + node_modules/önbellek ('npm')."""
    atolye = atolye or VIDEO_ATOLYESI
    veri = veri or VERI_KLASORU
    simdi = time.time() if simdi is None else simdi
    if not atolye.exists():
        return []
    adaylar: list[dict[str, Any]] = []
    renders = [p for p in atolye.glob("*/renders/*") if p.is_file() and not p.is_symlink()]
    renders = [p for p in renders if simdi - p.stat().st_mtime >= min_yas_sn]
    if renders and veri.exists():
        boyutlar = {p.stat().st_size for p in renders}
        kopyalar: dict[int, list[Path]] = {}
        for p in veri.rglob("*.mp4"):
            if COP_KLASORU.name in p.relative_to(veri).parts:  # çöpteki kopya sayılmaz
                continue
            try:
                if p.is_file() and not p.is_symlink() and p.stat().st_size in boyutlar:
                    kopyalar.setdefault(p.stat().st_size, []).append(p)
            except OSError:
                continue
        for r in renders:
            esler = kopyalar.get(r.stat().st_size) or []
            if not esler:
                continue
            ozet = _sha256(r)
            es = next((e for e in esler if _sha256(e) == ozet), None)
            if es:
                adaylar.append(_aday(r, "video", f"kopyası: {es.relative_to(veri).as_posix()}"))
    nm = atolye / "node_modules"
    if nm.is_dir() and (atolye / "package.json").exists():
        adaylar.append(_aday(nm, "npm", "npm ci ile yeniden kurulur"))
    for ad in VIDEO_ONBELLEK_KLASORLERI:
        for d in [atolye / ad, *atolye.glob(f"*/{ad}")]:
            if d.is_dir() and not d.is_symlink():
                adaylar.append(_aday(d, "npm", "HyperFrames önbelleği"))
    return adaylar


def tara(urunler: Path | None = None, atolye: Path | None = None, veri: Path | None = None,
         mesgul: Iterable[str] = (), simdi: float | None = None, min_yas_sn: int = MIN_YAS_SN,
         reels_klasoru: Path | None = None, video_mesgul: bool = False) -> dict[str, list[dict[str, Any]]]:
    """KURU tarama (hiçbir şey silmez). Dönüş: kategori → aday listesi ({yol, boyut, kat, neden}).
    mesgul: şu an iş çalışan ürünler (atlanır); video_mesgul: HyperFrames işi çalışıyor (Video_Atölyesi atlanır)."""
    urunler = urunler or URUNLER_KLASORU
    sonuc: dict[str, list[dict[str, Any]]] = {k: [] for k in KATEGORILER}
    mesgul = set(mesgul)
    if urunler.exists():
        for d in sorted(urunler.iterdir()):
            if not d.is_dir() or d.name in GIZLI_KLASORLER or d.name.startswith((".", "_")) or d.name in mesgul:
                continue
            for a in urun_adaylari(d, simdi, min_yas_sn, reels_klasoru):
                sonuc[a["kat"]].append(a)
    for a in ([] if video_mesgul else video_adaylari(atolye, veri, simdi, min_yas_sn)):
        sonuc[a["kat"]].append(a)
    return sonuc


def tarama_ozeti(tarama: dict[str, list[dict[str, Any]]], secili: Iterable[str] = ()) -> str:
    secili = set(secili)
    satirlar = ["🧹 *Klasör Temizliği — tarama* (henüz hiçbir şey silinmedi)", ""]
    for kat, (baslik, aciklama) in KATEGORILER.items():
        liste = tarama.get(kat) or []
        isaret = "☑" if kat in secili else "☐"
        satirlar.append(f"{isaret} *{baslik}* — {len(liste)} öğe, {boyut_metni(sum(a['boyut'] for a in liste))}\n"
                        f"   _{aciklama}_")
    satirlar += ["", "Silinecek kategorileri seç (☐ → ☑), sonra *🗑️ Seçilenleri Temizle*. Dosyalar çöp kutusuna "
                 "taşınır, oradan geri alınabilir. Emin olunamayan dosya listeye girmez."]
    return "\n".join(satirlar)


def onay_ozeti(tarama: dict[str, list[dict[str, Any]]], secili: Iterable[str], ornek: int = 4,
               kok: Path | None = None) -> str:
    kok = kok or KOK
    secili = [k for k in KATEGORILER if k in set(secili)]
    toplam_adet = sum(len(tarama.get(k) or []) for k in secili)
    toplam = sum(a["boyut"] for k in secili for a in tarama.get(k) or [])
    satirlar = [f"⚠️ *Emin misin?* {toplam_adet} öğe, toplam *{boyut_metni(toplam)}* çöp kutusuna taşınacak "
                "(oradan geri alınabilir).", ""]
    for k in secili:
        liste = tarama.get(k) or []
        satirlar.append(f"*{KATEGORILER[k][0]}* — {len(liste)} öğe, {boyut_metni(sum(a['boyut'] for a in liste))}")
        for a in sorted(liste, key=lambda x: -x["boyut"])[:ornek]:
            try:
                rel = a["yol"].relative_to(kok).as_posix().replace("veri/02_Urunler/", "")
            except ValueError:
                rel = a["yol"].name
            rel = rel if len(rel) <= 70 else "…" + rel[-69:]
            satirlar.append(f"  • `{rel}` ({boyut_metni(a['boyut'])})")
        if len(liste) > ornek:
            satirlar.append(f"  • … ve {len(liste) - ornek} öğe daha")
    return "\n".join(satirlar)


# --- çöpe taşıma ------------------------------------------------------------------------------------
def cope_tasi(yollar: Iterable[Path], cop_klasoru: Path | None = None, gio: bool | None = None,
              kok: Path | None = None) -> dict[str, Any]:
    """Yolları masaüstü çöp kutusuna (`gio trash`) ya da `cop_klasoru/<tarih>/<göreli yol>` altına taşır.
    gio'nun taşıyamadıkları da klasöre taşınır. Dönüş: {yontem, tasinan, hatalar, cop?}."""
    kalan = [Path(p) for p in yollar if Path(p).exists() or Path(p).is_symlink()]
    gio = (shutil.which("gio") is not None) if gio is None else gio
    tasinan: list[Path] = []
    yontem = None
    if gio and kalan:
        tasinamayan: list[Path] = []
        for i in range(0, len(kalan), 100):
            grup = kalan[i:i + 100]
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                subprocess.run(["gio", "trash", "--", *map(str, grup)], capture_output=True, text=True, timeout=300)
            tasinamayan += [p for p in grup if p.exists() or p.is_symlink()]
        tasinan += [p for p in kalan if p not in tasinamayan]
        yontem = "gio" if tasinan else None
        kalan = tasinamayan
    sonuc: dict[str, Any] = {"yontem": yontem, "tasinan": tasinan, "hatalar": []}
    if not kalan:
        return sonuc
    hedef_kok = (cop_klasoru or COP_KLASORU) / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    kok = kok or KOK
    for p in kalan:
        try:
            rel = p.resolve().relative_to(kok.resolve())
        except ValueError:
            rel = Path(p.name)
        hedef = hedef_kok / rel
        try:
            hedef.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(hedef))
            tasinan.append(p)
        except OSError:
            sonuc["hatalar"].append(p)
    sonuc["yontem"] = "klasor" if yontem is None else "gio+klasor"
    sonuc["cop"] = str(hedef_kok)
    return sonuc


def temizle(secili: Iterable[str], onceki: dict[str, list[dict[str, Any]]], **tara_arg: Any) -> dict[str, Any]:
    """Onaylanan kategorileri çöpe taşır. Güvenlik: yeniden tarar; yalnız onay anında listelenen VE hâlâ aday olan
    yollar taşınır (aradaki değişiklikle korumaya giren dosya silinmez)."""
    cop_klasoru = tara_arg.pop("cop_klasoru", None)
    gio = tara_arg.pop("gio", None)
    simdi = tara(**tara_arg)
    yollar: list[Path] = []
    toplam = 0
    for kat in secili:
        eski = {str(a["yol"]) for a in onceki.get(kat) or []}
        for a in simdi.get(kat) or []:
            if str(a["yol"]) in eski:
                yollar.append(a["yol"])
                toplam += a["boyut"]
    if not yollar:
        return {"yontem": None, "tasinan": [], "hatalar": [], "bayt": 0}
    sonuc = cope_tasi(yollar, cop_klasoru, gio)
    sonuc["bayt"] = toplam
    return sonuc


# --- 🗑️ Ürün Sil ------------------------------------------------------------------------------------
def silme_engeli(sku: str, urunler: Path | None = None) -> str | None:
    """Ürün silinemezse nedeni; silinebilirse None. Satıştaki/onaylı ürün ASLA silinmez."""
    urunler = urunler or URUNLER_KLASORU
    if not sku or "/" in sku or "\\" in sku or sku.startswith((".", "_")) or sku in GIZLI_KLASORLER:
        return "geçersiz ürün"
    kok = urunler / sku
    if not kok.is_dir() or kok.resolve().parent != urunler.resolve():
        return "ürün klasörü yok"
    v = _yaml(kok)
    ikas = v.get("ikas") if isinstance(v.get("ikas"), dict) else {}
    yukleme = _json(kok / "magaza" / "yukleme.json") if (kok / "magaza" / "yukleme.json").exists() else None
    if (kok / "magaza" / "yukleme.json").exists() or (isinstance(yukleme, dict) and yukleme.get("panel_linki")):
        return "satışta (İkas yükleme kaydı var)"
    if ikas.get("panel_linki") or ikas.get("urun_linki") or str(v.get("durum") or "") == "SATISTA":
        return "satışta"
    if str(v.get("icerik_onayi") or "") == "ONAYLANDI":
        return "içerik onaylı"
    return None


def silinebilir_urunler(urunler: Path | None = None) -> list[dict[str, Any]]:
    urunler = urunler or URUNLER_KLASORU
    if not urunler.exists():
        return []
    sonuc = []
    for d in sorted(urunler.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir() or silme_engeli(d.name, urunler):
            continue
        v = _yaml(d)
        erp = v.get("erp") if isinstance(v.get("erp"), dict) else {}
        sonuc.append({"sku": d.name, "ad": str(v.get("ad") or d.name), "durum": str(v.get("durum") or "—"),
                      "boyut": boyut(d), "erp_id": erp.get("product_id")})
    return sonuc


def silme_ozeti(urunler_listesi: list[dict[str, Any]]) -> str:
    toplam = sum(u["boyut"] for u in urunler_listesi)
    satirlar = [f"⚠️ *Emin misin?* {len(urunler_listesi)} ürün klasörü (toplam *{boyut_metni(toplam)}*) "
                "çöp kutusuna taşınacak, oradan geri alınabilir.", ""]
    for u in urunler_listesi:
        satirlar.append(f"• *{u['ad']}* `{u['sku']}` — {u['durum']}, {boyut_metni(u['boyut'])}")
    erp = [u for u in urunler_listesi if u.get("erp_id")]
    if erp:
        satirlar += ["", "🧾 *ERP uyarısı:* şu ürünlerin ERP kaydı var — ERP kaydı SİLİNMEZ, gerekirse ERP'den ayrıca "
                     "pasifleştir: " + ", ".join(f"`{u['sku']}` (#{u['erp_id']})" for u in erp)]
    return "\n".join(satirlar)


def urun_sil(skular: Iterable[str], urunler: Path | None = None, cop_klasoru: Path | None = None,
             gio: bool | None = None) -> dict[str, Any]:
    """Seçilen ürün klasörlerini çöpe taşır. Her ürün taşımadan hemen önce yeniden denetlenir; satıştaki/onaylı
    ürün atlanır (engellenen)."""
    urunler = urunler or URUNLER_KLASORU
    tasinacak, engellenen = [], []
    for sku in skular:
        neden = silme_engeli(sku, urunler)
        if neden:
            engellenen.append((sku, neden))
        else:
            tasinacak.append(urunler / sku)
    sonuc = cope_tasi(tasinacak, cop_klasoru, gio) if tasinacak else {"yontem": None, "tasinan": [], "hatalar": []}
    sonuc["engellenen"] = engellenen
    return sonuc
