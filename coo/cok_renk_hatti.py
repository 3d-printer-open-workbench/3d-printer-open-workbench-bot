"""Çok renkli 3MF hattı (bot tarafı; ağır işler alt süreçte).

Patron kararı 2026-11-16: çok renk boyamayı Claude ajanı Blender'da yapar (Qwen değil).
1) `claude_boyama_istemi`: ajan paletten ≤4 renk seçer, `coo/cok_renk_claude.py parcala` ile modeli numaralı
   bölgelerde görür, parça→renk kurallarını yazar, `boya` ile uygular (sınırlar iç bükey kıvrımlara oturur) ve
   6 açılı panoyu kendisi denetleyip doğru olana kadar düzeltir → `renkli.3mf`, `sema_son.json`, `rapor.json`.
2) Patron onayından sonra `orca_dilim.dilimle_3mf(boyama=...)` çok filamentli dilimler.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .ayar import PROGRAMLAR_KLASORU, PY_AI3D, URUNLER_KLASORU

MAKS_RENK = 4


def klasor(sku: str, urunler: Path | None = None) -> Path:
    return (urunler or URUNLER_KLASORU) / sku / "model" / "cok_renk"


def guncel_mi(sku: str, urunler: Path | None = None) -> bool:
    """Boyalı 3MF, şu anki STL'den yeni mi (model değiştiyse renk yeniden aktarılmalı)?"""
    kok = (urunler or URUNLER_KLASORU) / sku
    r = klasor(sku, urunler) / "renkli.3mf"
    stl = kok / "model" / f"{sku}.stl"
    return r.exists() and stl.exists() and r.stat().st_mtime >= stl.stat().st_mtime


