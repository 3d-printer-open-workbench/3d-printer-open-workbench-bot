"""Qwen stüdyo denetim ölçütleri (geometri / renk sapması / beyaz kapak) — GPU gerektirmez."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

from coo.studyo_qwen import beyaza_cek, geometri_skoru, renk_sapmasi  # noqa: E402


def _sahne(dx: int = 0, renk=(200, 120, 80), fon=(225, 222, 218)) -> tuple[Image.Image, np.ndarray]:
    img = Image.new("RGB", (256, 256), fon)
    d = ImageDraw.Draw(img)
    d.ellipse((80 + dx, 60, 176 + dx, 200), fill=renk)
    d.rectangle((110 + dx, 100, 146 + dx, 120), fill=(60, 40, 30))
    m = Image.new("L", (256, 256), 0)
    ImageDraw.Draw(m).ellipse((80, 60, 176, 200), fill=255)
    return img, np.asarray(m, np.float32) / 255


def test_geometri_kaymayi_yakalar() -> None:
    g, m = _sahne()
    assert geometri_skoru(g, _sahne()[0], m) > 0.9
    assert geometri_skoru(g, _sahne(dx=25)[0], m) < 0.6


def test_renk_sapmasi_isiga_degil_tona_bakar() -> None:
    g, m = _sahne()
    koyu = Image.fromarray((np.asarray(g, np.float32) * 0.8).astype(np.uint8))
    assert renk_sapmasi(g, koyu, m) < 5  # yalnız parlaklık değişimi
    assert renk_sapmasi(g, _sahne(renk=(90, 160, 90))[0], m) > 30  # farklı renk


def test_beyaza_cek_fonu_beyaz_yapar_urunu_korur() -> None:
    g, m = _sahne()
    b = np.asarray(beyaza_cek(g, m))
    assert b[5, 5].min() >= 250
    assert abs(int(b[130, 100, 0]) - 200) <= 3


def test_beyaza_cek_kaymis_maskede_hayalet_golge_birakmaz() -> None:
    """Qwen ürünü kaydırınca girdi maskesinin altındaki fon gri kalıyordu (sahte gölge silüeti)."""
    _, m = _sahne()
    # Vitrinde model ürünleri yeniden dizer: çıktıda ürün hem ~50 px kaymış hem büyümüş.
    c = Image.new("RGB", (256, 256), (225, 222, 218))
    ImageDraw.Draw(c).ellipse((130, 50, 240, 215), fill=(200, 120, 80))
    b = np.asarray(beyaza_cek(c, m))
    assert b[132, 118].min() >= 250  # eski maskenin altında kalan fon → beyaz (gri silüet yok)
    assert abs(int(b[132, 185, 0]) - 200) <= 3  # ürünün gerçek yeri korunur


def test_beyaz_fonda_aciklik_da_denetlenir() -> None:
    g, m = _sahne(renk=(156, 175, 136))  # adaçayı
    koyu = _sahne(renk=(70, 110, 60))[0]  # koyu yeşil: ton yakın, açıklık çok farklı
    assert renk_sapmasi(g, koyu, m, parlaklik=True) > 8  # beyaz kapak eşiği 7 → yakalanır
    assert renk_sapmasi(g, g, m, parlaklik=True) < 1


def test_renk_duzelt_kenar_disina_tasmaz() -> None:
    from coo.studyo_qwen import renk_duzelt
    g, m = _sahne(renk=(156, 175, 136))  # adaçayı filament
    c = _sahne(renk=(105, 150, 90))[0]  # modelin koyu/doygun yeşile kaydırdığı çıktı (gerçek gözlem)
    assert renk_sapmasi(g, c, m, parlaklik=True) > 8
    d = np.asarray(renk_duzelt(g, c, m, m, parlaklik=True))
    assert np.abs(d[5, 5].astype(int) - np.asarray(c)[5, 5].astype(int)).max() <= 2  # fon (pratikte) değişmez
    assert renk_sapmasi(g, Image.fromarray(d), m, parlaklik=True) < 8
