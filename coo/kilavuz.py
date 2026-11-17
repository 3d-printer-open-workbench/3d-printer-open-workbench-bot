"""Telegram kullanım kılavuzu: hangi buton / komut ne işe yarar, hangi ajan çalışır, ne maliyeti var.

Bölümler Telegram mesaj sınırına (4096) sığacak kadar kısa; Markdown (eski Telegram Markdown) ile yazılır —
`_` ve `*` dengeli olmalı. Maliyet rakamları 2026-11-14..16 gerçek oturum kayıtlarından (API karşılığı) ve
Flow kredi tablosundan; değişirse burada güncellenir.
"""
from __future__ import annotations

BOLUMLER: dict[str, tuple[str, str]] = {
    "akis": ("🧭 Genel Akış", """🧭 *Genel Akış — bir ürün baştan sona*

Ürün kartındaki adımlar (*▶️ Sıradaki* butonu her zaman bir sonrakini açar):
1️⃣ *Konsept* — Flow konsept görselleri → sen *seçersin*
2️⃣ *3B model* — Qwen görünümler → Hunyuan3D → Blender onarım → kalite kapısı
3️⃣ *Renk* — kartela: tek renk (varyant) / çok renkli tasarım (render ile onay)
4️⃣ *Dilimleme* — kategori ayarı, gerekirse ağaç destek → 3MF + G-code
5️⃣ *E-ticaret görselleri* — Qwen stüdyo: beyaz kapak, krem, koyu, katman dokusu
6️⃣ *Teknik Poster poster + Reels* — ölçü/malzeme bilgili poster (galeri + Pinterest) ve tanıtım Reels
7️⃣ *Numune + kullanım* (isteğe bağlı) — basılan numunenin fotoğrafından Flow kullanım görselleri + video
8️⃣ *Görsel onayı* → 9️⃣ *Pazar fiyatı* → 🔟 *Mağaza paketi* (fiyatı *sen seçersin*) → 1️⃣1️⃣ *İkas'a yükle*
📤 *Yazıcıya Yükle* → baskıyı *sen başlatırsın*; bot ilk katman ve riskli katmanlarda fotoğraf atar
⏳ Uzun işler tek bir canlı mesajla görünür: sırada / çalışıyor (adım, süre) / bitti.

🔒 Bot hiçbir zaman baskı başlatmaz, ödeme yapmaz, senin onayın olmadan yayınlamaz.
Her ürünün durumu: *📦 Ürünlerim* → ürün kartı."""),

    "fikir": ("💡 Fikir & Trend", """💡 *Fikir ve Trend*

*🔎 Trend Araştır* (`/trend <konu>`)
Trendyol, Etsy, Pinterest, MakerWorld'de satan gerçek ürünleri fiyat ve linkiyle getirir. Bir öneriye *💡 Bu Konseptle Fikir* dersen fikir hattı başlar.
_Ajan: trend-researcher · ~1–1,5 $_

*💡 Yeni Fikir* (`/fikir <tarif>`)
Metin yaz, ekran görüntüsü ya da link at (`fikir …` açıklamalı fotoğraf da olur). Flow'da en kaliteli modelle 4 konsept üretilir, bozukları elenir, sana gelir.
_Ajan: cmo-store-director (Chrome + Flow) · ~0,9 $ · Flow 0 kredi_

*💹 Pazar Fiyatı*
Konsepti seçince otomatik başlar: benzer ürünlerin gerçek fiyatlarından bant (alt / medyan / üst) çıkarır.
_Ajan: trend-researcher · ~1–1,5 $_

*🛍️ Trend Vitrini* — son trend paketini tekrar gösterir."""),

    "gorsel": ("🎨 Görseller", """🎨 *Görseller ve İçerik*

*🎨 Renk Görselleri* — filament ekran görüntüsü / fotoğrafı at → YZ filamentin olduğu bölgeyi seçer (site arayüzü, kutu, gölge sayılmaz), renk *piksellerden ölçülür* → palete ekle → her renk için görsel.\n*🎨 Renk Paleti* (ana menü) — tüm filament renkleri: ✅ ölçülmüş, ⚠️ tahmini. Açıklamasına `palet` yazılan fotoğraf yalnız palete ekler; ERP'deki filamentle eşleşirse stok kaydındaki renk kodunu da düzeltebilirsin.
*🛍️ E-ticaret görselleri* (adım 5) — Qwen (yerel, ücretsiz), ürünün kendi render'ından: beyaz kapak / krem / koyu fon + katman dokusu yakın; geometri ve renk ölçülür, sapan elenir. Çok renkli üründe çok renkli render'dan çekilir.
*🎨 Teknik Poster poster + Reels* (adım 6) — galerideki ölçü/malzeme görseli, Pinterest Pin'i ve ürün tanıtım Reels'i buradan gelir.
_Ajan: cmo-store-director · ~1–2 $ · Flow: görsel 0, video 24 kredi_
*📷 Numune → kullanım* (adım 7) — basılan ürünün fotoğrafını at → Flow yalnız çevresini değiştirir → kullanım görselleri + Veo; Reels bu gerçek kaynaklardan ve timelapse/çekimlerinden kurgulanır.\n*🏡 Numunesiz Kullanım Görseli* — numune beklemeden, ürünün Qwen stüdyo karesinden aynı Flow akışı (sıkı sadakat kontrolü; ürün değişirse görsel elenir, onayda sen karar verirsin).

🚫 Kullanılmayan yöntemler: ürünü YZ sahnesine yapıştırma, ürünü YZ'ye yeniden çizdirme, ham Blender render'ını galeride kullanma, düz ölçü kartı / editoryal föy.
ℹ️ Yazılar (ölçü, malzeme) yapay zekâya yazdırılmaz; gerçek veriden biz basarız."""),

    "uc_b": ("🧊 3B Model", """🧊 *3B Model (konsept seçilince otomatik)*

1. Qwen konseptin ön / yan / arka görünümünü çizer
2. Hunyuan3D-2mv 3 farklı tohumla model üretir, konsepte en benzeyeni seçilir
3. Taban düzlenir, saksıysa hazne bulunur + drenaj deliği
4. *Blender onarım:* su geçirmezlik, kopuk parça temizliği, 1 mm'den ince yerler ve 2 mm'den ince hazne duvarı kalınlaştırılır
5. Kalite kapısı + 4 yön görünüm (ön · sağ · arka · sol) sana gelir
6. Sorun kalırsa *🛠️ Onarım ajanı* Blender'da düzeltir

⏱️ ~20 dk · tamamı yerelde, *ücretsiz* (onarım ajanı gerekirse ~1 $)
_Ajan (yalnız sorun kalırsa): cad-artist_"""),

    "uretim": ("⚙️ Dilimleme & Baskı", """⚙️ *Dilimleme ve Baskı*

*⚙️ Dilimle → 3MF* — ürün tipine göre kategori seçer (Figür 0,16 mm · Çerçeve · Harf · Dekor · Standart · Dayanıklı · Hızlı), katman katman analiz eder, havada başlayan parça varsa yalnız tabladan ağaç destek ekler, seçtiğin rengi yazar, tabla önizlemesini gönderir.
Alttaki kategori butonlarıyla değiştirebilirsin.
*🎨 Renk (adım 3, kartela)* — paletten en fazla 4 renk seç: *⚪ Tek renk* (birden çok = mağaza varyantı) · *🎨 Çok renkli tasarla* (seçtiğin renkleri YZ parçalara dağıtır) · *🤖 YZ önersin*. Çok renkte Qwen modelin kendi renderlarını parça kodu renkleriyle boyar, renkler parça sınırlarına oturtulur → 4 yön + stüdyo render ile onayına gelir; benzer renkler (ör. kil/ahşap) uyarılır. Onaydan sonra çok filamentli 3MF: filament başına gram, renk değişimi, tek renge göre ek gram/süre. _~8–10 dk_
*🧩 YZ: Bu Ürüne Yeni Kategori* — slicer-engineer ürüne uygun yeni ayar ailesi ekler (yalnız güvenli ayarlar). _~0,5–1 $_
*🖥️ Orca'da Aç* — bilgisayarda OrcaSlicer'da açar.
*📤 Yazıcıya Yükle* — G-code'u yazıcı belleğine koyar, *başlatmaz*. Önce kontrol listesi: tabla, renk, stok, malzeme.

*Baskı sırasında:* 2. katmanda, riskli katmanlarda ve yarıda fotoğraf + *İyi / 🛑 Durdur*.
*🤖 YZ kontrol (Gemini):* baskı boyunca 5 dk'da bir kamera karesi incelenir: spagetti, tabladan kopma, kalkma, katman kayması, tıkanma, boş tabla. Hata görürse fotoğrafla uyarır; *bot durdurmaz*, sen karar verirsin. *✅ Sorun Yok* → 20 dk sessiz + yanlış alarm olarak kaydedilir. _ücretsiz (Gemini ücretsiz katman)_
*🤖 Baskı sonu raporu:* baskı bitince timelapse'ten 10 kare + YZ geçmişi + ayarlar Gemini'ye gider → gözlemler, *⚙️ dilimleme önerileri* (*Uygula* → onayla kategoriye işlenir, o kategorideki tüm ürünleri etkiler · *⏳ Şimdi Değil* → ayarlar aynı kalır; öneri bekler, `/oneriler` ile istediğin an uygularsın, sonraki baskılarda yine önerilebilir) ve *🛠️ bakım önerileri*.
*🛠️ Bakım* (`/bakim`) — makine saatine göre tabla temizliği, yağlama, kayış… *Yapıldı* butonu sayacı sıfırlar.
*Bitince:* 🏠 Hobi / 🧪 Numune / 📦 Sipariş / 🎁 Hediye-Tanıtım / 🗑️ Fire → ERP'ye işlenir (Hobi ve Hediye ciroya karışmaz; Hediye pazarlama gideri etiketiyle). Numunede *⚖️ tartı* sorulur; yarıda kalan fire yalnız harcanan gram kadar düşülür.
*🖨️ Yazıcı* (`/durum`) · *🧾 Stok* · *🗂️ Üretim Kuyruğu*"""),

    "stok": ("🧾 Stok & Alım", """🧾 *Stok ve Alım (ERP)*

*Fatura / alım listesi gönder* → stok otomatik girilir:
• Faturanın, e-arşivin, sipariş özetinin veya elle yazılmış listenin *fotoğrafını ya da PDF'ini* gönder. Çok sayfalıysa albüm olarak at.
• Açıklamaya `fatura …` yazabilir ya da *🧾 Stok → 🧾 Fatura / Alım Gir* butonunu kullanabilirsin. PDF her zaman alım belgesi sayılır.
• Finans ajanı satırları okur ve ERP'deki filament / malzemelerle eşleştirir.
• Sana tablo gelir: ➕ var olan kalem (stoğa eklenir) · 🆕 yeni kalem (önce oluşturulur).
• *✅ ERP'ye İşle* dersen işlenir; onaysız hiçbir şey yazılmaz.
_Ajan: finance-tracker · ~0,5–1 $_

*Kurallar:*
• Filament gram, fiyat TL/kg; malzeme kendi biriminde. Fiyatlar *KDV dahil* (esnaf muafiyeti).
• Maliyet ağırlıklı ortalamayla güncellenir: kalan stok eski fiyatla, yeni alım yeni fiyatla.
• Her satır ERP'de alım kaydı olarak saklanır; aynı fatura no ikinci kez işlenmez.
• Toplam tutmazsa, fiyat olağan dışıysa ya da okunamayan satır varsa uyarır.

*🧾 Stok* (`/stok`) — filament gram + TL/kg, malzemeler, kritik stok uyarıları, *🔄 Makineye Tak*."""),

    "magaza": ("🛒 Mağaza","""🛒 *Mağaza (İkas)*

*🛒 Mağazaya Hazırla* — fire oranını sorar; ERP'den gerçek maliyet + pazar bandı → fiyat seçenekleri; rakip başlıklardan SEO metni; 2048 px kare, alt metinli galeri.
_Ajan: cmo-store-director · ~1 $_
*Fiyat butonları / ✏️ Elle Fiyat* — fiyatı sen seçersin (başa baş altı kabul edilmez).
*🚀 Mağazaya Yükle* — Chrome ile İkas'ta ürünü birebir oluşturur, sonra yayındaki sayfayı açıp ad / fiyat / görsel / varyantı paketle karşılaştırır.
_Ajan: cmo-store-director · ~1,5 $_

⚠️ İkas'a yükleme için bilgisayardaki Chrome'da İkas oturumunun açık olması gerekir."""),

    "teklif": ("💼 Teklif", """💼 *İşletmeye Teklif (B2B)*

*💼 Teklif Hazırla* (`/teklif <talep>`) — örn: _Kahve Durağı — 120 cm Hoş Geldiniz duvar yazısı mat yeşil + 30 QR menü standı_
1. Teklif ajanı (Sonnet 5.5) her kalemi *gerçek modele* çevirir: yazı/tabela → Kaligraf, QR → QR plaka üreteci, katalog ürünü → mevcut model; OrcaSlicer ile *gerçek gram ve süre* ölçülür.
2. *Opus 5.5 denetler:* yazı metni, ölçü, adet, parça bölme, montaj malzemesi, gram tutarlılığı.
3. Fiyatı *ERP* hesaplar: makine saati + filament + ek malzeme, B2B marjı, adet indirimi (Bronz/Silver/Gold), kargo; esnaf muafiyeti ayarı.
4. Sana özet (maliyet ve kâr dahil) + müşteriye gidecek *Teknik Poster PDF* (maliyet görünmez) gelir.
*✏️ Revize* → notunla yeniden hesaplanır · *✅ Müşteriye Gönderildi* → işaretlenir. Göndermeyi sen yaparsın.
_~1–2 $ (Sonnet modelleme + Opus denetim)_"""),

    "ajanlar": ("🤖 Ajanlar & Maliyet", """🤖 *Ajanlar ve Maliyet*

*Opus 5.5* — karar, kalite, kod; *son söz her zaman Opus'ta*:
• 🎩 ceo-orchestrator — sohbet, yönlendirme, *Sonnet çıktılarının son denetimi*
• 📢 cmo-store-director — Flow konsept, mağaza paketi, İkas yükleme
• 🎨 cad-artist — 3B onarım · 🔧 cto-architect / backend-architect — sistem ve kod
• 🛡️ brand-guardian, ⚖️ legal-compliance-checker

*Sonnet 5.5* — araştırma, okuma, rutin; çıktısı Patrona gitmeden *Opus denetiminden* geçer:
• 🔎 trend-researcher (trend + pazar fiyatı) · 📊 finance-tracker (fatura/alım)
• ⚙️ slicer-engineer (yeni kategori) · 💼 teklif modelleme · diğer pazarlama/destek ajanları

($ = API karşılığı; abonelikte kotadan düşer.) Ürün başına ≈ *5–7 $* (önceki ≈7–9 $).
*Gemini API (ücretsiz katman):* baskı YZ kontrolü (3.5-flash-lite) + baskı sonu raporu (3.5-flash) · 0 $.
*Ücretsiz (yerel):* Qwen görseller, Hunyuan3D, Blender, OrcaSlicer, ffmpeg.
*Google Flow (AI Pro):* görsel 0 kredi · 8 sn Veo video 24 kredi · ayda ~1.000 kredi.

*🤖 Ajanlarla Konuş* — istediğin ajana doğrudan yaz. `/gorevler` çalışanlar, `/iptal` durdurur, `/devam` kota dolunca kaldığı yerden sürdürür."""),

    "komut": ("⌨️ Komutlar", """⌨️ *Komutlar*

`/menu` ana menü · `/kilavuz` bu kılavuz
`/trend <konu>` trend araştır · `/fikir <tarif>` yeni fikir · `/teklif <talep>` işletme teklifi
`/fikir <sku> revize: <not>` konsepti yeniden üret
`/konsept` konsept kütüphanesi (yeni stil eklemek için başlık + istem yapıştır)
`/urunler` ürün kartları · `/ozet` tüm hat özeti
`/durum` yazıcı + kamera · `/stok` · `/kuyruk`
`/gorevler` · `/iptal` · `/devam` · `/bakim` makine bakımı · `/oneriler` bekleyen ayar önerileri

*Fotoğraf gönderince:*
• açıklamada `fikir …` → referanslı yeni fikir
• *🎨 Renk* sonrası → renk örneği
• *📷 Numune* sonrası → gerçek ürün fotoğrafı
• video → Reels + Pinterest kurgusu"""),
}


