from pathlib import Path

from coo.renk_paleti import delta_e, en_yakin, erp_eslesmesi, palet_oku, palete_ekle

ERP = [{"id": 9, "brand": "Sunlu", "material_type": "Mat PLA", "color_name": "Kemik", "color_hex": "#1F2937"}]


def test_delta_e():
    assert delta_e("#FFFFFF", "#FFFFFF") == 0
    assert delta_e("#E2DDC7", "#1F2937") > 50


def test_erp_eslesmesi_marka_ve_ad():
    assert erp_eslesmesi({"ad": "Kemik Rengi", "marka": "SUNLU"}, ERP)["id"] == 9
    assert erp_eslesmesi({"ad": "Kemik", "marka": "eSUN"}, ERP) is None


def test_palete_ekle_gunceller(tmp_path: Path):
    dosya = tmp_path / "p.yaml"
    palete_ekle({"ad": "Kemik", "hex": "#e2ddc7", "marka": "Sunlu", "erp_filament_id": 9}, "test", dosya)
    k = palete_ekle({"ad": "Kemik", "hex": "#E0DBC5", "marka": "Sunlu", "erp_filament_id": 9}, "test2", dosya)
    assert len(palet_oku(dosya)) == 1 and k["hex"] == "#E0DBC5" and k["eski_hex"] == "#E2DDC7" and k["dogrulandi"]
    yakin, de = en_yakin("#E1DCC6", dosya)
    assert yakin["ad"] == "Kemik" and de < 2
