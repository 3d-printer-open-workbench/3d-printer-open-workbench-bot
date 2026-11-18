import json
import os
import time
from pathlib import Path

import yaml

from coo import klasor_temizlik as kt

ESKI = time.time() - 3 * 86400  # tarama yalnız MIN_YAS_SN'den eski dosyalara bakar


def _dosya(yol: Path, icerik: bytes = b"x" * 10, eski: bool = True) -> Path:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_bytes(icerik)
    if eski:
        os.utime(yol, (ESKI, ESKI))
    return yol


def _urun(kok: Path, sku: str, **alanlar) -> Path:
    d = kok / sku
    d.mkdir(parents=True, exist_ok=True)
    (d / "urun.yaml").write_text(yaml.safe_dump({"sku": sku, "ad": sku, **alanlar}, allow_unicode=True), encoding="utf-8")
    return d


def _rel(adaylar, kok: Path) -> set[str]:
    return {a["yol"].relative_to(kok).as_posix() for a in adaylar}


def _sahte_urun(kok: Path, sku: str, durum: str) -> Path:
    """Gerçek ürün klasörü yapısı (tipik bir ürün klasörü düzeni)."""
    d = _urun(kok, sku, durum=durum, ai3d={"konsept": "konsept/flow-2.jpg"},
              teknik_poster={"foto": "model/cok_renk/render/studyo-ic/krem-fon.png"},
              sanal_test={"pano": "model/sanal_test/v2/pano.png", "onceki": "v1 RED — model/v1_kisa_RED.stl"})
    for rel in ("model/{s}.stl", "uretim/{s}.3mf", "uretim/{s}.gcode", "uretim/{s}-tabla.png",
                "model/ai3d/ham.stl", "model/ai3d/ham.glb", "model/ai3d/gorusler/on.png",
                "model/cok_renk/renkli.3mf", "model/cok_renk/renkli.stl", "model/cok_renk/parcala.stl",
                "model/cok_renk/etiket.npz", "model/cok_renk/sema_son.json", "model/cok_renk/parca_kareler/on.png",
                "model/cok_renk/render/studyo-ic/kapak-beyaz.png", "model/cok_renk/render/studyo-ic/krem-fon.png",
                "model/sanal_test/v2/pano.png", "model/sanal_test/v2/test_H185.png", "model/v1_kisa_RED.stl",
                "model/v2_RED.stl", "model/tasarim.blend",
                "gorsel/beyaz.png", "gorsel/kullanim-q-1.png", "gorsel/numune-1.jpg",
                "gorsel/sahne/qwen-tmp/render-kapak-beyaz-7.png", "gorsel/sahne/qwen-tmp/girdi-render-krem-fon.png",
                "gorsel/sahne/eski/kullanim-q-1-onceki.png", "gorsel/konsept/teknik-poster-3x4.png",
                "gorsel/konsept/eski/teknik-poster-3x4-gri.png",
                "konsept/flow-1.jpg", "konsept/flow-2.jpg", "konsept/flow-3.jpg", "konsept/referans/ref-1.jpg",
                "konsept/kartela.png",
                "medya/reels-son.mp4", "medya/flow-q-1-red.mp4", "medya/konsept-teknik-poster-reels-red2.mp4",
                "medya/hf-reels-20261118-0047.mp4", "medya/pinterest/pin.json",
                "magaza/paket.json", "magaza/gorseller/x-01.jpg", "pazar/fiyat.json"):
        _dosya(d / rel.format(s=sku))
    (d / "magaza" / "gorseller.json").write_text(json.dumps(
        {"gorseller": [{"dosya": "magaza/gorseller/x-01.jpg", "kaynak": "gorsel/sahne/qwen-tmp/girdi-render-krem-fon.png"}]}),
        encoding="utf-8")
    return d


