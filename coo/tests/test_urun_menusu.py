"""Ürün kartı (coo/urun_menusu.py) testleri: butonlar ürünün gerçek aşamasına göre çıkar."""
from __future__ import annotations

from pathlib import Path

from coo.urun_menusu import aktif_urunler, sonraki_adim, urun_karti, urun_listesi_butonlari


def _veriler(butonlar: list[list[dict[str, str]]]) -> list[str]:
    return [b["callback_data"] for satir in butonlar for b in satir]


def test_sadece_konsept_asamasi(tmp_path: Path) -> None:
    kok = tmp_path / "kedi"
    (kok / "konsept").mkdir(parents=True)
    (kok / "konsept" / "flow-1.jpg").write_bytes(b"x")
    (kok / "urun.yaml").write_text("ad: Kedi Saksı\ndurum: KONSEPT_SECIMI\n")
    metin, butonlar, kapak = urun_karti("kedi", tmp_path)
    v = _veriler(butonlar)
    assert "fikir:goster:kedi" in v and "orca:analiz:kedi" not in v
    assert "✅ 1. Konsept — 1 görsel" in metin and "👉 2. 3B model" in metin
    assert butonlar[0][0]["text"].startswith("▶️ 2. 3B model")
    assert kapak == kok / "konsept" / "flow-1.jpg"


def test_tam_asamalar_ve_yukle_butonu(tmp_path: Path) -> None:
    kok = tmp_path / "kedi"
    for alt in ("model", "uretim", "magaza", "gorsel/renkler/krem-e8dfd1"):
        (kok / alt).mkdir(parents=True)
    (kok / "model" / "kedi.stl").write_bytes(b"x")
    (kok / "uretim" / "kedi.3mf").write_bytes(b"x")
    (kok / "magaza" / "paket.json").write_text("{}")
    (kok / "gorsel" / "renkler" / "krem-e8dfd1" / "beyaz.png").write_bytes(b"x")
    (kok / "gorsel" / "renkler" / "krem-e8dfd1" / "studyo-ic").mkdir()
    (kok / "gorsel" / "renkler" / "krem-e8dfd1" / "studyo-ic" / "kapak-beyaz.png").write_bytes(b"x")
    (kok / "urun.yaml").write_text(
        "ad: Kedi\ndurum: TASARIM\nicerik_onayi: ONAYLANDI\ndilimleme: {gercek_gram: 262.6, gercek_sure_dk: 528}\n"
        "renkler: [{ad: Krem, hex: '#E8DFD1', slug: krem-e8dfd1, klasor: gorsel/renkler/krem-e8dfd1}]\n"
    )
    # e-ticaret kareleri var ama Patron onaylamadı → 5. adım bekler, buton onay ekranına götürür
    assert sonraki_adim("kedi", tmp_path)["ad"] == "E-ticaret görselleri"
    assert "studyo:sun:kedi" in _veriler(urun_karti("kedi", tmp_path)[1])
    with (kok / "urun.yaml").open("a") as f:
        f.write("studyo_onayi: ONAYLANDI\n")
    metin, butonlar, kapak = urun_karti("kedi", tmp_path)
    v = _veriler(butonlar)
    for beklenen in ("orca:analiz:kedi", "kartela:ac:kedi", "orca:ac:kedi", "icerik:studyo:kedi", "numune:iste:kedi",
                     "icerik:sun:kedi", "magaza:hazirla:kedi", "magaza:yukle:kedi", "menu:urunler"):
        assert beklenen in v, beklenen
    assert "icerik:kullanim:kedi" not in v  # numune yokken Flow kullanım görseli yok
    assert "262.6 g · 8 sa 48 dk" in metin and "Krem" in metin and "onaylandı" in metin
    assert "icerik:uret:kedi" not in v  # reddedilen yapıştırma yöntemi kartta yok
    assert sonraki_adim("kedi", tmp_path)["ad"] == "Teknik Poster poster + Reels"  # numune isteğe bağlı, atlanır
    assert kapak.name == "kapak-beyaz.png"
    (kok / "gorsel" / "numune-1.jpg").write_bytes(b"x")
    assert "icerik:kullanim:kedi" in _veriler(urun_karti("kedi", tmp_path)[1])
    assert all(len(x.encode()) <= 64 for x in v)

    (kok / "magaza" / "yukleme.json").write_text('{"durum": "YUKLENDI", "urun_linki": "https://x"}')
    _, butonlar, _ = urun_karti("kedi", tmp_path)
    assert "magaza:yukle:kedi" not in _veriler(butonlar)


def test_liste_iptal_ve_gizli_klasorleri_atlar(tmp_path: Path) -> None:
    for ad, durum in (("a", "TASARIM"), ("b", "IPTAL"), ("_sablon", "KONSEPT")):
        (tmp_path / ad).mkdir()
        (tmp_path / ad / "urun.yaml").write_text(f"ad: {ad}\ndurum: {durum}\n")
    assert aktif_urunler(tmp_path) == ["a"]
    v = _veriler(urun_listesi_butonlari(tmp_path))
    assert v == ["urunmenu:a", "fikir:baslat", "menu:ana"]


def test_fiyatsiz_taslak_paket_tamam_sayilmaz(tmp_path: Path) -> None:
    """MAGAZA_EKSIK ile yazılan fiyatı boş taslak paket 10. adımı tamamlamış göstermemeli."""
    from coo.urun_menusu import urun_durumu
    (tmp_path / "x" / "magaza").mkdir(parents=True)
    (tmp_path / "x" / "urun.yaml").write_text("sku: x\n", encoding="utf-8")
    (tmp_path / "x" / "magaza" / "paket.json").write_text('{"baslik": "X", "satis_fiyati_tl": null}', encoding="utf-8")
    assert urun_durumu("x", tmp_path)["paket"] is False
