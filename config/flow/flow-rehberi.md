# Google Flow Kullanım Rehberi (ajanlar için — arayüz 2026-11 itibarıyla; menü adları değişebilir)

Flow, Patronun Chrome'undaki oturumda (Google AI Pro) çalışır: `https://flow.google.com/`. Claude in Chrome
araçlarını **tek ToolSearch** ile yükle (tabs_context_mcp, tabs_create_mcp, navigate, computer, find, read_page,
javascript_tool, file_upload, tabs_close_mcp). Her zaman **yeni sekme** aç, işin bitince kapat.
Giriş / ödeme / abonelik / kredi satın alma / "kullanım hakları" onayı çıkarsa **DUR** ve bildir; hiçbirini onaylama.

## 1. Proje ve oluşturma kutusu
- Ana sayfa → **"+ Yeni proje"** (alt orta). Proje sayfası: `flow.google.com/project/<id>`.
- Alttaki oluşturma kutusu: metin alanı **"Ne oluşturmak istiyorsunuz?"**, solda **"Ajan"** düğmesi, sağda ayar
  çipi (`button[aria-label="Ayarlar tetikleyicisi"]`, ör. "Video · 720p · 8 sn. x1") ve gönder
  **"Oluşturmaya başla"** (istem boşken pasif).
- **"Ajan" modu:** konsept posteri, kullanım görseli ve Teknik Poster Reels'te KAPALI (istem birebir uygulanır).
  **Reklam kreatifinde AÇIK** — bkz. §7 (Patron kararı 2026-11-17).

## 2. Ayarlar (ayar çipine tıkla)
- Üstte **Resim / Video** sekmesi.
- **Resim:** en yüksek kaliteli resim modeli (Nano Banana Pro; Pro üyelikte 0 kredi), oran, çıktı sayısı.
- **Video:** **"Kareler"** (başlangıç/bitiş karesinden video) seç — "İçerik öğeleri" DEĞİL. Oran **9:16**.
  Model menüsü `button[aria-label="Model ailesi seçin"]`:
  | Model | Kredi (8 sn, x1) | Not |
  |---|---|---|
  | Veo 3.1 - Fast | 20 | kaldırılma tarihi duyuruldu; o tarihe kadar varsayılan |
  | Omni 1.2 Flash | 24 | 720p, süre kaydırıcısı; Veo Fast kalkınca varsayılan |
  | Veo 3.1 - Lite | 10 | yalnız kredi azsa |
  | Veo 3.1 - Quality / Omni 1.1 Flash | — | kullanma (pahalı / kaldırılıyor) |
  Çıktı **x1**. Menünün altındaki "Üretme işlemi için N kredi kullanılır" satırını oku ve raporla.
- Menüyü Escape ile kapat.

## 3. Dosya yükleme (ürün fotoğrafı / başlangıç karesi)
- Yerel dosya için önce `javascript_tool` ile `HTMLInputElement.prototype.click`'i, `type=file` olanları DOM'a
  ekleyip dialog AÇMAYACAK şekilde yamala; sonra yükleme düğmesine bas, `find` ile file-input'u bul,
  `file_upload` ile dosyayı ver.
- **Resim istemine görsel eklemek:** kutudaki **"+"** (`Medya menüsü ekle`) → **"Medya yükle"**.
- **Video başlangıç karesi:** kutudaki **"Başlat"** düğmesi → **"Çerçeve resmi seçin"** penceresi açılır →
  soldaki **"Medya yükle"** ile dosyayı yükle (ya da listeden seç) → sağda önizleme → **"İsteme ekle"**.
  **"Bitir"** (bitiş karesi) BOŞ kalır. Yanlış olursa pencereyi **"Kapat"** ile kapat.

## 4. Üretme ve bekleme
- İstemi metin alanına yaz (yazmadan önce alana tıkla; başka kutuya yazılmadığını kontrol et) → "Oluşturmaya başla".
- Görsel ~1 dk, video ~2–4 dk sürer; %100 olana kadar 20–30 sn aralıklarla ekran görüntüsüyle kontrol et
  (en fazla ~8 dk). Hata/"politika" uyarısı çıkarsa istemi sadeleştirip BİR kez yeniden dene.

## 5. İndirme (en sık takılan adım)
- Chrome sekme başına **tek otomatik indirmeye** izin verir: **HER indirme için yeni sekme** aç
  (`tabs_create_mcp`), öğenin sayfasına (`/project/<id>/edit/<öğe-id>`) git.
- `button[aria-label="Medyayı indir"]` → görselde **"2K"** (yükseltme ~20 sn sürer, bekle), videoda
  **"720p Orijinal"**. JS ile tıklama gerekiyorsa önce sayfaya gerçek bir tıklama yap (kullanıcı etkinleşmesi).
- Dosya `~/İndirilenler` ya da `~/Downloads`'a iner; en yeni dosyayı hedef yola taşı (PNG/MP4). İnmezse bir
  kez daha dene; yine inmezse `HATA Chrome otomatik indirme izni gerekli` ile dur.

## 6. Doğrulama
- Görseli Read ile aç; ürün fotoğraftakinden farklıysa (şekil, yüz, renk, yazı) ELE.
- Videodan ffmpeg ile 0 / 4 / 7.8 sn kareleri çıkar, Read ile bak; ürün değiştiyse videoyu `-red` ekiyle
  yeniden adlandır ve bildir. Kareleri sil.
- Sekmeleri kapat. Raporda: model, harcanan kredi, üretilen dosya yolları.

## 7. Reklam kreatifi — Flow Ajan modu (Patron kararı 2026-11-17)
Reklam görseli ve videosu Flow'un kendi **Ajan**'ıyla, kalıcı **"Reklam"** talimatıyla üretilir.
- Yeni proje → kutudaki **"Ajan"** düğmesini AÇ (beyaz). Sağdaki `tune` simgesi = **Ajan ayarları**:
  "Üretme işleminden önce onaylayın: **Her zaman**" (kredi harcamadan önce sorar), resim **Nano Banana Pro**, 3:4;
  video **9:16**, Omni 1.2 Flash, x1 → **Kaydet**.
- `article_spark` simgesi = **Ajan talimatları** (proje başına): "+ Talimat ekle" → başlık "Reklam",
  metin = `config/flow/ajan-reklam-talimati.md`, **Referans** = `config/konseptler/referans/<konsept>/<referans>.jpg` (varsa),
  anahtar AÇIK → **Bitti**. (Talimat proje başına; her yeni projede yeniden eklenir.)
- Ürün fotoğrafı: kutudaki **"+"** (İçerik öğelerini istem kutusuna ekle) → **Medya yükle** → ürünü seç → **İsteme ekle**.
  Kaynak = ürünün onaylı Qwen stüdyo karesi (kapak-beyaz) ya da numune fotoğrafı.
- İstek: "Create a paid ad set for this product (<kısa İngilizce ürün tarifi>) following my ad
  instruction: one 9:16 image, one 3:4 feed image, then an 8-second 9:16 video from the 9:16 image."
  **4:5 desteklenmiyor** (1:1, 9:16, 16:9, 3:4, 4:3) → akış için 3:4 iste; 4:5'e biz kırparız.
- Ajan sohbeti sağ panelde açılır (görünmüyorsa kutunun sağ üstündeki `expand_content`). Video için
  "N kredi karşılığında … başlatmak ister misiniz?" → **Onayla** (yalnız Patron kredi izni verdiyse; "her zaman" seçme).
- Denetim §6 aynen geçerli: ürün değiştiyse ELE; görselde yazı olmamalı.
