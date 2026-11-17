import shutil
from pathlib import Path

import yaml

import coo.baski_rapor as br
from coo.orca_dilim import KATEGORI_DOSYASI, kategori_guncelle, kategoriler


def test_kare_secki():
    k = [Path(f"k{i}") for i in range(100)]
    s = br.kare_secki(k, 10)
    assert len(s) == 10 and s[0] == k[0] and s[-1] == k[-1]
    assert br.kare_secki(k[:4], 10) == k[:4]


def test_bakim_durumu_ve_yapildi(tmp_path):
    d = tmp_path / "bakim.yaml"
    shutil.copy(br.BAKIM_DOSYASI, d)
    durum = {b["anahtar"]: b for b in br.bakim_durumu(20, d)}
    assert durum["tabla_temizlik"]["durum"] == "GECIKTI"          # 15 sa aralık, hiç kayıt yok, 20 sa
    assert durum["yaglama"]["durum"] == "KAYIT_YOK"
    br.bakim_yapildi("tabla_temizlik", 20, d)
    durum = {b["anahtar"]: b for b in br.bakim_durumu(33, d)}
    assert durum["tabla_temizlik"]["durum"] == "YAKLASTI" and durum["tabla_temizlik"]["kalan"] == 2
    assert d.read_text(encoding="utf-8").startswith("#")            # yorumlar korunur
    assert "Bakım durumu" in br.bakim_metni(br.bakim_durumu(33, d), 33)


def test_onerileri_suz():
    rapor = {"dilimleme_onerileri": [
        {"ayar": "brim_type", "onerilen": "outer_only", "gerekce": "köşe kalkması", "guven": 0.8},
        {"ayar": "nozzle_temperature", "onerilen": "220", "gerekce": "x", "guven": 0.9},   # izinsiz
        {"ayar": "wall_loops", "onerilen": "3", "gerekce": "zaten 3", "guven": 0.9},       # değişiklik yok
        {"ayar": "layer_height", "onerilen": "0.5", "gerekce": "aralık dışı", "guven": 0.9},
        {"ayar": "seam_position", "onerilen": "back", "gerekce": "emin değil", "guven": 0.3}]}
    o = br.onerileri_suz(rapor, {"wall_loops": "3", "brim_type": "no_brim", "seam_position": "aligned"})
    assert [x["ayar"] for x in o] == ["brim_type"] and o[0]["mevcut"] == "no_brim"
    m = br.rapor_metni({"genel": "KUSURLU", "ozet": "köşe *kalkmış*", "gozlemler": ["sol köşe kalkık"],
                        "bakim_onerileri": [{"is": "Tablayı IPA ile sil", "neden": "yağ izi", "aciliyet": "simdi"}]},
                       o, "figur")
    assert "brim_type" in m and "🔴 şimdi" in m and "*kalkmış*" not in m


def test_kategori_guncelle(tmp_path):
    d = tmp_path / "k.yaml"
    shutil.copy(KATEGORI_DOSYASI, d)
    s = kategori_guncelle("figur", {"brim_type": "outer_only"}, d, profil_yaz=False, not_="test")
    assert s["yeni"] == {"brim_type": "outer_only"} and s["onceki"] == {"brim_type": None}
    k = kategoriler(d)["figur"]
    assert k["ayarlar"]["brim_type"] == "outer_only" and k["ayarlar"]["layer_height"] == "0.16"
    assert k["degisiklikler"][-1]["not"] == "test"
    assert d.read_text(encoding="utf-8").startswith("#")
    assert yaml.safe_load(d.read_text(encoding="utf-8"))["kategoriler"]["harf"]


def test_bekleyen_oneriler(tmp_path):
    import json
    yaz = lambda ad, v: (tmp_path / f"{ad}.json").write_text(json.dumps(v), encoding="utf-8")  # noqa: E731
    yaz("20261101-100000", {"kategori": "figur", "ertelendi": "x", "oneriler": [{"ayar": "brim_type", "onerilen": "outer_only"}]})
    yaz("20261102-100000", {"kategori": "figur", "uygulandi": {"yeni": {}}, "oneriler": [{"ayar": "a", "onerilen": "1"}]})
    yaz("20261103-100000", {"kategori": "harf", "oneriler": []})
    b = br.bekleyen_oneriler(klasor=tmp_path)
    assert [x["rid"] for x in b] == ["20261101-100000"] and b[0]["ertelendi"] == "x"
    # ertelenen öneri sonraki raporda yeniden önerilebilir (filtrelenmez)
    o = br.onerileri_suz({"dilimleme_onerileri": [{"ayar": "brim_type", "onerilen": "outer_only", "gerekce": "g",
                                                   "guven": 0.9}]}, {})
    assert [x["ayar"] for x in o] == ["brim_type"]
