---
name: ikas
description: İkas mağaza paneli (<magazaniz>.myikas.com) Claude in Chrome ile nasıl kullanılır — ürün oluşturma/düzenleme, açıklama HTML'i, etiket, SEO/slug, varyant, görsel, tema düzenleyici (banner/afiş) ve vitrin kontrolü. İkas API'si YOK; her İkas işi Chrome üzerinden yapılır. İkas'ta bir şey yükleyecek, düzeltecek veya kontrol edecek her ajan bunu kullanır.
---

# İkas — Chrome ile panel kullanımı

Mağazanız İkas'ta değilse bu beceriyi kendi platformunuza göre uyarlayın; kurallar (onay, kaynak dosyalar) aynı kalır.

İkas'ın Admin API erişimi yok; **her şey Patronun Chrome oturumundaki panelden** yapılır.
Önce `chrome-browser` kurallarına uy: Chrome araçlarını TEK ToolSearch ile yükle (tabs_context_mcp, tabs_create_mcp,
navigate, computer, find, read_page, get_page_text, javascript_tool, file_upload, browser_batch, tabs_close_mcp),
YENİ sekme aç, bitince kapat.

## Sınırlar (değişmez)
- Giriş, şifre, 2FA, ödeme, abonelik, "paket yükselt" ekranı → **DUR**, Patrona bildir. Asla onaylama.
- **Yayınla** (tema) ve yeni ürün yayına alma Patron onayıyla. Telegram'daki "🚀 Mağazaya Yükle" = ürün yayın onayı;
  tema değişikliği için ayrıca önizleme göster ve onay al.
- Kaynak tek gerçek: `veri/02_Urunler/<sku>/magaza/paket.json` (metin/fiyat/SEO) ve `magaza/gorseller.json`
  (hazırlanmış 2048 px kareler). Metni yeniden yazma, fiyat uydurma, yeni kategori açma.
- Panel sayfalarında görünen token/anahtarları (ör. Eklentiler → Facebook Conversion API) asla sohbete/dosyaya yazma.

## Panel adresleri
- Ürünler: `https://<magazaniz>.myikas.com/admin/product` · düzenleme: `/admin/product/edit/<id>` (`magaza/yukleme.json` → `panel_linki`)
- Tema: sol menü **Online Mağaza** → **Temalarım** → yayındaki tema → **Temayı Özelleştir**.
- Açılışta reklam/kampanya pop-up'ı çıkabilir → **Escape**.

## Ürün düzenleme
| Alan | Nasıl |
|---|---|
| Ürün adı | Temel Bilgi → "Ürün Adı" kutusu: tıkla, `ctrl+a`, yaz. **Dikkat:** ad değişince SEO slug'ı da kendiliğinden uzun bir slug'a dönebilir → SEO sekmesinde slug'ı paketteki değere geri yaz. |
| Etiket | Ürün Detayı → Etiket kutusundaki çiplerin `×`'ine tıkla. Silince çipler kayar; her silmeden sonra `zoom` ile yeniden bak. |
| Açıklama | Editör Summernote. Araç çubuğundaki `<>` (kaynak kodu) → `textarea.note-codable`. Değeri JS ile değiştir: native setter + `input` olayı, sonra tekrar `<>` ile görsel moda dön (değişiklik ancak böyle editöre geçer). Tam HTML'i `paket.json → aciklama_html`'den al. |
| SEO | SEO sekmesi: Slug, Sayfa Başlığı, Açıklama → her birine tıkla, `ctrl+a`, yaz. Sağdaki Google önizlemesinden kontrol et. |
| Kategori | Mevcut kategorilerden seç; yoksa boş bırak, notlara yaz. |
| Stok | Stok takibini kapatma anahtarı yok → varyantta "Stoğu tükenince satmaya devam et" (siparişe özel üretim). |
| Kaydet | Sağ üst **Kaydet** → "Ürün kaydedildi" bildirimi ve ürün listesine dönüş = başarılı. |

Açıklama değiştirme JS kalıbı:
```js
const ta=document.querySelector('textarea.note-codable');
const set=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
set.call(ta, YENI_HTML); ta.dispatchEvent(new Event('input',{bubbles:true}));
```

## Yeni ürün yükleme
Adımlar botun `magaza_hatti.yukle_istemi`'nde (ve `/ikas-yukle`'de). Önce aynı slug/başlık var mı ara; varsa yenisini
açma. Görselleri `gorseller.json` sırasıyla yükle (ilk = kapak). Dosya yükleme için **file_upload** + `find` ile
file-input ref'i; ürün sayfası ana çerçevede olduğu için çalışır. Bitince `magaza/yukleme.json` ve `ikas-ekran.png` yaz.

