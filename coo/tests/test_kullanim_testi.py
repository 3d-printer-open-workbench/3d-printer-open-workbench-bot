"""🧪 Kullanım testi motoru (coo/kullanim_testi.py): sentetik STL'lerle fizik + ölçü kuralları.

Ağır bağımlılıklar (.venv-cad: mujoco, coacd, python-fcl, shapely) yoksa atlanır.
"""
from __future__ import annotations

import copy
import math
import os
from pathlib import Path

import pytest
import yaml

os.environ.setdefault("MUJOCO_GL", "egl")  # mujoco ilk içe aktarılmadan önce (başsız GPU render)
pytest.importorskip("mujoco")
pytest.importorskip("coacd")
pytest.importorskip("fcl")
trimesh = pytest.importorskip("trimesh")

from coo import kullanim_testi as kt  # noqa: E402

GERCEK_KONFIG = kt.KT_KONFIG


def _birlesim(parcalar) -> "trimesh.Trimesh":
    m = trimesh.boolean.union(parcalar, engine="manifold")
    m.apply_translation([0, 0, -m.bounds[0][2]])
    return m


def _kutu(boyut, merkez, donme=None):
    b = trimesh.creation.box(extents=boyut)
    if donme is not None:
        b.apply_transform(donme)
    b.apply_translation(merkez)
    return b


def _konfig(tmp: Path, nesne_suz=None, sablon_ezme=None, fizik_ezme=None) -> Path:
    """Gerçek şablon/nesne kütüphanesinden hızlandırılmış kopya (az senaryo, az açı)."""
    k = tmp / "konfig"
    k.mkdir(exist_ok=True)
    nes = yaml.safe_load((GERCEK_KONFIG / "nesneler.yaml").read_text(encoding="utf-8"))
    if nesne_suz:
        nesne_suz(nes)
    sab = yaml.safe_load((GERCEK_KONFIG / "sablonlar.yaml").read_text(encoding="utf-8"))
    sab["fizik"].update({"egme_acilari_derece": [5], "oturma_suresi_s": 1.5, "egme_suresi_s": 1.0,
                         "sarsma": {"genlik_m_s2": 1.0, "frekans_hz": 3.0, "sure_s": 1.0}, **(fizik_ezme or {})})
    for ad, ez in (sablon_ezme or {}).items():
        sab["sablonlar"][ad] = kt.derin_birlestir(sab["sablonlar"][ad], ez)
    (k / "nesneler.yaml").write_text(yaml.safe_dump(nes, allow_unicode=True), encoding="utf-8")
    (k / "sablonlar.yaml").write_text(yaml.safe_dump(sab, allow_unicode=True), encoding="utf-8")
    return k


def _calistir(tmp: Path, mesh, urun: dict, konfig: Path) -> dict:
    stl = tmp / "model" / "stand.stl"
    stl.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(stl)
    return kt.kullanim_testi(stl, urun, cikti=None, gorsel=False, konfig=konfig)


def _kural(rapor: dict, ad: str) -> list[dict]:
    return [k for k in rapor["kurallar"] if k["kural"] == ad]


# ------------------------------------------------------------------------------------------------ saf işlevler
def test_sablon_tahmini_ve_urun_ezmesi() -> None:
    assert kt.sablon_tahmin({"ad": "Ayı Figürlü Kulaklık Standı"}) == "kulaklik_standi"
    assert kt.sablon_tahmin({"ad": "Kemer Formlu Kontrolcü Standı"}) == "kontrolcu_standi"
    assert kt.sablon_tahmin({"ad": "Samuray telefon standı"}) == "telefon_standi"
    assert kt.sablon_tahmin({"ad": "Vazo"}) is None
    t = kt.test_tanimi({"ad": "x", "kullanim_testi": {"sablon": "telefon_standi", "yonler": ["dik", "yatay"],
                                                       "kurallar": {"gorus_acisi_derece": {"min": 50}}}})
    assert t["yonler"] == ["dik", "yatay"]
    assert t["kurallar"]["gorus_acisi_derece"] == {"min": 50, "max": 75}  # derin birleştirme: max şablondan
    assert t["fizik"]["pla_yogunluk_g_cm3"] == 1.24
    with pytest.raises(ValueError):
        kt.test_tanimi({"ad": "Vazo"})


def test_nesne_kutuphanesi_kaynakli_ve_olcuye_sadik() -> None:
    kut = kt.nesne_kutuphanesi()
    for kimlik, t in kut["nesneler"].items():
        if t["tip"] == "kulaklik":
            for v in t["varyantlar"].values():
                assert v.get("kaynak") and (v.get("dogrulanmadi") or v["kaynak"].get("url"))
        else:
            assert t["kaynak"]["url"].startswith("https://") and t["kaynak"]["tarih"], kimlik
    for kimlik in ("dualsense", "xbox_series"):
        n = kt.nesne_olustur(kimlik)
        lo, hi = n.zarf()
        o = kut["nesneler"][kimlik]["olcu"]
        assert abs((hi - lo)[0] - o["genislik"]) < 1 and abs((hi - lo)[1] - o["derinlik"]) < 1
        assert abs((hi - lo)[2] - o["kalinlik"]) < 1.5
        assert {p.rol for p in n.parcalar} >= {"tetik", "cubuk", "tutamak"}
        assert abs(sum(p.kutle_g for p in n.parcalar) - n.kutle_g) < 1e-6
    tel = kt.nesne_olustur("iphone_17_pro_max", kilif=True)
    assert tel.bilgi["olcu"] == {"genislik": 81.0, "yukseklik": 166.4, "kalinlik": 11.25}
    assert tel.kutle_g == 233 + 40
    kul = kt.nesne_olustur("kulaklik", "airpods_max")
    lo, _ = kul.zarf()
    assert abs(lo[2] + 177) < 0.5 and kul.kutle_g == 386.2


