"""E-ticaret stüdyo + vitrin görselleri: Qwen-Image-Edit-2511 (Apache 2.0) ile her renk için "gerçek çekim".

Patron kararları (2026-11-16): sahneye yapıştırılmış ürün yok; ürün sahneyle birlikte yeniden çekilir.
Her renk varyantının Blender render'ı (filament renginde) girdi olur; Qwen yalnızca ışık/fon/malzeme
gerçekçiliğini ekler. Her çıktı iki ölçütle denetlenir:
- geometri: Blender kenarlarının çıktıda ±3 px içinde bulunma oranı (silüet + yüz + detaylar)
- renk_sapma: ürün bölgesinde a*b* (Lab) ortalama farkı — ışıktan bağımsız ton sapması
Eşik altı kalan kare bir kez başka tohumla yeniden üretilir; en iyisi tutulur.

Çıktı (renk klasörü): studyo-ic/{kapak-beyaz,krem-fon,koyu-fon}.png + rapor.json
Vitrin (≥2 renk): gorsel/renkler-birlikte.png — tüm renkler tek karede, aynı ışıkta.

Kullanım (.venv-gorsel: numpy/PIL/yaml):
  .venv-gorsel/bin/python -m coo.studyo_qwen <sku> [--renk slug] [--tohum 7] [--sadece ad] [--vitrin]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coo import qwen_edit  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # depo kökü → coo paketi
from coo.ayar import URUNLER_KLASORU as URUNLER  # noqa: E402
BOYUT = 1024
URUN_YUKSEKLIK = 0.56
TABAN_Y = 0.84
FON = (226, 224, 220)
GEOMETRI_ESIK = 0.60  # kalibrasyon (gri fon girdisi): hizalı iyi çıktılar 0.63–0.76; kaymış/bozuk ürün <0.52
RENK_ESIK = {"kapak-beyaz": 7.0, "renkler-birlikte": 8.0}  # beyaz fonda renk birebir olmalı
RENK_ESIK_SAHNE = 13.0  # renkli fon/ışık tonu hafif ısıtır (krem fon ≈10)

KORU = ("Keep the object exactly identical: same shape, same face, same details, same proportions, same position and "
        "size in the frame, and exactly the same color as in the input image. Matte plastic; keep the surface "
        "texture exactly as it appears in the input, change nothing on the object surface. Photorealistic, sharp "
        "focus, no text, no glow.")
# Not: tam boy karede istemde 'layer lines' geçerse model izleri ~5 kat kalın çizer (0.2 mm → ~1 mm oluk).
# Gerçek ölçekli doku Blender girdisinden gelir (blender_ciz.py, katman_mm); yakın çekimde açıkça istenir.
# Yakın çekim: katman izlerinin gerçek ölçekte göründüğü makro detay karesi (girdi: Blender yakin.png ≈52 mm kadraj,
# ürünün dilimleme katman yüksekliğiyle; izler 1024 girdide ≈3 px — modelin silmemesi için açıkça korunur)
DOKU_ISTEM = ("Turn this 3D render close-up into a real macro detail product photograph: soft natural studio light "
              "from the left, shallow depth of field on the far background only. Keep everything exactly identical: "
              "same shapes, same details, same framing, same color, and the same fine horizontal FDM 3D-print "
              "layer lines exactly as visible in the input (same spacing and depth, clearly visible, not "
              "exaggerated, not smoothed out, not removed). "
              "Matte PLA plastic. Photorealistic, sharp focus, no text.")
CEKIMLER = [
    ("kapak-beyaz", "Turn this 3D render into a real professional e-commerce studio photograph. Pure white seamless "
                    "background, large softbox light from the left, soft natural contact shadow under the object. "),
    ("krem-fon", "Turn this 3D render into a real catalog photograph. The same object on a warm beige seamless paper "
                 "backdrop, soft diffused window light from the left with a gentle window-frame shadow pattern on the "
                 "backdrop, soft natural shadow falling to the right. "),
    ("koyu-fon", "Turn this 3D render into a real moody product photograph. The same object on a dark charcoal "
                 "seamless studio backdrop, soft rim light from the right, subtle reflection on the dark floor, "
                 "elegant and dramatic. "),
]
VITRIN_ISTEM = ("Turn this 3D render into one real professional e-commerce studio photograph of {n} identical objects "
                "in different colors standing side by side on a pure white seamless background, soft even softbox "
                "light, soft natural contact shadows. Keep every object exactly identical in shape and details, keep "
                "each object's own color exactly as in the input, same order, same positions and sizes. Matte PLA "
                "plastic, photorealistic, sharp focus, no text.")


# ---------------------------------------------------------------- yerleşim
def _urun(seffaf: Path) -> Image.Image:
    urun = Image.open(seffaf).convert("RGBA")
    r, g, b, a = urun.split()
    a = a.point(lambda v: 0 if v < 120 else v)  # Blender gölge yakalayıcı
    return Image.merge("RGBA", (r, g, b, a)).crop(a.getbbox())


def urun_girdisi(seffaf: Path) -> tuple[Image.Image, np.ndarray]:
    """Ürünü nötr açık gri kare fona ortalar. Dönüş: (girdi, maske 0..1)."""
    urun = _urun(seffaf)
    h = int(BOYUT * URUN_YUKSEKLIK)
    w = int(urun.width * h / urun.height)
    if w > BOYUT * 0.8:
        w = int(BOYUT * 0.8)
        h = int(urun.height * w / urun.width)
    urun = urun.resize((w, h), Image.LANCZOS)
    x, y = (BOYUT - w) // 2, int(BOYUT * TABAN_Y) - h
    girdi = Image.new("RGB", (BOYUT, BOYUT), FON)
    girdi.paste(urun.convert("RGB"), (x, y), urun)
    maske = Image.new("L", (BOYUT, BOYUT), 0)
    maske.paste(urun.split()[3], (x, y))
    return girdi, np.asarray(maske, np.float32) / 255.0


def vitrin_girdisi(seffaflar: list[Path]) -> tuple[Image.Image, np.ndarray]:
    """Renkleri yan yana dizer (3:2 kare). Qwen tümünü tek karede, aynı ışıkta yeniden çeker."""
    gen, yuk = 1536, 1024
    urunler = [_urun(p) for p in seffaflar]
    h = int(yuk * 0.52)
    olcekli = [u.resize((int(u.width * h / u.height), h), Image.LANCZOS) for u in urunler]
    toplam = sum(u.width for u in olcekli)
    bosluk = max(20, int((gen * 0.86 - toplam) / max(1, len(olcekli) - 1))) if len(olcekli) > 1 else 0
    if toplam + bosluk * (len(olcekli) - 1) > gen * 0.9:  # sığmıyorsa küçült
        k = gen * 0.9 / (toplam + 20 * (len(olcekli) - 1))
        olcekli = [u.resize((int(u.width * k), int(u.height * k)), Image.LANCZOS) for u in olcekli]
        toplam, bosluk = sum(u.width for u in olcekli), 20
    x = (gen - toplam - bosluk * (len(olcekli) - 1)) // 2
    girdi = Image.new("RGB", (gen, yuk), FON)
    maske = Image.new("L", (gen, yuk), 0)
    for u in olcekli:
        y = int(yuk * 0.82) - u.height
        girdi.paste(u.convert("RGB"), (x, y), u)
        maske.paste(u.split()[3], (x, y))
        x += u.width + bosluk
    return girdi, np.asarray(maske, np.float32) / 255.0


# ---------------------------------------------------------------- denetim
def _kenarlar(img: Image.Image, esik: float) -> np.ndarray:
    g = np.asarray(img.convert("L").filter(ImageFilter.GaussianBlur(1.2)), np.float32)
    gx, gy = np.zeros_like(g), np.zeros_like(g)
    gx[:, 1:-1] = g[:, 2:] - g[:, :-2]
    gy[1:-1, :] = g[2:, :] - g[:-2, :]
    return np.hypot(gx, gy) > esik


def geometri_skoru(girdi: Image.Image, cikti: Image.Image, maske: np.ndarray, tolerans: int = 3,
                   kayma: int = 16) -> float:
    """Blender kenarlarının (ürün içi + silüet) çıktıda ±tolerans px içinde bulunma oranı.

    Model kareyi birkaç piksel kaydırabilir; ±kayma px içindeki en iyi hizalama alınır (şekli değil
    konumu affeder)."""
    cikti = cikti.resize(girdi.size, Image.LANCZOS)
    bolge = np.asarray(Image.fromarray((maske * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))) > 0
    k_girdi = _kenarlar(girdi, 14) & bolge
    k_cikti = Image.fromarray((_kenarlar(cikti, 8) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * tolerans + 1))
    if k_girdi.sum() == 0:
        return 0.0
    kc = np.asarray(k_cikti) > 0
    ys, xs = np.nonzero(k_girdi)
    h, w = kc.shape
    en_iyi = 0.0
    for dy in range(-kayma, kayma + 1, 4):
        for dx in range(-kayma, kayma + 1, 4):
            yy, xx = np.clip(ys + dy, 0, h - 1), np.clip(xs + dx, 0, w - 1)
            en_iyi = max(en_iyi, float(kc[yy, xx].mean()))
    return round(en_iyi, 3)


def _lab(rgb: np.ndarray) -> np.ndarray:
    c = rgb / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = c @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def _lab_fark(a: np.ndarray, b: np.ndarray, parlaklik: bool) -> float:
    """parlaklik=False: yalnız ton (renkli ışıklı sahneler; doyma parlaklığa göre normalize).
    parlaklik=True: nötr beyaz stüdyoda açıklık da filamentle eşleşmeli (ör. adaçayı koyu yeşile dönmesin)."""
    if parlaklik:
        return round(float(np.sqrt((0.6 * (a[0] - b[0])) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)), 2)
    k = a[0] / max(b[0], 1.0)
    return round(float(np.hypot(a[1] - b[1] * k, a[2] - b[2] * k)), 2)


def renk_sapmasi(girdi: Image.Image, cikti: Image.Image, maske: np.ndarray, parlaklik: bool = False) -> float:
    """Ürün bölgesinde ortalama Lab farkı (bkz. _lab_fark)."""
    ic = np.asarray(Image.fromarray((maske * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(9))) > 127
    if ic.sum() < 100:
        return 99.0
    a = _lab(np.asarray(girdi.convert("RGB"), np.float32)[ic]).mean(0)
    b = _lab(np.asarray(cikti.resize(girdi.size, Image.LANCZOS).convert("RGB"), np.float32)[ic]).mean(0)
    return _lab_fark(a, b, parlaklik)


def parca_maskeleri(maske: np.ndarray, min_sutun: int = 1) -> list[np.ndarray]:
    """Yan yana ürünleri sütun boşluklarından ayırır (vitrin karesinde ürün başına denetim).
    min_sutun: bir sütunun 'dolu' sayılması için gereken piksel (gölge köprülerini keser)."""
    sutun = (maske > 0.5).sum(0) >= min_sutun
    parcalar, bas = [], None
    for x, dolu in enumerate(list(sutun) + [False]):
        if dolu and bas is None:
            bas = x
        elif not dolu and bas is not None:
            m = np.zeros_like(maske)
            m[:, bas:x] = maske[:, bas:x]
            parcalar.append(m)
            bas = None
    return parcalar


def _kutu(m: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(m > 0.5)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def cikti_parcalari(cikti: Image.Image, adet: int) -> list[np.ndarray]:
    """Beyaz fonlu çıktıda ürünleri ayırır (gölge köprüleri kesilir). Sayı tutmazsa boş liste."""
    c = np.asarray(cikti, np.float32)
    fon = np.median(np.concatenate([c[:20].reshape(-1, 3), c[-20:].reshape(-1, 3)]), 0)
    urun = (np.abs(c - fon).max(-1) > 28).astype(np.float32)
    urun = np.asarray(Image.fromarray((urun * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(5))
                      .filter(ImageFilter.MaxFilter(5)), np.float32) / 255
    parcalar = [p for p in parca_maskeleri(urun, min_sutun=int(cikti.height * 0.08)) if p.sum() > 2000]
    return parcalar if len(parcalar) == adet else []


def _ic(m: np.ndarray) -> np.ndarray:
    return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(9))) > 127


def renk_duzelt(girdi: Image.Image, cikti: Image.Image, m_girdi: np.ndarray, m_cikti: np.ndarray,
                parlaklik: bool = False) -> Image.Image:
    """Ürün bölgesinin tonunu (parlaklik=True ise açıklığını da) filament rengine (Blender render) geri çeker.

    m_cikti çıktıdaki ürüne HİZALI olmalı; düzeltme maskenin içinde kalır (kenar dışına taşarsa fon/gölge
    boyanır → turuncu hale / mor saçak)."""
    g = np.asarray(girdi.convert("RGB"), np.float32)
    c = np.asarray(cikti.convert("RGB"), np.float32)

    def derin(m: np.ndarray) -> np.ndarray:  # ortalama için güvenli iç bölge (kayma/ölçek farkına dayanıklı)
        return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(21))) > 127

    ic_g, ic_c = derin(m_girdi), derin(m_cikti)
    if ic_g.sum() < 100 or ic_c.sum() < 100:
        return cikti
    ort_g, ort_c = g[ic_g].mean(0), c[ic_c].mean(0)
    y = np.array([0.299, 0.587, 0.114])
    kazanc = ort_g / np.maximum(ort_c, 1)
    if not parlaklik:
        kazanc = kazanc / max(float(ort_g @ y) / max(float(ort_c @ y), 1.0), 1e-3)
    # Ağırlık maskeden değil RENKTEN: ürünün çıktıdaki tonuna benzeyen pikseller düzeltilir; beyaz fon ve
    # nötr gri gölge bu tona benzemez → boyanmaz (maske kayması/ölçeği hale bırakmaz).
    lab_c = _lab(c)
    ab = _lab(c[ic_c]).mean(0)[1:]
    kroma = float(np.hypot(*ab))
    if kroma >= 8:
        d = np.hypot(lab_c[..., 1] - ab[0], lab_c[..., 2] - ab[1])
        yumusak = np.exp(-(d / max(6.0, 0.45 * kroma)) ** 2)[..., None]
    else:  # nötr filament (beyaz/gri): renkten ayrılamaz → aşındırılmış maske
        yumusak = np.asarray(Image.fromarray((m_cikti * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(9))
                             .filter(ImageFilter.GaussianBlur(2)), np.float32)[..., None] / 255
    duz = np.clip(c * kazanc, 0, 255)
    return Image.fromarray((duz * yumusak + c * (1 - yumusak)).astype(np.uint8))


def renk_sapmasi_parca(girdi: Image.Image, cikti: Image.Image, maske: np.ndarray) -> list[float]:
    """Vitrin: her ürünün renk sapması, çıktıdaki gerçek konumunda ölçülür."""
    cikti = cikti.resize(girdi.size, Image.LANCZOS)
    giris = parca_maskeleri(maske)
    cikis = cikti_parcalari(cikti, len(giris))
    if not cikis:
        return [renk_sapmasi(girdi, cikti, m) for m in giris]
    sonuc = []
    for mg, mc in zip(giris, cikis):
        a = _lab(np.asarray(girdi.convert("RGB"), np.float32)[_ic(mg)]).mean(0)
        b = _lab(np.asarray(cikti.convert("RGB"), np.float32)[_ic(mc)]).mean(0)
        sonuc.append(_lab_fark(a, b, parlaklik=True))  # vitrin beyaz fonda: açıklık da eşleşmeli
    return sonuc


def vitrin_geometri(girdi: Image.Image, cikti: Image.Image, maske: np.ndarray) -> float:
    """Vitrinde model ürünleri yeniden dizebilir: her ürünü kendi kutusunda kırpıp boyut eşleyerek ölçer
    (konum/ölçek affedilir, şekil değil). En kötü ürünün skoru döner."""
    cikti = cikti.resize(girdi.size, Image.LANCZOS)
    giris = parca_maskeleri(maske)
    cikis = cikti_parcalari(cikti, len(giris))
    if not cikis:
        return 0.0
    skorlar = []
    for mg, mc in zip(giris, cikis):
        kg, kc = _kutu(mg), _kutu(mc)
        g_kirp = girdi.crop(kg)
        c_kirp = cikti.crop(kc).resize(g_kirp.size, Image.LANCZOS)
        skorlar.append(geometri_skoru(g_kirp, c_kirp, mg[kg[1]:kg[3], kg[0]:kg[2]], kayma=8))
    return min(skorlar)


def maskeyi_hizala(maske: np.ndarray, img: np.ndarray, kayma: int = 32) -> np.ndarray:
    """Girdi maskesinin silüet kenarını çıktının kenarlarıyla eşleştiren (dy, dx) kaydırmaya taşır.

    Alan örtüşmesi kullanılmaz: yumuşak gölge de 'ürün' sayılıp maskeyi gölgeye doğru kaydırıyordu
    (düzeltme gölgeyi boyuyordu → turuncu hale). Gölgenin keskin kenarı yoktur; silüet kenarı vardır."""
    m_img = Image.fromarray(((maske > 0.5) * 255).astype(np.uint8))
    silu = (np.asarray(m_img.filter(ImageFilter.MaxFilter(3))) > 0) & ~(np.asarray(m_img.filter(ImageFilter.MinFilter(3))) > 0)
    kc = _kenarlar(Image.fromarray(img.clip(0, 255).astype(np.uint8)), 8)
    kc = np.asarray(Image.fromarray((kc * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
    ys, xs = np.nonzero(silu)
    if len(ys) == 0:
        return maske
    h, w = kc.shape
    en_iyi, ofs = -1.0, (0, 0)
    for dy in range(-kayma, kayma + 1, 2):
        for dx in range(-kayma, kayma + 1, 2):
            skor = float(kc[np.clip(ys + dy, 0, h - 1), np.clip(xs + dx, 0, w - 1)].mean())
            if skor > en_iyi:
                en_iyi, ofs = skor, (dy, dx)
    return np.roll(np.roll(maske, ofs[0], 0), ofs[1], 1)


def _maske_resmi(m: np.ndarray) -> Image.Image:
    return Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8))


def urun_korumasi(img: np.ndarray, maske: np.ndarray) -> np.ndarray:
    """Beyaza çekmede korunacak ürün ağırlığı (0 = fon/gölge, 1 = ürün), ÇIKTININ KENDİSİNDEN.

    Girdi maskesi kullanılmaz: Qwen ürünü kaydırır/ölçekler (vitrinde yeniden dizer); kayan maskenin altındaki
    fon parlatılmayıp gri kalıyordu → ürünün yanında sahte 'hayalet gölge' ve şapka çevresinde hale.
    Renkli üründe ağırlık fona göre krom farkından gelir (fon ve gölge nötr gridir, ürün değildir);
    nötr filamentte (beyaz/gri/siyah) renkten ayrılamaz → çıktıya hizalanmış maske (eski yol)."""
    lab = _lab(img)
    kenar = np.concatenate([lab[:12].reshape(-1, 3), lab[-12:].reshape(-1, 3),
                            lab[:, :12].reshape(-1, 3), lab[:, -12:].reshape(-1, 3)])
    fon_ab = np.median(kenar[:, 1:], 0)
    d = np.hypot(lab[..., 1] - fon_ab[0], lab[..., 2] - fon_ab[1])
    hizali = maskeyi_hizala(maske, img)
    genis = np.asarray(_maske_resmi(hizali).filter(ImageFilter.MaxFilter(7)), np.float32) / 255
    if float(np.percentile(d, 99.5)) < 12:  # nötr ürün
        return np.asarray(_maske_resmi(genis).filter(ImageFilter.GaussianBlur(2)), np.float32) / 255
    # Ölü bölge: fondaki sıkıştırma gürültüsü d≈2 (ölçüm) → tamamen fon; aksi halde kısmi koruma fonda
    # gri benek bırakır. Kenar yumuşatma pikselleri (3–9) kısmi → sert hat yok.
    t = np.clip((d - 3.0) / 6.0, 0, 1)
    koru = t * t * (3 - 2 * t)
    # Çok renkli ürünün nötr parçaları (siyah tepsi, beyaz detay): yalnız hizalı maskenin derin içi ve
    # fondan belirgin koyu pikseller (gölge kadar açık olanlar fon sayılır).
    ic = np.asarray(_maske_resmi(hizali).filter(ImageFilter.MinFilter(15)), np.float32) / 255
    koyu = np.clip((lab[..., 0].max() * 0.55 - lab[..., 0]) / 10, 0, 1)
    return np.maximum(koru, ic * koyu)


def beyaza_cek(cikti: Image.Image, maske: np.ndarray) -> Image.Image:
    """Pazaryeri kapağı: fonu #FFFFFF'e çeker; gölge oranı korunur, ürün pikselleri değişmez."""
    img = np.asarray(cikti.resize((maske.shape[1], maske.shape[0]), Image.LANCZOS), np.float32)
    koru = urun_korumasi(img, maske)
    yakin = np.asarray(_maske_resmi((koru > 0.5).astype(np.float32)).filter(ImageFilter.MaxFilter(31))) > 0
    fon = img[~yakin]
    if fon.size == 0:
        return cikti
    ref = np.percentile(fon, 25, axis=0) * 0.98  # fonun büyük kısmı (gradyan dahil) → #FFFFFF; gölge orantılı kalır
    beyaz = np.clip(img * (255.0 / np.maximum(ref, 1)), 0, 255)
    k = koru[..., None]
    return Image.fromarray((img * k + beyaz * (1 - k)).astype(np.uint8))