def test_aktif_urunde_yalniz_red_gorseller_ve_secilmeyen_konseptler(tmp_path: Path) -> None:
    d = _sahte_urun(tmp_path, "ayi", "TASARIM")
    adaylar = kt.urun_adaylari(d, reels_klasoru=tmp_path / "yok")
    assert {a["kat"] for a in adaylar} == {"gorsel"}
    assert _rel(adaylar, d) == {
        "gorsel/sahne/qwen-tmp/render-kapak-beyaz-7.png",
        "gorsel/sahne/eski/kullanim-q-1-onceki.png",
        "gorsel/konsept/eski/teknik-poster-3x4-gri.png",
        "medya/flow-q-1-red.mp4",
        "medya/konsept-teknik-poster-reels-red2.mp4",
        "konsept/flow-1.jpg",
        "konsept/flow-3.jpg",
    }  # girdi-render-krem-fon.png gorseller.json'da kaynak → korunur; flow-2 seçili → korunur


def test_arsivlenen_urunde_ara_dosyalar_ama_korunanlar_kalir(tmp_path: Path) -> None:
    d = _sahte_urun(tmp_path, "ayi", "IPTAL")
    rel = _rel(kt.urun_adaylari(d, reels_klasoru=tmp_path / "yok"), d)
    for silinir in ("model/ai3d/ham.stl", "model/ai3d/ham.glb", "model/ai3d/gorusler/on.png",
                    "model/cok_renk/renkli.stl", "model/cok_renk/parcala.stl", "model/cok_renk/etiket.npz",
                    "model/cok_renk/parca_kareler/on.png", "model/sanal_test/v2/test_H185.png", "model/v2_RED.stl",
                    "model/tasarim.blend", "konsept/kartela.png", "gorsel/sahne/qwen-tmp/render-kapak-beyaz-7.png"):
        assert silinir in rel, silinir
    for korunur in ("urun.yaml", "model/ayi.stl", "uretim/ayi.3mf", "uretim/ayi.gcode", "uretim/ayi-tabla.png",
                    "model/cok_renk/renkli.3mf", "model/cok_renk/sema_son.json",
                    "model/cok_renk/render/studyo-ic/kapak-beyaz.png", "model/cok_renk/render/studyo-ic/krem-fon.png",
                    "model/sanal_test/v2/pano.png",  # urun.yaml'da geçiyor
                    "model/v1_kisa_RED.stl",  # urun.yaml notunda geçiyor → emin değiliz, silinmez
                    "gorsel/beyaz.png", "gorsel/kullanim-q-1.png", "gorsel/numune-1.jpg",
                    "gorsel/konsept/teknik-poster-3x4.png", "konsept/flow-2.jpg", "konsept/referans/ref-1.jpg",
                    "medya/reels-son.mp4", "medya/hf-reels-20261118-0047.mp4", "medya/pinterest/pin.json",
                    "magaza/paket.json", "magaza/gorseller/x-01.jpg", "magaza/gorseller.json", "pazar/fiyat.json",
                    "gorsel/sahne/qwen-tmp/girdi-render-krem-fon.png"):
        assert korunur not in rel, korunur


def test_konsept_secimi_yoksa_konseptlere_dokunulmaz(tmp_path: Path) -> None:
    d = _urun(tmp_path, "yeni", durum="KONSEPT_SECIMI")
    for n in (1, 2):
        _dosya(d / "konsept" / f"flow-{n}.jpg")
    assert kt.urun_adaylari(d, reels_klasoru=tmp_path / "yok") == []
    # seçim kayıtlı ama STL yoksa da dokunulmaz
    d2 = _urun(tmp_path, "yarim", ai3d={"konsept": "konsept/flow-1.jpg"})
    for n in (1, 2):
        _dosya(d2 / "konsept" / f"flow-{n}.jpg")
    assert kt.urun_adaylari(d2, reels_klasoru=tmp_path / "yok") == []


def test_yeni_dosyalar_ve_dizin_notlari_korunur(tmp_path: Path) -> None:
    d = _urun(tmp_path, "x", teknik_poster={"not": "eski gri poster gorsel/konsept/eski/ içinde"})
    _dosya(d / "gorsel" / "konsept" / "eski" / "p.png")
    _dosya(d / "gorsel" / "sahne" / "qwen-tmp" / "yeni.png", eski=False)  # çalışan Qwen işi olabilir
    assert kt.urun_adaylari(d, reels_klasoru=tmp_path / "yok") == []