def test_devrilme_acisi_kare_taban() -> None:
    from shapely.geometry import box

    import numpy as np

    d = kt.devrilme_acilari(box(-50, -50, 50, 50), np.array([0.0, 0.0, 100.0]))
    assert d["yonler"]["ön (−y)"] == pytest.approx(math.degrees(math.atan2(50, 100)), abs=0.1)
    assert d["min_derece"] == pytest.approx(26.6, abs=0.2)
    d2 = kt.devrilme_acilari(box(-50, -50, 50, 50), np.array([0.0, 40.0, 100.0]))
    assert d2["en_zayif_yon"] == "arka (+y)" and d2["min_derece"] < 6
    assert kt.devrilme_acilari(box(-50, -50, 50, 50), np.array([80.0, 0, 50]))["min_derece"] == 0.0


# ------------------------------------------------------------------------------------------------ kulaklık
def _kulaklik_standi(yukseklik: float):
    taban = trimesh.creation.cylinder(radius=60, height=12)
    taban.apply_translation([0, 0, 6])
    direk = trimesh.creation.cylinder(radius=12, height=yukseklik)
    direk.apply_translation([0, 0, yukseklik / 2 + 6])
    sele = _kutu([110, 34, 10], [0, 0, yukseklik + 10])
    return _birlesim([taban, direk, sele])


def _tek_kulaklik(nes: dict) -> None:
    nes["nesneler"]["kulaklik"]["varyantlar"] = {"airpods_max": nes["nesneler"]["kulaklik"]["varyantlar"]["airpods_max"]}


def test_kisa_kulaklik_standi_kaldi_uzun_gecti(tmp_path: Path) -> None:
    urun = {"sku": "x", "ad": "Kulaklık standı", "kullanim_testi": {"sablon": "kulaklik_standi"}}
    konfig = _konfig(tmp_path, nesne_suz=_tek_kulaklik)
    kisa = _calistir(tmp_path / "kisa", _kulaklik_standi(110), urun, konfig)
    assert kisa["durum"] == "KALDI"
    kupa = _kural(kisa, "kupa_masa_mesafesi_mm")
    assert kupa and kupa[0]["durum"] == "KALDI" and kupa[0]["deger"] < 10
    assert any("tepe noktasını" in o and "mm yükselt" in o for o in kisa["duzeltme_onerisi"])

    uzun = _calistir(tmp_path / "uzun", _kulaklik_standi(230), urun, konfig)
    kupa = _kural(uzun, "kupa_masa_mesafesi_mm")
    assert kupa[0]["durum"] == "GEÇTİ" and kupa[0]["deger"] > 30
    assert _kural(uzun, "yerlesme")[0]["durum"] == "GEÇTİ"
    assert _kural(uzun, "bant_temasi")[0]["durum"] == "GEÇTİ"
    assert uzun["stand"]["kutle_kaynagi"].startswith("geometri tahmini")
    assert "surtunme" in uzun["varsayimlar"] and uzun["varsayimlar"]["surtunme"]["pla"] == 0.3


# ------------------------------------------------------------------------------------------------ kontrolcü
def _kollar(nes: dict) -> None:
    nes["nesneler"] = {"dualsense": nes["nesneler"]["dualsense"]}


def test_genis_tepsi_kolu_tutar_dudaksiz_rampa_tutamaz(tmp_path: Path) -> None:
    urun = {"sku": "x", "ad": "Kontrolcü standı", "kullanim_testi": {"sablon": "kontrolcu_standi"}}
    ez = {"kontrolcu_standi": {"nesneler": ["dualsense"], "yerlesim": {"egimler_derece": [0], "adim_mm": 10}}}
    konfig = _konfig(tmp_path, nesne_suz=_kollar, sablon_ezme=ez)
    dis = _kutu([200, 150, 30], [0, 0, 15])
    oyuk = _kutu([180, 128, 30], [0, 0, 8 + 15])
    tepsi = trimesh.boolean.difference([dis, oyuk], engine="manifold")
    iyi = _calistir(tmp_path / "iyi", tepsi, urun, konfig)
    assert _kural(iyi, "yerlesme")[0]["durum"] == "GEÇTİ"
    assert _kural(iyi, "yasak_temas")[0]["durum"] == "GEÇTİ"  # tetik/çubuk yukarıda, standa değmiyor
    assert _kural(iyi, "egme")[0]["durum"] == "GEÇTİ"

    # dudaksız 35° rampa: kayma açısı atan(0.45) ≈ 24° < 35° → kol kayıp masaya düşer
    R = trimesh.transformations.rotation_matrix(math.radians(35), [1, 0, 0])
    rampa = _birlesim([_kutu([120, 90, 6], [0, 0, 3]), _kutu([120, 110, 8], [0, 0, 35], R)])
    kotu = _calistir(tmp_path / "kotu", rampa, urun, konfig)
    assert kotu["durum"] == "KALDI"
    # ya hiç oturmaz ya da rampa tepesinde dengede kalır ama 5° eğmede kayıp düşer
    kalan = {k["kural"] for k in kotu["kurallar"] if k["durum"] == "KALDI"}
    assert kalan & {"yerlesme", "egme"}
    assert any("yuvada kalmadı" in o or "yuvada tutunmuyor" in o for o in kotu["duzeltme_onerisi"])