# ---------------------------------------------------------------- üretim
def _uret(girdi: Image.Image, maske: np.ndarray, istem: str, hedef: Path, tohum: int, gecici: Path,
          parcali: bool = False) -> dict:
    renk_esik = RENK_ESIK.get(hedef.stem, RENK_ESIK_SAHNE)
    parlak = hedef.stem in ("kapak-beyaz", "renkler-birlikte")  # nötr beyaz stüdyo: açıklık da denetlenir
    onek = f"{hedef.parent.parent.name}-{hedef.stem}"  # renkler birbirinin ara dosyasını ezmesin
    girdi_yolu = gecici / f"girdi-{onek}.png"
    girdi.save(girdi_yolu)
    en_iyi: dict | None = None
    for deneme, t in enumerate((tohum, tohum + 101)):
        aday = gecici / f"{onek}-{t}.png"
        sonuc = qwen_edit.duzenle(girdi_yolu, aday, istem, tohum=t, mp=girdi.width * girdi.height / 1e6)
        if not sonuc.get("basarili"):
            if en_iyi is None and deneme == 1:
                return {"basarili": False, "hata": sonuc.get("hata")}
            continue
        img = Image.open(aday).convert("RGB")
        kayit = {"basarili": True, "tohum": t, "yol": aday, "sure_sn": sonuc.get("sure_sn"),
                 "geometri": vitrin_geometri(girdi, img, maske) if parcali else geometri_skoru(girdi, img, maske),
                 "renk_sapma": max(renk_sapmasi_parca(girdi, img, maske)) if parcali
                 else renk_sapmasi(girdi, img, maske, parlaklik=parlak)}
        puan = kayit["geometri"] - kayit["renk_sapma"] / 100
        if en_iyi is None or puan > en_iyi["geometri"] - en_iyi["renk_sapma"] / 100:
            en_iyi = kayit
        if kayit["geometri"] >= GEOMETRI_ESIK and kayit["renk_sapma"] <= renk_esik:
            break
    if en_iyi is None:
        return {"basarili": False, "hata": "üretim başarısız"}
    if en_iyi["renk_sapma"] > renk_esik:  # ton kaydıysa filament rengine geri çek (şekle dokunmaz)
        img = Image.open(en_iyi["yol"]).convert("RGB").resize(girdi.size, Image.LANCZOS)
        if parcali:
            giris = parca_maskeleri(maske)
            for mg, mc in zip(giris, cikti_parcalari(img, len(giris))):
                mc = mc * (np.abs(np.asarray(img, np.float32) - 250).max(-1) > 40)  # gölgeyi dışla
                img = renk_duzelt(girdi, img, mg, mc, parlaklik=True)
            yeni = max(renk_sapmasi_parca(girdi, img, maske))
        else:
            hizali = maskeyi_hizala(maske, np.asarray(img, np.float32))
            img = renk_duzelt(girdi, img, maske, hizali, parlaklik=parlak)
            yeni = renk_sapmasi(girdi, img, hizali, parlaklik=parlak)
        duzeltilmis = Path(str(en_iyi["yol"]).replace(".png", "-renk.png"))
        img.save(duzeltilmis)
        en_iyi.update(yol=duzeltilmis, renk_sapma_ham=en_iyi["renk_sapma"], renk_sapma=yeni, renk_duzeltildi=True)
    en_iyi["gecti"] = en_iyi["geometri"] >= GEOMETRI_ESIK and en_iyi["renk_sapma"] <= renk_esik
    return en_iyi


