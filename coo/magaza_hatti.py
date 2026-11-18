"""Mağazaya Hazırla → Önizleme → Mağazaya Yükle hattı (Telegram butonları).

1. Hazırla: Claude (ERP MCP) maliyet ve satış fiyatını `gcode_maliyet` ile hesaplar (fire Patrondan,
   ambalaj ERP malzemelerinden, kargo fiyata dahil değil), SEO metnini yazar, görselleri sıralar ve
   `02_Urunler/<sku>/magaza/paket.json` yazar. Bot paketi doğrular ve önizlemeyi Telegram'a yollar.
2. Yükle: Patron "🚀 Mağazaya Yükle"ye bastığında Claude, Chrome'daki İkas yönetim panelinde ürünü
   paket.json'dan BİREBİR oluşturur (yorum yok), ekran görüntüsü + ürün linkini `magaza/yukleme.json`'a yazar.

İkas Start pakette Özel Uygulama (API) yok; bu yüzden yükleme Chrome ile yapılır.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ayar import URUNLER_KLASORU
from .renk_hatti import urun_renkleri

ZORUNLU_ALANLAR = ("baslik", "aciklama_html", "satis_fiyati_tl", "gorseller", "slug", "meta_baslik",
                   "meta_aciklama", "etiketler", "maliyet")
STUDYO_CEKIMLERI = ("kapak-beyaz.png", "krem-fon.png", "koyu-fon.png", "doku-yakin.png")  # coo/studyo_qwen.py çıktıları


def paket_yolu(sku: str, urunler_klasoru: Path | None = None) -> Path:
    return (urunler_klasoru or URUNLER_KLASORU) / sku / "magaza" / "paket.json"


def renk_gorselleri(kok: Path, klasor: Path) -> list[str]:
    """Bir renk için Qwen stüdyo görselleri (göreli yollar). Ham Blender render'ı galeriye GİRMEZ (Patron kararı)."""
    return [str((klasor / "studyo-ic" / ad).relative_to(kok)) for ad in STUDYO_CEKIMLERI
            if (klasor / "studyo-ic" / ad).exists()]


def galeri_posterleri(kok: Path) -> list[str]:
    """Galeriye girecek konsept posterleri: yalnız bilgi katmanlı (gerçek ölçü/malzeme bandı basılan) konseptlerin
    ana `<ad>-3x4.png` dosyası — konsept başına bir tane. Bilgisiz/dekoratif posterler (ör. editoryal-poster)
    sosyal medya içindir, ürün galerisine girmez (Patron: Teknik Poster seçildi, 2026-11-16)."""
    from .konsept_hatti import konseptler

    sonuc = []
    for k in konseptler():
        if k.get("bilgi_katmani"):
            p = kok / "gorsel" / "konsept" / f"{k['ad']}-3x4.png"
            if p.exists():
                sonuc.append(str(p.relative_to(kok)))
    return sonuc


def mevcut_gorseller(sku: str, urunler_klasoru: Path | None = None) -> list[str]:
    """Mağaza galerisi (göreli yollar), patron kararı 2026-11-16:

    1) beyaz stüdyo kapağı (Qwen)  1b) tüm renkler vitrin karesi  1c) katman dokusu yakın  2) gerçek numune
    fotoğrafları  3) Flow kullanım görselleri (numuneden)  4) diğer Qwen stüdyo kareleri  5) Teknik Poster ölçü/malzeme
    posteri. Kompozit (yasam-*), ham Blender render'ı, düz kartlar ve editoryal föy galeriye ALINMAZ.
    """
    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    renkler = urun_renkleri(sku, urunler_klasoru)
    klasor = kok / str(renkler[0].get("klasor")) if renkler else kok / "gorsel"
    studyo = renk_gorselleri(kok, klasor)
    sonuc = studyo[:1]
    if (kok / "gorsel" / "renkler-birlikte.png").exists():  # vitrin: tüm renkler tek karede
        sonuc.append("gorsel/renkler-birlikte.png")
    sonuc += [g for g in studyo if g.endswith("doku-yakin.png")]  # Patron referansı: gerçek katman dokusu
    for desen in ("gorsel/numune-*.jpg", "gorsel/numune-*.png", "gorsel/kullanim-*.png", "gorsel/kullanim-*.jpg"):
        sonuc += [str(y.relative_to(kok)) for y in sorted(kok.glob(desen))]
    sonuc += studyo[1:]
    sonuc += galeri_posterleri(kok)  # ölçü/malzeme bilgisi yalnız teknik posternden
    tekil: list[str] = []
    for g in sonuc:
        if g not in tekil:
            tekil.append(g)
    return tekil