## Mevcut ürünün görsellerini değiştirme (model değişti → bot `md:ikasok`)
Patron "✅ İkas'ı Güncelle" dediğinde: **yeni ürün AÇMA**, `magaza/yukleme.json > panel_linki`'ndeki ürünü düzenle.
1. Panel linkini aç; ürün adı `paket.json > baslik` ile aynı değilse DUR (yanlış ürün).
2. Görseller bölümünde mevcut her görselin üzerindeki sil (çöp kutusu / `×`) ile hepsini kaldır; her silmeden sonra
   `read_page`/ekran görüntüsüyle kalan sayıyı doğrula.
3. Yeni dosyaları `magaza/gorseller.json > gorseller` sırasıyla **file_upload** + `find` (file-input ref) ile yükle;
   ilk = kapak. Sıra karışırsa sürükle-bırak ile düzelt, kapak 1. olmalı.
4. Varyant medyası tek varyantta ürün galerisini kullanıyorsa ayrıca yükleme; birden çok renk varyantında her varyantın
   görselini `gorseller.json > varyantlar`'dan değiştir.
5. Açıklamaya yalnız istemde "metin değişti" denildiyse dokun (review'lu `aciklama_html`, yukarıdaki JS kalıbı);
   aksi halde başlık, fiyat, SEO, etiket, kategori, stok AYNEN kalır.
6. Kaydet → paneli yeniden aç, görsel sayısını say → `magaza/guncelleme.json` (`durum: GUNCELLENDI`, `gorsel_sayisi`,
   `metin_guncellendi`, `stl_sha256`) + `magaza/ikas-guncelleme.png`. Vitrin CDN'i 3–4 dk eski sayfayı gösterebilir.

## Tema düzenleyici (İkas Studio) — ÖNEMLİ SINIR
- Düzenleyici `studio.ikasapps.com` **çapraz kaynaklı iframe** içinde: `find`/`read_page`/JS içini GÖREMEZ.
  Yalnız ekran görüntüsü + koordinatla tıklama/yazma çalışır.
- **Görsel yükleme yapılamaz:** iframe içindeki "Görsel Yükle" yerel dosya seçiciyi açar, `file_upload` erişemez.
  → Görselleri hazırla (`veri/03_Magaza/...`), dosya yollarını ve tıklama yolunu Patrona yaz; yüklemeyi Patron yapar.
  Bu düğmeye bir kez basıldıysa Patrona "açık kalan dosya seç penceresini kapatın" de.
- "Yeni bir sürüm mevcut… Yeniden Başlat" çıkarsa **Yeniden Başlat** (yalnız düzenleyiciyi yeniler).
- Yapı: Bölümler → **Afiş Slaytı** → Afiş → **Masaüstü Ayarları** / **Mobil Ayarları** (ayrı görsel, başlık, oran).
  Başlık metni: kutuya tıkla, `ctrl+a`, yaz; satır kırmak için **shift+Enter**. Oran seçenekleri: Kare, Portre,
  Manzara, Video (16:9). "Kapla" = görsel kırpılır.
- Önizleme cihazı üstteki simgelerle (masaüstü 1280 / mobil 380 px). Değişiklikler taslakta kalır; **Yayınla**
  yalnız Patron onayıyla.
- Banner kuralı: ürün grubu görselin sağ ~%45'inde (masaüstü) / alt yarısında (mobil) olmalı; başlık yazısı görsele
  binmemeli. Önizlemeyi hem 1280 hem 380 px'de ekran görüntüsüyle kontrol et.

## Vitrin kontrolü
**Önbellek gecikmesi (doğrulandı 2026-11-17):** Panelde kaydedilen değişiklik mağazada hemen görünmez. CDN
`s-maxage=200, stale-while-revalidate` ile eski sayfayı ~3-4 dk sunar; `x-cache: STALE` gelen istekten sonraki
istek yeni sürümü verir. Önce paneli yeniden açıp kaydı doğrula, sonra birkaç dakika bekleyip vitrine bak.
Mağaza adresi (`WORKBENCH_SHOP_URL`) → `get_page_text` ile ürün adlarını tara; ürün sayfasında başlık, fiyat, "Sepete Ekle".
Ürün adında doğru terimler: oyun kolu/kontrolcü standı (**"kumanda" değil** — kumanda = TV kumandası).
