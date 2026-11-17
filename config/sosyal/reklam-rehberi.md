# Reklam (Ücretli Tanıtım) Kreatif Rehberi — Instagram/Facebook ve TikTok

> Organik kalıplar için önce **[kisa-video-rehberi.md](kisa-video-rehberi.md)**. Reklam kreatifi aynı kanca/omurga
> kurallarını kullanır; farkları burada. Reklam **yayınlamak, bütçe girmek, kampanya açmak** Patronun işidir —
> ajan yalnızca kreatif ve metin paketi hazırlar, ödeme/yayın işlemi yapmaz.

## 1. Organik videodan farkları
- **Amaç tek ve ölçülebilir:** mağaza ziyareti, sepete ekleme ya da (B2B) teklif/WhatsApp mesajı. Video bu tek
  eyleme bağlanır; "beğen, kaydet" reklamda ana hedef değildir.
- **Teklif açık:** ne, kaça, ne zaman teslim. Fiyat yalnız **Patronun onayladığı mağaza fiyatıyla** yazılır
  (ERP/urun.yaml); uydurma indirim, sahte "son 3 ürün" yok.
- **Kanca daha da kısa:** reklam izleyicisi seni hiç tanımıyor ve reklam olduğunu biliyor. İlk 1–2 sn'de ürün
  ya da sonuç görünür.
- **Ses:** popüler şarkı **kullanılmaz** (telif). Lisanslı/telifsiz müzik, özgün ses ya da seslendirme.
- **Sessiz izlemeye hazır:** altyazı + ekran yazısı hikâyeyi tek başına anlatmalı.

## 2. Format ve güvenli alan
- **9:16 (1080×1920)** Reels/Hikâye/TikTok; akış için ayrıca **4:5 (1080×1350)** kesit; görsel reklam için **1:1**.
- Arayüz öğeleri üst ve özellikle **alt** bandı kaplar: önemli yazıyı, logoyu ve fiyatı ortadaki güvenli alanda tut
  (üstte ~%14, altta ~%35, yanlarda ~%6 boş bırak). Yayından önce platformun güncel güvenli alan şablonuyla doğrula.
- Süre: 6–15 sn kısa kesit + 20–30 sn uzun kesit. Logo en fazla küçük köşe işareti; açılış logosu yok.

## 3. Kreatif yapısı (reklam omurgası)
`Kanca (0–2 sn) → Sorun/istek → Ürün çözümü (gerçek görüntü) → Kanıt → Teklif + tek çağrı`
- **Kanıt:** gerçek ölçü/malzeme, üretim timelapse'i, yerinde takılmış fotoğraf, (varsa ve izinliyse) gerçek
  müşteri yorumu. Yorum, puan, satış adedi **uydurulmaz**.
- **Çağrı:** "Mağazada kişiye özel tasarla", "Ölçünü yaz, teklif alın" — tek eylem, butonla uyumlu.

## 4. Test mantığı (kreatif varyasyon)
- Aynı gövdeye **3–5 farklı kanca** (farklı türlerden) → hangisi tutuyor, ona göre ölçekle.
- Bir seferde tek değişken: kanca **ya da** görüntü **ya da** metin.
- Kazanan organik video reklama aday olur: TikTok'ta *Spark Ads* (kendi gönderini tanıtma), Instagram'da
  gönderiyi öne çıkarma. Önce organikte tutanı reklama al.
- Değerlendirme ölçütleri: ilk 3 sn izlenme oranı (kanca), tıklama oranı (teklif/çağrı), sepete ekleme maliyeti
  (sayfa+fiyat). Rakam yorumu Patrona "olası neden + önerilen tek değişiklik" olarak sunulur.

## 5. Yasal ve marka sınırları (Türkiye)
- **Ticari Reklam ve Haksız Ticari Uygulamalar Yönetmeliği:** "en iyi, en ucuz, 1 numara" gibi üstünlük iddiaları
  belgelenemiyorsa kullanılmaz; karşılaştırmalı reklamda rakip adı/logosu yok; indirimde gerçek önceki fiyat.
- Başka markanın logosu, karakteri, lisanslı figürü (çizgi film, takım arması vb.) reklam görselinde yer almaz.
- Müşteri adı/logosu/fotoğrafı yalnızca **yazılı izinle**.
- Hunyuan3D ile üretilmiş modellerin reklamı AB/BK/Güney Kore hedeflemesine açılmaz (lisans).
- YZ ile üretilmiş sahne (Flow) gerçek ürün gibi sunulmaz; ürünün kendisi gerçek geometriden/fotoğraftan gelir.

## 6. Teslim paketi (`veri/02_Urunler/<sku>/medya/reklam/`)
- `reklam-kisa.mp4` (6–15 sn, 9:16), `reklam-uzun.mp4` (20–30 sn, 9:16), `reklam-4x5.mp4`, `reklam-1x1.png`
- `reklam-metinleri.md`:
  - 3–5 kanca varyasyonu (tür etiketli)
  - **Ana metin** ×3 (kısa / orta / uzun; ilk 125 karakter tek başına anlamlı)
  - **Başlık** ×3 (≤40 karakter), **Açıklama** ×2, önerilen **buton** (Şimdi Satın Al / Daha Fazla Bilgi / Mesaj Gönder)
  - Hedef kitle önerisi (ilgi alanları, konum, yaş — tahmin olduğu belirtilir), önerilen test planı
  - Kontrol listesi: güvenli alan ✓, telifsiz ses ✓, fiyat ERP/urun.yaml ile aynı ✓, üstünlük iddiası yok ✓, izinler ✓
- Paket Patrona Telegram'dan önizleme ile sunulur; **yayın ve bütçe kararı Patronun.**