def test_reels_denetim_videosu_korunur(tmp_path: Path) -> None:
    d = _urun(tmp_path, "x")
    v = _dosya(d / "medya" / "a-red.mp4")
    reels = tmp_path / "reels"
    reels.mkdir()
    (reels / "k1.json").write_text(json.dumps({"kid": "k1", "video": str(v), "kaynak": {"sku": "x"}}), encoding="utf-8")
    assert kt.urun_adaylari(d, reels_klasoru=reels) == []
    assert len(kt.urun_adaylari(d, reels_klasoru=tmp_path / "yok")) == 1


def test_video_atolyesi_yalniz_kopyasi_olan_render_ve_npm(tmp_path: Path) -> None:
    atolye, veri = tmp_path / "Video_Atölyesi", tmp_path / "veri"
    _dosya(atolye / "p1" / "renders" / "a.mp4", b"AAAA")        # ürüne kopyalanmış
    _dosya(atolye / "p1" / "renders" / "b.mp4", b"BBBB")        # kopyası yok → korunur
    _dosya(atolye / "p1" / "renders" / "c.mp4", b"CCCC")        # aynı boyut, farklı içerik → korunur
    _dosya(atolye / "p1" / "compositions" / "s.html", b"<h1>")
    _dosya(veri / "02_Urunler" / "u" / "medya" / "hf-reels-1.mp4", b"AAAA")
    _dosya(veri / "02_Urunler" / "u" / "medya" / "hf-reels-2.mp4", b"CCCD")
    _dosya(veri / "99_Cop" / "x" / "b.mp4", b"BBBB")             # çöpteki kopya sayılmaz
    _dosya(atolye / "node_modules" / "hyperframes" / "i.js")
    (atolye / "package.json").write_text("{}")
    _dosya(atolye / "p1" / ".hyperframes" / "c.bin")
    adaylar = kt.video_adaylari(atolye, veri)
    rel = {(a["kat"], a["yol"].relative_to(atolye).as_posix()) for a in adaylar}
    assert rel == {("video", "p1/renders/a.mp4"), ("npm", "node_modules"), ("npm", "p1/.hyperframes")}


def test_tara_mesgul_urun_ve_video_atlanir(tmp_path: Path) -> None:
    urunler = tmp_path / "urunler"
    _sahte_urun(urunler, "ayi", "TASARIM")
    _sahte_urun(urunler, "_sablon", "KONSEPT")
    atolye = tmp_path / "atolye"
    _dosya(atolye / "node_modules" / "a.js")
    (atolye / "package.json").write_text("{}")
    t = kt.tara(urunler, atolye, tmp_path / "veri", reels_klasoru=tmp_path / "yok")
    assert set(t) == set(kt.KATEGORILER) and len(t["gorsel"]) == 7 and len(t["npm"]) == 1
    assert all("_sablon" not in str(a["yol"]) for a in t["gorsel"])
    t2 = kt.tara(urunler, atolye, tmp_path / "veri", mesgul={"ayi"}, video_mesgul=True, reels_klasoru=tmp_path / "yok")
    assert not any(t2.values())
    ozet = kt.tarama_ozeti(t, {"gorsel"})
    assert "☑ *🖼️" in ozet and "henüz hiçbir şey silinmedi" in ozet
    assert "çöp kutusuna" in kt.onay_ozeti(t, {"gorsel"}, kok=tmp_path)


