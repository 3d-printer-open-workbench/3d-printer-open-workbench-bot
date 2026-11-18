"""🔄 Model değişti → bağımlı çıktıları güncelle (Patron isteği 2026-11-18).

"Kullanım testi tamamlandığında revize STL varsa e-ticaret görselleri değişmeli; eğer mağazada ve Pinterest'te
yayındaysa onlar da güncellenmeli."

Saf işlevlerdir (Telegram'a bağlı değil; numpy/trimesh İMPORT ETMEZ). Bot (`coo/__main__.py`) zinciri çalıştırır.

urun.yaml şeması:
    model_surumu:                       # kabul edilen (kullanım testi GEÇTİ / Patron onayı) model sürümü
      stl_sha256, tarih, kaynak: "kullanim_testi tur N" | "kullanim_testi tur N (Patron onayı)" | ...
      olcu: {x, y, z}                   # STL sınır kutusu (mm)
      ciktilar:                         # her bağımlı çıktının hangi STL ile üretildiği
        renk|dilimleme|erp|studyo|poster|magaza_gorselleri|ikas|pinterest: {stl_sha256, tarih}
    model_degisimi:                     # "🔄 Model değişti" zinciri durumu
      durum: BEKLIYOR | CALISIYOR | STUDYO_ONAYI | DURDU | YAYIN_ONAYI | TAMAM | ERTELENDI
      stl_sha256, bildirilen_sha, tarih, kaynak, plan: [...], adim, tamamlanan: [...], hata, not_,
      onceki: {olcu, gram, sure_dk}, adim_baslangic (epoch sn)

Kayıt yoksa (eski ürünler) çıktı dosyalarının tarihi STL'nin tarihiyle karşılaştırılır: çıktı STL'den eskiyse eski.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import struct
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from .ayar import URUNLER_KLASORU

# Zincir sırası (eskiyen_ciktilar da bu sırayla döner)
ADIMLAR: dict[str, str] = {
    "renk": "🎨 Renk (çok renk boyama / renk render'ı)",
    "dilimleme": "⚙️ Dilimleme (3MF + G-code)",
    "erp": "🧮 ERP reçetesi (gram / süre)",
    "studyo": "📸 E-ticaret stüdyo görselleri",
    "poster": "📐 Teknik poster",
    "magaza_gorselleri": "🖼️ Mağaza paketi görselleri",
    "ikas": "🛒 İkas yayını",
    "pinterest": "📌 Pinterest pini",
}
URETIM_ADIMLARI = ("renk", "dilimleme", "erp", "studyo", "poster", "magaza_gorselleri")
YAYIN_ADIMLARI = ("ikas", "pinterest")
STUDYO_DOSYALARI = ("kapak-beyaz.png", "krem-fon.png", "koyu-fon.png", "doku-yakin.png")
BEKLEYEN_DURUMLAR = ("BEKLIYOR", "ERTELENDI", "DURDU", "YAYIN_ONAYI")
OLCU_TOLERANS_CM = 0.15
GRAM_TOLERANS = (10.0, 0.06)  # max(10 g, %6) — mağaza metni "Yaklaşık 180 g" gibi yuvarlar


# --------------------------------------------------------------------------------------------- dosya / yaml
def _kok(sku: str, urunler: Path | None = None) -> Path:
    return (urunler or URUNLER_KLASORU) / sku


def urun_oku(sku: str, urunler: Path | None = None) -> dict[str, Any]:
    yol = _kok(sku, urunler) / "urun.yaml"
    if not yol.exists():
        return {}
    try:
        v = yaml.safe_load(yol.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return v if isinstance(v, dict) else {}


def _yaz(sku: str, veri: dict[str, Any], urunler: Path | None = None) -> None:
    (_kok(sku, urunler) / "urun.yaml").write_text(yaml.safe_dump(veri, allow_unicode=True, sort_keys=False),
                                                  encoding="utf-8")


def _blok(v: dict[str, Any], ad: str) -> dict[str, Any]:
    b = v.get(ad)
    return b if isinstance(b, dict) else {}


def _json(yol: Path) -> dict[str, Any] | None:
    try:
        d = json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else None
    except (json.JSONDecodeError, OSError):
        return None
    return d if isinstance(d, dict) else None


def _simdi(zaman: dt.datetime | None = None) -> str:
    return (zaman or dt.datetime.now()).isoformat(timespec="seconds")


def stl_yolu(sku: str, urunler: Path | None = None) -> Path | None:
    kok = _kok(sku, urunler)
    v = urun_oku(sku, urunler)
    adaylar = ([kok / str(v["stl_yolu"])] if v.get("stl_yolu") else []) + [kok / "model" / f"{sku}.stl"]
    return next((p for p in adaylar if p.is_file()), None)


_SHA_ONBELLEK: dict[tuple[str, int, int], str] = {}


def dosya_sha256(yol: Path) -> str:
    st = yol.stat()
    anahtar = (str(yol.resolve()), st.st_mtime_ns, st.st_size)
    if anahtar not in _SHA_ONBELLEK:
        h = hashlib.sha256()
        with yol.open("rb") as f:
            for parca in iter(lambda: f.read(1 << 20), b""):
                h.update(parca)
        _SHA_ONBELLEK[anahtar] = h.hexdigest()
    return _SHA_ONBELLEK[anahtar]


def stl_olcu(yol: Path) -> dict[str, float] | None:
    """STL sınır kutusu (mm, x/y/z genişlik-derinlik-yükseklik). İkili ve ASCII STL; bağımlılıksız."""
    veri = yol.read_bytes()
    mn = [float("inf")] * 3
    mx = [float("-inf")] * 3

    def ekle(x: float, y: float, z: float) -> None:
        for i, d in enumerate((x, y, z)):
            mn[i] = min(mn[i], d)
            mx[i] = max(mx[i], d)

    ikili = len(veri) >= 84 and 84 + 50 * struct.unpack_from("<I", veri, 80)[0] == len(veri)
    if ikili:
        for t in struct.iter_unpack("<12fH", veri[84:]):
            ekle(*t[3:6])
            ekle(*t[6:9])
            ekle(*t[9:12])
    else:
        for m in re.finditer(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", veri):
            ekle(float(m.group(1)), float(m.group(2)), float(m.group(3)))
    if mn[0] == float("inf"):
        return None
    return {"x": round(mx[0] - mn[0], 1), "y": round(mx[1] - mn[1], 1), "z": round(mx[2] - mn[2], 1)}


# --------------------------------------------------------------------------------------------- model sürümü
def model_surumu_kaydet(sku: str, kaynak: str, urunler: Path | None = None,
                        zaman: dt.datetime | None = None) -> dict[str, Any] | None:
    """Kabul edilen STL'yi model_surumu'na yazar (sha değişmediyse dokunmaz). Dönüş: model_surumu."""
    stl = stl_yolu(sku, urunler)
    if stl is None:
        return None
    sha = dosya_sha256(stl)
    v = urun_oku(sku, urunler)
    ms = _blok(v, "model_surumu")
    if ms.get("stl_sha256") == sha:
        return ms
    gecmis = ms.get("gecmis") if isinstance(ms.get("gecmis"), list) else []
    if ms.get("stl_sha256"):
        gecmis.append({"stl_sha256": ms.get("stl_sha256"), "tarih": ms.get("tarih"), "kaynak": ms.get("kaynak"),
                       "olcu": ms.get("olcu")})
    ms.update(stl_sha256=sha, tarih=_simdi(zaman), kaynak=kaynak, olcu=stl_olcu(stl), gecmis=gecmis[-10:])
    ms.setdefault("ciktilar", {})
    v["model_surumu"] = ms
    _yaz(sku, v, urunler)
    return ms


def cikti_kaydet(sku: str, adim: str, urunler: Path | None = None, zaman: dt.datetime | None = None) -> str | None:
    """Bir bağımlı çıktının ŞU ANKİ STL ile üretildiğini kaydeder. Hiçbir akışı bozmamalı: hata → None."""
    if adim not in ADIMLAR:
        raise ValueError(f"bilinmeyen adım: {adim}")
    try:
        stl = stl_yolu(sku, urunler)
        if stl is None or not (_kok(sku, urunler) / "urun.yaml").exists():
            return None
        sha = dosya_sha256(stl)
        v = urun_oku(sku, urunler)
        ms = _blok(v, "model_surumu")
        ciktilar = ms.get("ciktilar") if isinstance(ms.get("ciktilar"), dict) else {}
        ciktilar[adim] = {"stl_sha256": sha, "tarih": _simdi(zaman)}
        ms["ciktilar"] = ciktilar
        v["model_surumu"] = ms
        _yaz(sku, v, urunler)
        return sha
    except (OSError, yaml.YAMLError):
        return None


# --------------------------------------------------------------------------------------------- tarama
def _renk_klasorleri(kok: Path, v: dict[str, Any]) -> list[Path]:
    from .renk_hatti import renkler_veriden

    return [kok / str(r["klasor"]) for r in renkler_veriden(v) if r.get("klasor")]


def _yuklendi(kok: Path) -> dict[str, Any] | None:
    y = _json(kok / "magaza" / "yukleme.json")
    return y if y and y.get("durum") == "YUKLENDI" else None


def _tarih_epoch(metin: Any) -> float | None:
    """'2026-11-18' / '2026-11-18T00:26:42+03:00' → epoch. Yalnız tarih → günün başı (temkinli: eski sayılır)."""
    if not metin:
        return None
    try:
        t = dt.datetime.fromisoformat(str(metin))
    except ValueError:
        return None
    return t.timestamp()


def _poster_yollari(kok: Path) -> list[Path]:
    from .magaza_hatti import galeri_posterleri

    try:
        return [kok / p for p in galeri_posterleri(kok)]
    except Exception:  # noqa: BLE001 — konsept kütüphanesi okunamazsa teknik poster varsayılır
        p = kok / "gorsel" / "konsept" / "teknik-poster-3x4.png"
        return [p] if p.exists() else []


def _mtime(yollar: list[Path], en_eski: bool = True) -> float | None:
    t = [p.stat().st_mtime for p in yollar if p.exists()]
    if not t:
        return None
    return min(t) if en_eski else max(t)


def _cikti_bilgisi(sku: str, adim: str, kok: Path, v: dict[str, Any]) -> dict[str, Any]:
    """{var, zaman (epoch | None), yayinda, ayrinti}. `var` False → bu çıktı hiç üretilmemiş (eskiyen sayılmaz)."""
    cr = _blok(v, "cok_renk")
    yk = _yuklendi(kok)
    pin = _blok(v, "pinterest")
    if adim == "renk":
        if cr.get("karar") == "onay":
            p = kok / "model" / "cok_renk" / "renkli.3mf"
            return {"var": p.exists(), "zaman": _mtime([p]), "yayinda": False, "ayrinti": "çok renk"}
        yollar = [k / "seffaf.png" for k in _renk_klasorleri(kok, v)]
        return {"var": any(p.exists() for p in yollar), "zaman": _mtime(yollar), "yayinda": False,
                "ayrinti": "tek renk render"}
    if adim == "dilimleme":
        yollar = [kok / "uretim" / f"{sku}.3mf", kok / "uretim" / f"{sku}.gcode"]
        return {"var": yollar[0].exists() or yollar[1].exists(), "zaman": _mtime(yollar), "yayinda": False,
                "ayrinti": ""}
    if adim == "erp":
        erp = _blok(v, "erp")
        return {"var": bool(erp.get("product_id")), "zaman": None, "yayinda": False,
                "ayrinti": f"ERP ürün #{erp.get('product_id')}" if erp.get("product_id") else "ERP reçetesi yok"}
    if adim == "studyo":
        yollar = [k / "studyo-ic" / ad for k in _renk_klasorleri(kok, v) or [kok / "gorsel"] for ad in STUDYO_DOSYALARI]
        yollar = [p for p in yollar if p.exists()]
        return {"var": bool(yollar), "zaman": _mtime(yollar), "yayinda": bool(yk), "ayrinti": f"{len(yollar)} kare"}
    if adim == "poster":
        yollar = _poster_yollari(kok)
        return {"var": bool(yollar), "zaman": _mtime(yollar), "yayinda": bool(yk) or bool(pin.get("pin_url")),
                "ayrinti": ", ".join(p.name for p in yollar)}
    if adim == "magaza_gorselleri":
        p = kok / "magaza" / "gorseller.json"
        return {"var": p.exists(), "zaman": _mtime([p]), "yayinda": bool(yk), "ayrinti": ""}
    if adim == "ikas":
        if not yk:
            return {"var": False, "zaman": None, "yayinda": False, "ayrinti": ""}
        gun = _json(kok / "magaza" / "guncelleme.json") or {}
        zaman = (_tarih_epoch(gun.get("tarih")) if gun.get("durum") == "GUNCELLENDI" else None) \
            or _mtime([kok / "magaza" / "ikas-ekran.png"]) or _tarih_epoch(yk.get("tarih"))
        return {"var": True, "zaman": zaman, "yayinda": True, "ayrinti": str(yk.get("urun_linki") or "")}
    if adim == "pinterest":
        if not pin.get("pin_url"):
            return {"var": False, "zaman": None, "yayinda": False, "ayrinti": ""}
        pj = _json(kok / "medya" / "pinterest" / "pin.json") or {}
        zaman = (_tarih_epoch(pj.get("tarih")) if pj.get("pin_url") == pin.get("pin_url") else None)
        # pin.json'daki tarih yalnız gün → dosyanın kendi zamanı daha kesin
        pjyol = kok / "medya" / "pinterest" / "pin.json"
        if pjyol.exists() and pj.get("pin_url") == pin.get("pin_url"):
            zaman = pjyol.stat().st_mtime
        return {"var": True, "zaman": zaman or _tarih_epoch(pin.get("tarih")), "yayinda": True,
                "ayrinti": str(pin.get("pin_url"))}
    raise ValueError(adim)


def gcode_gramlari(yol: Path) -> tuple[float | None, list[float]]:
    """Orca G-code sonundaki '; total filament used [g]' ve '; filament used [g]' satırları (dosyanın son 256 KB'ı)."""
    if not yol.exists():
        return None, []
    with yol.open("rb") as f:
        f.seek(max(0, yol.stat().st_size - (256 << 10)))
        kuyruk = f.read().decode("utf-8", "ignore")
    t = re.search(r"^; total filament used \[g\] = ([\d.]+)", kuyruk, re.M)
    p = re.search(r"^; filament used \[g\] = ([\d., ]+)$", kuyruk, re.M)
    parca = [float(x) for x in p.group(1).split(",") if x.strip()] if p else []
    return (float(t.group(1)) if t else (sum(parca) if parca else None)), parca


def _dilim_yaml_uyumsuz(kok: Path, sku: str, v: dict[str, Any]) -> bool:
    """urun.yaml > dilimleme.gercek_gram, mevcut G-code ile uyuşmuyor mu (elle/yarım dilimleme)?"""
    toplam, _ = gcode_gramlari(kok / "uretim" / f"{sku}.gcode")
    gram = _blok(v, "dilimleme").get("gercek_gram")
    return bool(toplam and gram) and abs(float(gram) - float(toplam)) > 1.0


def _erp_gram_uyumsuz(v: dict[str, Any], kok: Path | None = None, sku: str = "") -> bool:
    erp, dil = _blok(v, "erp"), _blok(v, "dilimleme")
    bom = [float(b.get("net_gr") or 0) for b in erp.get("bom_filamentler") or [] if isinstance(b, dict)]
    toplam, parca = gcode_gramlari(kok / "uretim" / f"{sku}.gcode") if kok else (None, [])
    hedef = [g for g in parca if g > 0] or ([toplam] if toplam else []) or [
        float(g) for g in dil.get("filament_gram") or [] if g] or (
        [float(dil["gercek_gram"])] if dil.get("gercek_gram") else [])
    if not bom or not hedef:
        return False
    if len(bom) != len(hedef):
        return abs(sum(bom) - sum(hedef)) > 1.0
    return any(abs(a - b) > 1.0 for a, b in zip(bom, hedef))


def durum_raporu(sku: str, urunler: Path | None = None) -> dict[str, Any]:
    """Tüm adımlar için güncellik raporu (kuru tarama da bunu kullanır; hiçbir şey yazmaz)."""
    kok = _kok(sku, urunler)
    v = urun_oku(sku, urunler)
    stl = stl_yolu(sku, urunler)
    if stl is None:
        return {"sku": sku, "stl": None, "adimlar": []}
    sha = dosya_sha256(stl)
    stl_zaman = stl.stat().st_mtime
    ms = _blok(v, "model_surumu")
    kayitlar = ms.get("ciktilar") if isinstance(ms.get("ciktilar"), dict) else {}
    adimlar: list[dict[str, Any]] = []
    for adim, ad in ADIMLAR.items():
        b = _cikti_bilgisi(sku, adim, kok, v)
        satir = {"adim": adim, "ad": ad, "var": b["var"], "yayinda": b["yayinda"], "ayrinti": b["ayrinti"],
                 "guncel": True, "kanit": "", "neden": ""}
        if b["var"]:
            kayit = kayitlar.get(adim) if isinstance(kayitlar.get(adim), dict) else {}
            if kayit.get("stl_sha256"):
                satir["kanit"] = "sha"
                satir["guncel"] = kayit["stl_sha256"] == sha
                satir["neden"] = "" if satir["guncel"] else f"başka STL ile üretildi ({kayit.get('tarih')})"
            elif adim == "erp":
                onceki_dilim = next((a for a in adimlar if a["adim"] == "dilimleme"), None)
                satir["kanit"] = "türetme"
                if onceki_dilim and onceki_dilim["var"] and not onceki_dilim["guncel"]:
                    satir["guncel"], satir["neden"] = False, "dilimleme eski → reçete gramı/süresi eski"
                elif _erp_gram_uyumsuz(v, kok, sku):
                    satir["guncel"], satir["neden"] = False, "reçete gramı G-code ile uyuşmuyor"
            elif b["zaman"] is not None:
                satir["kanit"] = "tarih"
                satir["guncel"] = b["zaman"] >= stl_zaman
                if not satir["guncel"]:
                    satir["neden"] = (f"çıktı {dt.datetime.fromtimestamp(b['zaman']):%Y-%m-%d %H:%M}, STL "
                                      f"{dt.datetime.fromtimestamp(stl_zaman):%Y-%m-%d %H:%M}")
        if adim == "dilimleme" and b["var"] and satir["guncel"] and _dilim_yaml_uyumsuz(kok, sku, v):
            satir["guncel"], satir["kanit"] = False, "gcode"
            satir["neden"] = "urun.yaml dilimleme gramı G-code ile uyuşmuyor (elle/yarım dilimleme)"
        adimlar.append(satir)
    return {"sku": sku, "stl": str(stl.relative_to(kok)), "stl_sha256": sha,
            "stl_tarihi": dt.datetime.fromtimestamp(stl_zaman).isoformat(timespec="seconds"),
            "model_surumu_sha": ms.get("stl_sha256"), "adimlar": adimlar}


def eskiyen_ciktilar(sku: str, urunler: Path | None = None) -> list[dict[str, Any]]:
    """STL'si güncel olmayan (var olan) çıktılar, zincir sırasıyla: [{adim, ad, yayinda, neden, kanit, ayrinti}]."""
    return [a for a in durum_raporu(sku, urunler)["adimlar"] if a["var"] and not a["guncel"]]


def zincir_plani(sku: str, urunler: Path | None = None) -> list[str]:
    """Yeniden üretilecek üretim adımları: ilk eskiyen üretim adımından itibaren, çıktısı var olan her adım
    (yukarı akış değişince aşağı akış da yeniden üretilir). ERP, dilimleme plandaysa her zaman eklenir
    (ürün ERP'de yoksa adım kendisi atlar)."""
    rapor = {a["adim"]: a for a in durum_raporu(sku, urunler)["adimlar"]}
    if not rapor:
        return []
    ilk = next((i for i, a in enumerate(URETIM_ADIMLARI) if rapor[a]["var"] and not rapor[a]["guncel"]), None)
    if ilk is None:
        return []
    plan = []
    for a in URETIM_ADIMLARI[ilk:]:
        if rapor[a]["var"] or (a == "erp" and "dilimleme" in plan):
            plan.append(a)
    return plan


def yayin_plani(sku: str, urunler: Path | None = None) -> list[str]:
    """Yayında olup eski model görselini gösteren kanallar (ikas, pinterest)."""
    return [a["adim"] for a in eskiyen_ciktilar(sku, urunler) if a["adim"] in YAYIN_ADIMLARI]


# --------------------------------------------------------------------------------------------- zincir durumu
def degisim_oku(sku: str, urunler: Path | None = None) -> dict[str, Any]:
    return _blok(urun_oku(sku, urunler), "model_degisimi")


def degisim_yaz(sku: str, urunler: Path | None = None, **alanlar: Any) -> dict[str, Any]:
    v = urun_oku(sku, urunler)
    md = _blok(v, "model_degisimi")
    md.update(alanlar)
    v["model_degisimi"] = md
    _yaz(sku, v, urunler)
    return md


def onceki_degerler(sku: str, urunler: Path | None = None) -> dict[str, Any]:
    """Değişimden önceki yayın değerleri: ölçü mağaza metninden (yoksa önceki model_surumu / urun.yaml), gram ve
    süre dilimleme bloğundan (zincir dilimlemeden ÖNCE çağrılmalı)."""
    v = urun_oku(sku, urunler)
    dil = _blok(v, "dilimleme")
    ms = _blok(v, "model_surumu")
    paket = _json(_kok(sku, urunler) / "magaza" / "paket.json") or {}
    olcu = metin_olcusu(str(paket.get("aciklama_html") or ""))
    if olcu is None:
        gecmis = ms.get("gecmis") if isinstance(ms.get("gecmis"), list) else []
        eski = next((g.get("olcu") for g in reversed(gecmis) if isinstance(g, dict) and g.get("olcu")), None)
        b = eski or _blok(v, "boyut_mm")
        olcu = {k: float(b[k]) for k in ("x", "y", "z") if b.get(k)} or None
    return {"olcu": olcu, "gram": dil.get("gercek_gram"), "sure_dk": dil.get("gercek_sure_dk")}


def bildirim_kaydi(sku: str, kaynak: str, urunler: Path | None = None,
                   zaman: dt.datetime | None = None) -> bool:
    """Kullanım testi GEÇTİ / kt:onay sonrası çağrılır. Model sürümünü kaydeder; eskiyen çıktı varsa ve bu STL
    için daha önce bildirilmediyse model_degisimi'ni BEKLIYOR yapar → True (bot "🔄 Model değişti" gönderir)."""
    stl = stl_yolu(sku, urunler)
    if stl is None:
        return False
    sha = dosya_sha256(stl)
    md = degisim_oku(sku, urunler)
    if md.get("bildirilen_sha") == sha:
        model_surumu_kaydet(sku, kaynak, urunler, zaman)
        return False
    eski = eskiyen_ciktilar(sku, urunler)
    onceki = onceki_degerler(sku, urunler) if eski else None
    model_surumu_kaydet(sku, kaynak, urunler, zaman)
    if not eski:
        return False
    v = urun_oku(sku, urunler)
    v["model_degisimi"] = {"durum": "BEKLIYOR", "stl_sha256": sha, "bildirilen_sha": sha, "tarih": _simdi(zaman),
                           "kaynak": kaynak, "plan": [], "adim": None, "tamamlanan": [], "hata": "", "not_": "",
                           "onceki": onceki}
    _yaz(sku, v, urunler)
    return True


def bekliyor_mu(sku: str, urunler: Path | None = None) -> bool:
    """Bekleyen İşler: bildirilmiş, karar/devam bekleyen ve hâlâ eskiyen çıktısı olan değişim."""
    md = degisim_oku(sku, urunler)
    if md.get("durum") not in BEKLEYEN_DURUMLAR:
        return False
    if md.get("durum") == "YAYIN_ONAYI":
        return bool(yayin_plani(sku, urunler))
    return bool(eskiyen_ciktilar(sku, urunler))


def sonraki_adim(plan: list[str], adim: str | None) -> str | None:
    if not plan:
        return None
    if adim is None:
        return plan[0]
    if adim not in plan:
        return None
    i = plan.index(adim)
    return plan[i + 1] if i + 1 < len(plan) else None


# --------------------------------------------------------------------------------------------- ölçü / metin
def _sayi(m: str) -> float:
    return float(m.replace(",", "."))


def metin_olcusu(aciklama_html: str) -> dict[str, float] | None:
    """Mağaza tablosundaki 'Ölçü' satırı ('10,2 × 10,4 × 9,8 cm') → {x, y, z} mm."""
    m = re.search(r"<th>\s*Ölçü\s*</th>\s*<td>(.*?)</td>", aciklama_html or "", re.S | re.I)
    if not m:
        return None
    hucre = html.unescape(m.group(1))
    sayilar = re.findall(r"\d+(?:[.,]\d+)?", hucre)
    if len(sayilar) < 3:
        return None
    carpan = 1.0 if re.search(r"\bmm\b", hucre) else 10.0
    x, y, z = (_sayi(s) * carpan for s in sayilar[:3])
    return {"x": round(x, 1), "y": round(y, 1), "z": round(z, 1)}


def metin_agirligi(aciklama_html: str) -> float | None:
    m = re.search(r"<th>\s*Ağırlık\s*</th>\s*<td>(.*?)</td>", aciklama_html or "", re.S | re.I)
    if not m:
        return None
    s = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g)\b", html.unescape(m.group(1)))
    if not s:
        return None
    return _sayi(s.group(1)) * (1000.0 if s.group(2) == "kg" else 1.0)