def renk_varyantlari(sku: str, urunler_klasoru: Path | None = None) -> list[dict[str, Any]]:
    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    return [
        {"secenek": "Renk", "deger": r["ad"], "hex": r["hex"],
         "gorseller": renk_gorselleri(kok, kok / str(r.get("klasor") or "gorsel"))}
        for r in urun_renkleri(sku, urunler_klasoru)
    ]


def pazar_basliklari(sku: str, urunler_klasoru: Path | None = None, en_fazla: int = 12) -> list[str]:
    """Pazar araştırmasındaki benzer ürünlerin gerçek başlıkları (benzerlik ≥2, önce TR)."""
    yol = (urunler_klasoru or URUNLER_KLASORU) / sku / "pazar" / "fiyat.json"
    try:
        veri = json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else {}
    except json.JSONDecodeError:
        return []
    ornekler = [o for o in veri.get("ornekler") or [] if o.get("ad") and int(o.get("benzerlik") or 0) >= 2]
    ornekler.sort(key=lambda o: (str(o.get("ulke") or "TR").upper() != "TR", -int(o.get("benzerlik") or 0)))
    return [f"{o['ad']} ({o.get('platform', '?')})" for o in ornekler[:en_fazla]]


def hazirla_istemi(sku: str, fire_yuzde: float, urunler_klasoru: Path | None = None, not_: str = "") -> str:
    gorseller = mevcut_gorseller(sku, urunler_klasoru)
    basliklar = pazar_basliklari(sku, urunler_klasoru)
    seo_satiri = (
        "   ANAHTAR KELİME: Rakiplerin GERÇEK başlıkları (pazar araştırmasından): "
        + json.dumps(basliklar, ensure_ascii=False)
        + ". Bunlarda tekrar eden Türkçe arama terimlerini çıkar (ürün tipi + kullanım + malzeme/stil); en sık "
        "geçen ana terim başlığın başında olsun, diğerlerini etiketlere ve meta açıklamaya dağıt. Rakip MARKA "
        "adlarını ve tescilli karakter adlarını KULLANMA. Kullandığın terimleri `seo_terimleri` alanına yaz.\n"
        if basliklar else
        "   ANAHTAR KELİME: pazar araştırması yok; Türk kullanıcının arayacağı sade terimleri kullan "
        "(ürün tipi + kullanım). `seo_terimleri` alanına yaz.\n"
    )
    varyantlar = renk_varyantlari(sku, urunler_klasoru)
    varyant_satiri = (
        f"   VARYANTLAR: `varyantlar` alanına BİREBİR şunu yaz: {json.dumps(varyantlar, ensure_ascii=False)} "
        "(hepsi aynı fiyat). Açıklamada renk seçeneklerini adlarıyla bir kez an (tabloda 'Renk' satırı yeter).\n"
        if varyantlar else "   VARYANTLAR: renk varyantı yok → `varyantlar: []`.\n"
    )
    return (
        f"Görev: `{sku}` ürününü İkas mağazasına yüklenmeye hazır pakete dönüştür. YÜKLEME YAPMA.\n"
        f"Kaynak: `02_Urunler/{sku}/urun.yaml` (ölçüler, gram, süre, `gcode_yolu`, filament).\n"
        + (f"PATRON NOTU (öncelikli — önceki pakete göre düzeltme; ERP fiyat tabanı ve metin rehberi kuralları yine "
           f"geçerli): {not_.strip()}\n" if not_.strip() else "")
        + "\n"
        "1) MALİYET/FİYAT (workbench-erp MCP — ASLA tahmin etme):\n"
        "   a) `get_erp_inventory_summary` ile ambalaj/kutu/koruyucu malzemelerini bul; ürün ölçüsüne uyan "
        "kalemleri seç ve birim fiyatlarının toplamını `ek_malzeme_tl` yap. Uygun kayıt yoksa DUR ve son satıra "
        "`MAGAZA_EKSIK ambalaj malzemesi ERP'de yok` yaz.\n"
        "   b) Filament: urun.yaml'daki filamente en yakın ERP filamentini `get_erp_inventory_summary`'den seç "
        "(yoksa makinedeki aktif filamenti kullan) → `filament_id`.\n"
        f"   c) `gcode_maliyet(gcode_yolu=<mutlak yol>, fire_yuzde={fire_yuzde}, ek_malzeme_tl=<a>, "
        "filament_id=<b>, kargo_tl=0)` — kargo fiyata DAHİL DEĞİL. Önerilen satış fiyatını ve maliyet dökümünü al.\n"
        "   d) Fiyatı psikolojik olarak yukarı yuvarla (ör. 437 → 449,90); ERP önerisinin altına İNME.\n"
        "2) METİN: önce `config/marka/magaza-metin-rehberi.md` dosyasını oku ve BİREBİR uygula — kısa, insan "
        "sesiyle, profesyonel; tablo hariç 50–130 kelime, 3–4 düz madde ('Kalın etiket:' kalıbı yok), ≤5 satır "
        "tablo, tek son not (bakım + ısı + üretim/kargo). Başlık ≤70 karakter, en fazla bir ayraç; meta_baslik "
        "(≤60), meta_aciklama (≤155), slug, 8-12 etiket. Her bilgi bir kez geçer. Yazdıktan sonra "
        f"`python3 -m coo.metin_denetim {sku}` ile kontrol et ve hataları düzelt (review ayrı bir editör "
        "adımıdır, `--review` VERME).\n"
        + seo_satiri +
        "   DOĞRULUK: Her iddia urun.yaml veya ERP verisine dayanmalı. 'El yapımı', 'bitkisel bazlı', 'su "
        "geçirmez', 'her parça kalite kontrolden geçer' gibi doğrulanmamış iddialar YAZMA. Malzeme: PLA. "
        "Saksıysa: drenaj deliği varsa belirt; PLA'nın doğrudan güneş/55°C üstü ısıda deforme olabileceğini yaz.\n"
        f"3) GÖRSELLER: bu sırayı kullan (yalnızca var olanlar): {json.dumps(gorseller, ensure_ascii=False)}. "
        + varyant_satiri +
        "   Listede `numune-` ile başlayan gerçek fotoğraf yoksa son nota şu cümleyi ekle: 'Görseller 3B "
        "modelden hazırlanmıştır, renk tonu filamente göre hafif değişebilir.' (Bu bir engel DEĞİL, uyarı yazma.)\n"
        f"4) `02_Urunler/{sku}/magaza/paket.json` dosyasını şu anahtarlarla yaz: "
        '{"sku","baslik","aciklama_html","satis_fiyati_tl","indirimli_fiyat_tl":null,"kategori",'
        '"etiketler":[],"slug","meta_baslik","meta_aciklama","gorseller":[göreli yollar],'
        '"varyantlar":[],"seo_terimleri":[],"stok_notu":"Siparişe özel üretim","hazirlik_suresi_gun":<gerçek baskı süresine göre>,'
        '"maliyet":{"birim_maliyet_tl","basa_bas_tl","erp_onerilen_tl","fire_yuzde","ek_malzeme_tl",'
        '"ambalaj_kalemleri":[],"filament_id","gram","baski_dk"},"uyarilar":[]}\n'
        "5) Son yanıtın tek satır olsun: `MAGAZA_HAZIR` veya `MAGAZA_EKSIK <neden>`."
    )


