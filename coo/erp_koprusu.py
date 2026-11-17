"""Open Workbench COO <-> Open Workbench ERP Köprüsü ve 4 Baskı Sonrası Muhasebe Motoru.

Baskı bittiğinde kullanıcının Telegram'dan seçtiği 4 senaryoyu (Hobi, İş: Numune,
İş: Sipariş, Hatalı/Fire) hem workbench-erp veritabanına hem de Obsidian raporlarına işler.
Ayrıca kritik stok uyarılarını denetler.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .ayar import BASKI_KAYITLARI_KLASORU, URUNLER_KLASORU, ayarlari_yukle
from .yazici import GcodeReferans


@dataclass
class BaskiMuhasebeSonucu:
    senaryo: str  # HOBI | IS_NUMUNE | IS_SIPARIS | FIRE
    basarili: bool
    baslik: str
    ozet_mesaj: str
    harcanan_gram: float = 0.0
    sure_dakika: int = 0
    tahmini_maliyet_tl: float = 0.0
    onerilen_satis_tl: float = 0.0
    ambalaj_listesi: list[str] = field(default_factory=list)
    kritik_stok_uyarilari: list[str] = field(default_factory=list)
    rapor_dosyasi: Path | None = None


class ErpKoprusu:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or ayarlari_yukle().erp_url).rstrip("/")

    def _sync_istek(self, metot: str, yol: str, veri: dict[str, Any] | None = None, zaman_asimi: float = 12.0) -> Any:
        url = f"{self.base_url}{yol}"
        govde = json.dumps(veri).encode("utf-8") if veri is not None else None
        basliklar = {"Accept": "application/json"}
        if govde is not None:
            basliklar["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=govde, headers=basliklar, method=metot)
        with urllib.request.urlopen(req, timeout=zaman_asimi) as r:
            ham = r.read().decode("utf-8")
            return json.loads(ham) if ham else {}

    async def _get(self, yol: str) -> Any:
        return await asyncio.to_thread(self._sync_istek, "GET", yol, None, 10.0)

    async def _post(self, yol: str, veri: dict[str, Any]) -> Any:
        return await asyncio.to_thread(self._sync_istek, "POST", yol, veri, 15.0)

    async def _put(self, yol: str, veri: dict[str, Any]) -> Any:
        return await asyncio.to_thread(self._sync_istek, "PUT", yol, veri, 15.0)

    async def makineler(self) -> list[dict[str, Any]]:
        try:
            return await self._get("/api/machines")
        except Exception:
            return []

    async def filamentler(self) -> list[dict[str, Any]]:
        try:
            return await self._get("/api/filaments")
        except Exception:
            return []

    async def malzemeler(self) -> list[dict[str, Any]]:
        try:
            return await self._get("/api/materials")
        except Exception:
            return []

    async def urunler(self) -> list[dict[str, Any]]:
        try:
            return await self._get("/api/products")
        except Exception:
            return []

    async def kuyruk(self) -> list[dict[str, Any]]:
        try:
            return await self._get("/api/queue")
        except Exception:
            return []

    async def makine_yuklu_filament_bul(self, makine_id: int = 1) -> dict[str, Any] | None:
        makineler = await self.makineler()
        filamentler = await self.filamentler()
        yuklu_id = None
        for m in makineler:
            if int(m.get("id", 0)) == makine_id:
                yuklu_id = m.get("loaded_filament_id")
                break
        if yuklu_id:
            for f in filamentler:
                if int(f.get("id", 0)) == int(yuklu_id):
                    return f
        return filamentler[0] if filamentler else None

    async def makine_filament_degistir(self, filament_id: int, makine_id: int = 1) -> bool:
        try:
            await self._put(f"/api/machines/{makine_id}/yuklu-filament", {"filament_id": filament_id})
            return True
        except Exception:
            return False

    async def ayarlar_ve_muafiyet(self) -> dict[str, Any]:
        """ERP ayarlarını ve Esnaf Vergi Muafiyeti (GVK 9/10) özetini getirir."""
        try:
            pano = await self._get("/api/dashboard")
            if isinstance(pano, dict) and (pano.get("settings") or pano.get("esnaf_muafiyeti_summary")):
                return {
                    "settings": pano.get("settings") or {},
                    "muafiyet": pano.get("esnaf_muafiyeti_summary") or {},
                }
        except Exception:
            pass
        try:
            ayar = await self._get("/api/settings")
            if isinstance(ayar, dict):
                return {
                    "settings": ayar.get("settings") or {},
                    "muafiyet": {},
                }
        except Exception:
            pass
        return {"settings": {}, "muafiyet": {}}

    @staticmethod
    def _esnaf_muafiyet_satirlari(
        ayar_bilgi: dict[str, Any],
        brut_satis_tl: float,
        stopaj_tl: float | None = None,
        banka_net_tl: float | None = None,
        net_kar_tl: float | None = None,
    ) -> list[str]:
        """Telegram özeti için Esnaf Muafiyeti (%4 stopaj, net banka girişi ve yıllık sınır) satırlarını kurar."""
        ayar = ayar_bilgi.get("settings") or {}
        muaf = ayar_bilgi.get("muafiyet") or {}
        aktif = bool(muaf.get("enabled") if "enabled" in muaf else ayar.get("esnaf_muafiyeti_enabled"))
        if not aktif:
            return []

        stopaj_oran = float(muaf.get("stopaj_rate_percent") or ayar.get("bank_withholding_rate_percent") or 4.0)
        komisyon_oran = float(ayar.get("commission_rate_percent") or 0.0)
        if stopaj_tl is None or banka_net_tl is None:
            kom_tl = brut_satis_tl * (komisyon_oran / 100.0)
            bankaya_gelen = brut_satis_tl - kom_tl
            stopaj_tl = round(bankaya_gelen * (stopaj_oran / 100.0), 2)
            banka_net_tl = round(bankaya_gelen - stopaj_tl, 2)

        satirlar = [
            f"• **Esnaf Muafiyeti (%{stopaj_oran:g} Stopaj):** `-{stopaj_tl:.2f} TL` → Banka Net: `{banka_net_tl:.2f} TL`"
            + (f" • Net Kâr: `{net_kar_tl:.2f} TL`" if net_kar_tl is not None else "")
        ]
        yillik_sinir = float(muaf.get("annual_limit_tl") or ayar.get("esnaf_yillik_limit_tl") or 0.0)
        kalan = float(muaf.get("remaining_limit_tl") or yillik_sinir)
        if yillik_sinir > 0:
            satirlar.append(f"• **Yıllık Muafiyet Limiti:** Kalan `{kalan:,.0f} TL` / `{yillik_sinir:,.0f} TL`")
        return satirlar

    async def kritik_stok_kontrol(self) -> list[str]:
        """Kritik eşiğin altına düşen filament ve ambalaj/yardımcı malzemeleri listeler."""
        uyarilar: list[str] = []
        for f in await self.filamentler():
            kalan = float(f.get("remaining_weight_gr") or 0.0)
            esik = float(f.get("min_stock_alert_gr") or 200.0)
            if kalan <= esik:
                tip = f.get("material_type") or f.get("type") or ""
                renk = f.get("color_name") or f.get("color") or ""
                uyarilar.append(
                    f"🧵 Filament Azaldı: {f.get('brand', '')} {tip} {renk} "
                    f"— Kalan: {kalan:.0f}g (Kritik eşik: {esik:.0f}g)"
                )
        for m in await self.malzemeler():
            stok = float(m.get("stock_quantity") or 0.0)
            esik = float(m.get("min_stock_alert") or 5.0)
            if stok <= esik:
                uyarilar.append(
                    f"📦 Malzeme Azaldı: {m.get('name', '')} — Kalan: {stok:.0f} {m.get('unit', 'adet')} "
                    f"(Kritik eşik: {esik:.0f})"
                )
        return uyarilar

    async def baski_sonucu_isle(
        self,
        senaryo: str,
        ref: GcodeReferans,
        makine_id: int = 1,
    ) -> BaskiMuhasebeSonucu:
        """Baskı Sonrası Senaryolarını (HOBI, HEDIYE, IS_NUMUNE, IS_SIPARIS, FIRE) yürütür."""
        senaryo = senaryo.upper().strip()
        dakika = max(1, int(ref.tahmini_dakika or 60))
        saat_tam = dakika // 60
        dk_kalan = dakika % 60
        if ref.tahmini_gram and ref.tahmini_gram > 0:
            gram = max(1.0, round(ref.tahmini_gram, 1))
            gram_notu = ""
        else:
            # G-code adında gram yazmadığında 50g uydurmak yerine süreden muhafazakâr tahmin yap
            gram = max(2.0, round(dakika * 0.45, 1))
            gram_notu = " _(süreden tahmini)_"

        yuklu_fil = await self.makine_yuklu_filament_bul(makine_id)
        fil_id = int(yuklu_fil["id"]) if yuklu_fil else None
        fil_tip = (yuklu_fil.get("material_type") or yuklu_fil.get("type") or "") if yuklu_fil else ""
        fil_renk = (yuklu_fil.get("color_name") or yuklu_fil.get("color") or "") if yuklu_fil else ""
        fil_ad = (
            f"{yuklu_fil.get('brand', '')} {fil_tip} {fil_renk}".strip()
            if yuklu_fil
            else "Tanımsız Filament"
        )
        gr_maliyet = (
            float(
                yuklu_fil.get("cost_per_gram_tl")
                or yuklu_fil.get("price_per_gram")
                or (float(yuklu_fil.get("price_per_kg_tl") or 850.0) / 1000.0)
            )
            if yuklu_fil
            else 0.85
        )
        tahmini_fil_maliyet = round(gram * gr_maliyet, 2)
        ayar_bilgi = await self.ayarlar_ve_muafiyet() if senaryo in ("IS_NUMUNE", "IS_SIPARIS") else {"settings": {}, "muafiyet": {}}

        ambalaj_listesi: list[str] = []
        onerilen_satis = 0.0
        birim_maliyet = tahmini_fil_maliyet
        erp_notu = ""

        # --- SENARYO 1: HOBİ / KİŞİSEL BASKI ---
        if senaryo == "HOBI":
            if fil_id is not None:
                try:
                    await self._post(
                        "/api/orders",
                        {
                            "order_type": "WASTE",
                            "machine_id": makine_id,
                            "waste_hours": saat_tam,
                            "waste_minutes": dk_kalan,
                            "waste_filament_id": fil_id,
                            "waste_grams": gram,
                            "notes": f"[HOBI] Kişisel baskı (ticari ciroya dahil değil): {ref.ham_dosya_adi}",
                        },
                    )
                    erp_notu = f"ERP'den {gram:.0f}g ({fil_ad}) ve {dakika} dk makine süresi Hobi tüketimi olarak düşüldü."
                except Exception as e:
                    erp_notu = f"ERP kaydı sırasında uyarı: {e}"
            else:
                erp_notu = "ERP'de kayıtlı filament bulunamadığı için yalnızca yerel baskı defterine işlendi."

            baslik = "🏠 Hobi / Kişisel Baskı Kaydedildi"
            ozet = (
                f"• **Dosya:** `{ref.ham_dosya_adi}`\n"
                f"• **Harcanan Filament:** `{gram:.1f} g`{gram_notu} ({fil_ad})\n"
                f"• **Baskı Süresi:** `{saat_tam} sa {dk_kalan} dk`\n"
                f"• **Yaklaşık İç Maliyet:** `{tahmini_fil_maliyet:.2f} TL`\n"
                f"• **Muhasebe Durumu:** Ticari ciroya ve ürün kârlılığına **karıştırılmadı**. {erp_notu}"
            )

        # --- SENARYO 1b: HEDİYE / TANITIM BASKISI (pazarlama gideri, ciroya dahil değil) ---
        elif senaryo == "HEDIYE":
            if fil_id is not None:
                try:
                    await self._post(
                        "/api/orders",
                        {
                            "order_type": "WASTE",
                            "machine_id": makine_id,
                            "waste_hours": saat_tam,
                            "waste_minutes": dk_kalan,
                            "waste_filament_id": fil_id,
                            "waste_grams": gram,
                            "notes": f"[HEDIYE] Hediye / tanıtım baskısı (pazarlama gideri): "
                                     f"{ref.eslesen_sku or ref.ham_dosya_adi}",
                        },
                    )
                    erp_notu = (f"ERP'den {gram:.0f}g ({fil_ad}) ve {dakika} dk makine süresi `[HEDIYE]` etiketiyle "
                                "düşüldü.")
                except Exception as e:
                    erp_notu = f"ERP kaydı sırasında uyarı: {e}"
            else:
                erp_notu = "ERP'de kayıtlı filament bulunamadığı için yalnızca yerel baskı defterine işlendi."

            baslik = "🎁 Hediye / Tanıtım Baskısı Kaydedildi"
            ozet = (
                f"• **Ürün:** `{ref.eslesen_sku or ref.ham_dosya_adi}`\n"
                f"• **Harcanan Filament:** `{gram:.1f} g`{gram_notu} ({fil_ad})\n"
                f"• **Baskı Süresi:** `{saat_tam} sa {dk_kalan} dk`\n"
                f"• **Maliyet (pazarlama gideri):** `{tahmini_fil_maliyet:.2f} TL` (filament)\n"
                f"• **Muhasebe Durumu:** Satış değil; ciroya ve ürün kârlılığına **karıştırılmadı**. {erp_notu}"
            )

        # --- SENARYO 2: İŞ — NUMUNE / AR-GE BASKISI ---
        elif senaryo == "IS_NUMUNE":
            urunler = await self.urunler()
            hedef_urun = None
            for u in urunler:
                uid = int(u.get("product_id") or u.get("id") or 0)
                if ref.erp_urun_id and uid == ref.erp_urun_id:
                    hedef_urun = u
                    break
                if ref.eslesen_sku and str(u.get("sku", "")).lower() == ref.eslesen_sku.lower():
                    hedef_urun = u
                    break

            if hedef_urun and fil_id is not None:
                uid = int(hedef_urun.get("product_id") or hedef_urun.get("id") or 0)
                try:
                    guncel_veri = {
                        "sku": hedef_urun.get("sku") or ref.eslesen_sku,
                        "name": hedef_urun.get("name") or ref.urun_adi,
                        "category": hedef_urun.get("category") or "B2C - Dekoratif Vazo & Obje",
                        "machine_id": makine_id,
                        "print_time_hours_int": saat_tam,
                        "print_time_minutes_int": dk_kalan,
                        "target_margin_percent": float(hedef_urun.get("target_margin_percent") or 50.0),
                        "filaments": [{"filament_id": fil_id, "net_weight_gr": gram, "waste_rate_percent": 5.0}],
                        "materials": [
                            {
                                "material_id": bm["material_id"],
                                "quantity": bm["quantity"],
                                "waste_rate_percent": bm.get("waste_rate_percent", 0.0),
                            }
                            for bm in (hedef_urun.get("materials") or [])
                            if "material_id" in bm
                        ],
                    }
                    await self._put(f"/api/products/{uid}", guncel_veri)
                    erp_notu = f"Ürünün (ID #{uid}) BOM gramajı ({gram:.0f}g) ve süresi ({dakika} dk) ERP'de güncellendi."
                except Exception as e:
                    erp_notu = f"Ürün BOM güncelleme uyarısı: {e}"
            elif fil_id is not None:
                try:
                    yeni_sku = (ref.eslesen_sku or ref.temiz_ad[:24]).lower()
                    yeni_veri = {
                        "sku": yeni_sku,
                        "name": ref.urun_adi or ref.temiz_ad,
                        "category": "B2C - Dekoratif Vazo & Obje",
                        "machine_id": makine_id,
                        "print_time_hours_int": saat_tam,
                        "print_time_minutes_int": dk_kalan,
                        "target_margin_percent": 50.0,
                        "filaments": [{"filament_id": fil_id, "net_weight_gr": gram, "waste_rate_percent": 5.0}],
                        "materials": [],
                    }
                    olusan = await self._post("/api/products", yeni_veri)
                    ref.erp_urun_id = int(olusan.get("product_id") or olusan.get("id") or 0) or None
                    erp_notu = f"ERP'de yeni ürün ve BOM kartı açıldı (`{yeni_sku}`)."
                except Exception as e:
                    erp_notu = f"Yeni ürün BOM kaydı uyarısı: {e}"
            else:
                erp_notu = "ERP'de henüz filament tanımlı değil; numune verisi `urun.yaml` dosyasına işlendi."

            # Numune filament düşümü
            if fil_id is not None:
                try:
                    await self._post(
                        "/api/orders",
                        {
                            "order_type": "WASTE",
                            "machine_id": makine_id,
                            "waste_hours": saat_tam,
                            "waste_minutes": dk_kalan,
                            "waste_filament_id": fil_id,
                            "waste_grams": gram,
                            "notes": f"[AR-GE NUMUNE] İlk numune baskısı: {ref.eslesen_sku or ref.ham_dosya_adi}",
                        },
                    )
                except Exception:
                    pass

            # Güncel maliyeti ve B2C fiyatını ERP'den tekrar oku
            stopaj_tl: float | None = None
            banka_net_tl: float | None = None
            net_kar_tl: float | None = None
            for u in await self.urunler():
                uid = int(u.get("product_id") or u.get("id") or 0)
                if (ref.erp_urun_id and uid == ref.erp_urun_id) or (
                    ref.eslesen_sku and str(u.get("sku", "")).lower() == ref.eslesen_sku.lower()
                ):
                    b2c = u.get("b2c_pricing") or {}
                    maliyet_obj = u.get("cost_breakdown") or {}
                    birim_maliyet = float(u.get("production_cost_tl") or maliyet_obj.get("total_cost") or tahmini_fil_maliyet)
                    onerilen_satis = float(
                        b2c.get("final_sale_price_gross_tl")
                        or maliyet_obj.get("suggested_price")
                        or round(birim_maliyet * 2.5, 2)
                    )
                    if "bank_withholding_amount_tl" in b2c:
                        stopaj_tl = float(b2c["bank_withholding_amount_tl"])
                    if "bank_net_payout_tl" in b2c:
                        banka_net_tl = float(b2c["bank_net_payout_tl"])
                    if "net_profit_tl" in b2c:
                        net_kar_tl = float(b2c["net_profit_tl"])
                    break

            self._urun_yaml_muhasebe_guncelle(ref, gram, dakika, birim_maliyet, onerilen_satis)

            muaf_satirlari = (
                self._esnaf_muafiyet_satirlari(
                    ayar_bilgi,
                    onerilen_satis,
                    stopaj_tl=stopaj_tl,
                    banka_net_tl=banka_net_tl,
                    net_kar_tl=net_kar_tl,
                )
                if onerilen_satis > 0
                else []
            )
            muaf_blok = ("\n" + "\n".join(muaf_satirlari)) if muaf_satirlari else ""

            baslik = "🧪 İş: Numune Baskısı ve BOM Kaydedildi"
            ozet = (
                f"• **Ürün:** `{ref.urun_adi}` (`{ref.eslesen_sku or 'yeni-urun'}`)\n"
                f"• **Gerçekleşen BOM:** `{gram:.1f} g`{gram_notu} ({fil_ad}) • `{saat_tam} sa {dk_kalan} dk`\n"
                f"• **Birim Maliyet:** `{birim_maliyet:.2f} TL`\n"
                f"• **Önerilen Satış Fiyatı:** `{onerilen_satis:.2f} TL`{muaf_blok}"
                if onerilen_satis > 0
                else f"• **Ürün:** `{ref.urun_adi}`\n• **Gerçekleşen BOM:** `{gram:.1f} g`{gram_notu} • `{saat_tam} sa {dk_kalan} dk`"
            )
            ozet += (
                f"\n• **ERP Durumu:** {erp_notu}\n"
                f"• **Sonraki Adım:** Numune başarılıysa aşağıdan **🎬 Kliple Reels Üret** butonuna basabilir "
                f"veya ürünün videosunu gönderip *'bundan içerik üret'* diyebilirsiniz."
            )

        # --- SENARYO 3: İŞ — MÜŞTERİ SİPARİŞİ / STOK ÜRETİMİ ---
        elif senaryo == "IS_SIPARIS":
            kuyruk_listesi = await self.kuyruk()
            eslesen_emir = None
            for emir in kuyruk_listesi:
                if emir.get("status") in ("URETIMDE", "BEKLIYOR"):
                    if ref.erp_urun_id and int(emir.get("product_id") or 0) == ref.erp_urun_id:
                        eslesen_emir = emir
                        break

            siparis_sonucu: dict[str, Any] | None = None
            if eslesen_emir:
                try:
                    siparis_sonucu = await self._post(f"/api/queue/{eslesen_emir['id']}/tamamla", {})
                    erp_notu = f"Üretim emri `#{eslesen_emir['id']}` tamamlandı; BOM filament + ambalaj stoktan düşüldü."
                except Exception as e:
                    erp_notu = f"Kuyruk tamamlama uyarısı: {e}"
            elif ref.erp_urun_id:
                try:
                    siparis_sonucu = await self._post(
                        "/api/orders",
                        {
                            "order_type": "PRODUCTION",
                            "product_id": ref.erp_urun_id,
                            "machine_id": makine_id,
                            "quantity": 1,
                            "channel": "IKAS_B2C",
                            "notes": f"Baskı tamamlandı: {ref.ham_dosya_adi}",
                        },
                    )
                    erp_notu = "ERP'de üretim siparişi oluşturuldu ve BOM stoktan düşüldü."
                except Exception as e:
                    erp_notu = f"Sipariş kaydı uyarısı: {e}"
            else:
                erp_notu = "Ürün henüz ERP'de kayıtlı olmadığı için yerel sipariş defterine işlendi."

            # Ambalaj/BOM kontrol listesini ve fiyat/stopaj bilgisini çıkar
            brut_satis = 0.0
            stopaj_tl = None
            banka_net_tl = None
            net_kar_tl = None
            for u in await self.urunler():
                uid = int(u.get("product_id") or u.get("id") or 0)
                if (ref.erp_urun_id and uid == ref.erp_urun_id) or (
                    ref.eslesen_sku and str(u.get("sku", "")).lower() == ref.eslesen_sku.lower()
                ):
                    b2c = u.get("b2c_pricing") or {}
                    brut_satis = float(b2c.get("final_sale_price_gross_tl") or 0.0)
                    for bm in u.get("materials") or []:
                        m_ad = bm.get("material_name") or bm.get("name") or f"Malzeme #{bm.get('material_id')}"
                        miktar = bm.get("quantity", 1)
                        ambalaj_listesi.append(f"{miktar:g}x {m_ad}")
                    for grp in u.get("material_groups") or []:
                        g_ad = grp.get("group_name") or f"Grup #{grp.get('group_id')}"
                        ambalaj_listesi.append(f"{grp.get('quantity', 1):g}x {g_ad}")
                    break

            ord_obj = (
                siparis_sonucu.get("order")
                if isinstance(siparis_sonucu, dict) and isinstance(siparis_sonucu.get("order"), dict)
                else (siparis_sonucu if isinstance(siparis_sonucu, dict) else {})
            )
            if ord_obj and ord_obj.get("total_revenue_tl"):
                brut_satis = float(ord_obj["total_revenue_tl"])
                onerilen_satis = brut_satis
                if ord_obj.get("bank_withholding_amount_tl") is not None:
                    stopaj_tl = float(ord_obj["bank_withholding_amount_tl"])
                if ord_obj.get("bank_net_payout_tl") is not None:
                    banka_net_tl = float(ord_obj["bank_net_payout_tl"])
                if ord_obj.get("total_net_profit_tl") is not None:
                    net_kar_tl = float(ord_obj["total_net_profit_tl"])
                ayar_bilgi = await self.ayarlar_ve_muafiyet()

            if not ambalaj_listesi:
                ambalaj_listesi = ["1x Koruyucu Kraft Kutu", "1x Teşekkür / Bakım Kartı", "1x Kargo Etiketi"]

            muaf_satirlari = (
                self._esnaf_muafiyet_satirlari(
                    ayar_bilgi,
                    brut_satis,
                    stopaj_tl=stopaj_tl,
                    banka_net_tl=banka_net_tl,
                    net_kar_tl=net_kar_tl,
                )
                if brut_satis > 0
                else []
            )
            muaf_blok = ("\n" + "\n".join(muaf_satirlari)) if muaf_satirlari else ""
            satis_satiri = f"\n• **Sipariş Tutarı:** `{brut_satis:.2f} TL`" if brut_satis > 0 else ""

            baslik = "📦 İş: Sipariş Üretimi Tamamlandı"
            ambalaj_metni = "\n".join(f"  ▫️ {a}" for a in ambalaj_listesi)
            ozet = (
                f"• **Ürün:** `{ref.urun_adi}`\n"
                f"• **Tüketim:** `{gram:.1f} g`{gram_notu} ({fil_ad}) • `{saat_tam} sa {dk_kalan} dk`"
                f"{satis_satiri}{muaf_blok}\n"
                f"• **ERP Durumu:** {erp_notu}\n\n"
                f"📋 **Paketleme Kontrol Listesi (BOM):**\n{ambalaj_metni}"
            )

        # --- SENARYO 4: HATALI BASKI / FİRE ---
        else:
            senaryo = "FIRE"
            kuyruk_listesi = await self.kuyruk()
            uretimdeki = next((e for e in kuyruk_listesi if e.get("status") == "URETIMDE"), None)
            if uretimdeki:
                try:
                    await self._post(
                        f"/api/queue/{uretimdeki['id']}/hata",
                        {"gram": gram, "saat": saat_tam, "dakika": dk_kalan},
                    )
                    erp_notu = (
                        f"Üretim emri `#{uretimdeki['id']}` yeniden basılmak üzere `BEKLIYOR` durumuna alındı; "
                        f"`{gram:.0f}g` fire kaydedildi."
                    )
                except Exception as e:
                    erp_notu = f"Fire kaydı uyarısı: {e}"
            elif fil_id is not None:
                try:
                    await self._post(
                        "/api/orders",
                        {
                            "order_type": "WASTE",
                            "machine_id": makine_id,
                            "waste_hours": saat_tam,
                            "waste_minutes": dk_kalan,
                            "waste_filament_id": fil_id,
                            "waste_grams": gram,
                            "notes": f"[FIRE] Hatalı baskı: {ref.ham_dosya_adi}",
                        },
                    )
                    erp_notu = f"`{gram:.0f}g` ({fil_ad}) ve `{dakika} dk` ERP fire hesabına işlendi."
                except Exception as e:
                    erp_notu = f"ERP fire kaydı uyarısı: {e}"
            else:
                erp_notu = "Yerel fire defterine kaydedildi."

            baslik = "🗑️ Hatalı Baskı / Fire Kaydedildi"
            ozet = (
                f"• **Dosya:** `{ref.ham_dosya_adi}`\n"
                f"• **Fire Gramajı:** `{gram:.1f} g`{gram_notu} ({fil_ad})\n"
                f"• **Kaybedilen Süre:** `{saat_tam} sa {dk_kalan} dk`\n"
                f"• **Fire Maliyeti:** `{tahmini_fil_maliyet:.2f} TL`\n"
                f"• **ERP Durumu:** {erp_notu}"
            )

        kritik_uyarilar = await self.kritik_stok_kontrol()
        rapor_yolu = self._baski_raporu_yaz(senaryo, ref, gram, dakika, fil_ad, birim_maliyet, erp_notu)

        return BaskiMuhasebeSonucu(
            senaryo=senaryo,
            basarili=True,
            baslik=baslik,
            ozet_mesaj=ozet,
            harcanan_gram=gram,
            sure_dakika=dakika,
            tahmini_maliyet_tl=birim_maliyet,
            onerilen_satis_tl=onerilen_satis,
            ambalaj_listesi=ambalaj_listesi,
            kritik_stok_uyarilari=kritik_uyarilar,
            rapor_dosyasi=rapor_yolu,
        )

    def _urun_yaml_muhasebe_guncelle(
        self,
        ref: GcodeReferans,
        gram: float,
        dakika: int,
        birim_maliyet: float,
        onerilen_satis: float,
    ) -> None:
        if not ref.eslesen_sku:
            return
        yaml_yolu = URUNLER_KLASORU / ref.eslesen_sku / "urun.yaml"
        if not yaml_yolu.exists():
            return
        try:
            veri = yaml.safe_load(yaml_yolu.read_text(encoding="utf-8")) or {}
            veri.setdefault("uretim", {})
            veri["uretim"]["tahmini_gram"] = gram
            veri["uretim"]["tahmini_sure_dk"] = dakika
            veri.setdefault("muhasebe", {})
            veri["muhasebe"]["erp_urun_id"] = ref.erp_urun_id
            veri["muhasebe"]["birim_maliyet_tl"] = round(birim_maliyet, 2)
            if onerilen_satis > 0:
                veri["muhasebe"]["onerilen_satis_fiyati_tl"] = round(onerilen_satis, 2)
            veri["muhasebe"]["bom_islendi"] = True
            yaml_yolu.write_text(yaml.safe_dump(veri, allow_unicode=True, sort_keys=False), encoding="utf-8")
        except Exception:
            pass

    def _baski_raporu_yaz(
        self,
        senaryo: str,
        ref: GcodeReferans,
        gram: float,
        dakika: int,
        filament_ad: str,
        maliyet_tl: float,
        erp_notu: str,
    ) -> Path:
        simdi = dt.datetime.now()
        gun_str = simdi.strftime("%Y-%m-%d")
        saat_str = simdi.strftime("%H:%M")
        BASKI_KAYITLARI_KLASORU.mkdir(parents=True, exist_ok=True)
        dosya = BASKI_KAYITLARI_KLASORU / f"{gun_str}-baski-defteri.md"

        if not dosya.exists():
            dosya.write_text(
                f"# 🖨️ Günlük Baskı ve Muhasebe Defteri ({gun_str})\n\n"
                "| Saat | Senaryo | SKU / Ürün | Dosya | Gram | Süre (dk) | Filament | İç Maliyet (TL) | ERP Notu |\n"
                "|---|---|---|---|---:|---:|---|---:|---|\n",
                encoding="utf-8",
            )

        satir = (
            f"| {saat_str} | **{senaryo}** | `{ref.eslesen_sku or '-'}` {ref.urun_adi} "
            f"| `{ref.ham_dosya_adi}` | {gram:.1f}g | {dakika} dk | {filament_ad} "
            f"| {maliyet_tl:.2f} TL | {erp_notu} |\n"
        )
        with dosya.open("a", encoding="utf-8") as f:
            f.write(satir)
        return dosya
