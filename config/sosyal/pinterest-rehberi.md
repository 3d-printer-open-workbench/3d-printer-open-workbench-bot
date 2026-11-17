# Pinterest Rehberi (ajanlar için — arayüz 2026-11-17'de doğrulandı)

Hesap: kendi Pinterest işletme hesabınız (`WORKBENCH_PINTEREST_URL`); mağaza alan adınızı Pinterest'te doğrulayın.
Paylaşım Patronun Chrome'undaki oturumla, **Claude in Chrome** ile yapılır (Postiz yok). Giriş/şifre isteyen bir ekran
çıkarsa **DUR** ve bildir; asla şifre girme. Her zaman yeni sekme aç, iş bitince kapat.

## Panolar (kategoriye göre)
| Mağaza kategorisi | Pano |
|---|---|
| Masa düzenleyiciler, standlar | Masa Düzenleyici ve Standlar \| 3D Baskı |
| Fotoğraf çerçeveleri | Fotoğraf Çerçeveleri \| 3D Baskı |
| Kişiye özel, isimlik, hediye | Kişiye Özel Hediye ve İsim Tabelaları |
| İşletmelere özel, duvar yazısı, tabela | İşletmelere Özel 3D Duvar Yazısı ve Tabela |
| Diğer dekor, vazo, saksı, figür, tütsülük | Dekoratif Objeler ve Ev Dekorasyonu |

## Pin içeriği
- **Görsel:** dikey (2:3 ya da 3:4). Öncelik: teknik poster (`gorsel/konsept/teknik_poster-3x4.png`) → kullanım görseli
  (`gorsel/kullanim-*.png`) → stüdyo krem fon karesi. Ürün görselde birebir gerçek olmalı.
- **Başlık (≤100 karakter):** ürünün aranan adı + ayırt edici özellik (ör. "Diz Çökmüş Samuray Tütsülük — Mat PLA 3D Baskı").
- **Açıklama (≤500, ilk 50 karakter en önemli):** 2–3 doğal anahtar kelime (ev dekorasyonu, masa düzeni, hediye…),
  ölçü/malzeme gerçeği (urun.yaml), tek çağrı ("<mağaza alan adı>'nda incele"). Uydurma iddia, indirim, yorum YOK.
- **Alt metin:** görselde ne var, sade (erişilebilirlik).
- **Bağlantı:** ürünün İkas linki (`magaza/yukleme.json → urun_linki`); yoksa `WORKBENCH_SHOP_URL`.
- **"Yapay zeka ile değiştirildi"** kutusu: görsel Flow/Qwen ile üretildiyse (Teknik Poster, kullanım, stüdyo) **İŞARETLE**.
  Gerçek numune fotoğrafıysa işaretleme.

## Arayüz adımları (tr.pinterest.com)
1. `https://tr.pinterest.com/pin-creation-tool/` aç.
2. Dosya alanı ana sayfada (`input[type=file]`, ad "Dosya Yükleme") → `find` ile bul, `file_upload` ile görseli ver.
   Yüklenince sağda alanlar açılır ve otomatik **taslak** kaydedilir.
3. **Başlık** (placeholder "Pininizin ne hakkında olduğunu herkese söyleyin"), **Açıklama**, **Bağlantı** alanlarını doldur.
4. **Pano** açılır listesinden doğru panoyu seç.
5. "Yapay zeka ile değiştirildi olarak işaretle" → "Tamamen veya kısmen Yapay Zeka ile yapılan içerik" (gerekiyorsa).
6. "Daha fazla seçenek" → **Alternatif metin**.
7. Sağ üst **Yayınla**. Sonra profilde "Oluşturulanlar" sekmesinden yeni pin'i aç, URL'sini (`/pin/<id>/`) al.
8. Hata/inceleme çıkarsa taslağı silme; durumu yaz ve dur.