# ------------------------------------------------------------------------------------------------ telefon
def _telefonlar(nes: dict) -> None:
    nes["nesneler"] = {"iphone_16": nes["nesneler"]["iphone_16"]}
    nes["kilif"] = nes["kilif"]


def _telefon_standi(dayanak_derece: float = 65.0):
    taban = _kutu([90, 110, 6], [0, 0, 3])
    dudak = _kutu([90, 6, 14], [0, -40, 7])
    a = math.radians(90 - dayanak_derece)  # dikeyden arkaya yatma
    R = trimesh.transformations.rotation_matrix(-a, [1, 0, 0])
    dayanak = _kutu([90, 6, 110], [0, -18 + 55 * math.sin(a), 55 * math.cos(a) + 2], R)
    return _birlesim([taban, dudak, dayanak])


def test_telefon_standi_aci_olcer_ve_kablo_boslugu_yoksa_kaldi(tmp_path: Path) -> None:
    urun = {"sku": "x", "ad": "Telefon standı", "kullanim_testi": {"sablon": "telefon_standi"}}
    ez = {"telefon_standi": {"nesneler": ["iphone_16"], "kilif": [False],
                             "yerlesim": {"egimler_derece": [65], "adim_mm": 6}}}
    konfig = _konfig(tmp_path, nesne_suz=_telefonlar, sablon_ezme=ez)
    r = _calistir(tmp_path / "t", _telefon_standi(), urun, konfig)
    assert _kural(r, "yerlesme")[0]["durum"] == "GEÇTİ"
    aci = _kural(r, "gorus_acisi_derece")[0]
    assert 50 <= aci["deger"] <= 80
    kablo = _kural(r, "kablo_boslugu")[0]
    assert kablo["durum"] == "KALDI"  # dolu dudak + taban: fiş telefonun altından çıkamaz
    assert any("şarj fişi" in o and "kanal" in o for o in r["duzeltme_onerisi"])
    sen = r["senaryolar"][0]
    assert sen["testler"]["dokunma"]["kuvvet_n"] == 3.0
    assert {"birakma", "egme", "sarsma", "dokunma"} <= set(sen["testler"])


def test_dokunma_moment_dengesi() -> None:
    s = {"etiket": "t", "kutle_g": 200.0,
         "olcumler": {"gorus_acisi_derece": 90.0, "birlesik_com_mm": [0, 0, 50],
                      "devrilme": {"mesafe_mm": {"arka (+y)": 20.0}}},
         "testler": {"dokunma": {"nokta_mm": [0, 0, 100]}}}
    g = kt.dokunma_arka_kenar(s, 100.0, 3.0, pay=1.0)
    # dik ekran: y_r = F·z / (M·g) = 3·100 / (0.3·9.81) ≈ 101.9 mm
    assert g["gereken_y_mm"] == pytest.approx(3 * 100 / (0.3 * 9.81), rel=1e-3)
    assert g["uzatma_mm"] == pytest.approx(g["gereken_y_mm"] - 20 + 2, rel=1e-6)


def test_cikti_dosyalari_ve_pano(tmp_path: Path) -> None:
    urun = {"sku": "x", "ad": "Kulaklık standı", "kullanim_testi": {"sablon": "kulaklik_standi"}}
    konfig = _konfig(tmp_path, nesne_suz=_tek_kulaklik)
    stl = tmp_path / "model" / "x.stl"
    stl.parent.mkdir(parents=True)
    _kulaklik_standi(230).export(stl)
    cikti = tmp_path / "model" / "kullanim_testi" / "t1"
    r = kt.kullanim_testi(stl, urun, cikti=cikti, gorsel=True, konfig=konfig)
    assert (cikti / "rapor.json").exists() and (cikti / "pano.png").exists() and (cikti / "birakma.gif").exists()
    import json

    j = json.loads((cikti / "rapor.json").read_text(encoding="utf-8"))
    assert j["durum"] == r["durum"] and j["varsayimlar"]["kutle"] and j["kurallar"]
    from PIL import Image

    assert Image.open(cikti / "pano.png").size[0] > 1000
    assert copy.deepcopy(j)  # JSON'a dönüşebilir
