"""Open Workbench renk paleti — tek kaynak: `config/renk_paleti.yaml`.

Her kayıt bir filament rengidir: ad, HEX, marka, malzeme, ERP filament kimliği, kaynak (ekran görüntüsü) ve
`dogrulandi` (HEX ekran görüntüsünden piksel ölçümüyle mi alındı). ERP'den gelen eski HEX'ler tahmindi;
palete ilk aktarımda `dogrulandi: false` işaretlenir ve ekran görüntüsü gönderilince düzeltilir.

Bot sürecinde çalışır (numpy gerekmez); renk farkı (ΔE76) saf Python.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from .ayar import CONFIG_KLASORU, ERP_URL_VARSAYILAN

PALET_DOSYASI = CONFIG_KLASORU / "renk_paleti.yaml"


def _lab(hex_kod: str) -> tuple[float, float, float]:
    h = hex_kod.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    x = (0.4124564 * c[0] + 0.3575761 * c[1] + 0.1804375 * c[2]) / 0.95047
    y = 0.2126729 * c[0] + 0.7151522 * c[1] + 0.0721750 * c[2]
    z = (0.0193339 * c[0] + 0.1191920 * c[1] + 0.9503041 * c[2]) / 1.08883
    f = [t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116 for t in (x, y, z)]
    return 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])


def delta_e(a: str, b: str) -> float:
    return sum((p - q) ** 2 for p, q in zip(_lab(a), _lab(b))) ** 0.5


def _sade(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower().replace("ı", "i")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def palet_oku(dosya: Path | None = None) -> list[dict[str, Any]]:
    yol = dosya or PALET_DOSYASI
    if not yol.exists():
        return []
    veri = yaml.safe_load(yol.read_text(encoding="utf-8")) or {}
    return list(veri.get("renkler") or [])


def palet_yaz(renkler: list[dict[str, Any]], dosya: Path | None = None) -> None:
    yol = dosya or PALET_DOSYASI
    yol.parent.mkdir(parents=True, exist_ok=True)
    baslik = ("# Open Workbench renk paleti — Telegram'dan ekran görüntüsü gönderilerek güncellenir (coo/renk_al.py).\n"
              "# dogrulandi: true = HEX ekran görüntüsünden piksel ölçümüyle alındı; false = tahmin, doğrulanmalı.\n")
    yol.write_text(baslik + yaml.safe_dump({"renkler": renkler}, allow_unicode=True, sort_keys=False), encoding="utf-8")


def erp_filamentleri(erp_url: str = ERP_URL_VARSAYILAN) -> list[dict[str, Any]]:
    try:
        with urllib.request.urlopen(f"{erp_url}/api/filaments", timeout=10) as y:
            return json.load(y)
    except Exception:
        return []


def erpden_tohumla(filamentler: list[dict[str, Any]], dosya: Path | None = None) -> int:
    """Palette olmayan ERP filamentlerini `dogrulandi: false` olarak ekler; eklenen sayısını döndürür."""
    renkler = palet_oku(dosya)
    var = {r.get("erp_filament_id") for r in renkler}
    yeni = 0
    for f in filamentler:
        if f.get("id") in var or not f.get("color_hex"):
            continue
        renkler.append({"ad": f.get("color_name"), "hex": str(f["color_hex"]).upper(), "marka": f.get("brand"),
                        "malzeme": f.get("material_type"), "erp_filament_id": f.get("id"), "stokta": True,
                        "dogrulandi": False, "kaynak": "ERP (tahmini HEX)", "tarih": dt.date.today().isoformat()})
        yeni += 1
    if yeni:
        palet_yaz(renkler, dosya)
    return yeni


def erp_istek(yontem: str, yol: str, govde: dict | None = None, erp_url: str | None = None) -> Any:
    from .ayar import ayarlari_yukle

    taban = (erp_url or ayarlari_yukle().erp_url).rstrip("/")
    istek = urllib.request.Request(f"{taban}{yol}", method=yontem,
                                   data=json.dumps(govde).encode() if govde is not None else None,
                                   headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(istek, timeout=20) as r:
        return json.loads(r.read().decode())


def erp_eslesmesi(renk: dict[str, Any], filamentler: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Ekran görüntüsündeki renk ERP'deki bir filamentle aynı ürün mü (marka + renk adı)?"""
    if renk.get("erp_filament_id"):
        return next((f for f in filamentler if f.get("id") == renk["erp_filament_id"]), None)
    ad, marka = _sade(renk.get("ad", "")), _sade(renk.get("marka", ""))
    for f in filamentler:
        fad = _sade(f.get("color_name", ""))
        if marka and _sade(f.get("brand", "")) == marka and fad and (fad in ad or ad in fad):
            return f
    return None


