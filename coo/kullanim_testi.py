"""🧪 Kullanım testi motoru: ürün vaat ettiği kullanımı sağlıyor mu? (kulaklığı taşıyor mu, kolu tutuyor mu, telefon durur mu)

Patron (2026-11-18): "Görsel onay verebiliyorum ama kullanım amacına uygun mu test edilmeli … testten geçmezse
feedback'lerle yeniden tasarlanmalı."

Çalıştırma (ağır bağımlılıklar yalnız .venv-cad'de: trimesh, coacd, mujoco, python-fcl, shapely):
    ortamlar/.venv-cad/bin/python -m coo.kullanim_testi <sku> [--kayit] [--gorselsiz] [--cikti <klasör>]

Akış:
1. Test tanımı = config/kullanim_testi/sablonlar.yaml şablonu ⊕ urun.yaml > kullanim_testi (ürün ezer).
2. Referans nesneler (config/kullanim_testi/nesneler.yaml) ölçüye sadık ilkel bileşimine çevrilir.
3. Stand STL: 20k üçgene sadeleştirilir (python-fcl çakışma/boşluk), CoACD ile dışbükey parçalara ayrılır
   (MuJoCo çarpışma; önbellek model/kullanim_testi/_onbellek/). Kütle: numune tartımı > tek renk dilim gramı >
   geometri tahmini (PLA 1.24 g/cm³, duvar + dolgu%). Çok renkli dilim gramı tasfiye atığı içerdiği için kullanılmaz.
4. Yerleşim: nesne stand üstünden dikey indirilir (ilk temasa kadar, fcl), MuJoCo'da bırakılır, oturduğu konum ölçülür.
   Tarama yönteminde ön→arka konum × eğim açıları denenir; standda duran en iyi aday seçilir.
5. Statik: kupa–masa / parça–stand boşluğu (mm), temas noktaları, birleşik ağırlık merkezi + taban çokgeni →
   yön başına devrilme açısı. Dinamik: bırakma (birkaç cm), masa eğme (±5°/±10°, yerçekimi döndürülerek),
   ekrana dokunma (telefon), sarsma (masa yatay titreşimi).
6. Çıktı: veri/02_Urunler/<sku>/model/kullanim_testi/<tarih>/rapor.json + pano.png (+ birakma.gif);
   KALDI ise ölçülü `duzeltme_onerisi` listesi.

Tüm varsayımlar (sürtünme, yoğunluk, nesne parça yerleşimi) raporda `varsayimlar` altında yazılır; doğrulanmamış
nesne ölçüleri `dogrulanmadi` olarak işaretlenir.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("MUJOCO_GL", "egl")

import numpy as np  # noqa: E402
import yaml  # noqa: E402

from .ayar import CONFIG_KLASORU, URUNLER_KLASORU  # noqa: E402

KT_KONFIG = CONFIG_KLASORU / "kullanim_testi"
G = 9.81
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_KALIN = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
YON_ADLARI = {(1, 0): "sağ (+x)", (-1, 0): "sol (−x)", (0, 1): "arka (+y)", (0, -1): "ön (−y)"}


# ============================================================================ yapılandırma
def _yaml_oku(yol: Path) -> dict[str, Any]:
    v = yaml.safe_load(yol.read_text(encoding="utf-8")) if yol.exists() else {}
    return v if isinstance(v, dict) else {}


def derin_birlestir(taban: dict[str, Any], ust: dict[str, Any]) -> dict[str, Any]:
    sonuc = copy.deepcopy(taban)
    for k, v in (ust or {}).items():
        if isinstance(v, dict) and isinstance(sonuc.get(k), dict):
            sonuc[k] = derin_birlestir(sonuc[k], v)
        else:
            sonuc[k] = copy.deepcopy(v)
    return sonuc


def nesne_kutuphanesi(konfig: Path | None = None) -> dict[str, Any]:
    return _yaml_oku((konfig or KT_KONFIG) / "nesneler.yaml")


def sablon_kutuphanesi(konfig: Path | None = None) -> dict[str, Any]:
    return _yaml_oku((konfig or KT_KONFIG) / "sablonlar.yaml")


def sablon_tahmin(urun: dict[str, Any]) -> str | None:
    """Ürün adı/tarifinden şablon tahmini (urun.yaml'da kullanim_testi.sablon yoksa)."""
    metin = " ".join(str(x) for x in (urun.get("ad"), urun.get("sku"), (urun.get("fikir") or {}).get("tarif")
                                        if isinstance(urun.get("fikir"), dict) else "")).lower()
    if any(k in metin for k in ("kulaklık", "kulaklik", "headphone", "headset")):
        return "kulaklik_standi"
    if any(k in metin for k in ("kontrolcü", "kontrolcu", "controller", "gamepad", "oyun kolu", "joystick")):
        return "kontrolcu_standi"
    if any(k in metin for k in ("telefon", "iphone", "phone", "tablet")):
        return "telefon_standi"
    return None


def test_tanimi(urun: dict[str, Any], konfig: Path | None = None) -> dict[str, Any]:
    """Şablon ⊕ ürün ezmeleri. Dönen sözlük: sablon, vaat, nesneler, kurallar, fizik, yerlesim, ..."""
    sk = sablon_kutuphanesi(konfig)
    kt = urun.get("kullanim_testi") if isinstance(urun.get("kullanim_testi"), dict) else {}
    ad = str(kt.get("sablon") or sablon_tahmin(urun) or "")
    if ad not in (sk.get("sablonlar") or {}):
        raise ValueError(f"kullanım testi şablonu bulunamadı: {ad!r} (urun.yaml > kullanim_testi.sablon yazın)")
    tanim = copy.deepcopy(sk["sablonlar"][ad])
    ezme = {k: v for k, v in kt.items() if k in ("vaat", "nesneler", "kurallar", "fizik", "yerlesim", "yonler",
                                                 "kilif", "kapasite")}
    tanim = derin_birlestir(tanim, ezme)
    tanim["fizik"] = derin_birlestir(sk.get("fizik") or {}, tanim.get("fizik") or {})
    tanim["sablon"] = ad
    tanim.setdefault("kilif", [False])
    tanim.setdefault("yonler", ["dik"])
    tanim.setdefault("kapasite", 1)
    return tanim


# ============================================================================ geometri yardımcıları
def _rot(eksen: str, derece: float) -> np.ndarray:
    a = math.radians(derece)
    c, s = math.cos(a), math.sin(a)
    if eksen == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if eksen == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _z_hizala(yon: np.ndarray) -> np.ndarray:
    """z eksenini verilen yöne çeviren dönme matrisi."""
    z = yon / (np.linalg.norm(yon) + 1e-12)
    yardim = np.array([1.0, 0, 0]) if abs(z[0]) < 0.9 else np.array([0, 1.0, 0])
    x = np.cross(yardim, z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.column_stack([x, y, z])


def _quat_wxyz(R: np.ndarray) -> np.ndarray:
    from scipy.spatial.transform import Rotation

    x, y, z, w = Rotation.from_matrix(R).as_quat()
    return np.array([w, x, y, z])


def _mat(q_wxyz: np.ndarray) -> np.ndarray:
    from scipy.spatial.transform import Rotation

    w, x, y, z = q_wxyz
    return Rotation.from_quat([x, y, z, w]).as_matrix()


def _aci_farki(R1: np.ndarray, R2: np.ndarray) -> float:
    c = (np.trace(R1.T @ R2) - 1) / 2
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


@dataclass
class Parca:
    """Nesnenin ilkel parçası (mm, nesne yerel ekseni)."""
    ad: str
    tip: str                        # box | capsule | ellipsoid | cylinder
    boyut: tuple[float, ...]        # box/ellipsoid: yarı ölçüler; capsule/cylinder: (yarıçap,)
    pos: np.ndarray = field(default_factory=lambda: np.zeros(3))
    R: np.ndarray = field(default_factory=lambda: np.eye(3))
    uzunluk: float = 0.0            # capsule/cylinder: eksen boyu (yerel z)
    kutle_g: float = 0.0
    rol: str = "govde"

    def hacim(self) -> float:
        if self.tip == "box":
            return 8 * self.boyut[0] * self.boyut[1] * self.boyut[2]
        if self.tip == "ellipsoid":
            return 4 / 3 * math.pi * self.boyut[0] * self.boyut[1] * self.boyut[2]
        r = self.boyut[0]
        return math.pi * r * r * self.uzunluk + (4 / 3 * math.pi * r ** 3 if self.tip == "capsule" else 0)

    def kose_noktalari(self) -> np.ndarray:
        """Zarf noktaları (AABB/alt nokta hesabı için; yerel nesne ekseninde)."""
        if self.tip in ("box",):
            hx, hy, hz = self.boyut
            k = np.array([[sx * hx, sy * hy, sz * hz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])
        elif self.tip == "ellipsoid":
            t = np.linspace(0, 2 * math.pi, 16)
            p = np.linspace(-math.pi / 2, math.pi / 2, 9)
            tt, pp = np.meshgrid(t, p)
            k = np.column_stack([(np.cos(pp) * np.cos(tt)).ravel() * self.boyut[0],
                                 (np.cos(pp) * np.sin(tt)).ravel() * self.boyut[1], np.sin(pp).ravel() * self.boyut[2]])
        else:
            r, h = self.boyut[0], self.uzunluk / 2
            t = np.linspace(0, 2 * math.pi, 16, endpoint=False)
            halka = np.column_stack([np.cos(t) * r, np.sin(t) * r])
            uc = r if self.tip == "capsule" else 0
            k = np.vstack([np.column_stack([halka, np.full(16, z)]) for z in (-h, h)]
                          + [np.array([[0, 0, -h - uc], [0, 0, h + uc]])])
        return k @ self.R.T + self.pos


def _kapsul(ad: str, a: np.ndarray, b: np.ndarray, r: float, rol: str) -> Parca:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return Parca(ad, "capsule", (r,), (a + b) / 2, _z_hizala(b - a), float(np.linalg.norm(b - a)), rol=rol)


@dataclass
class Nesne:
    kimlik: str
    ad: str
    tip: str
    parcalar: list[Parca]
    kutle_g: float
    noktalar: dict[str, np.ndarray]          # tutma/ölçüm noktaları (yerel)
    bilgi: dict[str, Any]                    # ölçü, kaynak, varsayımlar
    yon: str = "dik"
    kilif: bool = False

    def zarf(self) -> tuple[np.ndarray, np.ndarray]:
        k = np.vstack([p.kose_noktalari() for p in self.parcalar])
        return k.min(0), k.max(0)

    @property
    def etiket(self) -> str:
        e = self.ad + (" + kılıf" if self.kilif else "")
        return e + (" (yatay)" if self.yon == "yatay" else "")


def _kutle_dagit(parcalar: list[Parca], toplam_g: float, oranlar: dict[str, float] | None = None) -> None:
    """Kütleyi rol oranına (verilmişse), rol içinde hacme göre dağıtır."""
    roller = {p.rol for p in parcalar}
    oran = {r: (oranlar or {}).get(r) for r in roller}
    serbest = [r for r in roller if oran[r] is None]
    kalan = 1 - sum(v for v in oran.values() if v is not None)
    hacim_rol = {r: sum(p.hacim() for p in parcalar if p.rol == r) for r in roller}
    serbest_h = sum(hacim_rol[r] for r in serbest) or 1
    for r in serbest:
        oran[r] = kalan * hacim_rol[r] / serbest_h
    for p in parcalar:
        p.kutle_g = toplam_g * oran[p.rol] * p.hacim() / (hacim_rol[p.rol] or 1)


def nesne_olustur(kimlik: str, varyant: str | None = None, kilif: bool = False, yon: str = "dik",
                  kutuphane: dict[str, Any] | None = None, _zarf_oturtuldu: bool = False, _zarf_tur: int = 0) -> Nesne:
    kut = kutuphane or nesne_kutuphanesi()
    t = (kut.get("nesneler") or {}).get(kimlik)
    if not t:
        raise KeyError(f"nesne kütüphanesinde yok: {kimlik}")
    tip = t["tip"]
    bilgi: dict[str, Any] = {"kaynak": t.get("kaynak"), "dogrulanmadi": bool(t.get("dogrulanmadi")),
                             "parca_varsayimi_dogrulanmadi": bool(t.get("parca_varsayimi_dogrulanmadi"))}
    if tip == "telefon":
        o = dict(t["olcu"])
        kutle = float(t["kutle_g"])
        if kilif:
            k = kut.get("kilif") or {}
            o = {"genislik": o["genislik"] + k.get("genislik_artis", 3), "yukseklik": o["yukseklik"]
                 + k.get("yukseklik_artis", 3), "kalinlik": o["kalinlik"] + k.get("kalinlik_artis", 2.5)}
            kutle += float(k.get("kutle_artis_g", 40))
            bilgi["kilif"] = k
        w, h, d = o["genislik"], o["yukseklik"], o["kalinlik"]
        if yon == "yatay":
            w, h = h, w
        parcalar = [Parca("govde", "box", (w / 2, h / 2, d / 2), rol="govde")]
        noktalar = {"alt_kenar": np.array([0, -h / 2, 0.0]), "ekran_ust_ucte_bir": np.array([0, h / 6, d / 2]),
                    "port": np.array([0, -h / 2, 0.0]) if yon == "dik" else np.array([w / 2, 0, 0.0])}
        bilgi["olcu"] = {"genislik": round(o["genislik"], 2), "yukseklik": round(o["yukseklik"], 2),
                         "kalinlik": round(o["kalinlik"], 2)}
        _kutle_dagit(parcalar, kutle)
        return Nesne(kimlik, t["ad"], tip, parcalar, kutle, noktalar, bilgi, yon, kilif)

    if tip == "oyun_kolu":
        p = t["parca"]
        gv, tt, cb, tk = p["govde"], p["tutamak"], p["cubuk"], p["tetik"]
        gz = tt["yaricap"] + 8  # gövde orta düzlemi (tutamak alt ucunun masaya yakın olacağı yükseklik)
        parcalar = [Parca("govde", "box", (gv["genislik"] / 2, gv["derinlik"] / 2, gv["kalinlik"] / 2),
                          np.array([0, -gv["derinlik"] * 0.15, gz]), rol="govde")]
        e = math.radians(tt["egim_derece"])
        for s, ad in ((-1, "sol"), (1, "sag")):
            a = np.array([s * tt["acik_x"], 0.0, gz])
            b = a + np.array([s * 10.0, tt["uzunluk"] * math.cos(e), -tt["uzunluk"] * math.sin(e)])
            parcalar.append(_kapsul(f"tutamak_{ad}", a, b, tt["yaricap"], "tutamak"))
            ust = gz + gv["kalinlik"] / 2
            parcalar.append(Parca(f"cubuk_{ad}", "cylinder", (cb["yaricap"],),
                                  np.array([s * cb["aralik_x"], cb["y"], ust + cb["yukseklik"] / 2]),
                                  uzunluk=cb["yukseklik"], rol="cubuk"))
            parcalar.append(Parca(f"tetik_{ad}", "box", (tk["genislik"] / 2, tk["derinlik"] / 2, tk["yukseklik"] / 2),
                                  np.array([s * tk["aralik_x"], -gv["derinlik"] * 0.15 - gv["derinlik"] / 2
                                            - tk["derinlik"] / 2 + 4, ust - tk["yukseklik"] / 2 + 6]), rol="tetik"))
        n = Nesne(kimlik, t["ad"], tip, parcalar, float(t["kutle_g"]), {}, bilgi)
        if not _zarf_oturtuldu:
            # ilkel bileşimin dış zarfını kaynak ölçüye (genişlik × derinlik × kalınlık) oturt
            hedef = np.array([t["olcu"]["genislik"], t["olcu"]["derinlik"], t["olcu"]["kalinlik"]], float)
            lo, hi = n.zarf()
            fark = hedef - (hi - lo)
            if np.abs(fark).max() > 0.5:
                t2 = copy.deepcopy(t)
                tp = t2["parca"]
                tp["tutamak"]["acik_x"] = tt["acik_x"] + fark[0] / 2
                tp["tutamak"]["uzunluk"] = max(20.0, tt["uzunluk"] + fark[1] / max(math.cos(e), 0.3))
                tp["govde"]["kalinlik"] = max(12.0, gv["kalinlik"] + fark[2])
                kut2 = copy.deepcopy(kut)
                kut2["nesneler"][kimlik] = t2
                return nesne_olustur(kimlik, varyant, kilif, yon, kut2, _zarf_oturtuldu=_zarf_tur + 1 >= 6,
                                     _zarf_tur=_zarf_tur + 1)
        lo, hi = n.zarf()
        merkez = (lo + hi) / 2
        for q in parcalar:
            q.pos = q.pos - merkez
        lo, hi = n.zarf()
        n.noktalar = {"tutamak_sol_uc": parcalar[1].pos + parcalar[1].R[:, 2] * parcalar[1].uzunluk / 2,
                      "tutamak_sag_uc": parcalar[4].pos + parcalar[4].R[:, 2] * parcalar[4].uzunluk / 2}
        bilgi["olcu"] = dict(t["olcu"])
        bilgi["ilkel_zarf_mm"] = [round(float(x), 1) for x in (hi - lo)]
        _kutle_dagit(parcalar, n.kutle_g)
        return n

    if tip == "kulaklik":
        vs = t.get("varyantlar") or {}
        varyant = varyant or next(iter(vs))
        v = vs[varyant]
        p = t["parca"]
        H, Wic, rb = float(v["H"]), float(v["Wic"]), float(p["bant_yaricap"])
        kp = p["kupa"]
        ka, kb, kc = kp["kalinlik"] / 2, kp["genislik"] / 2, kp["yukseklik"] / 2
        Rc = Wic / 2 + ka                      # bant merkez çizgisi yarıçapı (kupa merkezleri üstünden)
        zc = rb - Rc                           # yay merkezi (bant iç tepesi z=0)
        parcalar = []
        n_seg = 12
        acilar = np.linspace(0, math.pi, n_seg + 1)
        for i in range(n_seg):
            a = np.array([Rc * math.cos(acilar[i]), 0, zc + Rc * math.sin(acilar[i])])
            b = np.array([Rc * math.cos(acilar[i + 1]), 0, zc + Rc * math.sin(acilar[i + 1])])
            parcalar.append(_kapsul(f"bant_{i}", a, b, rb, "bant"))
        kupa_z = -H + kc
        for s, ad in ((-1, "sol"), (1, "sag")):
            if zc > kupa_z + kc * 0.6:
                parcalar.append(_kapsul(f"catal_{ad}", np.array([s * Rc, 0, zc]),
                                        np.array([s * Rc, 0, kupa_z + kc * 0.6]), rb * 0.8, "bant"))
            parcalar.append(Parca(f"kupa_{ad}", "ellipsoid", (ka, kb, kc), np.array([s * Rc, 0, kupa_z]), rol="kupa"))
        bilgi.update({"varyant": varyant, "H": H, "Wic": Wic, "kaynak": v.get("kaynak"),
                      "dogrulanmadi": bool(v.get("dogrulanmadi"))})
        n = Nesne(kimlik, f"Kulaklık {varyant} (H {H:.0f} mm)", tip, parcalar, float(v["kutle_g"]),
                  {"bant_tepe": np.zeros(3), "kupa_alt_sol": np.array([-Rc, 0, -H]),
                   "kupa_alt_sag": np.array([Rc, 0, -H])}, bilgi)
        _kutle_dagit(parcalar, n.kutle_g, {"kupa": 0.7, "bant": 0.3})
        return n
    raise ValueError(f"bilinmeyen nesne tipi: {tip}")


# ============================================================================ stand
@dataclass
class Stand:
    stl: Path
    mesh: Any                    # trimesh (sadeleştirilmiş, fcl + taban)
    gorsel: Any                  # trimesh (görsel; daha da sadeleştirilmiş)
    parcalar: list[np.ndarray]   # CoACD dışbükey parça köşeleri (mm)
    kutle_g: float
    kutle_kaynagi: str
    com: np.ndarray
    atalet_g_mm2: np.ndarray     # 3x3, com etrafında
    bilgi: dict[str, Any]

    @property
    def zarf(self) -> tuple[np.ndarray, np.ndarray]:
        return self.mesh.bounds[0], self.mesh.bounds[1]


def _dosya_ozeti(yol: Path) -> str:
    h = hashlib.sha1()
    with open(yol, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()[:12]


def stand_kutlesi(urun: dict[str, Any], mesh: Any, fizik: dict[str, Any]) -> tuple[float, str]:
    dil = urun.get("dilimleme") if isinstance(urun.get("dilimleme"), dict) else {}
    numune = dil.get("gercek_numune_gram")
    if numune:
        return float(numune), f"numune tartımı {float(numune):.1f} g (urun.yaml)"
    yog = float(fizik.get("pla_yogunluk_g_cm3", 1.24))
    dolgu = float(dil.get("dolgu_yuzde") or fizik.get("dolgu_yuzde", 15)) / 100
    duvar = float(dil.get("duvar_sayisi") or 0) * 0.42 or float(fizik.get("duvar_mm", 1.26))
    hacim = abs(float(mesh.volume))
    kabuk = min(hacim, float(mesh.area) * duvar)
    tahmin = yog * (kabuk + dolgu * (hacim - kabuk)) / 1000
    gram = dil.get("gercek_gram") or dil.get("tahmini_gram")
    cok_renk = bool(dil.get("cok_renk")) or len(dil.get("filament_gram") or []) > 1
    if gram and float(gram) > 0 and not cok_renk:
        return float(gram), f"dilimleme gramajı {float(gram):.1f} g (urun.yaml, destek dahil olabilir)"
    neden = (f"çok renkli dilim gramı ({float(gram):.0f} g) tasfiye/kule atığı içerdiği için kullanılmadı; "
             if gram and cok_renk else "")
    return tahmin, (neden + f"geometri tahmini {tahmin:.1f} g = PLA {yog} g/cm³ × (kabuk {kabuk / 1000:.1f} cm³ "
                    f"[{duvar:.2f} mm duvar] + %{dolgu * 100:.0f} dolgu × iç {(hacim - kabuk) / 1000:.1f} cm³)")


def stand_hazirla(stl: Path, urun: dict[str, Any], fizik: dict[str, Any], onbellek: Path | None = None,
                  yuz_sayisi: int = 20000, log: Callable[[str], None] | None = None) -> Stand:
    import trimesh

    tam = trimesh.load(str(stl), force="mesh")
    mesh = tam.simplify_quadric_decimation(face_count=yuz_sayisi) if len(tam.faces) > yuz_sayisi * 1.2 else tam
    gorsel = tam.simplify_quadric_decimation(face_count=8000) if len(tam.faces) > 9000 else tam
    onbellek = onbellek or (stl.parent / "kullanim_testi" / "_onbellek")
    ozet = _dosya_ozeti(stl)
    yol = onbellek / f"coacd-{ozet}.npz"
    if yol.exists():
        veri = np.load(yol, allow_pickle=False)
        parcalar = [veri[k] for k in sorted(veri.files, key=lambda s: int(s[1:]))]
    else:
        import coacd

        if log:
            log("CoACD dışbükey ayrıştırma (ilk sefer, ~10–40 sn)")
        coacd.set_log_level("error")
        sonuc = coacd.run_coacd(coacd.Mesh(np.asarray(mesh.vertices), np.asarray(mesh.faces)), threshold=0.02,
                                max_convex_hull=128, preprocess_resolution=50, resolution=2000, mcts_iterations=100,
                                mcts_max_depth=3, mcts_nodes=20, seed=1)
        parcalar = [np.asarray(v, float) for v, _f in sonuc]
        onbellek.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(yol, **{f"p{i}": p for i, p in enumerate(parcalar)})
    kutle, kaynak = stand_kutlesi(urun, tam, fizik)
    tam_hacim = abs(float(tam.volume))
    yog = kutle / tam_hacim  # g/mm³ (homojen dağılım varsayımı)
    com = np.asarray(tam.center_mass, float)
    atalet = np.asarray(tam.moment_inertia, float) * (yog / (tam.density or 1.0))
    return Stand(stl, mesh, gorsel, parcalar, kutle, kaynak, com, atalet,
                 {"stl_ucgen": int(len(tam.faces)), "fcl_ucgen": int(len(mesh.faces)), "coacd_parca": len(parcalar),
                  "zarf_mm": [round(float(x), 1) for x in tam.extents], "hacim_cm3": round(tam_hacim / 1000, 1),
                  "su_gecirmez": bool(tam.is_watertight), "onbellek": str(yol)})


def taban_cokgeni(stand: Stand, esik_mm: float = 0.8):
    from shapely.geometry import MultiPoint

    v = np.asarray(stand.mesh.vertices)
    zmin = v[:, 2].min()
    alt = v[v[:, 2] <= zmin + esik_mm][:, :2]
    return MultiPoint([tuple(p) for p in alt]).convex_hull


def _yon_adi(derece: float) -> str:
    adlar = ["sağ (+x)", "sağ-arka", "arka (+y)", "sol-arka", "sol (−x)", "sol-ön", "ön (−y)", "sağ-ön"]
    return adlar[int(((derece % 360) + 22.5) // 45) % 8]


def devrilme_acilari(cokgen, com: np.ndarray, n_yon: int = 72) -> dict[str, Any]:
    """Birleşik ağırlık merkezinden yön başına devrilme açısı (masa o yöne eğilince devrilme eşiği)."""
    from shapely.geometry import LineString, Point

    p = Point(float(com[0]), float(com[1]))
    h = float(com[2])
    if not cokgen.buffer(1e-6).contains(p):
        return {"min_derece": 0.0, "en_zayif_yon": "ağırlık merkezi taban dışında", "yonler": {}, "mesafe_mm": {}}

    def mesafe(ux: float, uy: float) -> float:
        hat = LineString([(p.x, p.y), (p.x + ux * 2000, p.y + uy * 2000)])
        kesisim = hat.intersection(cokgen.exterior)
        noktalar = [kesisim] if kesisim.geom_type == "Point" else list(getattr(kesisim, "geoms", []))
        return min((p.distance(q) for q in noktalar), default=0.0)

    yonler, mesafeler = {}, {}
    for (ux, uy), ad in YON_ADLARI.items():
        d = mesafe(ux, uy)
        mesafeler[ad] = round(d, 1)
        yonler[ad] = round(math.degrees(math.atan2(d, h)), 1)
    en_kucuk, en_yon = 1e9, ""
    for i in range(n_yon):
        a = 2 * math.pi * i / n_yon
        d = mesafe(math.cos(a), math.sin(a))
        aci = math.degrees(math.atan2(d, h))
        if aci < en_kucuk:
            en_kucuk, en_yon = aci, _yon_adi(math.degrees(a))
    return {"min_derece": round(en_kucuk, 1), "en_zayif_yon": en_yon, "yonler": yonler, "mesafe_mm": mesafeler,
            "com_yukseklik_mm": round(h, 1)}


def orta_aciklik(stand: Stand, z_alt: float = 15.0, adim: float = 5.0) -> dict[str, Any] | None:
    """Yan direkler (ör. kapı formlu standın sütunları) arasındaki iç açıklık. Direk = kesitte |x| < 10 mm bölgesine girmeyen,
    standın dış kenarına (yarı genişliğin %55'i ötesine) uzanan, y'de orta yarıyla örtüşen malzeme; örneklenen
    yüksekliklerin en az yarısında her iki yanda bulunmalı. Yoksa None (direksiz tasarım)."""
    from shapely.geometry import Polygon

    lo, hi = stand.zarf
    dy = hi[1] - lo[1]
    y1, y2 = lo[1] + dy * 0.25, hi[1] - dy * 0.25
    olcumler, toplam = [], 0
    for z in np.arange(z_alt, hi[2] * 0.85, adim):
        kesit = stand.mesh.section(plane_origin=[0, 0, float(z)], plane_normal=[0, 0, 1])
        toplam += 1
        if kesit is None:
            continue
        sol, sag = -1e9, 1e9
        for d in kesit.discrete:
            if len(d) < 4:
                continue
            x0, yy0, x1, yy1 = Polygon(d[:, :2]).bounds
            if yy1 < y1 or yy0 > y2 or x1 > -10 and x0 < 10:
                continue
            if x1 <= -10 and x0 < lo[0] * 0.55:
                sol = max(sol, x1)
            elif x0 >= 10 and x1 > hi[0] * 0.55:
                sag = min(sag, x0)
        if sol > -1e8 and sag < 1e8:
            olcumler.append((float(sag - sol), float(z), float(sol), float(sag)))
    if not olcumler or len(olcumler) < max(2, toplam // 2):
        return None
    gen, z, sol, sag = min(olcumler)
    return {"aciklik_mm": round(gen, 1), "z_mm": round(z, 1), "sol_x_mm": round(sol, 1), "sag_x_mm": round(sag, 1),
            "direkli_kesit": f"{len(olcumler)}/{toplam}"}


# ============================================================================ fcl (çakışma / boşluk)
class Carpisma:
    def __init__(self, stand: Stand) -> None:
        import fcl

        self.fcl = fcl
        m = fcl.BVHModel()
        v = np.asarray(stand.mesh.vertices, float)
        f = np.asarray(stand.mesh.faces, np.int32)
        m.beginModel(len(v), len(f))
        m.addSubModel(v, f)
        m.endModel()
        self.stand = fcl.CollisionObject(m, fcl.Transform())

    def _geo(self, p: Parca):
        fcl = self.fcl
        if p.tip == "box":
            return fcl.Box(*(2 * np.array(p.boyut)))
        if p.tip == "ellipsoid":
            return fcl.Ellipsoid(*p.boyut)
        if p.tip == "capsule":
            return fcl.Capsule(p.boyut[0], p.uzunluk)
        return fcl.Cylinder(p.boyut[0], p.uzunluk)

    def _nesneler(self, parcalar: list[Parca], R: np.ndarray, t: np.ndarray):
        return [(p, self.fcl.CollisionObject(self._geo(p), self.fcl.Transform(R @ p.R, R @ p.pos + t)))
                for p in parcalar]

    def cakisiyor(self, parcalar: list[Parca], R: np.ndarray, t: np.ndarray) -> bool:
        istek = self.fcl.CollisionRequest()
        return any(self.fcl.collide(o, self.stand, istek, self.fcl.CollisionResult()) for _p, o in
                   self._nesneler(parcalar, R, t))

    def mesafe(self, parca: Parca, R: np.ndarray, t: np.ndarray) -> tuple[float, float]:
        """(en kısa mesafe mm, çakışma derinliği mm). Çakışmada mesafe 0 ve derinlik > 0."""
        fcl = self.fcl
        o = self._nesneler([parca], R, t)[0][1]
        istek = fcl.CollisionRequest(num_max_contacts=50, enable_contact=True)
        sonuc = fcl.CollisionResult()
        if fcl.collide(o, self.stand, istek, sonuc):
            derinlik = max((c.penetration_depth for c in sonuc.contacts), default=0.0)
            return 0.0, float(derinlik)
        ds = fcl.DistanceResult()
        return float(fcl.distance(o, self.stand, fcl.DistanceRequest(), ds)), 0.0

    def indir(self, nesne: Nesne, R: np.ndarray, x: float, y: float, z_ust: float, adim: float = 1.5,
              bosluk: float = 1.0, masaya_inebilir: bool = False) -> float | None:
        """Nesneyi (x, y) üstünden dikey indirir; standa ilk temastan `bosluk` mm önceki merkez z'si.
        Standa hiç değmeden masaya inerse None (masaya_inebilir: masanın `bosluk` mm üstü)."""
        lo = (np.vstack([p.kose_noktalari() for p in nesne.parcalar]) @ R.T)[:, 2].min()
        z = z_ust - lo
        while z + lo > 0.5:
            if self.cakisiyor(nesne.parcalar, R, np.array([x, y, z])):
                if z + adim >= z_ust - lo - 1e-6:
                    return None  # en üstte bile çakışıyor
                # ince ayar
                ust, alt = z + adim, z
                for _ in range(6):
                    orta = (ust + alt) / 2
                    if self.cakisiyor(nesne.parcalar, R, np.array([x, y, orta])):
                        alt = orta
                    else:
                        ust = orta
                return ust + bosluk
            z -= adim
        return (bosluk - lo) if masaya_inebilir else None


# ============================================================================ MuJoCo sahnesi
def _f(x: Any) -> str:
    return " ".join(f"{float(v):.6g}" for v in np.ravel(x))


def sahne_xml(stand: Stand, nesneler: list[Nesne], fizik: dict[str, Any], kamera: dict[str, Any]) -> str:
    mm = 0.001
    sur = fizik.get("surtunme") or {}
    mu_pla, mu_masa = float(sur.get("pla", 0.3)), float(sur.get("masa", 0.35))
    varliklar, stand_geom = [], []
    for i, p in enumerate(stand.parcalar):
        if len(p) < 4:
            continue
        varliklar.append(f'<mesh name="h{i}" vertex="{_f(p * mm)}" inertia="shell"/>')
        stand_geom.append(f'<geom type="mesh" mesh="h{i}" friction="{mu_pla} 0.005 0.0001" group="3" '
                          f'rgba=".8 .7 .5 .3"/>')
    gv, gf = np.asarray(stand.gorsel.vertices) * mm, np.asarray(stand.gorsel.faces)
    varliklar.append(f'<mesh name="gorsel" vertex="{_f(gv)}" face="{" ".join(map(str, gf.ravel()))}" inertia="shell"/>')
    I = stand.atalet_g_mm2 * 1e-3 * 1e-6
    govdeler = []
    renkler = [".16 .17 .2 1", ".15 .35 .6 1", ".55 .2 .2 1"]
    for k, n in enumerate(nesneler):
        mu = float(sur.get(n.tip, 0.4))
        geomlar = []
        for p in n.parcalar:
            ortak = (f'name="n{k}_{p.ad}" mass="{p.kutle_g * 1e-3:.6g}" friction="{mu} 0.005 0.0001" condim="4" '
                     f'rgba="{renkler[k % 3]}"')
            if p.tip in ("capsule", "cylinder"):
                a = p.pos - p.R[:, 2] * p.uzunluk / 2
                b = p.pos + p.R[:, 2] * p.uzunluk / 2
                geomlar.append(f'<geom type="{p.tip}" size="{p.boyut[0] * mm:.6g}" fromto="{_f(np.r_[a, b] * mm)}" '
                               + ortak + "/>")
            else:
                geomlar.append(f'<geom type="{p.tip}" size="{_f(np.array(p.boyut) * mm)}" pos="{_f(p.pos * mm)}" '
                               f'quat="{_f(_quat_wxyz(p.R))}" ' + ortak + "/>")
        govdeler.append(f'<body name="nesne{k}" pos="0 0 1"><freejoint name="j{k}"/>' + "".join(geomlar) + "</body>")
    c, e = kamera["merkez"] * mm, kamera["olcek"] * mm
    return f"""<mujoco model="kullanim_testi">
  <compiler angle="radian" inertiafromgeom="auto"/>
  <option timestep="{float(fizik.get('zaman_adimi_s', 0.0005))}" cone="elliptic" impratio="10" integrator="implicitfast"/>
  <default><geom solref="0.004 1" solimp="0.95 0.99 0.0005"/></default>
  <visual><headlight ambient=".45 .45 .45" diffuse=".55 .55 .55" specular=".1 .1 .1"/>
    <global offwidth="1600" offheight="1600"/><quality shadowsize="4096"/></visual>
  <asset>
    <texture name="gok" type="skybox" builtin="flat" rgb1="1 1 1" rgb2="1 1 1" width="16" height="16"/>
    <texture name="izgara" type="2d" builtin="checker" rgb1=".93 .93 .93" rgb2=".87 .87 .87" width="64" height="64"/>
    <material name="masa" texture="izgara" texrepeat="40 40"/>
    {"".join(varliklar)}
  </asset>
  <worldbody>
    <light pos="0.3 -0.5 0.8" dir="-0.3 0.5 -0.8" diffuse=".5 .5 .5" castshadow="true"/>
    <geom name="masa" type="plane" size="2 2 0.01" material="masa" friction="{mu_masa} 0.005 0.0001"/>
    <camera name="on" pos="{_f([c[0], c[1] - 2.0, c[2]])}" xyaxes="1 0 0 0 0 1" projection="orthographic" fovy="{e:.6g}"/>
    <camera name="yan" pos="{_f([c[0] + 2.0, c[1], c[2]])}" xyaxes="0 1 0 0 0 1" projection="orthographic" fovy="{e:.6g}"/>
    <camera name="perspektif" pos="{_f([c[0] + e * 0.9, c[1] - e * 1.6, c[2] + e * 0.7])}" mode="targetbody" target="stand" fovy="40"/>
    <body name="stand" pos="0 0 0"><freejoint name="js"/>
      <inertial pos="{_f(stand.com * mm)}" mass="{stand.kutle_g * 1e-3:.6g}" fullinertia="{_f([I[0, 0], I[1, 1], I[2, 2], I[0, 1], I[0, 2], I[1, 2]])}"/>
      {"".join(stand_geom)}
      <geom type="mesh" mesh="gorsel" contype="0" conaffinity="0" group="1" rgba=".86 .82 .74 1"/>
    </body>
    {"".join(govdeler)}
  </worldbody>
</mujoco>"""


class Sahne:
    def __init__(self, stand: Stand, nesneler: list[Nesne], fizik: dict[str, Any]) -> None:
        import mujoco

        self.mj = mujoco
        self.stand, self.nesneler, self.fizik = stand, nesneler, fizik
        lo, hi = stand.zarf
        for n in nesneler:
            nlo, nhi = n.zarf()
            r = float(np.linalg.norm(nhi - nlo)) * 0.45
            lo, hi = np.minimum(lo, -r + (lo + hi) / 2), np.maximum(hi, r + (lo + hi) / 2)
        lo[2] = 0
        merkez = (lo + hi) / 2
        self.kamera = {"merkez": merkez, "olcek": float(max(hi[2] - lo[2], hi[0] - lo[0], hi[1] - lo[1]) * 1.08)}
        self.xml = sahne_xml(stand, nesneler, fizik, self.kamera)
        self.m = mujoco.MjModel.from_xml_string(self.xml)
        self.d = mujoco.MjData(self.m)
        self.masa_geom = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_GEOM, "masa")
        self.stand_govde = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_BODY, "stand")
        self.nesne_govde = [mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_BODY, f"nesne{k}") for k in range(len(nesneler))]
        self.g0 = np.array([0, 0, -G])
        self._render: Any = None

    # --- durum
    def sifirla(self, nesne_pozlari: list[tuple[np.ndarray, np.ndarray]] | None = None, durum: np.ndarray | None = None):
        mj = self.mj
        mj.mj_resetData(self.m, self.d)
        if durum is not None:
            self.d.qpos[:] = durum
        else:
            self.d.qpos[0:7] = [0, 0, 0, 1, 0, 0, 0]
            for k, (R, t) in enumerate(nesne_pozlari or []):
                self.d.qpos[7 + 7 * k: 14 + 7 * k] = np.r_[t * 0.001, _quat_wxyz(R)]
            for k in range(len(nesne_pozlari or []), len(self.nesneler)):  # yerleşmemiş nesneler uzakta
                self.d.qpos[7 + 7 * k: 14 + 7 * k] = [5 + k, 5, 0.2, 1, 0, 0, 0]
        self.d.qvel[:] = 0
        self.m.opt.gravity[:] = self.g0
        mj.mj_forward(self.m, self.d)

    def poz(self, govde: int) -> tuple[np.ndarray, np.ndarray]:
        return self.d.xmat[govde].reshape(3, 3).copy(), self.d.xpos[govde].copy() * 1000

    def nesne_stand_gore(self, k: int) -> tuple[np.ndarray, np.ndarray]:
        Rs, ts = self.poz(self.stand_govde)
        Rn, tn = self.poz(self.nesne_govde[k])
        return Rs.T @ Rn, Rs.T @ (tn - ts)

    def temaslar(self) -> list[dict[str, Any]]:
        mj = self.mj
        sonuc = []
        for i in range(self.d.ncon):
            c = self.d.contact[i]
            b1, b2 = self.m.geom_bodyid[c.geom1], self.m.geom_bodyid[c.geom2]
            sonuc.append({"g1": int(c.geom1), "g2": int(c.geom2), "b1": int(b1), "b2": int(b2),
                          "ad1": mj.mj_id2name(self.m, mj.mjtObj.mjOBJ_GEOM, c.geom1) or "",
                          "ad2": mj.mj_id2name(self.m, mj.mjtObj.mjOBJ_GEOM, c.geom2) or "",
                          "pos": (c.pos * 1000).round(1).tolist(), "derinlik_mm": round(-float(c.dist) * 1000, 2)})
        return sonuc

    def masaya_degiyor(self, k: int) -> bool:
        g = self.nesne_govde[k]
        return any((t["b1"] == g and t["g2"] == self.masa_geom) or (t["b2"] == g and t["g1"] == self.masa_geom)
                   for t in self.temaslar())

    # --- benzetim
    def calistir(self, sure_s: float, yercekimi: Callable[[float], np.ndarray] | None = None,
                 kuvvet: Callable[[float], dict[int, tuple[np.ndarray, np.ndarray]]] | None = None,
                 kare: Callable[[float], None] | None = None, kare_araligi_s: float = 1 / 12,
                 izle: Callable[[float], None] | None = None) -> None:
        mj, m, d = self.mj, self.m, self.d
        dt_ = m.opt.timestep
        adim = max(1, int(round(0.002 / dt_)))  # 2 ms'de bir dış etki güncelle
        t0 = d.time
        son_kare = -1e9
        while d.time - t0 < sure_s - 1e-9:
            t = d.time - t0
            if yercekimi is not None:
                m.opt.gravity[:] = yercekimi(t)
            d.xfrc_applied[:] = 0
            if kuvvet is not None:
                for govde, (F, tork) in kuvvet(t).items():
                    d.xfrc_applied[govde, :3] = F
                    d.xfrc_applied[govde, 3:] = tork
            mj.mj_step(m, d, nstep=adim)
            if izle is not None:
                izle(d.time - t0)
            if kare is not None and d.time - t0 - son_kare >= kare_araligi_s - 1e-9:
                son_kare = d.time - t0
                kare(son_kare)
        m.opt.gravity[:] = self.g0
        d.xfrc_applied[:] = 0

    def otur(self, k: int, sure_s: float, hiz_esik_mm_s: float, kare: Callable[[float], None] | None = None) -> dict[str, Any]:
        """Serbest bırak, sure_s sonra durum: durdu mu, masaya değdi mi, stand döndü mü."""
        Rs0, _ = self.poz(self.stand_govde)
        izler: list[tuple[float, np.ndarray]] = []
        masa = {"degdi": False}

        def izle(t: float) -> None:
            if t > sure_s - 0.35:
                izler.append((t, self.poz(self.nesne_govde[k])[1]))
            if int(t * 1000) % 20 == 0 and self.masaya_degiyor(k):
                masa["degdi"] = True

        self.calistir(sure_s, kare=kare, izle=izle)
        hiz = 0.0
        if len(izler) >= 2:
            hiz = float(np.linalg.norm(izler[-1][1] - izler[0][1]) / max(izler[-1][0] - izler[0][0], 1e-6))
        Rs1, _ = self.poz(self.stand_govde)
        return {"durdu": hiz < hiz_esik_mm_s, "hiz_mm_s": round(hiz, 2), "masada": self.masaya_degiyor(k),
                "masaya_degdi": masa["degdi"], "stand_donme_derece": round(_aci_farki(Rs0, Rs1), 2)}

    # --- görüntü
    def kadraj(self) -> None:
        """Ortografik kameraları stand + oturmuş nesnelerin dünya zarfına oturtur."""
        Rs, ts = self.poz(self.stand_govde)
        pts = [np.asarray(self.stand.gorsel.vertices) @ Rs.T + ts]
        for k, n in enumerate(self.nesneler):
            Rn, tn = self.poz(self.nesne_govde[k])
            if abs(tn[0]) > 3000:  # yerleşmemiş (uzakta) nesne
                continue
            pts += [_parca_dunya_noktalari(p, Rn, tn) for p in n.parcalar]
        tum = np.vstack(pts)
        lo, hi = tum.min(0), tum.max(0)
        lo[2] = min(lo[2], 0.0)
        merkez = (lo + hi) / 2
        olcek = float(max(hi[2] - lo[2], hi[0] - lo[0], hi[1] - lo[1]) * 1.12)
        self.kamera = {"merkez": merkez, "olcek": olcek}
        mj = self.mj
        for ad, ofs in (("on", np.array([0, -2000.0, 0])), ("yan", np.array([2000.0, 0, 0]))):
            cid = mj.mj_name2id(self.m, mj.mjtObj.mjOBJ_CAMERA, ad)
            self.m.cam_pos[cid] = (merkez + ofs) / 1000
            self.m.cam_fovy[cid] = olcek / 1000
        mj.mj_forward(self.m, self.d)

    def goruntu(self, kamera: str, gen: int = 900, yuk: int = 900) -> np.ndarray:
        if kamera in ("on", "yan"):
            self.kadraj()
        if self._render is None or self._render.width != gen or self._render.height != yuk:
            self._render = self.mj.Renderer(self.m, yuk, gen)
        opt = self.mj.MjvOption()
        opt.geomgroup[:] = [1, 1, 1, 0, 0, 0]
        self._render.update_scene(self.d, kamera, scene_option=opt)
        return self._render.render().copy()

    def piksel(self, kamera: str, p_mm: np.ndarray, gen: int, yuk: int) -> tuple[float, float]:
        """Ortografik kamerada dünya noktası → piksel (fovy = dikey kapsam)."""
        c = self.kamera["merkez"]
        olcek = yuk / self.kamera["olcek"]
        yatay = (p_mm[0] - c[0]) if kamera == "on" else (p_mm[1] - c[1])
        return gen / 2 + yatay * olcek, yuk / 2 - (p_mm[2] - c[2]) * olcek


# ============================================================================ yerleşim
def _yon_matrisi(tanim: dict[str, Any], nesne: Nesne, egim: float, aci_z: float = 0.0) -> np.ndarray:
    """Nesnenin dünya yönelimi. Ön = −y (ürün ön yüzü; blender_gorunus kuralı)."""
    if nesne.tip == "telefon":
        # yerel: +z ekran, +y üst. Ekran öne (−y) ve yukarı bakar, üst kenar arkaya yaslanır.
        return _rot("z", aci_z) @ _rot("x", egim)
    if nesne.tip == "oyun_kolu":
        # yüz öne-yukarı, tutamaklar öne-aşağı, tetikler arkada-yukarıda (sergileme duruşu); egim=0 → düz yatık
        return _rot("z", aci_z) @ _rot("x", egim) @ _rot("z", 180)
    return _rot("z", aci_z)


def _tepe_ekseni(stand: Stand, kalinlik_mm: float = 15.0) -> tuple[float, float, float, float]:
    v = np.asarray(stand.mesh.vertices)
    zmax = v[:, 2].max()
    ust = v[v[:, 2] > zmax - kalinlik_mm][:, :2]
    merkez = ust.mean(0)
    cov = np.cov((ust - merkez).T)
    w, vec = np.linalg.eigh(cov)
    ana = vec[:, int(np.argmax(w))]
    return float(merkez[0]), float(merkez[1]), math.degrees(math.atan2(ana[1], ana[0])), float(zmax)


def adaylar(tanim: dict[str, Any], stand: Stand, nesne: Nesne, slot_x: float = 0.0) -> list[dict[str, Any]]:
    lo, hi = stand.zarf
    yer = tanim.get("yerlesim") or {}
    if yer.get("yontem") == "tepe" or nesne.tip == "kulaklik":
        cx, cy, aci, _ = _tepe_ekseni(stand)
        return [{"R": _yon_matrisi(tanim, nesne, 0, aci + d), "x": cx, "y": cy, "egim": 0, "aci_z": aci + d}
                for d in (0, 90)]
    adim = float(yer.get("adim_mm", 5))
    egimler = [float(e) for e in yer.get("egimler_derece") or [0]]
    sonuc = []
    for egim in egimler:
        R = _yon_matrisi(tanim, nesne, egim)
        y_lo, y_hi = (yer.get("y_aralik_mm") or [lo[1] + 2, hi[1]])
        for y in np.arange(float(y_lo), float(y_hi) + 1e-6, adim):
            sonuc.append({"R": R, "x": slot_x, "y": float(y), "egim": egim, "aci_z": 0.0})
    return sonuc


# ============================================================================ ölçümler
def _parca_dunya_noktalari(p: Parca, R: np.ndarray, t: np.ndarray) -> np.ndarray:
    return p.kose_noktalari() @ R.T + t


def gorus_acisi(R: np.ndarray) -> float:
    """Ekran düzleminin yataydan açısı (derece): ekran normali yerel +z."""
    n = R[:, 2]
    return math.degrees(math.acos(max(-1.0, min(1.0, abs(float(n[2]))))))


def kablo_boslugu(carp: Carpisma, nesne: Nesne, R: np.ndarray, t: np.ndarray, fis: dict[str, Any]) -> dict[str, Any]:
    if nesne.yon != "dik":
        return {"uygulanmadi": "yatay yönde port yanda; ölçülmedi"}
    L = float(fis.get("uzunluk", 22))
    port = nesne.noktalar["port"]
    parca = Parca("sarj_fisi", "box", (float(fis.get("genislik", 12.5)) / 2, L / 2, float(fis.get("kalinlik", 7)) / 2),
                  port + np.array([0, -L / 2 - 0.5, 0]))
    mesafe, derinlik = carp.mesafe(parca, R, t)
    return {"bosluk_mm": round(mesafe, 1), "cakisma_mm": round(derinlik, 1), "uygun": mesafe > 0.2,
            "fis_zarfi_mm": [fis.get("genislik"), fis.get("kalinlik"), L]}


def birlesik_com(stand: Stand, sahne: Sahne, yerlesen: list[int]) -> np.ndarray:
    Rs, ts = sahne.poz(sahne.stand_govde)
    toplam = stand.kutle_g * (Rs @ stand.com + ts)
    kutle = stand.kutle_g
    for k in yerlesen:
        n = sahne.nesneler[k]
        com = sahne.d.xipos[sahne.nesne_govde[k]] * 1000
        toplam += n.kutle_g * com
        kutle += n.kutle_g
    return toplam / kutle


# ============================================================================ senaryo
def _rel_kayma(a: tuple[np.ndarray, np.ndarray], b: tuple[np.ndarray, np.ndarray]) -> tuple[float, float]:
    return float(np.linalg.norm(a[1] - b[1])), _aci_farki(a[0], b[0])


def _saglam_mi(sahne: "Sahne", k: int, durum: np.ndarray, aci: float, fz: dict[str, Any], sure: float = 1.0) -> bool:
    """Oturmuş poz, masa `aci` derece 4 yöne eğilince nesne yerinde kalıyor mu (hızlı ön eleme)."""
    sinir = float((fz.get("stand_donme_siniri_derece") or 3))
    for (ux, uy) in YON_ADLARI:
        sahne.sifirla(durum=durum)
        ref = sahne.nesne_stand_gore(k)
        Rs0, _ = sahne.poz(sahne.stand_govde)
        a = math.radians(aci)
        g = np.array([ux * G * math.sin(a), uy * G * math.sin(a), -G * math.cos(a)])
        sahne.calistir(sure, yercekimi=lambda _t, g=g: g)
        kayma, _ = _rel_kayma(ref, sahne.nesne_stand_gore(k))
        if kayma > 5 or sahne.masaya_degiyor(k) or _aci_farki(Rs0, sahne.poz(sahne.stand_govde)[0]) >= sinir:
            return False
    return True


def senaryo_calistir(tanim: dict[str, Any], stand: Stand, carp: Carpisma, nesne: Nesne,
                     kutuphane: dict[str, Any], gif_kareleri: list | None = None,
                     log: Callable[[str], None] | None = None) -> dict[str, Any]:
    fz = tanim["fizik"]
    kur = tanim.get("kurallar") or {}
    kapasite = max(1, int(tanim.get("kapasite") or 1))
    nesneler = [nesne] + [copy.deepcopy(nesne) for _ in range(kapasite - 1)]
    sahne = Sahne(stand, nesneler, fz)
    lo, hi = stand.zarf
    sure = float(fz.get("oturma_suresi_s", 2.0))
    hiz_esik = float(fz.get("dinlenme_hiz_mm_s", 6))
    slotlar = [0.0] if kapasite == 1 else list(np.linspace(lo[0], hi[0], kapasite + 2)[1:-1])
    pozlar: list[tuple[np.ndarray, np.ndarray]] = []
    durum = None
    secilen_adaylar = []
    denenen = 0
    en_iyi_kotu: dict[str, Any] | None = None
    for k, sx in enumerate(slotlar):
        en_iyi = None
        basarililar: list[dict[str, Any]] = []
        for a in adaylar(tanim, stand, nesne, sx):
            z = carp.indir(nesne, a["R"], a["x"], a["y"], float(hi[2]) + 5, masaya_inebilir=nesne.tip == "kulaklik")
            if z is None:
                continue
            denenen += 1
            t0 = np.array([a["x"], a["y"], z])
            sahne.sifirla(pozlar + [(a["R"], t0)])
            if durum is not None:  # önceki nesneler oturmuş halleriyle
                sahne.d.qpos[: 7 * (k + 1)] = durum[: 7 * (k + 1)]
                sahne.d.qpos[7 + 7 * k: 14 + 7 * k] = np.r_[t0 * 0.001, _quat_wxyz(a["R"])]
                sahne.mj.mj_forward(sahne.m, sahne.d)
            o = sahne.otur(k, sure, hiz_esik)
            Rn, tn = sahne.poz(sahne.nesne_govde[k])
            basarili = o["durdu"] and not o["masada"] and o["stand_donme_derece"] < float(fz.get("stand_donme_siniri_derece", 3))
            puan = 0.0
            if nesne.tip == "telefon":
                ga = gorus_acisi(Rn)
                g = kur.get("gorus_acisi_derece") or {}
                orta = (float(g.get("min", 55)) + float(g.get("max", 75))) / 2
                puan = -abs(ga - orta) - 0.02 * float(sahne.d.xipos[sahne.nesne_govde[k]][2] * 1000)
            elif nesne.tip == "oyun_kolu":
                yasak = set((kur.get("yasak_temas") or {}).get("parcalar") or [])
                temas_yasak = any(any(r in (t["ad1"] + t["ad2"]) for r in yasak) for t in sahne.temaslar()
                                  if sahne.stand_govde in (t["b1"], t["b2"]))
                puan = -100 * temas_yasak - 0.05 * float(sahne.d.xipos[sahne.nesne_govde[k]][2] * 1000)
            kayit = {"aday": {k2: (v if k2 != "R" else None) for k2, v in a.items() if k2 != "R"}, "otur": o,
                     "puan": puan, "durum": sahne.d.qpos.copy(), "R": a["R"], "t0": t0, "basarili": basarili,
                     "son": (Rn, tn)}
            if basarili:
                basarililar.append(kayit)
                if en_iyi is None or puan > en_iyi["puan"]:
                    en_iyi = kayit
            if not basarili and (en_iyi_kotu is None or o["hiz_mm_s"] < en_iyi_kotu["otur"]["hiz_mm_s"]):
                en_iyi_kotu = kayit
        if en_iyi is None:
            break
        # Kullanıcı nesneyi tutan pozu bulur: puan sırasıyla ilk N adaydan küçük (zorunlu açı) eğmeye dayananı seç
        zorunlu = float((kur.get("egme") or {}).get("zorunlu_aci_derece", 5))
        for aday_k in sorted(basarililar, key=lambda x: -x["puan"])[: int((tanim.get("yerlesim") or {}).get("saglamlik_aday", 6))]:
            if _saglam_mi(sahne, k, aday_k["durum"], zorunlu, fz):
                aday_k["saglam"] = True
                en_iyi = aday_k
                break
        secilen_adaylar.append(en_iyi)
        durum = en_iyi["durum"]
        pozlar.append((en_iyi["R"], en_iyi["t0"]))
    yerlesen = list(range(len(secilen_adaylar)))
    sonuc: dict[str, Any] = {"nesne": nesne.kimlik, "etiket": nesne.etiket, "tip": nesne.tip, "yon": nesne.yon,
                             "kilif": nesne.kilif, "kutle_g": round(nesne.kutle_g, 1), "denenen_aday": denenen,
                             "nesne_bilgi": _json_temiz(nesne.bilgi), "olcumler": {}, "testler": {}}
    if len(secilen_adaylar) < len(slotlar):
        sonuc["yerlesti"] = False
        sonuc["yerlesen_adet"] = len(secilen_adaylar)
        if en_iyi_kotu is not None:
            sonuc["en_iyi_basarisiz"] = {"aday": en_iyi_kotu["aday"], "otur": en_iyi_kotu["otur"]}
            sahne.sifirla(durum=en_iyi_kotu["durum"])
            sonuc["_sahne"] = sahne
            if nesne.tip == "kulaklik":  # kupalar masaya oturduysa da ölç (≤ 0 mm)
                Rk, tk = sahne.poz(sahne.nesne_govde[0])
                sonuc["olcumler"]["kupa_masa_mesafesi_mm"] = round(min(
                    float(_parca_dunya_noktalari(p, Rk, tk)[:, 2].min()) for p in nesne.parcalar
                    if p.ad.startswith("kupa")), 1)
        else:
            sahne.sifirla(pozlar)
            sonuc["_sahne"] = sahne
            sonuc["en_iyi_basarisiz"] = {"aciklama": "nesne hiçbir konumda standa değmeden masaya iniyor "
                                                     "veya her konumda standla çakışıyor"}
        return sonuc

    sonuc["yerlesti"] = True
    sonuc["yerlesen_adet"] = len(secilen_adaylar)
    sonuc["aday"] = secilen_adaylar[0]["aday"]
    sonuc["aday_saglam_on_eleme"] = bool(secilen_adaylar[0].get("saglam"))
    sonuc["basarili_aday"] = len(basarililar)
    durum_otur = secilen_adaylar[-1]["durum"].copy()
    sahne.sifirla(durum=durum_otur)
    sonuc["_sahne"] = sahne
    sonuc["_durum"] = durum_otur
    olc = sonuc["olcumler"]
    Rn, tn = sahne.poz(sahne.nesne_govde[0])
    Rs, ts = sahne.poz(sahne.stand_govde)
    # temaslar (nesne ↔ stand)
    temas = []
    for t in sahne.temaslar():
        govdeler = {t["b1"], t["b2"]}
        if sahne.stand_govde in govdeler and govdeler & set(sahne.nesne_govde):
            parca = (t["ad1"] or t["ad2"]).split("_", 1)[-1] if t["ad1"].startswith("n") else t["ad2"].split("_", 1)[-1]
            temas.append({"parca": parca, "nokta_mm": t["pos"]})
    olc["temas_noktalari"] = temas[:24]
    olc["temas_parcalari"] = sorted({t["parca"] for t in temas})
    olc["nesne_konum_mm"] = tn.round(1).tolist()
    # en alçak parça noktaları
    alt = {}
    for p in nesne.parcalar:
        alt[p.ad] = float(_parca_dunya_noktalari(p, Rn, tn)[:, 2].min())
    olc["nesne_alt_mm"] = round(min(alt.values()), 1)
    if nesne.tip == "kulaklik":
        olc["kupa_masa_mesafesi_mm"] = round(min(v for k2, v in alt.items() if k2.startswith("kupa")), 1)
    if nesne.tip == "telefon":
        olc["gorus_acisi_derece"] = round(gorus_acisi(Rn), 1)
        olc["kablo"] = kablo_boslugu(carp, nesne, Rs.T @ Rn, Rs.T @ (tn - ts), kutuphane.get("sarj_fisi") or {})
    yasak = (kur.get("yasak_temas") or {}).get("parcalar") or []
    if yasak:
        mesafeler = {}
        for p in nesne.parcalar:
            if p.rol in yasak:
                m_, d_ = carp.mesafe(p, Rs.T @ Rn, Rs.T @ (tn - ts))
                mesafeler[p.ad] = {"mesafe_mm": round(m_, 2), "cakisma_mm": round(d_, 2)}
        olc["yasak_parca_mesafe"] = mesafeler
    com = birlesik_com(stand, sahne, yerlesen)
    olc["birlesik_com_mm"] = com.round(1).tolist()
    olc["devrilme"] = devrilme_acilari(taban_cokgeni(stand), com)

    # ---- dinamik testler (her biri oturmuş durumdan)
    def _bas() -> tuple[np.ndarray, np.ndarray]:
        sahne.sifirla(durum=durum_otur)
        return sahne.nesne_stand_gore(0)

    def _bitir(ref, Rs0, masa_izi) -> dict[str, Any]:
        kayma, donme = _rel_kayma(ref, sahne.nesne_stand_gore(0))
        Rs1, _ = sahne.poz(sahne.stand_govde)
        return {"nesne_kayma_mm": round(kayma, 1), "nesne_donme_derece": round(donme, 1),
                "stand_donme_derece": round(_aci_farki(Rs0, Rs1), 2), "masaya_degdi": bool(masa_izi["v"])}

    def _izleyici(masa_izi):
        def izle(t: float) -> None:
            if int(t * 1000) % 20 == 0 and sahne.masaya_degiyor(0):
                masa_izi["v"] = True
        return izle

    testler = sonuc["testler"]
    # bırakma
    ref = _bas()
    Rs0, _ = sahne.poz(sahne.stand_govde)
    h = float(fz.get("birakma_yuksekligi_mm", 25))
    sahne.d.qpos[9] += h / 1000
    sahne.mj.mj_forward(sahne.m, sahne.d)
    iz = {"v": False}
    gif_fn = None
    if gif_kareleri is not None:
        def gif_fn(_t: float) -> None:
            gif_kareleri.append(sahne.goruntu("perspektif", 480, 360))
    sahne.calistir(sure, kare=gif_fn, izle=_izleyici(iz))
    testler["birakma"] = {"yukseklik_mm": h, "sure_s": sure, **_bitir(ref, Rs0, iz)}
    # eğme
    egme = []
    for aci in fz.get("egme_acilari_derece") or [5, 10]:
        for (ux, uy), ad in YON_ADLARI.items():
            ref = _bas()
            Rs0, _ = sahne.poz(sahne.stand_govde)
            a = math.radians(float(aci))
            g = np.array([ux * G * math.sin(a), uy * G * math.sin(a), -G * math.cos(a)])
            iz = {"v": False}
            sahne.calistir(float(fz.get("egme_suresi_s", 2.0)), yercekimi=lambda _t, g=g: g, izle=_izleyici(iz))
            egme.append({"aci_derece": float(aci), "asagi_inen_kenar": ad, **_bitir(ref, Rs0, iz)})
    testler["egme"] = egme
    # sarsma
    sr = fz.get("sarsma") or {}
    A, f, ss = float(sr.get("genlik_m_s2", 1.5)), float(sr.get("frekans_hz", 3)), float(sr.get("sure_s", 2))
    sarsma = []
    for eksen in ("x", "y"):
        ref = _bas()
        Rs0, _ = sahne.poz(sahne.stand_govde)
        iz = {"v": False}

        def yc(t: float, e=eksen) -> np.ndarray:
            v = A * math.sin(2 * math.pi * f * t)
            return np.array([v if e == "x" else 0, v if e == "y" else 0, -G])

        sahne.calistir(ss, yercekimi=yc, izle=_izleyici(iz))
        sarsma.append({"eksen": eksen, "genlik_m_s2": A, "frekans_hz": f, **_bitir(ref, Rs0, iz)})
    testler["sarsma"] = sarsma
    # dokunma (telefon)
    if nesne.tip == "telefon" and "dokunma" in kur:
        dk = fz.get("dokunma") or {}
        F = float(dk.get("kuvvet_n", 3))
        ref = _bas()
        Rs0, _ = sahne.poz(sahne.stand_govde)
        Rn0, tn0 = sahne.poz(sahne.nesne_govde[0])
        p_yerel = nesne.noktalar["ekran_ust_ucte_bir"]
        iz = {"v": False}
        en_cok = {"stand": 0.0, "kayma": 0.0}
        gid = sahne.nesne_govde[0]

        def kuvvet(_t: float):
            Rn_, tn_ = sahne.poz(gid)
            p = (Rn_ @ p_yerel + tn_) / 1000
            Fv = -Rn_[:, 2] * F
            r = p - sahne.d.xipos[gid]
            return {gid: (Fv, np.cross(r, Fv))}

        def izle(t: float) -> None:
            if int(t * 1000) % 10 == 0:
                Rs1, _ = sahne.poz(sahne.stand_govde)
                en_cok["stand"] = max(en_cok["stand"], _aci_farki(Rs0, Rs1))
                en_cok["kayma"] = max(en_cok["kayma"], _rel_kayma(ref, sahne.nesne_stand_gore(0))[0])
                if sahne.masaya_degiyor(0):
                    iz["v"] = True

        sahne.calistir(float(dk.get("sure_s", 1.0)), kuvvet=kuvvet, izle=izle)
        b = _bitir(ref, Rs0, iz)
        nokta_dunya = Rn0 @ p_yerel + tn0
        testler["dokunma"] = {"kuvvet_n": F, "nokta_mm": nokta_dunya.round(1).tolist(),
                              "en_cok_stand_donme_derece": round(en_cok["stand"], 2),
                              "en_cok_nesne_kayma_mm": round(en_cok["kayma"], 1), **b}
    sahne.sifirla(durum=durum_otur)
    return sonuc


def _json_temiz(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): _json_temiz(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, (list, tuple)):
        return [_json_temiz(v) for v in x]
    if isinstance(x, np.ndarray):
        return x.round(3).tolist()
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


# ============================================================================ kurallar
def _k(kural: str, senaryo: str, gecti: bool, deger: Any, sinir: Any, birim: str, aciklama: str) -> dict[str, Any]:
    return {"kural": kural, "senaryo": senaryo, "durum": "GEÇTİ" if gecti else "KALDI", "deger": deger,
            "sinir": sinir, "birim": birim, "aciklama": aciklama}


def kurallari_degerlendir(tanim: dict[str, Any], senaryolar: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kur = tanim.get("kurallar") or {}
    fz = tanim["fizik"]
    st_sinir = float(fz.get("stand_donme_siniri_derece", 3))
    sonuc: list[dict[str, Any]] = []
    for s in senaryolar:
        e = s["etiket"]
        if "yerlesme" in kur:
            ac = ("standda durdu" if s["yerlesti"] else
                  f"{s['denenen_aday']} konum/eğim denendi; nesne standda tutunamadı")
            sonuc.append(_k("yerlesme", e, bool(s["yerlesti"]), s.get("yerlesen_adet"), max(1, int(tanim.get("kapasite") or 1)),
                            "adet", ac))
        if not s["yerlesti"]:
            v = (s.get("olcumler") or {}).get("kupa_masa_mesafesi_mm")
            if "kupa_masa_mesafesi_mm" in kur and v is not None:
                mn = float(kur["kupa_masa_mesafesi_mm"].get("min", 10))
                sonuc.append(_k("kupa_masa_mesafesi_mm", e, v >= mn, v, f"≥ {mn:g}", "mm",
                                "kupa altının masaya uzaklığı (kulaklık standda tutunamadı; en iyi denemedeki konum)"))
            continue
        o, t = s["olcumler"], s["testler"]
        if "kupa_masa_mesafesi_mm" in kur:
            mn = float(kur["kupa_masa_mesafesi_mm"].get("min", 10))
            v = o.get("kupa_masa_mesafesi_mm")
            sonuc.append(_k("kupa_masa_mesafesi_mm", e, v is not None and v >= mn, v, f"≥ {mn:g}", "mm",
                            "kupa altının masaya uzaklığı"))
        if (kur.get("bant_temasi") or {}).get("gerekli"):
            parcalar = o.get("temas_parcalari") or []
            bant = any(p.startswith("bant") or p.startswith("catal") for p in parcalar)
            sonuc.append(_k("bant_temasi", e, bant, ", ".join(parcalar) or "—", "bant", "mm",
                            "standa değen kulaklık parçaları"))
        if "yasak_temas" in kur:
            mn = float(kur["yasak_temas"].get("min_mesafe_mm", 0.5))
            ms = o.get("yasak_parca_mesafe") or {}
            if ms:
                en = min(ms.items(), key=lambda kv: kv[1]["mesafe_mm"] - kv[1]["cakisma_mm"])
                gecti = all(v["mesafe_mm"] >= mn for v in ms.values())
                sonuc.append(_k("yasak_temas", e, gecti, en[1]["mesafe_mm"], f"≥ {mn:g}", "mm",
                                f"en yakın yasak parça: {en[0]}" + (f" (çakışma {en[1]['cakisma_mm']} mm)"
                                                                     if en[1]["cakisma_mm"] else "")))
        if "gorus_acisi_derece" in kur:
            g = kur["gorus_acisi_derece"]
            v = o.get("gorus_acisi_derece")
            sonuc.append(_k("gorus_acisi_derece", e, v is not None and float(g["min"]) <= v <= float(g["max"]), v,
                            f"{g['min']}–{g['max']}", "°", "ekran düzleminin yataydan açısı"))
        if (kur.get("kablo_boslugu") or {}).get("gerekli") and "kablo" in o and "uygun" in o["kablo"]:
            kb = o["kablo"]
            sonuc.append(_k("kablo_boslugu", e, bool(kb["uygun"]), kb["bosluk_mm"] if kb["uygun"] else -kb["cakisma_mm"],
                            "> 0", "mm", f"alt kenar ortasında şarj fişi zarfı {kb['fis_zarfi_mm']} mm"))
        if "devrilme_acisi_derece" in kur:
            mn = float(kur["devrilme_acisi_derece"].get("min", 10))
            dv = o.get("devrilme") or {}
            sonuc.append(_k("devrilme_acisi_derece", e, float(dv.get("min_derece", 0)) >= mn, dv.get("min_derece"),
                            f"≥ {mn:g}", "°", f"en zayıf yön {dv.get('en_zayif_yon')}; ağırlık merkezi "
                                                f"{dv.get('com_yukseklik_mm')} mm yükseklikte"))
        b = t.get("birakma") or {}
        if b:
            mx = float((kur.get("egme") or {}).get("nesne_kayma_mm_max", 5))
            sonuc.append(_k("birakma", e, b["nesne_kayma_mm"] <= mx and not b["masaya_degdi"]
                            and b["stand_donme_derece"] < st_sinir, b["nesne_kayma_mm"], f"≤ {mx:g}", "mm",
                            f"{b['yukseklik_mm']:.0f} mm'den bırakınca oturduğu yere dönüş"
                            + (" — masaya düştü" if b["masaya_degdi"] else "")))
        if "egme" in kur and t.get("egme"):
            mx = float(kur["egme"].get("nesne_kayma_mm_max", 5))
            zorunlu = float(kur["egme"].get("zorunlu_aci_derece", 5))

            def _iyi(x: dict[str, Any]) -> bool:
                return x["nesne_kayma_mm"] <= mx and not x["masaya_degdi"] and x["stand_donme_derece"] < st_sinir

            for aci in sorted({x["aci_derece"] for x in t["egme"]}):
                grup = [x for x in t["egme"] if x["aci_derece"] == aci]
                en = max(grup, key=lambda x: (x["masaya_degdi"], x["stand_donme_derece"] >= st_sinir, x["nesne_kayma_mm"]))
                devrildi = en["stand_donme_derece"] >= st_sinir
                kayit = _k("egme" if aci <= zorunlu else f"egme_{aci:.0f}_zorlayici", e, all(_iyi(x) for x in grup),
                           en["nesne_kayma_mm"], f"≤ {mx:g}", "mm",
                           f"masa {aci:.0f}° — en kötü {en['asagi_inen_kenar']} aşağı: stand dönmesi "
                           f"{en['stand_donme_derece']}°" + (" — STAND DEVRİLDİ" if devrildi else "")
                           + (" — nesne masaya düştü" if en["masaya_degdi"] else ""))
                kayit["stand_devrildi"] = devrildi
                if aci > zorunlu:
                    kayit["zorunlu"] = False
                    kayit["aciklama"] += f" (bilgi: >{zorunlu:g}° zorlayıcı test, genel sonucu etkilemez)"
                sonuc.append(kayit)
        if "sarsma" in kur and t.get("sarsma"):
            mx = float(kur["sarsma"].get("nesne_kayma_mm_max", 10))
            en = max(t["sarsma"], key=lambda x: x["nesne_kayma_mm"])
            gecti = all(x["nesne_kayma_mm"] <= mx and not x["masaya_degdi"] and x["stand_donme_derece"] < st_sinir
                        for x in t["sarsma"])
            sonuc.append(_k("sarsma", e, gecti, en["nesne_kayma_mm"], f"≤ {mx:g}", "mm",
                            f"{en['genlik_m_s2']} m/s² · {en['frekans_hz']} Hz, en kötü eksen {en['eksen']}"))
        if "dokunma" in kur and t.get("dokunma"):
            mx = float(kur["dokunma"].get("nesne_kayma_mm_max", 3))
            d = t["dokunma"]
            gecti = d["en_cok_nesne_kayma_mm"] <= mx and d["en_cok_stand_donme_derece"] < st_sinir and not d["masaya_degdi"]
            sonuc.append(_k("dokunma", e, gecti, d["en_cok_nesne_kayma_mm"], f"≤ {mx:g}", "mm",
                            f"ekrana {d['kuvvet_n']:g} N: stand en çok {d['en_cok_stand_donme_derece']}° döndü"))
    return sonuc


# ============================================================================ düzeltme önerileri
def duzeltme_onerileri(tanim: dict[str, Any], senaryolar: list[dict[str, Any]], kurallar: list[dict[str, Any]],
                       stand: Stand) -> list[str]:
    kur = tanim.get("kurallar") or {}
    fz = tanim["fizik"]
    kalan = [k for k in kurallar if k["durum"] == "KALDI" and k.get("zorunlu", True)]
    oneriler: list[str] = []
    ss = {s["etiket"]: s for s in senaryolar}

    def ilk(ad: str) -> list[dict[str, Any]]:
        return [k for k in kalan if k["kural"] == ad]

    if ilk("kupa_masa_mesafesi_mm"):
        en = min(ilk("kupa_masa_mesafesi_mm"), key=lambda k: k["deger"])
        mn = float(kur["kupa_masa_mesafesi_mm"].get("min", 10))
        H = float(ss[en["senaryo"]]["nesne_bilgi"].get("H") or 0)
        deger = float(en["deger"])
        # kupa masaya oturduysa ölçülen değer gerçek açığı göstermez: gereken tepe = H + hedef − mevcut tepe
        artis = (mn - deger + 5) if deger > 0.5 else (H + mn - float(stand.zarf[1][2]) + 5)
        oneriler.append(f"Kulaklık bandının oturduğu tepe noktasını en az {max(artis, 5):.0f} mm yükselt: "
                        f"H={H:.0f} mm kulaklıkta kupa altı masadan {deger:.0f} mm (hedef ≥ {mn:.0f} mm, +5 mm pay; "
                        f"stand tepesi şu an {float(stand.zarf[1][2]):.0f} mm).")
    if ilk("bant_temasi"):
        oneriler.append("Yük kupalardan taşınıyor: bant yayının oturacağı sele/askıyı genişlet veya derinleştir; "
                        "kupaların standa değmemesi için sele altındaki gövdeyi her yandan en az "
                        f"{5:.0f} mm içeri al.")
    for k in ilk("yasak_temas"):
        s = ss[k["senaryo"]]
        ms = s["olcumler"].get("yasak_parca_mesafe") or {}
        for ad, v in ms.items():
            if v["mesafe_mm"] < float(kur["yasak_temas"].get("min_mesafe_mm", 0.5)):
                oneriler.append(f"{s['etiket']}: '{ad}' standa değiyor (çakışma {v['cakisma_mm']:.1f} mm): o bölgede "
                                f"en az {v['cakisma_mm'] + 3:.0f} mm boşluk aç (oyuk/pah) veya yuvayı tetik/çubuktan "
                                "uzaklaştır.")
        break
    for k in ilk("gorus_acisi_derece"):
        g = kur["gorus_acisi_derece"]
        orta = (float(g["min"]) + float(g["max"])) / 2
        v = float(k["deger"])
        yon = "dikleştir" if v < orta else "yatır"
        oneriler.append(f"{k['senaryo']}: ekran açısı {v:.0f}° (hedef {g['min']}–{g['max']}°): arka dayanağı "
                        f"{abs(orta - v):.0f}° {yon} (hedef ~{orta:.0f}°).")
        break
    if ilk("kablo_boslugu"):
        oneriler.append("Telefonun alt kenarı ortasında şarj fişi için en az 14 mm genişlik × 9 mm yükseklik × "
                        "24 mm derinlikte kanal/açıklık aç (USB-C fiş zarfı 12.5 × 7 × 22 mm + pay).")
    yer = ilk("yerlesme")
    if yer:
        kilifsiz_ok = any(s["yerlesti"] and not s["kilif"] for s in senaryolar)
        for k in yer:
            s = ss[k["senaryo"]]
            if s["tip"] == "telefon" and s["kilif"] and kilifsiz_ok:
                kal = s["nesne_bilgi"].get("olcu", {}).get("kalinlik")
                oneriler.append(f"{s['etiket']}: kılıflı telefon oturmuyor → telefon oluğunu/dudak aralığını en az "
                                f"{(kal or 11) + 1.5:.1f} mm'ye aç (kılıflı kalınlık {kal} mm + 1.5 mm pay).")
            elif s["tip"] == "telefon":
                b = (s.get("en_iyi_basarisiz") or {}).get("otur") or {}
                oneriler.append(f"{s['etiket']}: telefon standda durmuyor (en iyi denemede "
                                f"{'masaya kaydı' if b.get('masada') else 'durmadı'}): ön kenara en az 8 mm "
                                f"yüksekliğinde, {(s['nesne_bilgi'].get('olcu', {}).get('kalinlik') or 9) + 3:.0f} mm "
                                "genişliğinde tutma dudağı/oluk ekle ve arkasında 60–70° dayanak yüzeyi bırak.")
            elif s["tip"] == "oyun_kolu":
                zarf = s["nesne_bilgi"].get("ilkel_zarf_mm") or []
                oneriler.append(f"{s['etiket']}: kol hiçbir konumda yuvada kalmadı ({s['denenen_aday']} konum × eğim). "
                                f"Kol zarfı ~{' × '.join(f'{z:.0f}' for z in zarf)} mm; iki tutamağı ayrı ayrı "
                                "taşıyan, aralığı ~110–120 mm (tutamak merkezleri) ve en az 15 mm derinlikte iki "
                                "beşik ya da gövdenin altını taşıyan 20–25 mm derin tek beşik tasarla.")
            elif s["tip"] == "kulaklik":
                oneriler.append(f"{s['etiket']}: kulaklık bandı tepede tutunamadı: bant yayının oturacağı en az "
                                "40 mm uzunluk, 25 mm genişlikte iç bükey sele tasarla.")
    st_sinir = float(fz.get("stand_donme_siniri_derece", 3))
    dokunma_devirdi = [k for k in ilk("dokunma") if "STAND" in k["aciklama"] or
                       float(ss[k["senaryo"]]["testler"]["dokunma"]["en_cok_stand_donme_derece"]) >= st_sinir]
    dev = ilk("devrilme_acisi_derece") + [k for k in ilk("egme") if k.get("stand_devrildi")]
    kayma = [k for k in ilk("egme") + ilk("dokunma") if not k.get("stand_devrildi") and k not in dokunma_devirdi]
    if dev:
        # en kötü senaryo: en düşük devrilme açısı
        en_s = min((s for s in senaryolar if s["yerlesti"]), key=lambda s: s["olcumler"]["devrilme"]["min_derece"])
        dv = en_s["olcumler"]["devrilme"]
        mn = float((kur.get("devrilme_acisi_derece") or {}).get("min", 10))
        h = float(dv.get("com_yukseklik_mm") or 0)
        if dv.get("yonler"):
            zayif = min(dv["yonler"], key=dv["yonler"].get)
            d_simdi = float(dv["mesafe_mm"][zayif])
            hedef = max(mn, dv["yonler"][zayif] + 4)
            d_gerek = h * math.tan(math.radians(hedef))
            oneriler.append(f"Tabanı {zayif} yönünde {max(3.0, d_gerek - d_simdi + 2):.0f} mm uzat: devrilme açısı "
                            f"{dv['yonler'][zayif]:.0f}° → ~{hedef:.0f}° ({en_s['etiket']}, ağırlık merkezi "
                            f"{h:.0f} mm yükseklikte). Alternatif: tabana ~{max(20, int(stand.kutle_g * 0.3))} g "
                            "ağırlık/dolgu artışı.")
    dk = [s for s in senaryolar if s["yerlesti"] and "dokunma" in s["testler"]]
    if dokunma_devirdi and dk:
        F = float((fz.get("dokunma") or {}).get("kuvvet_n", 3))
        en_uzatma, metin = 0.0, ""
        for s in dk:
            gerek = dokunma_arka_kenar(s, stand.kutle_g, F)
            if gerek and gerek["uzatma_mm"] > en_uzatma:
                en_uzatma = gerek["uzatma_mm"]
                metin = (f"Ekrana {F:g} N dokunuşta devrilmemek için ({s['etiket']}; itme noktası "
                         f"{gerek['itme_yuksekligi_mm']:.0f} mm yükseklikte, ekran {gerek['aci']:.0f}°, toplam "
                         f"{gerek['kutle_g']:.0f} g) taban arka kenarı y ≥ {gerek['gereken_y_mm']:.0f} mm olmalı "
                         f"(şu an {gerek['simdi_y_mm']:.0f} mm, %20 pay dahil): tabanı arkaya "
                         f"{max(3.0, gerek['uzatma_mm']):.0f} mm uzat veya alt gövdeye ~"
                         f"{gerek['ek_kutle_g']:.0f} g ağırlık ekle.")
        if metin:
            oneriler.append(metin)
    dar = [k for k in kurallar if k["kural"] == "orta_aciklik" and k["durum"] == "KALDI"]
    if dar and kalan:
        en = max(dar, key=lambda k: float(k["sinir"].split()[-1]))
        oneriler.append(f"Orta açıklık {en['deger']} mm, en geniş telefon ({en['senaryo']}) için ≥ "
                        f"{en['sinir'].split()[-1]} mm gerekir: telefon yan engellerin (sütunların) arasına giremiyor, "
                        "ön kenara yaslanıyor. Sütun iç açıklığını bu ölçüye çıkar ya da dayanak/oluğu sütunların "
                        "önüne al.")
    tutma = kayma + ilk("sarsma") + ilk("birakma")
    if tutma:
        ayrinti = "; ".join(f"{k['kural']} {k['deger']} {k['birim']} ({k['senaryo']}: {k['aciklama'][:70]})"
                            for k in tutma[:3])
        oneriler.append("Nesne yuvada tutunmuyor (stand sağlam, nesne kayıyor/düşüyor): " + ayrinti
                        + ". Tutma yüzeyinin kayma yönündeki kenarına en az 5 mm yüksekliğinde dudak ekle veya "
                        "yuvayı 5 mm derinleştir; nesnenin ağırlık merkezini dayanak hattının gerisine al.")
    return list(dict.fromkeys(oneriler))


def dokunma_arka_kenar(s: dict[str, Any], stand_g: float, F: float, pay: float = 1.2) -> dict[str, float] | None:
    """Ekrana dik itmede (arkaya + aşağı bileşen) arka devrilme kenarı için moment dengesi.
    Kararlılık: M·g·(y_r − y_c) + F·cosθ·(y_r − y_p) ≥ F·sinθ·z_p  →  y_r ≥ (F sinθ z_p + M g y_c + F cosθ y_p)/(M g + F cosθ)."""
    o, d = s.get("olcumler") or {}, (s.get("testler") or {}).get("dokunma")
    if not d or "gorus_acisi_derece" not in o:
        return None
    th = math.radians(float(o["gorus_acisi_derece"]))
    yp, zp = float(d["nokta_mm"][1]), float(d["nokta_mm"][2])
    yc = float(o["birlesik_com_mm"][1])
    kutle = stand_g + float(s["kutle_g"])
    Mg = kutle / 1000 * G
    Fp = F * pay
    yr = (Fp * math.sin(th) * zp + Mg * yc + Fp * math.cos(th) * yp) / (Mg + Fp * math.cos(th))
    simdi = yc + float((o.get("devrilme") or {}).get("mesafe_mm", {}).get("arka (+y)", 0))
    # aynı kenarla dengelemek için gereken ek kütle (ağırlık merkezi civarına eklenirse)
    tork = Fp * math.sin(th) * zp - Fp * math.cos(th) * (simdi - yp) - Mg * (simdi - yc)
    ek = max(0.0, tork / max(simdi - yc, 1.0) / G * 1000)
    return {"gereken_y_mm": yr, "simdi_y_mm": simdi, "uzatma_mm": yr - simdi + 2, "itme_yuksekligi_mm": zp,
            "aci": math.degrees(th), "kutle_g": kutle, "ek_kutle_g": ek}


# ============================================================================ pano
def _font(boy: int, kalin: bool = False):
    from PIL import ImageFont

    try:
        return ImageFont.truetype(FONT_KALIN if kalin else FONT, boy)
    except OSError:
        return ImageFont.load_default()


def pano_ciz(yol: Path, urun_adi: str, sku: str, durum: str, temsil: dict[str, Any], senaryolar: list[dict[str, Any]],
             kurallar: list[dict[str, Any]], varsayim_satiri: str, tarih: str) -> None:
    from PIL import Image, ImageDraw

    S = 760
    sahne: Sahne = temsil["_sahne"]
    on = Image.fromarray(sahne.goruntu("on", S, S))
    yan = Image.fromarray(sahne.goruntu("yan", S, S))
    kucukler = []
    for s in senaryolar[:6]:
        im = Image.fromarray(s["_sahne"].goruntu("on", 300, 300)) if s.get("_sahne") else Image.new("RGB", (300, 300), "white")
        kucukler.append((s, im))
    W = 2 * S + 60
    satir_say = len(kurallar)
    H = 110 + S + 40 + (362 if kucukler else 0) + 40 + 30 * min(satir_say, 28) + 120
    pano = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(pano)
    renk = (25, 135, 60) if durum == "GEÇTİ" else (190, 35, 35)
    dr.text((20, 18), f"KULLANIM TESTİ — {urun_adi}", font=_font(34, True), fill=(20, 20, 20))
    dr.text((20, 62), f"{sku} · {tarih} · {temsil['etiket']}", font=_font(20), fill=(90, 90, 90))
    dr.rectangle([W - 250, 18, W - 20, 82], fill=renk)
    dr.text((W - 235, 28), durum, font=_font(40, True), fill="white")
    y0 = 110
    pano.paste(on, (20, y0))
    pano.paste(yan, (S + 40, y0))
    dr.text((30, y0 + 8), "ÖN", font=_font(22, True), fill=(60, 60, 60))
    dr.text((S + 50, y0 + 8), "YAN (sağdan; ön solda)", font=_font(22, True), fill=(60, 60, 60))
    o = temsil.get("olcumler") or {}
    kirmizi, mavi = (200, 30, 30), (20, 90, 200)
    # masa çizgisi + ölçü çizgileri (deterministik, gerçek ölçümden)
    for kam, x_off in (("on", 20), ("yan", S + 40)):
        _, ym = sahne.piksel(kam, np.array([0, 0, 0.0]), S, S)
        dr.line([(x_off, y0 + ym), (x_off + S, y0 + ym)], fill=(120, 120, 120), width=2)
        if "kupa_masa_mesafesi_mm" in o and temsil.get("yerlesti"):
            kmm = o["kupa_masa_mesafesi_mm"]
            Rn, tn = sahne.poz(sahne.nesne_govde[0])
            kupa = [p for p in sahne.nesneler[0].parcalar if p.ad.startswith("kupa")]
            pts = np.vstack([_parca_dunya_noktalari(p, Rn, tn) for p in kupa])
            alt = pts[np.argmin(pts[:, 2])]
            px, py = sahne.piksel(kam, alt, S, S)
            dr.line([(x_off + px, y0 + py), (x_off + px, y0 + ym)], fill=kirmizi if kmm < 10 else mavi, width=4)
            dr.text((x_off + px + 8, y0 + (py + ym) / 2 - 12), f"kupa–masa {kmm:.0f} mm", font=_font(22, True),
                    fill=kirmizi if kmm < 10 else mavi)
    if "gorus_acisi_derece" in o and temsil.get("yerlesti"):
        Rn, tn = sahne.poz(sahne.nesne_govde[0])
        a = sahne.piksel("yan", Rn @ temsil["_nokta_alt"] + tn, S, S) if "_nokta_alt" in temsil else None
        n = sahne.nesneler[0]
        alt = Rn @ n.noktalar["alt_kenar"] + tn
        ust = Rn @ (-n.noktalar["alt_kenar"]) + tn
        pa, pu = sahne.piksel("yan", alt, S, S), sahne.piksel("yan", ust, S, S)
        dr.line([(S + 40 + pa[0], y0 + pa[1]), (S + 40 + pu[0], y0 + pu[1])], fill=mavi, width=4)
        dr.line([(S + 40 + pa[0], y0 + pa[1]), (S + 40 + pa[0] + 140, y0 + pa[1])], fill=mavi, width=2)
        dr.text((S + 40 + pa[0] + 20, y0 + pa[1] - 40), f"ekran açısı {o['gorus_acisi_derece']:.0f}°",
                font=_font(22, True), fill=mavi)
        kb = o.get("kablo") or {}
        if "fis_zarfi_mm" in kb:
            fg, fk, fl = (float(x) for x in kb["fis_zarfi_mm"])
            port = n.noktalar["port"]
            kose = [port + np.array([0, -0.5 - dy, dz]) for dy, dz in ((0, -fk / 2), (fl, -fk / 2), (fl, fk / 2), (0, fk / 2))]
            pk = [sahne.piksel("yan", Rn @ q + tn, S, S) for q in kose]
            r_k = (25, 135, 60) if kb.get("uygun") else kirmizi
            dr.polygon([(S + 40 + a_[0], y0 + a_[1]) for a_ in pk], outline=r_k, width=3)
            etiket = "şarj fişi sığar" if kb.get("uygun") else f"şarj fişi çakışma {kb.get('cakisma_mm')} mm"
            dr.text((S + 40 + pk[1][0] - 230, y0 + pk[1][1] + 6), etiket, font=_font(20, True), fill=r_k)
        del a
    dv = o.get("devrilme") or {}
    if dv:
        dr.text((30, y0 + S - 34), f"devrilme (en zayıf): {dv.get('min_derece')}°", font=_font(20, True),
                fill=(60, 60, 60))
    y = y0 + S + 20
    if kucukler:
        dr.text((20, y), "Senaryolar (ön görünüm)", font=_font(22, True), fill=(40, 40, 40))
        y += 32
        for i, (s, im) in enumerate(kucukler):
            x = 20 + i * ((W - 40) // max(len(kucukler), 1))
            im = im.resize((min(300, (W - 40) // len(kucukler) - 10),) * 2)
            pano.paste(im, (x, y))
            s_durum = "GEÇTİ" if all(k["durum"] == "GEÇTİ" for k in kurallar
                                     if k["senaryo"] == s["etiket"] and k.get("zorunlu", True)) else "KALDI"
            dr.text((x, y + im.size[1] + 2), s["etiket"][:32], font=_font(15), fill=(40, 40, 40))
            dr.text((x, y + im.size[1] + 20), s["etiket"][32:64], font=_font(15), fill=(40, 40, 40))
            dr.text((x, y + im.size[1] + 38), s_durum, font=_font(15, True),
                    fill=(25, 135, 60) if s_durum == "GEÇTİ" else (190, 35, 35))
        y += 362
    dr.text((20, y), "Kurallar", font=_font(22, True), fill=(40, 40, 40))
    y += 34
    for k in kurallar[:28]:
        isaret = "✓" if k["durum"] == "GEÇTİ" else "✗"
        r = (25, 135, 60) if k["durum"] == "GEÇTİ" else (190, 35, 35)
        dr.text((24, y), isaret, font=_font(20, True), fill=r)
        dr.text((50, y), f"{k['kural']}: {k['deger']} {k['birim']} (sınır {k['sinir']}) — {k['senaryo']}"[:150],
                font=_font(17), fill=(30, 30, 30))
        y += 30
    if len(kurallar) > 28:
        dr.text((50, y), f"… +{len(kurallar) - 28} kural (rapor.json)", font=_font(17), fill=(90, 90, 90))
        y += 30
    y += 10
    for i in range(0, len(varsayim_satiri), 170):
        dr.text((20, y), varsayim_satiri[i:i + 170], font=_font(14), fill=(110, 110, 110))
        y += 20
    pano = pano.crop((0, 0, W, min(H, y + 20)))
    pano.save(yol)


# ============================================================================ ana akış
def senaryo_listesi(tanim: dict[str, Any], kutuphane: dict[str, Any]) -> list[Nesne]:
    nesneler = []
    for kimlik in tanim.get("nesneler") or []:
        t = (kutuphane.get("nesneler") or {}).get(kimlik)
        if not t:
            raise KeyError(f"nesne kütüphanesinde yok: {kimlik}")
        if t["tip"] == "kulaklik":
            for v in t.get("varyantlar") or {}:
                nesneler.append(nesne_olustur(kimlik, v, kutuphane=kutuphane))
        elif t["tip"] == "telefon":
            for yon in tanim.get("yonler") or ["dik"]:
                for kilif in tanim.get("kilif") or [False]:
                    nesneler.append(nesne_olustur(kimlik, kilif=bool(kilif), yon=yon, kutuphane=kutuphane))
        else:
            nesneler.append(nesne_olustur(kimlik, kutuphane=kutuphane))
    return nesneler


def kullanim_testi(stl: Path, urun: dict[str, Any], cikti: Path | None = None, gorsel: bool = True,
                   konfig: Path | None = None, log: Callable[[str], None] | None = None,
                   tanim: dict[str, Any] | None = None) -> dict[str, Any]:
    """Testi çalıştırır, rapor sözlüğünü döndürür; `cikti` verilirse rapor.json + pano.png (+ gif) yazar."""
    log = log or (lambda _m: None)
    tanim = tanim or test_tanimi(urun, konfig)
    kut = nesne_kutuphanesi(konfig)
    fz = tanim["fizik"]
    log(f"stand hazırlanıyor: {stl.name}")
    stand = stand_hazirla(Path(stl), urun, fz, log=log)
    carp = Carpisma(stand)
    senaryolar = []
    gif: list = []
    for n in senaryo_listesi(tanim, kut):
        log(f"senaryo: {n.etiket}")
        senaryolar.append(senaryo_calistir(tanim, stand, carp, n, kut, gif_kareleri=gif if (gorsel and not gif) else None,
                                           log=log))
    kurallar = kurallari_degerlendir(tanim, senaryolar)
    aciklik = orta_aciklik(stand) if tanim["sablon"] == "telefon_standi" else None
    if aciklik:
        for s in senaryolar:
            gen = float((s["nesne_bilgi"].get("olcu") or {}).get("genislik" if s["yon"] == "dik" else "yukseklik") or 0)
            k = _k("orta_aciklik", s["etiket"], aciklik["aciklik_mm"] >= gen + 2, aciklik["aciklik_mm"], f"≥ {gen + 2:.1f}",
                   "mm", f"yan engeller arası iç açıklık (z={aciklik['z_mm']} mm, x {aciklik['sol_x_mm']}…"
                         f"{aciklik['sag_x_mm']}); telefon genişliği {gen:.1f} mm + 2 mm pay — bilgi: telefon "
                         "engellerin önünde de durabilir, genel sonucu etkilemez")
            k["zorunlu"] = False
            kurallar.append(k)
    durum = "GEÇTİ" if kurallar and all(k["durum"] == "GEÇTİ" for k in kurallar if k.get("zorunlu", True)) else "KALDI"
    oneriler = duzeltme_onerileri(tanim, senaryolar, kurallar, stand) if durum == "KALDI" else []
    sur = fz.get("surtunme") or {}
    varsayimlar = {
        "kutle": stand.kutle_kaynagi,
        "kutle_dagilimi": "stand homojen yoğunluk (ağırlık merkezi geometrik hacim merkezi)",
        "surtunme": sur, "surtunme_kurali": "MuJoCo: temas çiftinde büyük μ",
        "masa": "düz, rijit; eğme yerçekimi döndürülerek, sarsma yatay sanal ivme ile",
        "nesne_geometrisi": "ilkel bileşim (kutu/kapsül/elipsoid/silindir); dış zarf ve kütle kaynakta",
        "on_yon": "−y (STL ön yüzü; blender_gorunus kuralı)",
        "zaman_adimi_s": fz.get("zaman_adimi_s"), "oturma_suresi_s": fz.get("oturma_suresi_s"),
        "dogrulanmamis_nesne_olculeri": sorted({s["etiket"] for s in senaryolar
                                                if s["nesne_bilgi"].get("dogrulanmadi")}),
        "dogrulanmamis_parca_yerlesimi": sorted({s["nesne"] for s in senaryolar
                                                 if s["nesne_bilgi"].get("parca_varsayimi_dogrulanmadi")}),
        "motor": "MuJoCo 4 (Apache-2.0) + CoACD (MIT) + python-fcl (BSD) + trimesh/shapely",
    }
    tarih = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    rapor = {
        "surum": 1, "tarih": tarih, "sku": urun.get("sku"), "urun": urun.get("ad"), "stl": str(stl),
        "sablon": tanim["sablon"], "vaat": tanim.get("vaat"), "durum": durum,
        "ozet": {"kural": len(kurallar), "gecti": sum(k["durum"] == "GEÇTİ" for k in kurallar),
                 "kaldi": sum(k["durum"] == "KALDI" for k in kurallar)},
        "kurallar": kurallar, "duzeltme_onerisi": oneriler,
        "stand": {"kutle_g": round(stand.kutle_g, 1), "kutle_kaynagi": stand.kutle_kaynagi,
                  "com_mm": stand.com.round(1).tolist(), **stand.bilgi},
        "senaryolar": [_json_temiz({k: v for k, v in s.items() if not k.startswith("_")}) for s in senaryolar],
        "tanim": _json_temiz(tanim), "varsayimlar": varsayimlar,
    }
    if cikti is not None:
        cikti.mkdir(parents=True, exist_ok=True)
        if gorsel:
            temsil = next((s for s in senaryolar if any(k["durum"] == "KALDI" and k["senaryo"] == s["etiket"]
                                                        and k.get("zorunlu", True) for k in kurallar)), senaryolar[0])
            vs = (f"Varsayımlar: kütle {stand.kutle_kaynagi}; μ " + ", ".join(f"{k} {v}" for k, v in sur.items())
                  + f"; nesneler ilkel geometri (dogrulanmadi: {', '.join(varsayimlar['dogrulanmamis_nesne_olculeri']) or '—'}).")
            pano_ciz(cikti / "pano.png", str(urun.get("ad") or ""), str(urun.get("sku") or ""), durum, temsil,
                     senaryolar, kurallar, vs, tarih)
            rapor["pano"] = str(cikti / "pano.png")
            if gif:
                from PIL import Image

                kareler = [Image.fromarray(k) for k in gif]
                kareler[0].save(cikti / "birakma.gif", save_all=True, append_images=kareler[1:], duration=83, loop=0)
                rapor["gif"] = str(cikti / "birakma.gif")
        (cikti / "rapor.json").write_text(json.dumps(_json_temiz(rapor), ensure_ascii=False, indent=2), encoding="utf-8")
        rapor["rapor"] = str(cikti / "rapor.json")
    return rapor


def urun_testi(sku: str, urunler: Path | None = None, kayit: bool = False, gorsel: bool = True,
               cikti: Path | None = None, log: Callable[[str], None] | None = None) -> dict[str, Any]:
    from .kullanim_testi_hatti import son_sonucu_kaydet, stl_yolu, urun_oku

    kok = (urunler or URUNLER_KLASORU) / sku
    urun = urun_oku(sku, urunler)
    urun.setdefault("sku", sku)
    stl = stl_yolu(sku, urunler)
    if stl is None:
        raise FileNotFoundError(f"{sku}: STL bulunamadı (urun.yaml stl_yolu / model/<sku>.stl)")
    cikti = cikti or (kok / "model" / "kullanim_testi" / dt.datetime.now().strftime("%Y%m%d-%H%M"))
    rapor = kullanim_testi(stl, urun, cikti, gorsel=gorsel, log=log)
    if kayit:
        son_sonucu_kaydet(sku, rapor, urunler)
    return rapor


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kullanım testi (fizik + geometri)")
    ap.add_argument("sku")
    ap.add_argument("--kayit", action="store_true", help="sonucu urun.yaml > kullanim_testi.son'a yaz")
    ap.add_argument("--gorselsiz", action="store_true")
    ap.add_argument("--cikti", type=Path)
    a = ap.parse_args(argv)
    rapor = urun_testi(a.sku, kayit=a.kayit, gorsel=not a.gorselsiz, cikti=a.cikti,
                       log=lambda m: print(f"· {m}", file=sys.stderr, flush=True))
    print(json.dumps({"durum": rapor["durum"], "rapor": rapor.get("rapor"), "pano": rapor.get("pano"),
                      "ozet": rapor["ozet"], "duzeltme_onerisi": rapor["duzeltme_onerisi"]}, ensure_ascii=False, indent=2))
    return 0 if rapor["durum"] == "GEÇTİ" else 2


if __name__ == "__main__":
    raise SystemExit(main())
