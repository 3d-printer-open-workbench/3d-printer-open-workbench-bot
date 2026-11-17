"""Fatura / alım listesi → ERP stok girişi (Telegram).

Akış: Patron faturanın / alım listesinin fotoğrafını veya PDF'ini gönderir → finans ajanı (finance-tracker)
belgeyi okur, kalemleri ERP'deki filament / malzemelerle eşleştirir ve `alim.json` yazar (ERP'ye YAZMAZ) →
bot doğrular ve tabloyu Patrona gösterir → Patron "✅ ERP'ye İşle" derse: kalem ERP'de varsa alım girilir,
yoksa önce kalem oluşturulur sonra alım girilir. Her alım ERP'de `PurchaseRecord` olarak izlenir; birim
maliyet hareketli ağırlıklı ortalama ile güncellenir.

Birimler: filament miktarı GRAM, fiyatı TL/kg; malzeme miktarı kendi biriminde (adet/metre/set/gr), fiyatı
TL/birim. Fiyatlar KDV DAHİL (esnaf muafiyeti: KDV indirilemez → maliyete girer).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .ayar import MUHASEBE_KLASORU

ALIM_KLASORU = MUHASEBE_KLASORU / "Alimlar"
TOPLAM_TOLERANS = 0.03  # kalem toplamı ile fatura genel toplamı arasındaki izinli fark (%3; kargo/yuvarlama)
MALZEME_KATEGORILERI = ("ELEKTRIK", "AMBALAJ", "MONTAJ", "AKSESUAR", "DIGER")


def yeni_alim_klasoru() -> Path:
    k = ALIM_KLASORU / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    k.mkdir(parents=True, exist_ok=True)
    return k


def alim_istemi(klasor: Path, filamentler: list[dict], malzemeler: list[dict], not_: str = "") -> str:
    dosyalar = sorted(str(p) for p in klasor.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".pdf", ".webp"))
    fil = [{k: f.get(k) for k in ("id", "code", "brand", "material_type", "color_name", "color_hex", "spool_weight_gr",
                                  "price_per_kg_tl")} for f in filamentler]
    mal = [{k: m.get(k) for k in ("id", "code", "name", "category", "unit", "unit_cost_tl")} for m in malzemeler]
    return (
        "Görev: Patronun gönderdiği ALIM BELGESİNİ (fatura, e-arşiv, sipariş özeti veya elle yazılmış liste) oku ve "
        "ERP stok girişi için yapılandır. ERP'YE HİÇBİR ŞEY YAZMA, MCP alım/ekleme araçlarını ÇAĞIRMA — yalnızca "
        f"`{klasor}/alim.json` dosyasını yaz; Patron onaylayınca bot işler.\n"
        f"Belge dosyaları (Read ile aç; PDF'te tüm sayfalar): {json.dumps(dosyalar, ensure_ascii=False)}\n"
        + (f"Patronun notu: {not_}\n" if not_ else "")
        + "\nERP'deki mevcut FİLAMENTLER: " + json.dumps(fil, ensure_ascii=False)
        + "\nERP'deki mevcut MALZEMELER: " + json.dumps(mal, ensure_ascii=False) + "\n\n"
        "KURALLAR:\n"
        "1) Her satırı bir kaleme çevir. Kargo, hizmet bedeli, indirim satırları KALEM DEĞİLDİR; `fatura.kargo_tl` / "
        "`fatura.indirim_tl` alanlarına yaz. Okuyamadığın veya emin olmadığın değeri UYDURMA → null yaz ve "
        "`belirsiz` listesine ekle.\n"
        "2) tur: 3B yazıcı filamenti ise FILAMENT, diğer her şey (kutu, bant, LED, kablo, yağ, IPA, uç vb.) MALZEME.\n"
        "3) EŞLEŞTİRME: Mevcut listede aynı kalem varsa `eslesen_id` = o id. Filamentte marka + tür (PLA/Mat PLA/"
        "PETG/Silk…) + renk aynı olmalı; renk adı farklı yazılmış olabilir (Kemik≈Bej değil, dikkat). Emin "
        "değilsen eşleştirme yapma (eslesen_id=null) ve `not` alanına adayı yaz.\n"
        "4) Eşleşme yoksa `yeni` alanını doldur:\n"
        '   FILAMENT: {"code":"FIL-<MARKA>-<TUR>-<RENK>" (büyük harf, Türkçe karaktersiz),"brand","material_type",'
        '"color_name","color_hex":"#RRGGBB" (renge yakın tahmin),"spool_weight_gr":1000}\n'
        '   MALZEME: {"code":"<AMB|SRF|ELK|MNT|AKS>-<KISA-AD>","name","category":' + json.dumps(list(MALZEME_KATEGORILERI))
        + ',"unit":"adet|metre|set|gr"}\n'
        "5) MİKTAR ve FİYAT (KDV DAHİL — esnaf muafiyeti, KDV maliyete girer; belgede KDV hariç fiyat varsa KDV'yi "
        "ekle ve `kdv_eklendi_yuzde` yaz):\n"
        "   FILAMENT: adet = makara sayısı; miktar = adet × makara gramı (1 kg = 1000); birim_fiyat_tl = TL/kg "
        "(makara 1 kg değilse kg'a çevir).\n"
        "   MALZEME: miktar = birim cinsinden toplam (ör. 3 paket × 50 adet = 150 adet); birim_fiyat_tl = TL/birim.\n"
        "   toplam_tl = o satırın KDV dahil tutarı.\n"
        f"6) `{klasor}/alim.json` şeması:\n"
        '{"fatura":{"tedarikci","no","tarih":"YYYY-AA-GG","genel_toplam_tl","kargo_tl","indirim_tl","kdv_dahil":true,'
        '"belge_turu":"fatura|e-arsiv|siparis|liste"},'
        '"kalemler":[{"tur":"FILAMENT|MALZEME","aciklama":"belgedeki satır","eslesen_id":int|null,"yeni":{...}|null,'
        '"adet":sayı,"miktar":sayı,"birim":"gr|adet|metre|set","birim_fiyat_tl":sayı,"toplam_tl":sayı,'
        '"kdv_eklendi_yuzde":sayı|null,"not":""}],"belirsiz":[...]}\n'
        "7) Son satır: `ALIM_HAZIR <kalem sayısı>` veya okunamıyorsa `ALIM_HATA <neden>`."
    )


def alim_oku(klasor: Path) -> tuple[dict[str, Any] | None, list[str]]:
    yol = klasor / "alim.json"
    if not yol.exists():
        return None, ["alim.json oluşmadı"]
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"alim.json bozuk: {exc}"]
    return veri, []


def dogrula(veri: dict[str, Any], filamentler: list[dict], malzemeler: list[dict],
            onceki_alimlar: list[dict] | None = None) -> tuple[list[str], list[str]]:
    """(engeller, uyarilar). Engel varsa ERP'ye işlenmez."""
    engel: list[str] = []
    uyari: list[str] = []
    fil_id = {int(f["id"]) for f in filamentler}
    mal_id = {int(m["id"]) for m in malzemeler}
    kalemler = veri.get("kalemler") or []
    if not kalemler:
        engel.append("Belgede kalem bulunamadı.")
    toplam = 0.0
    for i, k in enumerate(kalemler, 1):
        ad = f"{i}. {str(k.get('aciklama') or '')[:40]}"
        tur = k.get("tur")
        if tur not in ("FILAMENT", "MALZEME"):
            engel.append(f"{ad}: tür belirsiz ({tur}).")
            continue
        try:
            miktar = float(k.get("miktar") or 0)
            fiyat = float(k.get("birim_fiyat_tl") or 0)
            toplam += float(k.get("toplam_tl") or 0)
        except (TypeError, ValueError):
            engel.append(f"{ad}: miktar/fiyat sayı değil.")
            continue
        if miktar <= 0:
            engel.append(f"{ad}: miktar yok.")
        if fiyat <= 0:
            engel.append(f"{ad}: birim fiyat yok.")
        eid = k.get("eslesen_id")
        if eid is not None:
            if int(eid) not in (fil_id if tur == "FILAMENT" else mal_id):
                engel.append(f"{ad}: eşleşen ERP kaydı #{eid} bulunamadı.")
        else:
            yeni = k.get("yeni") or {}
            gerekli = ("code", "brand", "material_type", "color_name") if tur == "FILAMENT" else ("code", "name")
            eksik = [g for g in gerekli if not yeni.get(g)]
            if eksik:
                engel.append(f"{ad}: yeni kalem için eksik alan {eksik}.")
            if tur == "MALZEME" and str(yeni.get("category", "DIGER")).upper() not in MALZEME_KATEGORILERI:
                uyari.append(f"{ad}: kategori '{yeni.get('category')}' → DIGER yapılacak.")
        if tur == "FILAMENT" and fiyat and not 150 <= fiyat <= 6000:
            uyari.append(f"{ad}: {fiyat:.0f} TL/kg olağan dışı — kg'a çevrim doğru mu?")
        if tur == "FILAMENT" and miktar and miktar < 100:
            uyari.append(f"{ad}: {miktar} gr — makara sayısı mı yazıldı? (gram olmalı)")
        if fiyat and miktar and k.get("toplam_tl"):
            hesap = miktar / 1000 * fiyat if tur == "FILAMENT" else miktar * fiyat
            if abs(hesap - float(k["toplam_tl"])) > max(2.0, 0.03 * float(k["toplam_tl"])):
                uyari.append(f"{ad}: miktar×fiyat ({hesap:.2f}) satır toplamıyla ({k['toplam_tl']}) uyuşmuyor.")
    f = veri.get("fatura") or {}
    try:
        genel = float(f.get("genel_toplam_tl") or 0)
        ek = float(f.get("kargo_tl") or 0) - float(f.get("indirim_tl") or 0)
    except (TypeError, ValueError):
        genel, ek = 0.0, 0.0
    if genel and toplam and abs(toplam + ek - genel) > TOPLAM_TOLERANS * genel:
        uyari.append(f"Kalemler {toplam:.2f} + kargo/indirim {ek:.2f} ≠ genel toplam {genel:.2f} TL.")
    no = str(f.get("no") or "").strip()
    if no and any(str(a.get("invoice_no") or "") == no for a in (onceki_alimlar or [])):
        engel.append(f"Fatura {no} daha önce ERP'ye işlenmiş — çift giriş engellendi.")
    for b in veri.get("belirsiz") or []:
        uyari.append(f"Belirsiz: {b}")
    return engel, uyari