def cm(mm: float) -> str:
    deger = round(mm / 10, 1)
    return (f"{deger:.0f}" if deger == int(deger) else f"{deger:.1f}").replace(".", ",")


def olcu_metni(olcu: dict[str, float] | None) -> str:
    if not olcu:
        return "—"
    return f"{cm(olcu['x'])} × {cm(olcu['y'])} × {cm(olcu['z'])} cm"


def yaklasik_gram(gram: float) -> str:
    return f"Yaklaşık {int(round(gram / 10.0) * 10)} g"


def metin_farklari(sku: str, urunler: Path | None = None) -> list[dict[str, Any]]:
    """Mağaza metnindeki (paket.json aciklama_html) ölçü/ağırlık, GÜNCEL modelle (STL kutusu + dilimleme gramı)
    uyuşmuyorsa farklar: [{alan, metinde, yeni, oneri}]. Boş → metin değişmeyecek (review gerekmez)."""
    paket = _json(_kok(sku, urunler) / "magaza" / "paket.json")
    stl = stl_yolu(sku, urunler)
    if not paket or stl is None:
        return []
    a = str(paket.get("aciklama_html") or "")
    farklar: list[dict[str, Any]] = []
    mo = metin_olcusu(a)
    yeni = stl_olcu(stl)
    if mo and yeni and any(abs(mo[k] - yeni[k]) / 10 > OLCU_TOLERANS_CM for k in ("x", "y", "z")):
        farklar.append({"alan": "Ölçü", "metinde": olcu_metni(mo), "yeni": olcu_metni(yeni), "oneri": olcu_metni(yeni)})
    mg = metin_agirligi(a)
    gram = _blok(urun_oku(sku, urunler), "dilimleme").get("gercek_gram")
    if mg and gram and abs(mg - float(gram)) > max(GRAM_TOLERANS[0], GRAM_TOLERANS[1] * float(gram)):
        farklar.append({"alan": "Ağırlık", "metinde": f"{mg:.0f} g", "yeni": f"{float(gram):.0f} g",
                        "oneri": yaklasik_gram(float(gram))})
    return farklar