def paket_oku(sku: str, urunler_klasoru: Path | None = None) -> tuple[dict[str, Any] | None, list[str]]:
    """paket.json'ı okur ve doğrular. Dönüş: (paket, hatalar)."""
    yol = paket_yolu(sku, urunler_klasoru)
    if not yol.exists():
        return None, ["paket.json oluşmadı"]
    try:
        paket = json.loads(yol.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"paket.json bozuk: {exc}"]
    hatalar = [f"eksik alan: {a}" for a in ZORUNLU_ALANLAR if not paket.get(a)]
    try:
        fiyat = float(paket.get("satis_fiyati_tl") or 0)
        maliyet = float((paket.get("maliyet") or {}).get("birim_maliyet_tl") or 0)
        if fiyat <= 0:
            hatalar.append("satış fiyatı yok")
        elif maliyet and fiyat < maliyet:
            hatalar.append(f"satış fiyatı ({fiyat}) maliyetin ({maliyet}) altında")
    except (TypeError, ValueError):
        hatalar.append("fiyat sayı değil")
    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    for g in paket.get("gorseller") or []:
        if not (kok / g).exists():
            hatalar.append(f"görsel yok: {g}")
    beklenen = renk_varyantlari(sku, urunler_klasoru)
    gelen = paket.get("varyantlar") or []
    if beklenen and [v.get("deger") for v in gelen] != [v["deger"] for v in beklenen]:
        hatalar.append("renk varyantları urun.yaml ile uyuşmuyor")
    for v in gelen:
        for g in v.get("gorseller") or []:
            if not (kok / g).exists():
                hatalar.append(f"varyant görseli yok: {g}")
    return paket, hatalar