def ozet_metni(veri: dict[str, Any], filamentler: list[dict], malzemeler: list[dict],
               engel: list[str], uyari: list[str]) -> str:
    f = veri.get("fatura") or {}
    fil = {int(x["id"]): x for x in filamentler}
    mal = {int(x["id"]): x for x in malzemeler}
    s = [f"🧾 *Alım belgesi okundu* — {f.get('tedarikci') or '?'} · {f.get('no') or 'no yok'} · {f.get('tarih') or '?'}"]
    for i, k in enumerate(veri.get("kalemler") or [], 1):
        tur = k.get("tur")
        eid = k.get("eslesen_id")
        if eid is not None:
            x = (fil if tur == "FILAMENT" else mal).get(int(eid)) or {}
            hedef = (f"#{eid} {x.get('brand', '')} {x.get('material_type', '')} {x.get('color_name', '')}".strip()
                     if tur == "FILAMENT" else f"#{eid} {x.get('name', '')}")
            islem = "➕ stok"
        else:
            y = k.get("yeni") or {}
            hedef = (f"{y.get('brand', '')} {y.get('material_type', '')} {y.get('color_name', '')}".strip()
                     if tur == "FILAMENT" else str(y.get("name", "")))
            islem = "🆕 yeni kalem"
        birim = "TL/kg" if tur == "FILAMENT" else f"TL/{k.get('birim') or 'adet'}"
        miktar = (f"{float(k.get('miktar') or 0) / 1000:g} kg" if tur == "FILAMENT"
                  else f"{float(k.get('miktar') or 0):g} {k.get('birim') or 'adet'}")
        s.append(f"{i}. {islem} *{hedef[:45]}* — {miktar} × {float(k.get('birim_fiyat_tl') or 0):.2f} {birim} "
                 f"= `{float(k.get('toplam_tl') or 0):.2f} TL`")
    s.append(f"*Genel toplam:* `{f.get('genel_toplam_tl')}` TL (KDV dahil)"
             + (f" · kargo `{f.get('kargo_tl')}`" if f.get("kargo_tl") else ""))
    s += [f"⛔ {e}" for e in engel] + [f"⚠️ {u}" for u in uyari]
    s.append("\n_Onaylarsan: eşleşenlerin stoğu artar ve maliyeti ağırlıklı ortalamayla güncellenir; yeniler "
             "oluşturulur. Her satır ERP'de alım kaydı olarak saklanır._" if not engel
             else "\n_Engel giderilmeden ERP'ye işlenmez. Notla yeniden okut veya ERP'de düzelt._")
    return "\n".join(s)


