"""Reels takvimi: istek kuyruğu, ajan sonucunun birleştirilmesi, revizede Patron verisinin korunması (2026-11-17)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from coo import reels_takvim as rt


def _fikir(baslik: str, tarih: str = "2026-11-20") -> dict:
    return {"baslik": baslik, "tarih": tarih, "trend": {"ad": "T", "kaynak_url": "https://x"},
            "kancalar": [{"tur": "merak", "metin": "K"}], "senaryo": [{"sure": "0-2 sn", "goruntu": "G"}],
            "cekim_talimati": ["a", "b"]}


def test_kuyruk_birlestir_revize(tmp_path: Path) -> None:
    i1 = rt.istek_ekle("yeni_fikirler", "oyuncu", adet=2, k=tmp_path)
    i2 = rt.istek_ekle("yeni_fikirler", k=tmp_path)
    alinan = rt.siradaki_istek(tmp_path)
    assert alinan["id"] == i1["id"] and rt.siradaki_istek(tmp_path) is None  # aynı anda tek iş
    assert "oyuncu" in rt.istem(alinan, tmp_path) and "REELS_HAZIR" in rt.istem(alinan, tmp_path)

    rt.gelen_yolu(i1["id"], tmp_path).write_text(json.dumps({"fikirler": [_fikir("A"), _fikir("B", "2026-11-21"), {}]}))
    eklenen = rt.gelen_birlestir(alinan, tmp_path)
    assert [f["baslik"] for f in eklenen] == ["A", "B"] and all(f["durum"] == "fikir" for f in eklenen)
    rt.istek_bitir(i1["id"], "tamam", tmp_path)
    assert rt.siradaki_istek(tmp_path)["id"] == i2["id"]

    hedef = eklenen[0]
    tk = json.loads((tmp_path / "takvim.json").read_text())
    tk["fikirler"][0].update({"durum": "onaylandi", "notlar": [{"metin": "sesi değiştir"}], "cekim_tamam": [0]})
    (tmp_path / "takvim.json").write_text(json.dumps(tk))
    rev = rt.istek_ekle("revize", "sesi değiştir", hedef["id"], k=tmp_path)
    rt.istek_bitir(i2["id"], "tamam", tmp_path)
    rev = rt.siradaki_istek(tmp_path)
    assert "sesi değiştir" in rt.istem(rev, tmp_path) and '"baslik": "A"' in rt.istem(rev, tmp_path)
    rt.gelen_yolu(rev["id"], tmp_path).write_text(json.dumps({"fikirler": [{**_fikir("A2"), "revize_ozeti": "ses"}]}))
    out = rt.gelen_birlestir(rev, tmp_path)[0]
    assert out["id"] == hedef["id"] and out["baslik"] == "A2" and out["durum"] == "onaylandi"
    assert out["cekim_tamam"] == [0] and out["notlar"][-1]["kimden"] == "Claude" and "revize_ozeti" not in out
    assert len(rt.takvim(tmp_path)) == 2


def test_yarim_kalan_ve_hatirlatma(tmp_path: Path) -> None:
    rt.istek_ekle("yeni_fikirler", k=tmp_path)
    assert rt.siradaki_istek(tmp_path)
    rt.yarim_kalanlari_sifirla(tmp_path)
    assert rt.siradaki_istek(tmp_path)  # bot yeniden başlayınca kuyruğa döner
    bugun = dt.date.today().isoformat()
    (tmp_path / "takvim.json").write_text(json.dumps({"fikirler": [
        {**_fikir("Bugün", bugun), "durum": "onaylandi", "saat": "19:00"}, {**_fikir("İptal", bugun), "durum": "iptal"}]}))
    fk = rt.bugunun_fikirleri(tmp_path)
    assert [f["baslik"] for f in fk] == ["Bugün"]
    assert "Bugün" in rt.hatirlatma_metni(fk) and rt.SAYFA in rt.hatirlatma_metni(fk)