def boyut_guncelle(sku: str, urunler: Path | None = None) -> tuple[dict[str, Any] | None, dict[str, float] | None]:
    """urun.yaml > boyut_mm'yi STL sınır kutusuyla günceller (poster/pin bilgi satırları buradan). (eski, yeni)."""
    stl = stl_yolu(sku, urunler)
    if stl is None:
        return None, None
    yeni = stl_olcu(stl)
    v = urun_oku(sku, urunler)
    eski = dict(_blok(v, "boyut_mm")) or None
    if yeni and eski != yeni:
        v["boyut_mm"] = yeni
        _yaz(sku, v, urunler)
    return eski, yeni


# --------------------------------------------------------------------------------------------- ERP
ErpIstek = Callable[..., Any]


def _erp_ozet(p: dict[str, Any]) -> dict[str, Any]:
    pt = p.get("print_time") or {}
    b2c = p.get("b2c_pricing") or {}
    return {"gram": p.get("total_filament_net_gr"), "saat": pt.get("hours"), "dakika": pt.get("minutes"),
            "maliyet_tl": p.get("production_cost_tl"), "basa_bas_tl": b2c.get("break_even_gross_tl"),
            "onerilen_tl": b2c.get("recommended_gross_tl"),
            "filament_gram": [f.get("net_weight_gr") for f in p.get("filaments") or []],
            "olcu": p.get("dimensions_mm")}