def _istek(erp_url: str, yol: str, govde: dict | None = None) -> Any:
    istek = urllib.request.Request(f"{erp_url}{yol}", method="POST" if govde is not None else "GET",
                                   data=json.dumps(govde).encode() if govde is not None else None,
                                   headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(istek, timeout=20) as r:
        return json.loads(r.read().decode())


def uygula(veri: dict[str, Any], erp_url: str, kaynak: str = "telegram") -> list[dict[str, Any]]:
    """Onaylanmış alımı ERP'ye işler. Her kalem için sonuç: {kalem, durum, id, hata}."""
    f = veri.get("fatura") or {}
    ortak = {"tedarikci": f.get("tedarikci"), "fatura_no": f.get("no"), "fatura_tarihi": f.get("tarih"),
             "kaynak": kaynak}
    sonuc = []
    for k in veri.get("kalemler") or []:
        tur, eid = k["tur"], k.get("eslesen_id")
        try:
            yeni_kalem = eid is None
            if yeni_kalem:
                y = k.get("yeni") or {}
                if tur == "FILAMENT":
                    kayit = _istek(erp_url, "/api/filaments", {
                        "code": y["code"], "brand": y["brand"], "material_type": y["material_type"],
                        "color_name": y["color_name"], "color_hex": y.get("color_hex") or "#9CA3AF",
                        "price_per_kg_tl": float(k["birim_fiyat_tl"]),
                        "spool_weight_gr": float(y.get("spool_weight_gr") or 1000), "remaining_weight_gr": 0})
                else:
                    kat = str(y.get("category") or "DIGER").upper()
                    kayit = _istek(erp_url, "/api/materials", {
                        "code": y["code"], "name": y["name"],
                        "category": kat if kat in MALZEME_KATEGORILERI else "DIGER",
                        "unit": y.get("unit") or k.get("birim") or "adet",
                        "unit_cost_tl": float(k["birim_fiyat_tl"]), "stock_quantity": 0,
                        "supplier": f.get("tedarikci")})
                eid = int(kayit["id"])
            yol = f"/api/filaments/{eid}/alim" if tur == "FILAMENT" else f"/api/materials/{eid}/alim"
            r = _istek(erp_url, yol, {"miktar": float(k["miktar"]), "birim_fiyat_tl": float(k["birim_fiyat_tl"]),
                                      "yeni_kalem": yeni_kalem, **ortak})
            sonuc.append({"kalem": k.get("aciklama"), "durum": "YENI" if yeni_kalem else "STOK", "id": eid,
                          "stok_sonra": (r.get("filament") or r.get("malzeme") or {}).get(
                              "remaining_weight_gr" if tur == "FILAMENT" else "stock_quantity")})
        except (urllib.error.URLError, KeyError, ValueError, TypeError) as exc:
            sonuc.append({"kalem": k.get("aciklama"), "durum": "HATA", "id": eid, "hata": str(exc)[:200]})
    return sonuc


def sonuc_metni(sonuc: list[dict[str, Any]]) -> str:
    isaret = {"YENI": "🆕", "STOK": "➕", "HATA": "❌"}
    satir = [f"{isaret[s['durum']]} {str(s['kalem'])[:45]} → #{s['id']}"
             + (f" · stok {s['stok_sonra']:g}" if s.get("stok_sonra") is not None else "")
             + (f" · {s['hata']}" if s.get("hata") else "") for s in sonuc]
    hata = sum(s["durum"] == "HATA" for s in sonuc)
    return ("✅ *ERP'ye işlendi*" if not hata else f"⚠️ *{hata} kalem işlenemedi*") + "\n" + "\n".join(satir)


def aciklama_alim_mi(aciklama: str) -> bool:
    return bool(re.match(r"^\s*/?(fatura|al[ıi]m|filament|malzeme)\b", aciklama or "", flags=re.I))