def onizleme_metni(paket: dict[str, Any]) -> str:
    m = paket.get("maliyet") or {}
    satirlar = [
        f"🛒 *Mağaza paketi hazır* — `{paket.get('sku')}`",
        f"*{paket.get('baslik')}*",
        f"• *Satış fiyatı:* `{paket.get('satis_fiyati_tl')} TL` (kargo hariç)",
        f"• *Birim maliyet:* `{m.get('birim_maliyet_tl')} TL` • *Başa baş:* `{m.get('basa_bas_tl')} TL` "
        f"• *ERP önerisi:* `{m.get('erp_onerilen_tl')} TL`",
        f"• *Fire:* `%{m.get('fire_yuzde')}` • *Ambalaj:* `{m.get('ek_malzeme_tl')} TL` • *{m.get('gram')} g*",
        f"• *Renkler:* {', '.join(v.get('deger', '') for v in paket.get('varyantlar') or []) or 'tek renk'}",
        f"• *Görsel:* `{len(paket.get('gorseller') or [])}` • *Hazırlık:* `{paket.get('hazirlik_suresi_gun')} gün`",
        f"• *Etiketler:* {', '.join(paket.get('etiketler') or [])[:200]}",
    ]
    karar = paket.get("fiyat_karari") or {}
    if karar:
        pz = karar.get("pazar") or {}
        satirlar.append("")
        satirlar.append("💹 *Fiyat kararı*")
        if pz:
            satirlar.append(f"• Pazar bandı: `{pz.get('alt', 0):.0f}–{pz.get('ust', 0):.0f} TL` • medyan "
                            f"`{pz.get('medyan', 0):.0f} TL` ({pz.get('ornek')} benzer ürün)")
        satirlar.append(f"• Önerilen: `{karar.get('onerilen_tl')} TL`"
                        + (f" • marj %{karar['marj_yuzde']}" if karar.get("marj_yuzde") is not None else ""))
        satirlar.append(f"• {karar.get('gerekce', '')}")
        if karar.get("secim") == "PATRON":
            satirlar.append(f"• ✅ Senin seçimin: `{karar.get('secilen_tl')} TL`")
    rv = paket.get("metin_review") or {}
    if rv:
        satirlar.append(f"• *Metin:* editör review'u ✅ ({rv.get('kelime')} kelime, {rv.get('tarih')})")
    else:
        satirlar.append("• *Metin:* ⚠️ editör review'u yok — yüklenemez")
    for u in paket.get("uyarilar") or []:
        satirlar.append(f"⚠️ {u}")
    satirlar.append("\nFiyatı aşağıdan seç (✅ = geçerli fiyat), sonra *🚀 Mağazaya Yükle* — ürün İkas'ta "
                    "*yayında* olarak oluşturulur.")
    return "\n".join(satirlar)


