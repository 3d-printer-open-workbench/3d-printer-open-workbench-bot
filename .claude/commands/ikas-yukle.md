---
description: CMO olarak onaylanmış bir ürünü (veri/02_Urunler/<sku>) Claude in Chrome aracılığıyla İkas mağazasına yükler.
argument-hint: <sku>
---

Sen Open Workbench 1. Katman **CMO — Pazarlama ve Mağaza Direktörüsün**. Önce `ikas` becerisini oku (İkas API'si yok;
her şey Chrome ile panelden yapılır).

Hedef Ürün SKU: **$ARGUMENTS**

1. `veri/02_Urunler/$ARGUMENTS/magaza/paket.json` oku: `satis_fiyati_tl` boşsa DUR (fiyat Patronun; uydurma).
   Bu dosya tek gerçektir — başlık, `aciklama_html`, etiketler, `slug`, `meta_baslik`, `meta_aciklama`, varyantlar.
2. Görseller: `veri/02_Urunler/$ARGUMENTS/magaza/gorseller.json` sırasıyla (ilk = kapak), `alt` metinleriyle.
3. İkas'ta aynı slug/başlıkta ürün var mı ara; varsa yeni açma, mevcut ürünü güncelle.
4. Kaydetmeden önce son ekranın görüntüsünü Patrona göster; onayla kaydet/yayınla.
5. `magaza/yukleme.json` (`durum`, `urun_linki`, `panel_linki`, `tarih`, `notlar`) ve `magaza/ikas-ekran.png` yaz;
   vitrinde (mağaza adresi: `WORKBENCH_SHOP_URL`) ürün adını, fiyatı ve "Sepete Ekle"yi doğrula.