def kilavuz_dizini() -> tuple[str, list[list[dict[str, str]]]]:
    metin = ("📖 *Kullanım Kılavuzu*\n\nBir bölüm seç. Her bölüm hangi butonun ne yaptığını, hangi ajanın "
             "çalıştığını ve yaklaşık maliyetini anlatır.")
    anahtarlar = list(BOLUMLER)
    satirlar = [[{"text": BOLUMLER[a][0], "callback_data": f"kilavuz:{a}"} for a in anahtarlar[i:i + 2]]
                for i in range(0, len(anahtarlar), 2)]
    satirlar.append([{"text": "🏠 Ana Menü", "callback_data": "menu:ana"}])
    return metin, satirlar


def kilavuz_bolumu(anahtar: str) -> tuple[str, list[list[dict[str, str]]]]:
    if anahtar not in BOLUMLER:
        return kilavuz_dizini()
    anahtarlar = list(BOLUMLER)
    i = anahtarlar.index(anahtar)
    gezinme = []
    if i > 0:
        gezinme.append({"text": f"◀️ {BOLUMLER[anahtarlar[i - 1]][0]}", "callback_data": f"kilavuz:{anahtarlar[i - 1]}"})
    if i < len(anahtarlar) - 1:
        gezinme.append({"text": f"{BOLUMLER[anahtarlar[i + 1]][0]} ▶️", "callback_data": f"kilavuz:{anahtarlar[i + 1]}"})
    return BOLUMLER[anahtar][1], [gezinme, [{"text": "📖 Kılavuz", "callback_data": "kilavuz:ana"},
                                           {"text": "🏠 Ana Menü", "callback_data": "menu:ana"}]]