def renkler(kok: Path) -> list[dict]:
    from coo.renk_hatti import renkler_veriden  # çok renk onaylıysa çok renkli render klasörü

    return renkler_veriden(yaml.safe_load((kok / "urun.yaml").read_text(encoding="utf-8")) or {})


def renk_seti(kok: Path, slug: str | None, tohum: int, sadece: str | None, gecici: Path) -> dict:
    hedefler = [r for r in renkler(kok) if not slug or r.get("slug") == slug]
    klasor = kok / str(hedefler[0]["klasor"]) if hedefler else kok / "gorsel"
    seffaf = klasor / "seffaf.png"
    if not seffaf.exists():
        return {"basarili": False, "hata": f"{seffaf.relative_to(kok)} yok"}
    cikti = klasor / "studyo-ic"
    cikti.mkdir(exist_ok=True)
    girdi, maske = urun_girdisi(seffaf)
    rapor = {"motor": "qwen-image-edit-2511", "renk_klasoru": str(klasor.relative_to(kok)), "tohum": tohum,
             "cekimler": []}
    for ad, sahne in CEKIMLER:
        if sadece and ad != sadece:
            continue
        sonuc = _uret(girdi, maske, sahne + KORU, cikti / f"{ad}.png", tohum, gecici)
        if not sonuc.get("basarili"):
            rapor["cekimler"].append({"ad": ad, "basarili": False, "hata": sonuc.get("hata")})
            continue
        img = Image.open(sonuc["yol"]).convert("RGB")
        if ad == "kapak-beyaz":
            img = beyaza_cek(img, maske)
        img.save(cikti / f"{ad}.png")
        rapor["cekimler"].append({"ad": ad, "basarili": True, "yol": str((cikti / f"{ad}.png").relative_to(kok)),
                                  **{k: sonuc[k] for k in ("geometri", "renk_sapma", "gecti", "tohum")}})
    yakin = klasor / "yakin.png"
    if yakin.exists() and (not sadece or sadece == "doku-yakin"):
        g_yakin = Image.open(yakin).convert("RGB").resize((BOYUT, BOYUT), Image.LANCZOS)
        tam = np.ones((BOYUT, BOYUT), np.float32)
        sonuc = _uret(g_yakin, tam, DOKU_ISTEM, cikti / "doku-yakin.png", tohum, gecici)
        if sonuc.get("basarili"):
            Image.open(sonuc["yol"]).convert("RGB").save(cikti / "doku-yakin.png")
            rapor["cekimler"].append({"ad": "doku-yakin", "basarili": True,
                                      "yol": str((cikti / "doku-yakin.png").relative_to(kok)),
                                      **{k: sonuc[k] for k in ("geometri", "renk_sapma", "gecti", "tohum")}})
        else:
            rapor["cekimler"].append({"ad": "doku-yakin", "basarili": False, "hata": sonuc.get("hata")})
    rapor["basarili"] = any(c.get("basarili") for c in rapor["cekimler"])
    (cikti / "rapor.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")
    return rapor