def test_temizle_cope_tasir_ve_korunanlara_dokunmaz(tmp_path: Path) -> None:
    urunler = tmp_path / "urunler"
    d = _sahte_urun(urunler, "ayi", "IPTAL")
    arg = {"urunler": urunler, "atolye": tmp_path / "yok", "veri": tmp_path / "veri", "reels_klasoru": tmp_path / "yok"}
    onceki = kt.tara(**arg)
    # onaydan sonra bir dosya korumaya girdi (urun.yaml'da anıldı) → silinmemeli
    v = yaml.safe_load((d / "urun.yaml").read_text())
    v["not"] = "model/ai3d/ham.glb tekrar lazım"
    (d / "urun.yaml").write_text(yaml.safe_dump(v, allow_unicode=True))
    cop = tmp_path / "cop"
    sonuc = kt.temizle({"arsiv"}, onceki, cop_klasoru=cop, gio=False, **arg)
    assert sonuc["yontem"] == "klasor" and not sonuc["hatalar"] and sonuc["bayt"] > 0
    assert (d / "model" / "ai3d" / "ham.glb").exists()
    assert not (d / "model" / "ai3d" / "ham.stl").exists()
    assert (d / "model" / "ayi.stl").exists() and (d / "urun.yaml").exists() and (d / "magaza" / "paket.json").exists()
    tasinan = list(cop.rglob("ham.stl"))
    assert len(tasinan) == 1  # çöpte duruyor, geri alınabilir
    # seçilmeyen kategoriye dokunulmadı
    assert kt.temizle(set(), kt.tara(**arg), cop_klasoru=cop, gio=False, **arg)["tasinan"] == []


def test_satistaki_urun_asla_silinemez(tmp_path: Path) -> None:
    _urun(tmp_path, "satista", durum="SATISTA")
    d = _urun(tmp_path, "yuklu", durum="PATRON_ONAYINDA")
    _dosya(d / "magaza" / "yukleme.json", b'{"durum": "YUKLENDI", "panel_linki": "https://x"}')
    _urun(tmp_path, "ikasli", ikas={"panel_linki": "https://x"})
    _urun(tmp_path, "onayli", icerik_onayi="ONAYLANDI")
    _urun(tmp_path, "taslak", durum="TASARIM", icerik_onayi="BEKLIYOR", erp={"product_id": 7})
    _urun(tmp_path, "arsiv", durum="IPTAL")
    (tmp_path / "_sablon").mkdir()
    assert {u["sku"] for u in kt.silinebilir_urunler(tmp_path)} == {"taslak", "arsiv"}
    for sku in ("satista", "yuklu", "ikasli", "onayli", "_sablon", "../x", "yok"):
        assert kt.silme_engeli(sku, tmp_path), sku
    # liste eskimiş olsa bile kod düzeyinde engel: satıştaki ürün seçilse de taşınmaz
    cop = tmp_path.parent / (tmp_path.name + "-cop")
    sonuc = kt.urun_sil(["satista", "yuklu", "taslak"], tmp_path, cop, gio=False)
    assert [p.name for p in sonuc["tasinan"]] == ["taslak"]
    assert {s for s, _ in sonuc["engellenen"]} == {"satista", "yuklu"}
    assert (tmp_path / "satista").is_dir() and (tmp_path / "yuklu").is_dir() and not (tmp_path / "taslak").exists()
    assert list(cop.rglob("urun.yaml"))


def test_silme_ozeti_erp_uyarisi() -> None:
    ozet = kt.silme_ozeti([{"sku": "a", "ad": "A", "durum": "TASARIM", "boyut": 3 << 20, "erp_id": 7},
                           {"sku": "b", "ad": "B", "durum": "IPTAL", "boyut": 10, "erp_id": None}])
    assert "çöp kutusuna" in ozet and "geri alınabilir" in ozet and "ERP kaydı SİLİNMEZ" in ozet and "#7" in ozet
    assert "3,0 MB" in ozet


def test_cope_tasi_gio_basarisizsa_klasore_tasir(tmp_path: Path, monkeypatch) -> None:
    import subprocess

    f = _dosya(tmp_path / "kok" / "a" / "b.png")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "hata"))
    sonuc = kt.cope_tasi([f], tmp_path / "cop", gio=True, kok=tmp_path / "kok")
    assert sonuc["yontem"] == "klasor" and not f.exists()
    assert list((tmp_path / "cop").rglob("a/b.png"))