def yukle_istemi(sku: str, urunler_klasoru: Path | None = None) -> str:
    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    return (
        f"Görev: `{sku}` ürününü İkas mağazasına yükle. Patron Telegram'da '🚀 Mağazaya Yükle'ye bastı; "
        "bu, ürünü yayına alma onayıdır.\n"
        f"Kaynak (TEK GERÇEK): `{kok}/magaza/paket.json`. İçerikleri BİREBİR kopyala; metni yeniden yazma, "
        "fiyatı değiştirme, alan uydurma.\n"
        "1) Claude in Chrome araçlarını tek ToolSearch ile yükle (file_upload dahil); tabs_context_mcp; YENİ sekme aç.\n"
        "2) İkas yönetim paneline git (Patronun açık oturumu). Oturum kapalıysa veya giriş/şifre/doğrulama "
        "isteniyorsa DUR → `MAGAZA_YUKLEME_HATA giriş gerekli`.\n"
        "3) Ürünler → Yeni ürün. Önce aynı slug/başlıkta ürün var mı ara; varsa YENİSİNİ AÇMA, "
        "`MAGAZA_YUKLEME_HATA aynı ürün zaten var: <link>` yaz.\n"
        "4) Doldur: ad=baslik, açıklama=aciklama_html (HTML/kaynak kod modunda yapıştır), satış fiyatı=satis_fiyati_tl "
        "(indirimli_fiyat_tl null ise boş bırak), kategori (yoksa boş bırak, yeni kategori AÇMA), etiketler, "
        "SEO: slug/meta başlık/meta açıklama. Stok: stok takibi kapatılabiliyorsa kapat; kapatılamıyorsa "
        "DUR → `MAGAZA_YUKLEME_HATA stok ayarı için Patron kararı gerekli`.\n"
        "   VARYANT: `varyantlar` doluysa 'Renk' seçeneği oluştur, her `deger` için bir varyant aç (aynı fiyat), "
        "her varyanta kendi `gorseller`ini yükle. Boşsa varyantsız tek ürün.\n"
        + (f"5) GÖRSELLER: `{kok}/magaza/gorseller.json` dosyasındaki HAZIRLANMIŞ kare (2048 px) dosyaları kullan — "
           "paket.json'daki ham görselleri DEĞİL. `gorseller` sırasıyla yükle (mutlak yol: "
           f"`{kok}/<dosya>`), ilk görsel kapak olsun; panel alternatif metin (alt) alanı sunuyorsa her görsele "
           "`alt` değerini yaz. Varyant görselleri için aynı dosyadaki `varyantlar` listesini kullan.\n"
           if (kok / "magaza" / "gorseller.json").exists() else
           f"5) Görselleri `gorseller` sırasıyla yükle (mutlak yol: `{kok}/<göreli yol>`); ilk görsel kapak olsun.\n")
        + "6) Kaydet ve ürünü yayında (aktif) yap. Ödeme, abonelik, tema veya ayar ekranlarında hiçbir şeyi onaylama.\n"
        f"7) Ürün sayfasının ekran görüntüsünü al ve `{kok}/magaza/ikas-ekran.png` olarak kaydet "
        "(save_to_disk ile alınan yolu buraya kopyala); mağaza ürün linkini ve yönetim paneli linkini al.\n"
        f"8) `{kok}/magaza/yukleme.json` yaz: "
        '{"durum":"YUKLENDI","urun_linki","panel_linki","tarih","notlar":[]}. Sekmeyi kapat.\n'
        "9) Son satır: `MAGAZA_YUKLENDI <urun_linki>` veya `MAGAZA_YUKLEME_HATA <neden>`. "
        "Aynı başarısız adımı 3 kereden fazla deneme."
    )