def palete_ekle(renk: dict[str, Any], kaynak: str, dosya: Path | None = None) -> dict[str, Any]:
    """Ölçülmüş rengi palete ekler; aynı ERP filamenti / aynı marka+ad varsa günceller. Kaydı döndürür."""
    renkler = palet_oku(dosya)
    kayit = {"ad": renk["ad"], "hex": renk["hex"].upper(), "marka": renk.get("marka") or None,
             "malzeme": renk.get("malzeme") or None, "erp_filament_id": renk.get("erp_filament_id"),
             "stokta": bool(renk.get("erp_filament_id")), "dogrulandi": True, "guven": renk.get("guven"),
             "yayilma_de": renk.get("yayilma_de"), "kaynak": kaynak, "tarih": dt.date.today().isoformat()}
    for i, r in enumerate(renkler):
        ayni_erp = kayit["erp_filament_id"] and r.get("erp_filament_id") == kayit["erp_filament_id"]
        ayni_ad = _sade(r.get("ad", "")) == _sade(kayit["ad"]) and _sade(r.get("marka") or "") == _sade(kayit["marka"] or "")
        if ayni_erp or ayni_ad:
            kayit["eski_hex"] = r.get("hex")
            renkler[i] = {**r, **{k: v for k, v in kayit.items() if v is not None}}
            palet_yaz(renkler, dosya)
            return renkler[i]
    renkler.append(kayit)
    palet_yaz(renkler, dosya)
    return kayit


def en_yakin(hex_kod: str, dosya: Path | None = None) -> tuple[dict[str, Any] | None, float]:
    renkler = [r for r in palet_oku(dosya) if r.get("hex")]
    if not renkler:
        return None, 999.0
    r = min(renkler, key=lambda x: delta_e(hex_kod, x["hex"]))
    return r, round(delta_e(hex_kod, r["hex"]), 1)


def palet_metni(dosya: Path | None = None) -> str:
    satirlar = []
    for r in palet_oku(dosya):
        isaret = "✅" if r.get("dogrulandi") else "⚠️"
        stok = " · stokta" if r.get("stokta") else ""
        satirlar.append(f"{isaret} *{r.get('ad')}* `{r.get('hex')}` — {r.get('marka') or '?'} {r.get('malzeme') or ''}{stok}")
    return "\n".join(satirlar) or "_Palet boş._"


