"""E-ticaret karelerinin Claude denetimi: kare listesi ve istem (Patron kararı 2026-11-16)."""
from __future__ import annotations

from pathlib import Path

from coo.eticaret_denetim import istem, kare_listesi
from coo.renk_hatti import urun_renklerini_kaydet


def test_kareler_ve_istem(tmp_path: Path) -> None:
    kok = tmp_path / "kedi"
    for slug in ("kirmizi", "mavi"):
        s = kok / "gorsel" / "renkler" / slug / "studyo-ic"
        s.mkdir(parents=True)
        for ad in ("kapak-beyaz", "krem-fon"):
            (s / f"{ad}.png").write_bytes(b"x")
        (s.parent / "studyo.png").write_bytes(b"x")
    (kok / "urun.yaml").write_text("sku: kedi\n")
    urun_renklerini_kaydet("kedi", [{"ad": a, "hex": h, "slug": a, "klasor": f"gorsel/renkler/{a}", "gorseller": []}
                                    for a, h in (("kirmizi", "#C0392B"), ("mavi", "#2980B9"))], tmp_path)
    (kok / "gorsel" / "renkler-birlikte.png").write_bytes(b"x")
    k = kare_listesi("kedi", tmp_path)
    assert [x["kare"] for x in k] == ["kapak-beyaz", "krem-fon", "kapak-beyaz", "krem-fon", "vitrin"]
    assert k[0]["kaynak"].endswith("kirmizi/studyo.png")
    i = istem("kedi", tmp_path, not_="gölge çok koyu")
    assert "HALE" in i and "--sadece <kare>" in i and "--sadece vitrin" in i and "denetim.json" in i
    assert "gölge çok koyu" in i and "en fazla 5" in i
