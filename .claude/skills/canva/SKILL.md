---
name: canva
description: Canva (claude.ai Canva bağlantısı, Canva Free hesap) ile isteğe bağlı teknik ürün posteri ve şablondan görsel üretimi — ana şablonu kopyalama, ürün fotoğrafı yükleme, yer tutucuları gerçek veriyle doldurma, PNG dışa aktarma. Yazılı her şey (ölçü, malzeme, ürün adı) Canva'da gerçek fontla basılır; YZ harf çizmez. Poster/pin/hikâye gibi yazılı görsel üretecek ajan bunu kullanır.
---

# Canva — teknik poster (isteğe bağlı)

> **VARSAYILAN YEREL ŞABLON:** Teknik poster varsayılan olarak Canva'dan bağımsız, yerel ve açık kaynak üretilir:
> `config/konseptler/teknik-poster-sablon.svg` + `python -m coo.poster_sablon <sku>` (Inkscape; yedek Chrome/Chromium
> headless; fontlar Inter + Roboto Mono, OFL). Çıktı `gorsel/konsept/teknik-poster-3x4.png` (eskisi `eski/` altına) +
> `teknik-poster-9x16.png`. Bu beceri yalnız konsept dosyasında `poster_motoru: canva` seçildiyse ya da Patron
> açıkça Canva isterse kullanılır.

Şablon haritası: `config/konseptler/teknik-poster-canva.yaml` (ana tasarım id, sayfa id, öğe id'leri; örnek:
`teknik-poster-canva.example.yaml`). Bu dosya yoksa bot Canva yolunu kullanmaz. Hesap **Canva Free** varsayılır:
marka kiti / autofill yok → **kopyala + yer tutucu değiştir** yöntemi.

## Sınırlar
- **Ana şablonu (`ana_tasarim`) ASLA düzenleme**; her ürün için `copy-design` ile kopyala, kopyada çalış.
- Değerler YALNIZ istemde verilen gerçek veriden (urun.yaml → `coo/bilgi_verisi.bilgiler`). Ölçü/malzeme uydurma.
- Ürün fotoğrafı yalnız verilen dosya (onaylı Qwen stüdyo karesi / numune). Canva'nın YZ görsel üretimini kullanma.
- Satın alma, Pro deneme, paylaşım/yayın yok.

## Adımlar
1. Canva araçlarını ToolSearch ile yükle: `copy-design, read-design, edit-design-v2, create-upload-url, export-design`.
2. `copy-design` (ana_tasarim) → yeni `design_id`.
3. Ürün fotoğrafını hazırla: kare kırp (merkez), ≤1600 px JPG (PIL). `create-upload-url` → dönen URL'ye
   `curl -s -X POST -H "Content-Type: application/octet-stream" --data-binary @foto.jpg '<url>'` → `mediaId`.
4. `read-design` (`open_transaction: true`) → `transaction_id` (kodu döndürülen `code_guide`'a göre yaz).
5. `edit-design-v2` (keep_open), tek kod bloğunda:
   - `remove` eski görsel (`<sayfa>-<gorsel.id>`), `add_image` yeni `mediaId` aynı `kutu` ile.
   - `replace_text` ürün satırı: `"<ÜRÜN ADI BÜYÜK HARF>  ·  NO. <no>"` (`max_lines: 1`).
   - Her bilgi satırı i için: etiket = `"<kod>  <AD>"`, değer = `<değer>` (`max_lines: 1`); nokta rengini
     `recolor` ile kod harfine göre (şablon haritasındaki `renkler`: `A`, `P`).
   - Satır sayısı < 6 ise kalan hücrelerin `cizgi/nokta/etiket/deger` öğelerini `remove`.
   - Locator biçimi: `"<sayfa>-<öğe id>"`. `text_align` için `"end"` kullan ("right" yok).
6. Doğrula: dönen küçük resim + `layout_warnings`. İç içe yörünge çemberleri ve çember üstündeki düğümler
   **kasıtlı** çakışmadır; başka uyarı (taşan/kırılan yazı) varsa düzelt. Sonra `finalize: "commit"`
   (yalnız bu kasıtlı çakışmalar kaldıysa `commit_despite_warnings: true`).
7. `export-design` → `{"type":"png","width":1080}` → URL'yi `curl -s -o <hedef>.png` ile indir; Read ile aç,
   yazıları harf harf kontrol et (Türkçe karakterler, değerler istemdekiyle birebir).
8. Raporla: kopya `design_id`, edit URL'si, çıktı yolu.

## Bilinen davranışlar
- `edit-design-v2` yanıtı çok büyük (~25k token, tüm öğeler): tüm değişiklikleri TEK kod bloğunda yap, sonra doğrudan commit; gereksiz tekrar uygulama yapma. `read-design`'da yalnız `page_metadata` iste.
- Görsel `remove`+`add_image` sonrası yeni görsel öğenin id'si değişir (ana şablon etkilenmez).
- `describe_page()` öğe id'lerini zaten `sayfa-öğe` biçiminde döndürür; başına tekrar sayfa id ekleme.
- Kopyalanan tasarımda sayfa ve öğe id'leri aynı kalır.
- Tasarım başlığını değiştirme aracı yok; kopya ana şablonun başlığını taşır (önemsiz).
