"""İşletmelere (B2B) teklif: Telegram talebi → gerçek model + dilimleme → ERP fiyatı → Teknik Poster PDF.

Akış:
1. Patron talebi yazar (müşteri, ürünler, ölçü, adet, renk…).
2. Teklif ajanı (Sonnet 5.5) her kalemi GERÇEK modele çevirir — özel yazı/tabela/QR için `workbench-studio`
   (Kaligraf, qr_plaque, nameplate…), katalog ürünü için mevcut STL — ve `python3 -m coo.orca_dilim dilimle-stl`
   ile gram/süreyi ölçer. FİYAT HESAPLAMAZ; `teklif.json` yazar.
3. Opus 5.5 denetimi: talep ↔ kalemler, ölçü, parça sayısı, montaj malzemesi, gram/süre tutarlılığı; düzeltir.
4. Bot fiyatı ERP'nin teklif hesaplayıcısıyla (`/api/quotes/calculate`, kayıtlı) deterministik çıkarır:
   makine saati + filament (+%fire) + ek malzeme + tasarım bedeli, B2B marjı, adet indirimi (kurumsal kademe),
   esnaf muafiyeti stopajı, kargo.
5. Teknik Poster stilinde HTML → Chrome headless → PDF; Telegram'a özet + PDF. Müşteriye göndermek Patronun işi.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import math
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

from .ayar import MAGAZA_ADI, MAGAZA_ALAN_ADI, MUHASEBE_KLASORU, PROGRAMLAR_KLASORU

TEKLIF_KLASORU = MUHASEBE_KLASORU / "Teklifler"
FIRE_YUZDE = 5.0
GUNLUK_BASKI_SAAT = 16.0   # tek yazıcı, gece dahil gerçekçi doluluk
EK_HAZIRLIK_GUN = 2        # temizlik, montaj bandı, paketleme, kargoya teslim
GECERLILIK_GUN = 15


def yeni_teklif_klasoru() -> Path:
    k = TEKLIF_KLASORU / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    k.mkdir(parents=True, exist_ok=True)
    return k


def katalog(urunler_klasoru: Path) -> list[dict[str, Any]]:
    """B2B katalog ürünleri (PRN-B2B-*) — ajan katalogdan seçebilsin diye ad + STL listesi."""
    import yaml

    sonuc = []
    for k in sorted(urunler_klasoru.glob("PRN-B2B-*")):
        try:
            v = yaml.safe_load((k / "urun.yaml").read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            v = {}
        stl = sorted(str(p) for p in k.glob("model/**/*.stl"))[:30]
        sonuc.append({"sku": k.name, "ad": v.get("ad"), "stl": stl})
    return sonuc


def teklif_istemi(talep: str, klasor: Path, katalog_listesi: list[dict], malzemeler: list[dict],
                  revize: str = "") -> str:
    mal = [{k: m.get(k) for k in ("id", "code", "name", "category", "unit", "unit_cost_tl")} for m in malzemeler]
    return (
        f"Görev: İşletme (B2B) TEKLİFİ için ürün kalemlerini GERÇEK modele çevir ve ölç. FİYAT HESAPLAMA. "
        f"Çalışma klasörü: `{klasor}` (tüm STL/çıktılar burada).\n\n"
        f"PATRONUN TALEBİ:\n{talep}\n"
        + (f"\nREVİZE NOTU (önceki teklif `{klasor}/teklif.json` üzerinde düzelt): {revize}\n" if revize else "")
        + "\nKATALOG (hazır B2B ürünler): " + json.dumps(katalog_listesi, ensure_ascii=False)
        + "\nERP EK MALZEMELERİ: " + json.dumps(mal, ensure_ascii=False) + "\n\n"
        "ADIMLAR:\n"
        "1) Talebi kalemlere ayır. Eksik bilgi varsa (ölçü, adet, renk, yazı metni) MAKUL varsayım yap ve "
        "`varsayimlar`a yaz; kritik belirsizliği `sorular`a yaz (Patron müşteriye soracak).\n"
        "2) Her kalemin modeli:\n"
        "   - Özel yazı / duvar yazısı / tabela / logo yazısı → workbench-studio `make` ile Kaligraf "
        "(`kaligraf_flat` 2.5B duvar yazısı; `kaligraf_letters` 3B kutu harf). Önce `maker_generator_params` ile "
        "parametreleri öğren; istenen genişlik/yükseklik, kalınlık, font, `oversize_policy:\"split\"` (>250 mm "
        "parçala), montaj `mounting:[\"tape\"]` veya pim. Çıktı STL'lerini klasöre kopyala.\n"
        "   - QR standı / QR plaka → `qr_plaque` (montaj `stand`); isimlik → `nameplate`; diğer Studio üreteçleri.\n"
        "   - Katalogda birebir ürün varsa onun STL'lerini kullan.\n"
        "   - Hiçbiri uygun değilse kalemi `modellenemedi: true` işaretle (tahmini gram UYDURMA).\n"
        f"3) Ölç: `cd {PROGRAMLAR_KLASORU} && python3 -m coo.orca_dilim dilimle-stl <kategori> {klasor}/dilim <stl...>` "
        "→ JSON: toplam_gram, toplam_sure_sn (bir adet için TÜM parçalar). Kategori: harf (yazı/tabela), "
        "standart, dayanikli (yük taşıyan), cerceve. `hatali` boş değilse parçayı küçült/parçala ve tekrar ölç.\n"
        "4) Ek malzeme (birim başına): montaj bandı/pim, ambalaj — ERP listesinden id ile; listede yoksa adını ve "
        "tahmini birim maliyetini `ek_malzeme`ye `material_id:null` ile yaz ve `varsayimlar`a ekle.\n"
        "5) Tasarım/kurulum bedeli: yalnız özel logo çizimi gibi ek emek varsa `tasarim_ucreti_tl` (yoksa 0).\n"
        f"6) `{klasor}/teklif.json` yaz:\n"
        '{"musteri","proje","kalemler":[{"ad","aciklama","adet":int,"olcu":"G×Y×D mm","renk","kategori",'
        '"kaynak":"studio:<üreteç>|katalog:<sku>","stl":[yollar],"gram_birim","sure_sn_birim","parca_sayisi",'
        '"ek_malzeme":[{"material_id","ad","miktar","birim_tutar_tl"}],"tasarim_ucreti_tl":0,'
        '"gorsel":"varsa render/dims png yolu","modellenemedi":false}],"kargo_desi":sayı,"varsayimlar":[],'
        '"sorular":[]}\n'
        "7) Son satır: `TEKLIF_HAZIR <kalem sayısı>` veya `TEKLIF_HATA <neden>`. Yazıcıya iş gönderme."
    )


def denetim_istemi(talep: str, klasor: Path) -> str:
    return (
        "Görev: KALİTE DENETİMİ (Opus). Bir teklif ajanı aşağıdaki talep için ürün kalemlerini modelleyip ölçtü. "
        f"`{klasor}/teklif.json` dosyasını ve klasördeki STL/görselleri incele.\n\nTALEP:\n{talep}\n\n"
        "Kontrol et ve GEREKİRSE DÜZELT (dosyayı yerinde güncelle):\n"
        "- Talepteki her ürün kalem olarak var mı; adetler, ölçüler, renk, yazı metni (harf harf, Türkçe karakter) "
        "doğru mu?\n"
        "- gram_birim / sure_sn_birim gerçekten `coo.orca_dilim dilimle-stl` çıktısından mı; ölçüyle tutarlı mı "
        "(ör. 1 m yazı ~birkaç yüz gram; 10 g veya 10 kg ise yanlış)? Şüpheliyse yeniden ölç.\n"
        "- >250 mm parçalar bölünmüş mü, montaj malzemesi eklenmiş mi, varsayımlar makul ve açık mı?\n"
        "- Fiyat alanı EKLEME (fiyatı bot ERP'den hesaplar).\n"
        'Dosyaya `"denetim": {"sonuc": "ONAY|DUZELTILDI|RED", "notlar": [...]}` ekle.\n'
        "Son satır: `DENETIM_ONAY`, `DENETIM_DUZELTILDI <özet>` veya `DENETIM_RED <neden>`."
    )


def teklif_oku(klasor: Path) -> dict[str, Any] | None:
    yol = klasor / "teklif.json"
    try:
        return json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else None
    except json.JSONDecodeError:
        return None


def kalem_dogrula(t: dict[str, Any]) -> list[str]:
    hatalar = []
    if not t.get("kalemler"):
        hatalar.append("Teklifte kalem yok.")
    for i, k in enumerate(t.get("kalemler") or [], 1):
        if k.get("modellenemedi"):
            hatalar.append(f"{i}. {k.get('ad')}: modellenemedi — fiyat çıkarılamaz.")
            continue
        try:
            if int(k.get("adet") or 0) <= 0:
                hatalar.append(f"{i}. {k.get('ad')}: adet yok.")
            if float(k.get("gram_birim") or 0) <= 0 or float(k.get("sure_sn_birim") or 0) <= 0:
                hatalar.append(f"{i}. {k.get('ad')}: gram/süre ölçülmemiş.")
        except (TypeError, ValueError):
            hatalar.append(f"{i}. {k.get('ad')}: sayısal alan bozuk.")
    return hatalar


def indirim_kademesi(adet: int, kademeler: list[dict[str, Any]]) -> tuple[float, str]:
    for k in kademeler:
        if k.get("is_active", True) and int(k.get("min_quantity") or 0) <= adet <= int(k.get("max_quantity") or 10**9):
            return float(k.get("discount_percent") or 0), str(k.get("tier_name") or "")
    return 0.0, ""


def _erp(erp_url: str, yol: str, govde: dict | None = None) -> Any:
    istek = urllib.request.Request(f"{erp_url}{yol}", method="POST" if govde is not None else "GET",
                                   data=json.dumps(govde).encode() if govde is not None else None,
                                   headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(istek, timeout=30) as r:
        return json.loads(r.read().decode())


def fiyatla(t: dict[str, Any], erp_url: str, filament_id: int | None = None, kaydet: bool = True) -> dict[str, Any]:
    """Her kalemi ERP teklif hesaplayıcısıyla fiyatlar (kayıtlı); kargo ilk kaleme bir kez eklenir."""
    ayar = _erp(erp_url, "/api/settings")
    s = ayar.get("settings") or {}
    kademeler = ayar.get("b2b_tiers") or []
    marj = float(s.get("default_b2b_margin_percent") or s.get("default_target_margin_percent") or 30)
    kdv = bool(s.get("default_vat_enabled"))
    kargo = float(s.get("default_shipping_cost") or 0)
    satirlar, toplam, maliyet, kar = [], 0.0, 0.0, 0.0
    for i, k in enumerate(t.get("kalemler") or []):
        adet = int(k["adet"])
        sure_dk = math.ceil(float(k["sure_sn_birim"]) / 60)
        ek = sum(float(m.get("miktar") or 0) * float(m.get("birim_tutar_tl") or 0) for m in k.get("ek_malzeme") or [])
        indirim, kademe = indirim_kademesi(adet, kademeler)
        govde = {
            "customer_name": t.get("musteri") or "Kurumsal Müşteri", "project_title": f"{t.get('proje') or ''} — {k['ad']}"[:120],
            "quantity": adet, "print_hours_per_unit": sure_dk // 60, "print_minutes_per_unit": sure_dk % 60,
            "net_grams_per_unit": round(float(k["gram_birim"]), 2), "bom_waste_percent": FIRE_YUZDE,
            "extra_material_cost_per_unit_tl": round(ek, 2),
            "design_setup_fee_tl": float(k.get("tasarim_ucreti_tl") or 0),
            "shipping_total_tl": kargo if i == 0 else 0.0, "target_margin_percent": marj,
            "discount_percent": indirim, "vat_enabled": kdv, "vat_rate_percent": float(s.get("default_vat_rate_percent") or 20),
            "save_quote": kaydet,
        }
        if filament_id:
            govde["filament_id"] = filament_id
        r = _erp(erp_url, "/api/quotes/calculate", govde)
        p = r.get("pricing") or {}
        satir_toplam = float(p.get("final_sale_price_gross_tl") or 0)
        satirlar.append({"ad": k["ad"], "aciklama": k.get("aciklama", ""), "olcu": k.get("olcu", ""),
                         "renk": k.get("renk", ""), "adet": adet, "birim_tl": round(satir_toplam / adet, 2),
                         "toplam_tl": round(satir_toplam, 2), "indirim_yuzde": indirim, "kademe": kademe,
                         "sure_saat": round(float(k["sure_sn_birim"]) * adet / 3600, 1),
                         "gram": round(float(k["gram_birim"]) * adet), "teklif_id": r.get("saved_quote_id"),
                         "maliyet_tl": round(float(r.get("total_production_cost_tl") or 0), 2),
                         "gorsel": k.get("gorsel")})
        toplam += satir_toplam
        maliyet += float(r.get("total_production_cost_tl") or 0)
        kar += float(p.get("net_profit_tl") or 0)
    toplam_saat = sum(x["sure_saat"] for x in satirlar)
    teslim = math.ceil(toplam_saat / GUNLUK_BASKI_SAAT) + EK_HAZIRLIK_GUN
    return {"satirlar": satirlar, "genel_toplam_tl": round(toplam, 2), "maliyet_tl": round(maliyet, 2),
            "net_kar_tl": round(kar, 2), "kdv_dahil": kdv, "esnaf_muafiyeti": bool(s.get("esnaf_muafiyeti_enabled")),
            "kargo_tl": kargo, "marj_yuzde": marj, "toplam_baski_saat": round(toplam_saat, 1),
            "teslim_is_gunu": teslim, "marka": s.get("brand_name") or MAGAZA_ADI}


def _tl(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " TL"


def pdf_html(t: dict[str, Any], f: dict[str, Any], teklif_no: str) -> str:
    bugun = dt.date.today()
    e = html.escape
    satirlar = "".join(
        f"<tr><td class='kod'>{i:02d}</td><td><b>{e(s['ad'])}</b><br><span class='alt'>{e(s['aciklama'] or '')}"
        f"{' · ' + e(s['olcu']) if s['olcu'] else ''}{' · ' + e(s['renk']) if s['renk'] else ''}</span>"
        + (f"<br><span class='ind'>{e(s['kademe'])} adet indirimi %{s['indirim_yuzde']:g} uygulandı</span>"
           if s["indirim_yuzde"] else "")
        + f"</td><td class='s'>{s['adet']}</td><td class='s'>{_tl(s['birim_tl'])}</td><td class='s'>{_tl(s['toplam_tl'])}</td></tr>"
        for i, s in enumerate(f["satirlar"], 1))
    vergi = ("Fiyatlara KDV dahildir." if f["kdv_dahil"] else
             "Esnaf muafiyeti kapsamında KDV uygulanmamaktadır." if f["esnaf_muafiyeti"] else "Fiyatlara KDV dahil değildir.")
    varsayim = "".join(f"<li>{e(v)}</li>" for v in t.get("varsayimlar") or [])
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 0; }}
html {{ background:#F3EEE6; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
body {{ font-family: 'Inter','Noto Sans',sans-serif; color:#1E1E1E; background:#F3EEE6; font-size:10.5pt; margin:0; padding:16mm 15mm 22mm; }}
.ust {{ display:flex; justify-content:space-between; border-bottom:1px solid #1E1E1E; padding-bottom:6px;
        font-family:'Noto Sans Mono',monospace; font-size:8.5pt; letter-spacing:.06em; }}
h1 {{ font-weight:400; font-size:30pt; margin:18px 0 2px; letter-spacing:-.01em; }}
.mono {{ font-family:'Noto Sans Mono',monospace; font-size:8.5pt; color:#555; }}
.bilgi {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; margin:16px 0 18px; }}
.bilgi div {{ border-top:1px solid #1E1E1E; padding-top:4px; }}
.bilgi b {{ display:block; font-weight:600; margin-top:2px; }}
table {{ width:100%; border-collapse:collapse; }}
th {{ text-align:left; font-family:'Noto Sans Mono',monospace; font-size:8pt; font-weight:400; color:#555;
      border-bottom:1px solid #1E1E1E; padding:4px 6px; }}
td {{ border-bottom:1px solid #cfc7ba; padding:8px 6px; vertical-align:top; }}
.s {{ text-align:right; white-space:nowrap; }} .kod {{ font-family:'Noto Sans Mono',monospace; color:#B5603B; }}
.alt {{ color:#555; font-size:9pt; }} .ind {{ color:#4F7C7A; font-size:8.5pt; }}
.toplam {{ margin-top:12px; display:flex; justify-content:flex-end; gap:24px; align-items:baseline; }}
.toplam .t {{ font-size:20pt; }} .nokta {{ display:inline-block; width:8px; height:8px; border-radius:50%;
      background:#555; margin-right:6px; }} .ikinci {{ background:#555; }}
.not {{ margin-top:22px; font-size:9pt; color:#333; }} .not li {{ margin:2px 0; }}
.alt-bant {{ position:fixed; bottom:10mm; left:15mm; right:15mm; border-top:1px solid #1E1E1E; padding-top:5px;
      display:flex; justify-content:space-between; font-family:'Noto Sans Mono',monospace; font-size:8pt; }}
</style></head><body>
<div class="ust"><span>{e(f['marka'].upper())} STORE</span><span>İŞLETMELERE ÖZEL 3D BASKI / TEKLİF</span></div>
<h1>Fiyat Teklifi</h1><div class="mono">{e(teklif_no)} · {bugun.strftime('%d.%m.%Y')} · geçerlilik {GECERLILIK_GUN} gün</div>
<div class="bilgi"><div><span class="mono">MÜŞTERİ</span><b>{e(t.get('musteri') or '—')}</b></div>
<div><span class="mono">PROJE</span><b>{e(t.get('proje') or '—')}</b></div>
<div><span class="mono">TESLİM</span><b>≈ {f['teslim_is_gunu']} iş günü</b></div></div>
<table><tr><th>NO</th><th>ÜRÜN</th><th class="s">ADET</th><th class="s">BİRİM</th><th class="s">TUTAR</th></tr>{satirlar}</table>
<div class="toplam"><span class="mono"><span class="nokta"></span>GENEL TOPLAM</span><span class="t">{_tl(f['genel_toplam_tl'])}</span></div>
<div class="not"><span class="nokta ikinci"></span>{e(vergi)} Kargo dahildir. Ürünler mat PLA ile siparişe özel basılır;
renkler filament partisine göre hafif farklılık gösterebilir.
{('<ul>' + varsayim + '</ul>') if varsayim else ''}</div>
<div class="alt-bant"><span>{e(MAGAZA_ALAN_ADI)}</span><span>{e(teklif_no)}</span></div>
</body></html>"""


