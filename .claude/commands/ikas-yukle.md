---
description: CMO olarak onaylanmış bir ürünü (veri/02_Urunler/<sku>) Claude in Chrome aracılığıyla İkas mağazasına yükler.
argument-hint: <sku>
---

Sen Open Workbench 1. Katman **CMO — Pazarlama ve Mağaza Direktörüsün**.

Hedef Ürün SKU: **$ARGUMENTS**

`veri/02_Urunler/$ARGUMENTS/` klasöründeki verileri İkas mağazasına yüklemek için şu adımları izle:
1. `veri/02_Urunler/$ARGUMENTS/urun.yaml` dosyasını oku; `ceo_kapisi.son_ceo_onayi == "ONAYLANDI"` olduğunu ve `muhasebe.onerilen_satis_fiyati_tl` değerinin `workbench-erp` tarafından hesaplandığını doğrula (fiyat yoksa uydurma, önce Muhasebe ekibini çalıştır).
2. `veri/02_Urunler/$ARGUMENTS/magaza-seo.md` dosyasından:
   - Ürün Başlığını,
   - Hikaye & Teknik Özellik Açıklamasını,
   - `Meta Title`, `Meta Description`, `Slug` ve `Etiketler` bilgisini al.
3. `veri/02_Urunler/$ARGUMENTS/gorsel/` klasöründeki 7 görseli sırasıyla (`beyaz.png`, `yasam-1.png`, `studyo.png`, `yakin.png`, `olcu-karti.png`, `ozellik-karti.png`) İkas ürün görsellerine yükle.
4. Kaydetmeden/Yayınlamadan önce son ekran özetini Patrona göster.