def erp_gcode_guncelle(sku: str, istek: ErpIstek | None = None, urunler: Path | None = None) -> dict[str, Any]:
    """ERP reçetesindeki gram/süreyi YENİ G-code'dan günceller — ERP'nin mevcut ucu:
    POST /api/products/{id}/gcode-onayla (G-code'u depoya kopyalar, süre + katman + gramı reçeteye yazar).
    ERP koduna dokunulmaz. Dönüş: {durum: GUNCELLENDI | YOK | HATA, once, sonra, uyari, hata, product_id}."""
    if istek is None:
        from .renk_paleti import erp_istek as istek  # noqa: PLW0127
    kok = _kok(sku, urunler)
    gcode = kok / "uretim" / f"{sku}.gcode"
    if not gcode.exists():
        return {"durum": "HATA", "hata": f"G-code yok: uretim/{sku}.gcode"}
    v = urun_oku(sku, urunler)
    erp = _blok(v, "erp")
    try:
        urunler_erp = istek("GET", "/api/products") or []
    except Exception as exc:  # noqa: BLE001
        return {"durum": "HATA", "hata": f"ERP'ye ulaşılamadı: {exc}"}
    pid = erp.get("product_id")
    urun = next((p for p in urunler_erp if pid and int(p.get("product_id") or 0) == int(pid)), None) \
        or next((p for p in urunler_erp if p.get("sku") == sku), None)
    if not urun:
        return {"durum": "YOK", "hata": "ERP'de bu ürünün reçetesi yok (mağaza paketi gcode_maliyet ile fiyatlandı)."}
    pid = int(urun["product_id"])
    once = _erp_ozet(urun)
    try:
        sonuc = istek("POST", f"/api/products/{pid}/gcode-onayla", {"gcode_yolu": str(gcode.resolve())})
    except Exception as exc:  # noqa: BLE001 — 409 vb.
        return {"durum": "HATA", "hata": f"gcode-onayla: {exc}", "product_id": pid, "once": once}
    if isinstance(sonuc, dict) and sonuc.get("status") == "error":
        return {"durum": "HATA", "hata": str(sonuc.get("message")), "product_id": pid, "once": once}
    try:
        yeni = next((p for p in istek("GET", "/api/products") or [] if int(p.get("product_id") or 0) == pid), urun)
    except Exception:  # noqa: BLE001
        yeni = urun
    sonra = _erp_ozet(yeni)
    v = urun_oku(sku, urunler)
    erp = _blok(v, "erp")
    erp.update(product_id=pid, birim_uretim_maliyeti_tl=sonra["maliyet_tl"], basa_bas_fiyati_tl=sonra["basa_bas_tl"],
               onerilen_satis_fiyati_tl=sonra["onerilen_tl"],
               son_gcode_onayi={"tarih": _simdi(), "gram": (sonuc or {}).get("gram"), "saat": (sonuc or {}).get("saat"),
                                "dakika": (sonuc or {}).get("dakika"),
                                "gcode_sha256": (sonuc or {}).get("gcode_sha256"), "uyari": (sonuc or {}).get("uyari")})
    bom = erp.get("bom_filamentler") if isinstance(erp.get("bom_filamentler"), list) else []
    if bom and len(bom) == len(sonra["filament_gram"]) and not (sonuc or {}).get("uyari"):
        for b, g in zip(bom, sonra["filament_gram"]):
            if isinstance(b, dict) and g is not None:
                b["net_gr"] = g
    v["erp"] = erp
    _yaz(sku, v, urunler)
    return {"durum": "GUNCELLENDI", "product_id": pid, "once": once, "sonra": sonra,
            "uyari": (sonuc or {}).get("uyari"), "hata": ""}