def yukleme_oku(sku: str, urunler_klasoru: Path | None = None) -> dict[str, Any] | None:
    yol = (urunler_klasoru or URUNLER_KLASORU) / sku / "magaza" / "yukleme.json"
    if not yol.exists():
        return None
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def sayfa_bilgisi(html: str) -> dict[str, Any]:
    """İkas ürün sayfasından (JSON-LD Product + <title>) yayındaki bilgileri çıkarır."""
    import re

    bilgi: dict[str, Any] = {"ad": None, "baslik": None, "gorsel": 0, "fiyatlar": [], "teklif": 0, "stokta": None}
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if m:
        bilgi["baslik"] = re.sub(r"\s+", " ", m.group(1)).strip()
    for blok in re.findall(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", html, re.S):
        try:
            d = json.loads(blok)
        except json.JSONDecodeError:
            continue
        for u in d if isinstance(d, list) else [d]:
            if not isinstance(u, dict) or u.get("@type") != "Product":
                continue
            bilgi["ad"] = u.get("name")
            g = u.get("image")
            bilgi["gorsel"] = len(g) if isinstance(g, list) else (1 if g else 0)
            teklifler = u.get("offers") or []
            teklifler = teklifler if isinstance(teklifler, list) else [teklifler]
            bilgi["teklif"] = len(teklifler)
            bilgi["fiyatlar"] = sorted({float(t.get("price") or 0) for t in teklifler if t.get("price")})
            bilgi["stokta"] = any("InStock" in str(t.get("availability")) for t in teklifler)
    return bilgi


def yukleme_farklari(paket: dict[str, Any], bilgi: dict[str, Any], gorsel_sayisi: int | None = None) -> list[str]:
    """Yayındaki sayfa ile paket.json arasındaki farklar (boşsa birebir)."""
    f: list[str] = []
    if not bilgi.get("ad"):
        return ["Sayfada ürün verisi (JSON-LD Product) bulunamadı — ürün yayında değil veya link yanlış."]
    if str(bilgi["ad"]).strip() != str(paket.get("baslik") or "").strip():
        f.append(f"Ad farklı: sayfada '{bilgi['ad']}', pakette '{paket.get('baslik')}'.")
    meta = str(paket.get("meta_baslik") or "").strip()
    if meta and bilgi.get("baslik") and meta not in bilgi["baslik"]:
        f.append(f"SEO başlığı farklı: sayfada '{bilgi['baslik']}', pakette '{meta}'.")
    fiyat = float(paket.get("satis_fiyati_tl") or 0)
    if fiyat and (not bilgi["fiyatlar"] or abs(min(bilgi["fiyatlar"]) - fiyat) > 0.01):
        f.append(f"Fiyat farklı: sayfada {bilgi['fiyatlar'] or 'yok'}, pakette {fiyat:.2f} TL.")
    beklenen_g = gorsel_sayisi if gorsel_sayisi is not None else len(paket.get("gorseller") or [])
    if bilgi["gorsel"] < beklenen_g:
        f.append(f"Görsel eksik: sayfada {bilgi['gorsel']}, beklenen {beklenen_g}.")
    varyant = len(paket.get("varyantlar") or [])
    if varyant > 1 and bilgi["teklif"] < varyant:
        f.append(f"Varyant eksik: sayfada {bilgi['teklif']} seçenek, beklenen {varyant} renk.")
    if bilgi.get("stokta") is False:
        f.append("Sayfa ürünü stokta değil gösteriyor (sipariş alınamaz).")
    return f


def yukleme_dogrula(sku: str, urunler_klasoru: Path | None = None) -> dict[str, Any]:
    """Yayındaki ürün sayfasını açıp paket.json ile karşılaştırır; sonucu yukleme.json'a ekler."""
    import urllib.request

    kok = (urunler_klasoru or URUNLER_KLASORU) / sku
    paket, _ = paket_oku(sku, urunler_klasoru)
    kayit = yukleme_oku(sku, urunler_klasoru) or {}
    link = str(kayit.get("urun_linki") or "")
    if not (paket and link.startswith("http")):
        return {"tamam": False, "farklar": ["paket veya ürün linki yok"]}
    try:
        istek = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0 (WorkbenchDogrulama)"})
        html = urllib.request.urlopen(istek, timeout=30).read().decode("utf-8", "ignore")
    except Exception as exc:  # noqa: BLE001
        return {"tamam": False, "farklar": [f"Sayfa açılamadı: {exc}"]}
    gj = kok / "magaza" / "gorseller.json"
    gorsel_sayisi = len(json.loads(gj.read_text(encoding="utf-8")).get("gorseller") or []) if gj.exists() else None
    bilgi = sayfa_bilgisi(html)
    farklar = yukleme_farklari(paket, bilgi, gorsel_sayisi)
    sonuc = {"tamam": not farklar, "farklar": farklar, "sayfa": bilgi}
    kayit["dogrulama"] = sonuc
    (kok / "magaza" / "yukleme.json").write_text(json.dumps(kayit, ensure_ascii=False, indent=2), encoding="utf-8")
    return sonuc