def claude_boyama_istemi(sku: str, palet: list[dict[str, Any]], not_: str = "", onceki: list[str] | None = None,
                         urunler: Path | None = None, zorunlu: list[dict[str, Any]] | None = None,
                         maks_tur: int = 5) -> str:
    """Patron kararı 2026-11-16: çok renk boyamayı Claude yapar (Blender), Qwen değil. Ajan şemayı seçer, modeli
    numaralı parçalarda görür, parça→renk kurallarını yazar, boyalı panoyu kendisi denetler ve doğru olana kadar
    düzeltir; sonunda sema.json + sema_son.json + rapor.json (bot bunlarla Patrona onaya sunar)."""
    kok = (urunler or URUNLER_KLASORU) / sku
    k = klasor(sku, urunler)
    k.mkdir(parents=True, exist_ok=True)
    py = PY_AI3D
    pal = "\n".join(
        f"- {r.get('ad')} `{r.get('hex')}` — {r.get('marka') or '?'} {r.get('malzeme') or ''}"
        f"{' · stokta' if r.get('stokta') else ' · STOKTA YOK'}{'' if r.get('dogrulandi') else ' · HEX tahmini'}"
        for r in palet if r.get("hex")
    ) or "- (palet boş)"
    arac = f"cd {PROGRAMLAR_KLASORU} && {py} -m coo.cok_renk_claude"
    return (
        f"Görev: `{sku}` ürününü ÇOK RENKLİ basmak için (Elegoo Centauri Carbon + CANVAS, en fazla {MAKS_RENK} filament) "
        "renk şemasını seç ve modeli Blender'da SEN boya. Qwen / görsel üretici KULLANMA.\n"
        f"Ürünü tanı (Read): `{kok / 'urun.yaml'}`, konsept görselleri `{kok / 'konsept'}` ve `{kok / 'gorsel'}` (varsa).\n"
        f"Renk paleti (yalnız BUNLARDAN; HEX'i aynen kullan):\n{pal}\n"
        + (("PATRON RENKLERİ KARTELADAN SEÇTİ — yalnız ve tam olarak bunları kullan, hepsini bir parçaya ata: "
             + "; ".join(f"{r.get('ad')} `{r.get('hex')}`" for r in zorunlu) + "\n") if zorunlu else "")
        + (f"Patronun notu: {not_}\n" if not_ else "")
        + (f"Daha önce beğenilmeyen şemalar (TEKRARLAMA): {'; '.join(onceki)}\n" if onceki else "")
        + "Şema kuralları: 2–4 renk, birbirinden belirgin farklı; her renk büyük, net bir PARÇAYA (şapka, kıyafet, "
        "tepsi/taban…). Göz/düğme gibi küçük ayrıntılara renk verme. Konsepte uygun, satılabilir, sade.\n"
        "BASKI KOLAYLIĞI (Patron 2026-11-18): renk değişimi en az olsun ama boyama bozulmasın. Her katmanda bulunan "
        "her ek renk bir filament değişimidir; bir rengin z aralığını gereksiz uzatan ince şerit/taşma (yanak içinde "
        "kalan gövde rengi, kaskın aşağı sarkan kenarı) yüzlerce katman ekler. Yatay ayrımı (taban/gövde) z_min/z_max "
        "ile düz kes; aynı yüksekliklerde zaten bulunan rengi tercih et. `boya` ince uçları otomatik kırpar ve "
        "sınırları düzler; rapordaki `renk_degisimi_tahmini` (önce: `renk_degisimi_sadelestirmeden`) değerine bak.\n"
        "ADIMLAR (Bash):\n"
        f"1) `{arac} parcala {sku}` → `{k / 'parcalar_pano.png'}` (6 açı, NUMARALI bölgeler) ve `{k / 'parcalar.json'}` "
        "(bölge alanı, z aralığı mm). Panoyu Read ile dikkatle incele; her numaranın modelde neye denk geldiğini çıkar. "
        "Bir bölge iki parçayı kapsıyorsa daha ince bölmek için `--hedef 70` ile yeniden çalıştır.\n"
        f"2) Kuralları `{k / 'kurallar.json'}` dosyasına yaz (sırayla uygulanır, sonraki öncekini ezer): "
        '[{"renk": 1, "parcalar": [3, 7]}, {"renk": 2, "parcalar": [5], "z_min": 40.0}, {"renk": 0, "z_max": 2.0}]. '
        "renk = --renkler listesindeki sıra (0'dan). Kurala girmeyen her yüz --varsayilan rengini alır (genelde en büyük "
        "parça: tepsi/taban/gövde).\n"
        f"3) `{arac} boya {sku} --renkler '#HEX1,#HEX2,...' --kurallar {k / 'kurallar.json'} --varsayilan 0 --studyo-yok` "
        "→ sınırlar kıvrımlara oturtulur, `boyali_pano.png` (6 açı) üretilir.\n"
        f"4) `{k / 'boyali_pano.png'}`'yi Read ile 6 açıdan DENETLE: her parça tamamen doğru renkte mi; yarım boyanmış "
        "şapka, taşan/eksik bölge, yanlış renge kaçan küçük parça, alt yüzde yanlış renk var mı? Hata varsa kuralları "
        f"düzelt (bölge ekle/çıkar, z/x/y sınırı ver) ve 3'ü tekrarla. En fazla {maks_tur} tur.\n"
        f"5) Doğru olunca son kez `--studyo-yok` OLMADAN çalıştır (stüdyo render). Sonra `{k / 'sema.json'}` ve aynısını "
        f"`{k / 'sema_son.json'}` olarak Write ile yaz:\n"
        '{"ad": "kısa şema adı", "yontem": "claude-blender", "renkler": [{"hex": "#E2DDC7", "ad": "Kemik", "parcalar": "tepsi ve taban"}, ...], '
        '"gerekce": "neden bu şema (2 cümle)", "denetim": "son turda 6 açıda gördüklerin (1-2 cümle)", "tur": <kaç tur>, '
        '"renk_degisimi_tahmini": <rapor.json\'daki değer>}\n'
        f"{maks_tur} turda doğru boyanamadıysa yine yaz ama `denetim` alanına kalan sorunu açıkça yaz. "
        "Ürün klasöründe başka dosyaya dokunma, yazıcıya iş gönderme."
    )