def paket_maliyet_guncelle(sku: str, erp_sonuc: dict[str, Any] | None = None,
                           urunler: Path | None = None) -> list[str]:
    """paket.json > maliyet: gram/baskı süresini (ve ERP güncellendiyse maliyet/başa baş/öneri) yeni modele çeker.
    Satış fiyatına DOKUNMAZ (fiyat Patron kararı); fiyat yeni maliyetin altında kalırsa uyarı döner."""
    yol = _kok(sku, urunler) / "magaza" / "paket.json"
    paket = _json(yol)
    if not paket:
        return []
    dil = _blok(urun_oku(sku, urunler), "dilimleme")
    m = paket.get("maliyet") if isinstance(paket.get("maliyet"), dict) else {}
    if dil.get("gercek_gram"):
        m["gram"] = dil["gercek_gram"]
    if dil.get("gercek_sure_dk"):
        m["baski_dk"] = dil["gercek_sure_dk"]
    uyarilar: list[str] = []
    sonra = (erp_sonuc or {}).get("sonra") if (erp_sonuc or {}).get("durum") == "GUNCELLENDI" else None
    if sonra:
        m.update(birim_maliyet_tl=sonra.get("maliyet_tl"), basa_bas_tl=sonra.get("basa_bas_tl"),
                 erp_onerilen_tl=sonra.get("onerilen_tl"))
    paket["maliyet"] = m
    fiyat = float(paket.get("satis_fiyati_tl") or 0)
    basa_bas = float(m.get("basa_bas_tl") or 0)
    if fiyat and basa_bas and fiyat < basa_bas:
        uyarilar.append(f"Satış fiyatı {fiyat:.2f} TL yeni başa baş fiyatın ({basa_bas:.2f} TL) altında — fiyatı "
                        "yeniden seç (🛒 Mağaza paketi).")
    yol.write_text(json.dumps(paket, ensure_ascii=False, indent=2), encoding="utf-8")
    return uyarilar


