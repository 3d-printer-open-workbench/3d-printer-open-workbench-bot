"""Patronun kayıtlı içerik notu (ör. 'PS5 ile kullanım') kullanım istemine her zaman girmeli (2026-11-17)."""
from __future__ import annotations

from pathlib import Path

from coo.icerik_hatti import kullanim_istemi


def test_kayitli_not_isteme_girer(tmp_path: Path) -> None:
    kok = tmp_path / "torii"
    (kok / "gorsel").mkdir(parents=True)
    (kok / "urun.yaml").write_text("sku: torii\nicerik_revize_notu: Ps5 ile kullanım Reels i oluştur gamer odasında\n",
                                   encoding="utf-8")
    istem = kullanim_istemi("torii", tmp_path, numunesiz=True)
    assert "Ps5 ile kullanım" in istem and "PATRON NOTU" in istem and "kumandası" in istem
    assert "Ps5" not in kullanim_istemi("torii", tmp_path, revize_notu="sadece raf", numunesiz=True)


def test_gercek_kullanim_kurali_her_zaman(tmp_path: Path) -> None:
    (tmp_path / "x" / "gorsel").mkdir(parents=True)
    (tmp_path / "x" / "urun.yaml").write_text("sku: x\n", encoding="utf-8")
    istem = kullanim_istemi("x", tmp_path, numunesiz=True)
    assert "GERÇEK KULLANIMINI" in istem and "dekor" in istem
