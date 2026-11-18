---
name: flow
description: Google Flow (flow.google.com, Patronun AI Pro oturumu) Claude in Chrome ile nasıl kullanılır — Nano Banana Pro görsel üretimi/düzenleme (konsept, banner, kullanım görseli), Omni/Veo video, Flow Ajan modu, dosya yükleme, 2K indirme ve çıktı denetimi. Flow'da görsel veya video üretecek her ajan bunu kullanır.
---

# Google Flow — Chrome ile kullanım

**Ayrıntılı adımlar, model/kredi tablosu ve reklam Ajan modu: `config/flow/flow-rehberi.md` — işe başlamadan oku.**
Bu beceri o rehberin özeti ve son doğrulanan tuzaklardır.

## Sınırlar
- Giriş, abonelik, kredi satın alma, "kullanım hakları" onayı → DUR, bildir.
- Kredi harcayan video üretimi yalnız Patronun izin verdiği işte; görsel (Nano Banana Pro) 0 kredi.
- Ürün **asla yeniden çizilmez**: çıktıda ürünün şekli/renk/detayı değiştiyse ELE (CLAUDE.md görsel kuralları).
- YZ'nin yazdığı her yazı (tabela, "Hoş Geldiniz", menü) **harf harf** doğrulanır (ş/ğ/ı/İ/ö/ü/ç).

## Görsel üretimi / düzenleme (doğrulandı 2026-11-17)
1. Yeni sekme → `https://labs.google/fx/tr/tools/flow` → **Yeni proje**.
2. Ayar çipi (kutunun sağ altı) → **Resim** → oran (16:9 / 4:3 / 1:1 / 3:4 / 9:16; **4:5 yok**) → model menüsü →
   **Nano Banana Pro** → x2. Popup'ı kapatmak için **Escape** kullan — boş alana tıklamak arkadaki görseli açar.
3. Referans görsel: kutudaki **"+"** (İçerik öğesi ekle) → açılan medya penceresi → **Medya yükle**.
   Dosya seçici yerine file-input yakalamak için ÖNCE şu yamayı çalıştır, sonra "Medya yükle"ye tıkla,
   `find` ile `file-input`'u bul, `file_upload` ver, yüklenince listeden seç → **İsteme ekle**:
   ```js
   if(!window.__pick){window.__pick=true;const o=HTMLInputElement.prototype.click;
   HTMLInputElement.prototype.click=function(){if(this.type==='file'){if(!this.isConnected){
   this.style.display='none';document.body.appendChild(this);}return;}return o.call(this)}}
   ```
   Daha önce yüklenen görseller aynı pencerede listelidir; yeniden yüklemeden seçilebilir.
4. İstemi yaz (İngilizce, "keep X exactly the same" + yerleşim yüzdeleri) → gönder. ~40–60 sn.
5. Düzeltme: görseli aç → alttaki **"Neyi değiştirmek istiyorsunuz?"** kutusuna yaz → Enter. Yeni sonuç **sağ
   paneldeki geçmişte** belirir (ana görünüm değişmez) — sağdaki küçük kareye tıklayarak aç.
6. İndirme: görsel açıkken üstteki indir simgesi → **2K** (~10–20 sn) → dosya `~/İndirilenler/<istem>_<id>_2K.jpg`.
   Hemen hedef klasöre taşı ve `İndirilenler`'den sil.
7. Kontrol: Read ile aç; yerleşim (ör. ürün sağ %45'te mi), ürün sadakati, yazılar. Sonra sekmeyi kapat.

**Bilinen tuzaklar**
- "Sola %58'den başlasın" gibi kesin yüzdeleri model tam uygulamaz (~%48–50 yapar) → hedefi bir tık abartılı iste
  ya da yerleşimi metin tarafında (satır kırma) telafi et.
- Grid'e tıklamak görseli açar; geri dönmek için sağ üst **Bitti**.
- Masaüstü kompoziti PIL ile yapıştırma/aynalama denendi → ek yerleri belli oldu; Flow ile yeniden kompozisyon kullan.

## Video
- Reels/kullanım videosu: ayrıntı `flow-rehberi.md` §2–§5. Ürün-kullanım aksiyonu için Flow **Ajan** +
  `config/flow/ajan-kullanim-talimati.md` (boş ürün → el yerleştirir → kullanımda, son 2 sn sabit).
- Omni 1.2 Flash 24 kredi / 8 sn; Veo 3.1 Fast 5 Aralık 2026'da kalkıyor.
- Kurguda Flow'un **kendi sesini koru** (ffmpeg'de `-an` kullanma); yayın öncesi `ffprobe -select_streams a`.
- Denetim: 0/2/4/6/7.9 sn kareleri çıkar, Read ile bak (ürün bozulması, istenmeyen marka/konsol, el sayısı).
