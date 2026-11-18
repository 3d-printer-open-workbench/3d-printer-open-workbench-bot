# Mağaza Metin Rehberi (İkas ürün sayfası)

Patron kararı (2026-11-17): Ürün açıklamaları **kısa, insan eliyle yazılmış gibi ve profesyonel** olur.
Her metin yazıldıktan sonra **kıdemli editör review'undan** geçer; review'u olmayan veya otomatik
kontrolü (`python3 -m coo.metin_denetim <sku>`) geçemeyen metin mağazaya **yüklenmez**.

## Ses
- İyi bir tasarım dükkânının satıcısı gibi yaz: sakin, net, somut. Satış baskısı yok, övgü sıfatı yok.
- Okur ürünü zaten görselde görüyor. Metin görselin söyleyemediğini söyler: ne işe yarar, ne büyüklükte,
  neye sığar, nasıl bakılır.
- Kısa cümle. Bir cümlede tek bilgi. "Siz" diye hitap edilebilir ama her cümlede değil.
- Her bilgi **bir kez** geçer. Renk, ölçü, "siparişe özel" gibi bilgiler tekrarlanmaz.

## Yapı ve uzunluk
| Bölüm | Kural |
|---|---|
| Başlık | ≤ 70 karakter. Ürün tipi + ayırt edici özellik. En fazla bir ayraç (`-`). Anahtar kelime yığını yok. |
| Giriş | 1–2 cümle, ≤ 40 kelime. Ürün nedir, nerede kullanılır. |
| Maddeler | 3–4 madde, her biri ≤ 14 kelime, düz cümle. **"Kalın etiket: açıklama" kalıbı kullanılmaz.** |
| Tablo | En fazla 5 satır: Ölçü, Malzeme, Renk, Ağırlık (varsa), Hazırlık. |
| Son not | Tek paragraf: bakım + ısı uyarısı + üretim/kargo + (numune yoksa) görsel notu. |
| Toplam | Tablo hariç **50–130 kelime**. |

## Kullanılmayacak ifadeler (YZ izi)
"ilham alan", "dokunuş katar", "karakter katar", "hayat verir", "şıklık", "şık ve fonksiyonel",
"mükemmel", "kusursuz", "eşsiz", "benzersiz", "harika", "göz alıcı", "vazgeçilmez", "ideal",
"uyum sağlar", "sevimli bir yolu", "ile tanışın", "sadece bir … değil", "hem … hem de" süslemesi,
"yaşam alanınıza", "tarzınızı yansıtın", "fark yaratın", ünlem, emoji, uzun tire (—) ile cümle bağlama.

Üretim jargonu müşteriye anlatılmaz: katman kalınlığı (mm), temas yüzeyi (cm²), "renk değiştirilerek
basılır", FDM, dilimleme. Yeterli olan: "3B yazıcıda PLA ile basılır."

## Doğruluk
- Her ölçü ve özellik `urun.yaml` / ERP verisinden gelir. Doğrulanmamış iddia yok ("el yapımı",
  "su geçirmez", "dayanıklı", "kalite kontrolden geçer").
- Rakip marka adı, oyun/film adı, tescilli karakter adı yok.

## Sabit son not (uyarlanarak)
> Nemli bezle silinebilir; PLA güneşte, araç içinde veya 55 °C üstü ısıda şekil değiştirebilir.
> Siparişe özel basılır, N iş gününde kargoya verilir; kargo ücreti ayrıca hesaplanır.
> (Numune fotoğrafı yoksa:) Görseller 3B modelden hazırlanmıştır, renk tonu filamente göre hafif değişebilir.

## Örnek (iyi)
```html
<p>Kemer formunda bir oyun kolu standı. Kolu masada dik tutar, kullanmadığınızda raf objesi olarak durur.</p>
<ul>
<li>İki yuva, standart oyun kollarını dik ve sabit tutar.</li>
<li>Kırmızı direkler, siyah kiriş ve kemik rengi kaide; renkler boyasızdır.</li>
<li>14 × 10 cm taban, masada ya da TV ünitesinde az yer kaplar.</li>
</ul>
<table>
<tr><th>Ölçü</th><td>14,1 × 10,3 × 11,8 cm</td></tr>
<tr><th>Malzeme</th><td>Mat PLA</td></tr>
<tr><th>Renk</th><td>Kemik, kırmızı, siyah, turuncu</td></tr>
<tr><th>Ağırlık</th><td>Yaklaşık 160 g</td></tr>
</table>
<p>Nemli bezle silinebilir; PLA güneşte, araç içinde veya 55 °C üstü ısıda şekil değiştirebilir. Siparişe özel basılır, 3 iş gününde kargoya verilir; kargo ücreti ayrıca hesaplanır. Görseller 3B modelden hazırlanmıştır, renk tonu filamente göre hafif değişebilir.</p>
```

## Editör review'u (zorunlu)
Yazar (seo-copywriter / cmo-store-director) metni yazar, ardından **kıdemli e-ticaret editörü** (Opus)
okur ve yeniden düzenler:
1. Bu rehberi ve `urun.yaml`'ı açar. Her bilgiyi kaynağıyla karşılaştırır, yanlışı düzeltir.
2. Metni sesli okunuyormuş gibi kontrol eder: yapay, şişkin, tekrar eden ya da reklam kokan her cümleyi
   sadeleştirir veya siler.
3. `python3 -m coo.metin_denetim <sku> --review "<kısa not>"` çalıştırır. Bu komut kontrolleri yapar,
   geçerse paket.json'a `metin_review` kaydını (tarih, kelime sayısı, metin özeti) yazar.
4. Review'dan sonra metin değişirse kayıt geçersiz olur; yeniden review gerekir.