# --------------------------------------------------------------------------------------------- Telegram metinleri
def dugmeler(sku: str) -> list[list[dict[str, str]]]:
    from .bekleyen_isler import not_dugmesi

    return [[{"text": "▶️ Zinciri Güncelle", "callback_data": f"md:zincir:{sku}"}, not_dugmesi("md", sku)],
            [{"text": "⏭️ Şimdilik Değil", "callback_data": f"md:ertele:{sku}"},
             {"text": "📦 Ürün Kartı", "callback_data": f"urunmenu:{sku}"}]]


def ozet_metni(sku: str, urunler: Path | None = None) -> str:
    eski = eskiyen_ciktilar(sku, urunler)
    md = degisim_oku(sku, urunler)
    plan = zincir_plani(sku, urunler)
    satirlar = [f"🔄 *Model değişti* — `{sku}`",
                f"_Kaynak: {str(md.get('kaynak')).replace('_', ' ')}_" if md.get("kaynak") else "",
                "Yeni STL'den önce üretilmiş çıktılar (⚠️ = yayında, eski modeli gösteriyor):"]
    for a in eski:
        satirlar.append(f"{'⚠️' if a['yayinda'] else '•'} {a['ad']}" + (f" — _{a['neden']}_" if a["neden"] else ""))
    onceki = md.get("onceki") or {}
    if onceki.get("olcu"):
        stl = stl_yolu(sku, urunler)
        yeni = stl_olcu(stl) if stl else None
        if yeni and olcu_metni(onceki["olcu"]) != olcu_metni(yeni):
            satirlar.append(f"\n📏 Ölçü: {olcu_metni(onceki['olcu'])} → *{olcu_metni(yeni)}*")
    if plan:
        satirlar.append("\n*▶️ Zinciri Güncelle* sırayla yeniden üretir: " + " → ".join(
            ADIMLAR[a].split(" ", 1)[1].split(" (")[0] for a in plan)
                        + ". Ara onay sorulmaz; yalnız e-ticaret görsellerini sen onaylarsın.")
    yayin = [a for a in eski if a["adim"] in YAYIN_ADIMLARI]
    if yayin:
        satirlar.append("Yayındaki " + " ve ".join("İkas" if a["adim"] == "ikas" else "Pinterest" for a in yayin)
                        + " en sonda önizlemeyle *senin onayınla* güncellenir (Pinterest'te yeni pin; eski pin silinmez).")
    return "\n".join(s for s in satirlar if s)[:3900]


