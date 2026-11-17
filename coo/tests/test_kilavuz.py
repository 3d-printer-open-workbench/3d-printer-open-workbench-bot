from coo.kilavuz import BOLUMLER, kilavuz_bolumu, kilavuz_dizini


def test_bolumler_telegram_sinirinda_ve_markdown_dengeli():
    for anahtar, (baslik, metin) in BOLUMLER.items():
        assert len(metin) < 3800, anahtar
        govde = metin.replace("`", "\\x00")
        # kod blokları dışında * ve _ çift sayıda olmalı (eski Telegram Markdown)
        parcalar = metin.split("`")
        disarida = "".join(parcalar[0::2])
        assert disarida.count("*") % 2 == 0, anahtar
        assert disarida.count("_") % 2 == 0, anahtar
        assert len(f"kilavuz:{anahtar}".encode()) <= 64


def test_gezinme():
    m, b = kilavuz_dizini()
    assert sum(len(r) for r in b) == len(BOLUMLER) + 1
    m, b = kilavuz_bolumu("akis")
    assert b[0][0]["callback_data"] == "kilavuz:fikir"
    m, b = kilavuz_bolumu("yok")
    assert "Kılavuzu" in m
