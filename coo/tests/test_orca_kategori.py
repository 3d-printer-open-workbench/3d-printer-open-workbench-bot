import shutil
from pathlib import Path

import pytest

from coo.orca_dilim import KATEGORI_DOSYASI, ayar_dogrula, kategori_ekle, kategori_sec, kategoriler, workbench_prosesleri


@pytest.fixture
def kat_dosya(tmp_path: Path) -> Path:
    d = tmp_path / "kategoriler.yaml"
    shutil.copy(KATEGORI_DOSYASI, d)
    return d


def test_varsayilan_kategoriler_gecerli():
    k = kategoriler()
    for ad in ("figur", "cerceve", "harf", "standart"):
        assert ad in k
        ayar_dogrula(k[ad]["ayarlar"])  # dosyadaki her ayar izinli ve aralıkta
    p = workbench_prosesleri()
    assert p["Workbench Figur 0.16"]["seam_position"] == "back"
    assert "Workbench Standart 0.20 Utulu" in p  # ERP adları korunur


def test_ayar_dogrula_reddeder():
    with pytest.raises(ValueError):
        ayar_dogrula({"nozzle_temperature": "260"})  # izinsiz anahtar
    with pytest.raises(ValueError):
        ayar_dogrula({"layer_height": "0.5"})
    with pytest.raises(ValueError):
        ayar_dogrula({"seam_position": "front"})
    with pytest.raises(ValueError):
        ayar_dogrula({"wall_loops": "2.5"})
    assert ayar_dogrula({"sparse_infill_density": "30"}) == {"sparse_infill_density": "30%"}


def test_kategori_sec_onceligi(kat_dosya):
    assert kategori_sec({"baski_kategorisi": "harf"}, "x", kat_dosya) == ("harf", "urun.yaml baski_kategorisi")
    assert kategori_sec({"ad": "Ahşap görünümlü fotoğraf çerçevesi"}, "x", kat_dosya)[0] == "cerceve"
    assert kategori_sec({"ad": "Kaligraf isimlik"}, "x", kat_dosya)[0] == "harf"
    assert kategori_sec({"ai3d": {"konsept": "a"}}, "zz", kat_dosya)[0] == "figur"
    assert kategori_sec({}, "zz", kat_dosya)[0] == "standart"


def test_kategori_ekle(kat_dosya):
    k = kategori_ekle({"anahtar": "Lamba", "baslik": "Abajur / ışık geçiren", "aciklama": "ince tek duvar",
                       "anahtar_kelimeler": ["abajur", "lamba"],
                       "ayarlar": {"wall_loops": "1", "sparse_infill_density": "0%", "layer_height": "0.2"}},
                      kat_dosya, profil_yaz=False)
    assert k["anahtar"] == "lamba" and k["ekleyen"] == "YZ"
    yeniden = kategoriler(kat_dosya)
    assert yeniden["lamba"]["ayarlar"]["wall_loops"] == "1"
    assert "figur" in yeniden  # eskiler korunur
    assert kategori_sec({"ad": "Dalgalı abajur"}, "x", kat_dosya)[0] == "lamba"
    with pytest.raises(ValueError):
        kategori_ekle({"anahtar": "lamba", "ayarlar": {"wall_loops": "2"}}, kat_dosya, profil_yaz=False)
    with pytest.raises(ValueError):
        kategori_ekle({"anahtar": "kotu", "ayarlar": {"enable_support": "1"}}, kat_dosya, profil_yaz=False)