def vitrin(kok: Path, tohum: int, gecici: Path) -> dict:
    hedefler = [r for r in renkler(kok) if (kok / str(r.get("klasor")) / "seffaf.png").exists()]
    if len(hedefler) < 2:
        return {"basarili": False, "hata": "vitrin için en az 2 renk gerekli"}
    hedefler = hedefler[:5]
    girdi, maske = vitrin_girdisi([kok / str(r["klasor"]) / "seffaf.png" for r in hedefler])
    sonuc = _uret(girdi, maske, VITRIN_ISTEM.format(n=len(hedefler)), kok / "gorsel" / "renkler-birlikte.png",
                  tohum, gecici, parcali=True)
    if not sonuc.get("basarili"):
        return sonuc
    hedef = kok / "gorsel" / "renkler-birlikte.png"
    beyaza_cek(Image.open(sonuc["yol"]).convert("RGB"), maske).save(hedef)
    return {"basarili": True, "yol": str(hedef.relative_to(kok)), "renkler": [r["ad"] for r in hedefler],
            **{k: sonuc[k] for k in ("geometri", "renk_sapma", "gecti")}}


def sunucu_kapat() -> None:
    """ComfyUI'yi kapatır (≈20 GB RAM'i serbest bırakır)."""
    qwen_edit.sunucu_kapat()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sku")
    ap.add_argument("--renk", default=None, help="renk slug'ı (yoksa tüm renkler)")
    ap.add_argument("--tohum", type=int, default=7)
    ap.add_argument("--sadece", default=None, help="tek kare: kapak-beyaz | krem-fon | koyu-fon | doku-yakin | vitrin")
    ap.add_argument("--vitrin", action="store_true", help="≥2 renk varsa renkler-birlikte.png de üret")
    ap.add_argument("--acik-birak", action="store_true", help="iş bitince ComfyUI'yi kapatma")
    a = ap.parse_args()

    kok = URUNLER / a.sku
    gecici = kok / "gorsel" / "sahne" / "qwen-tmp"
    gecici.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    sonuc: dict = {"sku": a.sku, "renkler": []}
    try:
        slugs = [a.renk] if a.renk else ([str(r.get("slug")) for r in renkler(kok)] or [None])
        for slug in ([] if a.sadece == "vitrin" else slugs):  # --sadece vitrin: yalnız renkler-birlikte karesi
            r = renk_seti(kok, slug, a.tohum, a.sadece, gecici)
            sonuc["renkler"].append({"slug": slug, **r})
        if a.vitrin or a.sadece == "vitrin":
            sonuc["vitrin"] = vitrin(kok, a.tohum, gecici)
    except Exception as exc:  # sunucu/ağ hatası
        sonuc["hata"] = str(exc)[-600:]
    finally:
        if not a.acik_birak:
            sunucu_kapat()
    sonuc["basarili"] = any(r.get("basarili") for r in sonuc["renkler"]) or bool((sonuc.get("vitrin") or {}).get("basarili"))
    sonuc["sure_sn"] = round(time.time() - t0, 1)
    print(json.dumps(sonuc, ensure_ascii=False))


if __name__ == "__main__":
    main()