def secim_istemi(klasor: Path, filamentler: list[dict[str, Any]], not_: str = "") -> str:
    """Görsel ajanına: hangi numaralı bölgeler gerçek filament/ürün rengi? (sayı/HEX uydurmadan)"""
    erp = "\n".join(f"- id {f.get('id')}: {f.get('brand')} {f.get('material_type')} — {f.get('color_name')}" for f in filamentler)
    return (
        "Görev: Patronun gönderdiği ekran görüntüsünden/fotoğraftan FİLAMENT (veya basılmış ürün) rengini belirle.\n"
        f"Orijinal: `{klasor / 'kaynak.png'}` · numaralı aday bölgeler: `{klasor / 'isaretli.png'}` "
        f"(pembe çizgi + numara; bölge listesi `{klasor / 'adaylar.json'}`). İkisini de Read ile AÇ ve incele.\n"
        + (f"Patronun notu: {not_}\n" if not_ else "")
        + "Kurallar:\n"
        "- Yalnızca satılan filamentin/ürünün GERÇEK rengini gösteren bölgeleri seç: makaraya sarılı filament en iyisi, "
        "sonra basılmış örneğin düz ve iyi aydınlanmış yüzeyi. Sitenin arayüzü (başlık, buton, rozet, yazı), makaranın "
        "plastiği, kutu, arka plan, gölge ve parlama bölgelerini SEÇME.\n"
        "- Sayfada birden fazla renk seçeneği (renk kutucukları/varyantlar) varsa her biri ayrı renk olabilir; "
        "seçili/gösterilen ürün rengini öne al, kutucukları ayrı renk olarak ekle.\n"
        "- HEX'i SEN TAHMİN ETME — ölçüm piksellerden yapılacak. Sayfada YAZILI bir HEX/RAL kodu görüyorsan "
        "`yazili_hex` alanına aynen yaz, yoksa boş bırak.\n"
        "- Renk adı Türkçe ve satıcının adına sadık (ör. 'Kemik', 'Fildişi', 'Mat Siyah'); marka ve malzemeyi "
        "sayfadan oku.\n"
        f"- ERP'deki filamentler (aynı ürünse `erp_filament_id` ver, değilse null):\n{erp or '- (yok)'}\n"
        f"Sonucu şu JSON olarak `{klasor / 'secim.json'}` dosyasına YAZ (Write aracıyla):\n"
        '{"urun": "sayfadaki ürün adı", "renkler": [{"ad": "Kemik", "marka": "Sunlu", "malzeme": "Mat PLA", '
        '"bolgeler": [11, 17], "yazili_hex": "", "erp_filament_id": null, "neden": "makaradaki sarılı filament"}]}\n'
        "Renk göremiyorsan renkler boş liste olsun ve `neden` alanında açıkla. Başka dosyaya dokunma."
    )


def kartela_gorseli(hedef: Path, secili: set[int] | None = None, dosya: Path | None = None) -> Path:
    """Paletin numaralı renk kartelası (seçilenler çerçeveli ✓). Bot sürecinde PIL ile çizilir."""
    from PIL import Image, ImageDraw, ImageFont

    renkler = palet_oku(dosya)
    secili = secili or set()
    sutun, kw, kh = 4, 300, 230
    satir = max(1, (len(renkler) + sutun - 1) // sutun)
    im = Image.new("RGB", (sutun * kw + 20, satir * kh + 20), "#F4F1EA")
    d = ImageDraw.Draw(im)

    def yazi(boyut):
        for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"):
            if Path(f).exists():
                return ImageFont.truetype(f, boyut)
        return ImageFont.load_default()
    b1, b2 = yazi(26), yazi(19)
    for i, r in enumerate(renkler):
        x, y = 10 + (i % sutun) * kw, 10 + (i // sutun) * kh
        sec = i in secili
        d.rounded_rectangle((x + 6, y + 6, x + kw - 6, y + kh - 6), 14, fill="white",
                            outline="#1F8A5B" if sec else "#D9D4C7", width=6 if sec else 2)
        d.rounded_rectangle((x + 20, y + 20, x + kw - 20, y + 130), 10, fill=r.get("hex") or "#CCCCCC", outline="#BBBBBB")
        d.text((x + 24, y + 26), str(i + 1), fill="white" if delta_e(r.get("hex") or "#FFFFFF", "#FFFFFF") > 40 else "black", font=b1)
        if sec:
            d.text((x + kw - 58, y + 26), "✓", fill="white", font=b1)
        d.text((x + 20, y + 140), (r.get("ad") or "")[:20], fill="black", font=b1)
        alt = f"{r.get('hex')} · {(r.get('marka') or '')[:10]}" + ("" if r.get("dogrulandi") else " · ~")
        d.text((x + 20, y + 176), alt, fill="#555555", font=b2)
    im.save(hedef)
    return hedef
