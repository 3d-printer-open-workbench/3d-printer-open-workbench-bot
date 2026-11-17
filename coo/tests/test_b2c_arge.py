"""Open Workbench B2C Ar-Ge vitrini, kalite kapısı ve COO entegrasyon testleri."""
from __future__ import annotations

from pathlib import Path

import trimesh
import yaml
from PIL import Image

from coo import __main__ as coo_main
from coo import b2c_arge
from coo.ayar import CALISMA_ALANI
from coo.kalite_kapisi import kalite_kontrol_et


def test_kalite_kapisi_kaba_kutu_reddeder_pahli_kabul_eder(tmp_path: Path) -> None:
    from build123d import Align, Box, export_stl, fillet

    kaba_stl = tmp_path / "kaba.stl"
    kaba = Box(70, 50, 30, align=(Align.CENTER, Align.CENTER, Align.MIN))
    export_stl(kaba, str(kaba_stl))

    sonuc_kaba = kalite_kontrol_et(kaba_stl, mod="b2c")
    assert sonuc_kaba["durum"] == "RED"
    assert any("kaba/ilkel kutu geometrisi" in h for h in sonuc_kaba["hatalar"])

    # B2B düz kalıpta kaba kutu uyarısız geçebilmeli (su geçirmez & Z=0)
    sonuc_b2b = kalite_kontrol_et(kaba_stl, mod="b2b")
    assert sonuc_b2b["durum"] == "PASS"

    pahli_stl = tmp_path / "pahli.stl"
    pahli = fillet(Box(70, 50, 30, align=(Align.CENTER, Align.CENTER, Align.MIN)).edges(), 3.0)
    export_stl(pahli, str(pahli_stl))

    sonuc_pahli = kalite_kontrol_et(pahli_stl, mod="b2c")
    assert sonuc_pahli["durum"] == "PASS"
    assert sonuc_pahli["manifold"] is True
    assert sonuc_pahli["normal_cesitliligi"] >= 14


def test_kalite_kapisi_acik_mesh_reddeder(tmp_path: Path) -> None:
    box = trimesh.creation.box([40, 40, 20])
    box.apply_translation([0, 0, 10])
    acik = trimesh.Trimesh(vertices=box.vertices, faces=box.faces[:-2], process=True)
    acik_stl = tmp_path / "acik.stl"
    acik.export(str(acik_stl))

    sonuc = kalite_kontrol_et(acik_stl, mod="b2c")
    assert sonuc["durum"] == "RED"
    assert any("manifold" in h for h in sonuc["hatalar"])


def test_b2c_paket_katalog_ve_iskele_kurulumu(tmp_path: Path, monkeypatch) -> None:
    oneriler_dir = tmp_path / "01_Konsept_ve_ArGe" / "B2C_Oneriler"
    arge_dir = tmp_path / "01_Konsept_ve_ArGe"
    urunler_dir = tmp_path / "02_Urunler"
    sablon_dir = urunler_dir / "_sablon"
    sablon_dir.mkdir(parents=True)
    (sablon_dir / "urun.yaml").write_text(
        "sku: 'sablon'\nad: 'Şablon'\nkategori: 'B2C_DEKOR'\ndurum: 'KONSEPT'\ndilimleme:\n  tahmini_gram: 0\nerp:\n  onerilen_satis_fiyati_tl: null\n",
        encoding="utf-8",
    )

    gorsel_dir = oneriler_dir / "gorseller"
    gorsel_dir.mkdir(parents=True)
    sahte_foto = gorsel_dir / "dalga-abajur.jpg"
    Image.new("RGB", (400, 300), "#C88A55").save(sahte_foto)

    monkeypatch.setattr(b2c_arge, "B2C_ONERILER_KLASORU", oneriler_dir)

    pid = "2026-11-15-cok-uzun-paket-kimligi-denemesi"
    kayit_yolu = b2c_arge.paket_kaydet(
        pid,
        {
            "baslik": "Test B2C Trend Paketi",
            "adaylar": [
                {
                    "sku": "dalga-abajur",
                    "ad": "Oluklu Spiral Masa Lambası",
                    "kategori": "B2C_AYDINLATMA",
                    "ozet": "Sıcak ışık süzen dalgalı difüzör gövdeli masa lambası.",
                    "kaynak_url": "https://www.printables.com/model/12345",
                    "kaynak_platform": "Printables",
                    "rakip_fiyat": "850 - 1.250 TL",
                    "onerilen_satis_tl": 890,
                    "tahmini_gram": 110,
                    "tahmini_saat": 3.5,
                    "tahmini_kar_marji": "%58",
                    "lisans": "CC-BY 4.0",
                    "cad_rotasi": "Blender bpy",
                    "gorsel_yolu": str(sahte_foto),
                    "durum": "ONERILDI",
                }
            ],
        },
        kok=oneriler_dir,
    )
    assert kayit_yolu.exists()

    yuklenen = b2c_arge.paket_yukle(kok=oneriler_dir)
    assert yuklenen is not None
    temiz_pid = yuklenen["paket_id"]
    assert len(temiz_pid) <= 28

    butonlar = b2c_arge.aday_butonlari(temiz_pid, 0)
    for satir in butonlar:
        for btn in satir:
            assert len(btn["callback_data"].encode("utf-8")) <= 64

    katalog_yolu = b2c_arge.katalog_gorseli_olustur(yuklenen, calisma_alani=tmp_path)
    assert katalog_yolu.exists()
    with Image.open(katalog_yolu) as im:
        assert im.width >= 1000 and im.height >= 400

    aday, urun_dir, arge_md = b2c_arge.urun_iskelesi_kur(
        temiz_pid,
        0,
        ek_not="Taban pahını 3mm yap",
        kok_b2c=oneriler_dir,
        urunler_dizini=urunler_dir,
        arge_dizini=arge_dir,
    )
    assert aday["durum"] == "GELISTIRILIYOR"
    assert (urun_dir / "model").is_dir()
    assert arge_md.exists()

    manifest = yaml.safe_load((urun_dir / "urun.yaml").read_text(encoding="utf-8"))
    assert manifest["sku"] == "dalga-abajur"
    assert manifest["tasarim_araci"] == "blender"
    assert manifest["revize_notu"] == "Taban pahını 3mm yap"
    assert manifest["erp"]["onerilen_satis_fiyati_tl"] == 890.0


def test_metinden_gorselleri_bul_sinir_kontrolu(tmp_path: Path, monkeypatch) -> None:
    sahte_kok = tmp_path / "ws"
    (sahte_kok / "02_Urunler" / "test" / "gorsel").mkdir(parents=True)
    ici = sahte_kok / "02_Urunler" / "test" / "gorsel" / "studyo.png"
    ici.write_bytes(b"png")
    disi = tmp_path / "gizli.png"
    disi.write_bytes(b"secret")

    monkeypatch.setattr(coo_main, "CALISMA_ALANI", sahte_kok)
    sonuc = coo_main._metinden_gorselleri_bul(
        f"Hazır: 02_Urunler/test/gorsel/studyo.png ve dış: {disi} veya ../gizli.png",
    )
    assert sonuc == [ici.resolve()]