def gorsel_sirasi(sku: str, urunler: Path | None = None) -> list[str]:
    g = _json(_kok(sku, urunler) / "magaza" / "gorseller.json") or {}
    return [str(x.get("dosya")) for x in g.get("gorseller") or [] if isinstance(x, dict)]


def ikas_onizleme_metni(sku: str, urunler: Path | None = None, uyarilar: list[str] | None = None) -> str:
    v = urun_oku(sku, urunler)
    yk = _yuklendi(_kok(sku, urunler)) or {}
    md = _blok(v, "model_degisimi")
    onceki = md.get("onceki") or {}
    dil = _blok(v, "dilimleme")
    sira = gorsel_sirasi(sku, urunler)
    satirlar = [f"🛒 *İkas görsellerini güncelle* — `{sku}`", f"Ürün: {yk.get('urun_linki') or '—'}",
                f"Panel: {yk.get('panel_linki') or '—'} _(yeni ürün AÇILMAZ, bu ürün düzenlenir)_",
                f"\n*Yeni galeri sırası* ({len(sira)} görsel, ilk = kapak):"]
    satirlar += [f"{i}. `{Path(s).name}`" for i, s in enumerate(sira, 1)]
    if onceki.get("gram") and dil.get("gercek_gram") and onceki["gram"] != dil["gercek_gram"]:
        satirlar.append(f"\n⚖️ Gram: {onceki['gram']} → *{dil['gercek_gram']}* g · süre: {onceki.get('sure_dk')} → "
                        f"*{dil.get('gercek_sure_dk')}* dk")
    farklar = metin_farklari(sku, urunler)
    if farklar:
        satirlar.append("\n✍️ *Mağaza metni değişmeli* (tablo):")
        satirlar += [f"• {f['alan']}: {f['metinde']} → *{f['oneri']}*" for f in farklar]
        satirlar.append("Metin değişince kıdemli editör review'u zorunlu (`coo.metin_denetim --review`); önce "
                        "*✍️ Metni Güncelle*, sonra İkas.")
    else:
        satirlar.append("\n✅ Mağaza metnindeki ölçü/ağırlık yeni modelle uyumlu; açıklamaya dokunulmaz.")
    satirlar += [f"⚠️ {u}" for u in uyarilar or []]
    return "\n".join(satirlar)[:3900]


def ikas_dugmeleri(sku: str, urunler: Path | None = None, engeller: list[str] | None = None) -> list[list[dict[str, str]]]:
    if metin_farklari(sku, urunler):
        ilk = [{"text": "✍️ Metni Güncelle (+ editör review)", "callback_data": f"md:metin:{sku}"}]
    elif engeller:
        ilk = [{"text": "✍️ Metni Düzelt (+ editör review)", "callback_data": f"md:metin:{sku}"}]
    else:
        ilk = [{"text": "✅ İkas'ı Güncelle", "callback_data": f"md:ikasok:{sku}"}]
    return [ilk, [{"text": "⏭️ Şimdilik Değil", "callback_data": f"md:ertele:{sku}"},
                  {"text": "📦 Ürün Kartı", "callback_data": f"urunmenu:{sku}"}]]


def metin_guncelle_istemi(sku: str, urunler: Path | None = None) -> str:
    farklar = metin_farklari(sku, urunler)
    satirlar = "\n".join(f"- {f['alan']}: metinde '{f['metinde']}' → '{f['oneri']}'" for f in farklar) or \
        "- (tablo farkı yok; metin_denetim hatalarını düzelt)"
    return (
        f"Görev: `{sku}` 3B modeli değişti (kullanım testi revizyonu); mağaza metnindeki ölçü/ağırlık eskidi. "
        f"`veri/02_Urunler/{sku}/magaza/paket.json` içindeki `aciklama_html`'de YALNIZ şu değerleri güncelle:\n"
        f"{satirlar}\n"
        "Aynı değerin metindeki diğer geçişlerini (madde içinde 'X × Y cm taban' gibi) de yeni ölçüye göre düzelt; "
        f"doğruluğu `veri/02_Urunler/{sku}/urun.yaml` (boyut_mm, dilimleme.gercek_gram) ile kontrol et. Başka cümleyi, "
        "başlığı, fiyatı, görselleri, varyantları, etiketleri, SEO alanlarını DEĞİŞTİRME; dosya şemasını koru.\n"
        f"`python3 -m coo.metin_denetim {sku}` ile kontrol et (review ayrı editör adımıdır, `--review` VERME). "
        "İkas'a girme. Son satır: `METIN_GUNCEL` veya `METIN_HATA <neden>`."
    )


