from pathlib import Path

from coo import studio_hatti as sh


def test_istem_mcp_ile_uretir_ve_sonucu_yazdirir(tmp_path: Path) -> None:
    i = sh.istem("kaligraf_letters", "3B harfler", "'Berber' 200 mm siyah", tmp_path, [tmp_path / "logo.png"])
    assert "mcp__workbench-studio__" in i and "maker_generator_params" in i and "`make`" in i
    assert str(tmp_path / "sonuc.json") in i and "harfi harfine" in i and "baskı başlatma" in i
    assert "logo.png" in i
    r = sh.istem("maker_keychain", "Anahtarlık", "kırmızı yap", tmp_path, onceki={"job_dir": "/x/job", "talep": "Elif"})
    assert "REVİZE" in r and "/x/job" in r


def test_is_kaydi(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sh, "IS_KLASORU", tmp_path)
    iid, k = sh.yeni_is("maker_keychain")
    sh.is_guncelle(iid, talep="Elif")
    assert sh.is_bilgisi(iid)["pid"] == "maker_keychain" and sh.is_bilgisi(iid)["talep"] == "Elif"
    assert sh.sonuc_oku(k) is None
    (k / "sonuc.json").write_text('{"basarili": true, "job_dir": "/j"}')
    assert sh.sonuc_oku(k)["job_dir"] == "/j"