def pdf_uret(html_metin: str, hedef: Path) -> bool:
    """HTML → PDF (Chrome headless). Orca gibi Chrome da çalışma alanındaki dosyayı okur."""
    import tempfile

    hedef = hedef.resolve()
    kaynak = hedef.with_suffix(".html")
    kaynak.write_text(html_metin, encoding="utf-8")
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        return False
    with tempfile.TemporaryDirectory(prefix="workbench-pdf-") as profil:  # açık Chrome oturumuna dokunma
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={profil}",
                        f"--print-to-pdf={hedef}", kaynak.as_uri()], capture_output=True, text=True, timeout=90)
    return hedef.exists() and hedef.stat().st_size > 1000


def ozet_metni(t: dict[str, Any], f: dict[str, Any], teklif_no: str) -> str:
    s = [f"💼 *Teklif hazır* — `{teklif_no}`", f"*{t.get('musteri') or '—'}* · {t.get('proje') or ''}"]
    for x in f["satirlar"]:
        s.append(f"• {x['ad']} × {x['adet']} = `{_tl(x['toplam_tl'])}`"
                 + (f" (%{x['indirim_yuzde']:g} {x['kademe']})" if x["indirim_yuzde"] else "")
                 + f" · {x['gram']} g · {x['sure_saat']} sa")
    s.append(f"*Genel toplam:* `{_tl(f['genel_toplam_tl'])}` (kargo dahil{', KDV dahil' if f['kdv_dahil'] else ''})")
    s.append(f"Maliyet `{_tl(f['maliyet_tl'])}` · net kâr `{_tl(f['net_kar_tl'])}` · marj %{f['marj_yuzde']:g} · "
             f"baskı {f['toplam_baski_saat']} sa → teslim ≈ {f['teslim_is_gunu']} iş günü")
    den = t.get("denetim") or {}
    if den:
        s.append(f"🔎 Opus denetimi: *{den.get('sonuc')}*" + (" — " + "; ".join(den.get("notlar") or [])[:300]
                                                            if den.get("notlar") else ""))
    for q in t.get("sorular") or []:
        s.append(f"❓ {q}")
    s.append("_Maliyet/kâr satırı yalnız sana; PDF'te görünmez._")
    return "\n".join(s)[:3900]
