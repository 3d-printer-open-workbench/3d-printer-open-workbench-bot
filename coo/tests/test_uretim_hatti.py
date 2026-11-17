from pathlib import Path

from coo.uretim_hatti import (baski_oncesi_kontrol, engel_var, fire_grami, kritik_katmanlar, renk_farki,
                              riskli_z_listesi, tarti_cozumle, tarti_ozeti)
from coo.yazici import gcode_basligindan_oku

URUN = {"dilimleme": {"gercek_gram": 262.6, "renk_hex": "#E8DFD1", "filament": "Elegoo PLA Matte @ECC",
                      "katman_mm": 0.16, "riskli_z_mm": [40.3], "destek_gerekli": True, "destek_nedeni": "1 parça"}}
KREM = {"brand": "Elegoo", "material_type": "Mat PLA", "color_name": "Krem", "color_hex": "#EDE3D3",
        "remaining_weight_gr": 800}


def test_kontrol_temiz():
    k = baski_oncesi_kontrol(URUN, KREM, tabla_bos=True)
    assert not engel_var(k) and all(m["durum"] == "ok" for m in k)


def test_kontrol_engeller():
    az = dict(KREM, remaining_weight_gr=200, color_hex="#C2603E", material_type="PETG")
    k = baski_oncesi_kontrol(URUN, az, tabla_bos=False, yazici_durum="BASKIDA")
    adlar = {m["ad"]: m["durum"] for m in k}
    assert adlar["Tabla"] == adlar["Stok"] == adlar["Malzeme"] == adlar["Yazıcı"] == "engel"
    assert adlar["Renk"] == "uyari"
    assert baski_oncesi_kontrol(URUN, None, True)[1]["durum"] == "uyari"


def test_renk_farki():
    assert renk_farki("#E8DFD1", "#EDE3D3") < 60 < renk_farki("#E8DFD1", "#C2603E")


def test_kritik_katmanlar():
    plan = kritik_katmanlar(URUN, toplam_katman=860)
    katlar = [n for n, _ in plan]
    assert katlar[0] == 2
    assert round(40.3 / 0.16) + 4 in katlar
    assert 430 in katlar  # yarı yol


def test_riskli_z_listesi():
    a = {"ada": [{"z_mm": 19.9}, {"z_mm": 30.7}, {"z_mm": 31.7}], "sarkma_en_buyuk": [[107.1, 56.7], [5.0, 3.0]]}
    assert riskli_z_listesi(a) == [19.9, 30.7, 107.1]


def test_fire_ve_tarti():
    assert fire_grami(262.6, 40) == 105.0
    assert fire_grami(10, 0) == 1.0
    assert tarti_cozumle("268,4 g") == 268.4 and tarti_cozumle("abc") is None
    assert "%+2.2" in tarti_ozeti(268.4, 262.6)


def test_orca_gcode_kuyrugundan_okur(tmp_path: Path):
    g = tmp_path / "a.gcode"
    g.write_text("; HEADER\n" + "G1 X1\n" * 3000 + "; filament used [g] = 262.60\n"
                 "; estimated printing time (normal mode) = 8h 47m 59s\n")
    assert gcode_basligindan_oku(g) == (262.6, 528)