def ikas_guncelle_istemi(sku: str, urunler: Path | None = None, metin_degisti: bool = False) -> str:
    """cmo-store-director: panel_linki'ndeki MEVCUT ürünün görsellerini değiştirir; metin_degisti → review'lu
    aciklama_html'i de yapıştırır."""
    kok = _kok(sku, urunler)
    yk = _yuklendi(kok) or {}
    stl = stl_yolu(sku, urunler)
    sha = dosya_sha256(stl) if stl else ""
    return (
        f"Görev: İkas'taki MEVCUT `{sku}` ürününün GÖRSELLERİNİ yeni 3B modelin görselleriyle değiştir. Patron "
        "Telegram'da '✅ İkas'ı Güncelle'ye bastı; bu, bu ürünü güncelleme onayıdır. YENİ ÜRÜN AÇMA.\n"
        "Önce `.claude/skills/ikas/SKILL.md` dosyasını oku (özellikle 'Mevcut ürünün görsellerini değiştirme').\n"
        f"Kaynak (TEK GERÇEK): `{kok}/magaza/gorseller.json` (hazırlanmış 2048 px kareler) ve `{kok}/magaza/paket.json`.\n"
        "1) Claude in Chrome araçlarını tek ToolSearch ile yükle (file_upload, javascript_tool dahil); tabs_context_mcp; "
        f"YENİ sekme aç; ürün düzenleme sayfasına git: {yk.get('panel_linki')}. Giriş/şifre/doğrulama isteniyorsa DUR "
        "→ `IKAS_GUNCELLEME_HATA giriş gerekli`.\n"
        "2) Sayfadaki ürün adının paket.json `baslik` ile aynı olduğunu doğrula; değilse DUR → "
        "`IKAS_GUNCELLEME_HATA ürün eşleşmedi`.\n"
        "3) Ürün galerisindeki TÜM mevcut görselleri kaldır; `gorseller.json > gorseller` sırasıyla yeni dosyaları "
        f"yükle (mutlak yol `{kok}/<dosya>`), ilk görsel kapak. Varyant görselleri: `varyantlar` listesi; tek varyantta "
        "varyant medyası ürün galerisini kullanıyorsa ayrıca yükleme.\n"
        + ("4) AÇIKLAMA: paket.json `aciklama_html` editör review'undan geçti ve DEĞİŞTİ — açıklama alanına HTML "
           "(kaynak kodu) modunda BİREBİR yapıştır (beceri dosyasındaki JS kalıbı). Başka alana dokunma.\n"
           if metin_degisti else
           "4) Açıklamaya, başlığa, fiyata, SEO'ya, etiketlere, kategoriye, stoğa ve varyant ayarlarına DOKUNMA.\n")
        + "5) Kaydet ('Ürün kaydedildi'). Paneli yeniden aç, görsel sayısını say. Vitrin sayfasını birkaç dakika sonra "
        f"aç ({yk.get('urun_linki')}) ve ekran görüntüsünü `{kok}/magaza/ikas-guncelleme.png` olarak kaydet.\n"
        f"6) `{kok}/magaza/guncelleme.json` yaz: "
        '{"durum":"GUNCELLENDI","tarih":"<ISO zaman>","gorsel_sayisi":<panelde>,'
        f'"metin_guncellendi":{"true" if metin_degisti else "false"},"stl_sha256":"{sha}","notlar":[]}}. '
        "Hata olursa durum HATA + hata alanı. Sekmeyi kapat.\n"
        "7) Ödeme, abonelik, tema veya ayar ekranlarında hiçbir şeyi onaylama. Aynı başarısız adımı 3 kereden fazla "
        "deneme. Son satır: `IKAS_GUNCELLENDI <urun_linki>` veya `IKAS_GUNCELLEME_HATA <neden>`."
    )


def guncelleme_oku(sku: str, urunler: Path | None = None) -> dict[str, Any] | None:
    return _json(_kok(sku, urunler) / "magaza" / "guncelleme.json")


def pin_notu(sku: str, urunler: Path | None = None) -> str:
    pin = _blok(urun_oku(sku, urunler), "pinterest")
    return (f"MODEL GÜNCELLENDİ: yayındaki pin ({pin.get('pin_url')}) eski 3B modeli gösteriyor. Yeni görsellerden "
            "(öncelik yeni teknik poster) YENİ bir pin hazırla. Pinterest'te pin görseli düzenlenemez; eski pin "
            "silinmeyecek.")


def pinterest_kaydi(eski: dict[str, Any], yeni: dict[str, Any]) -> dict[str, Any]:
    """Yeni pin paylaşılınca urun.yaml > pinterest: eski pin_url `onceki_pinler`e taşınır (SİLİNMEZ)."""
    onceki = [p for p in (eski.get("onceki_pinler") or []) if isinstance(p, dict)]
    if eski.get("pin_url") and eski.get("pin_url") != yeni.get("pin_url"):
        onceki.append({"pin_url": eski.get("pin_url"), "tarih": eski.get("tarih"), "pano": eski.get("pano")})
    kayit = {"pin_url": yeni.get("pin_url"), "tarih": yeni.get("tarih"), "pano": yeni.get("pano")}
    if onceki:
        kayit["onceki_pinler"] = onceki
    return kayit
