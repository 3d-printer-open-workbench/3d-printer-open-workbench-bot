"""Yerel web okuyucu — Crawl4AI (Apache-2.0) ile tek sayfa okuma (ücretsiz, yerel; Firecrawl yerine).

Yalnız OKUR: tek URL'ye GET (gerçek tarayıcı, Playwright Chromium), form/POST/oturum yok, bağlantı takibi yok.
Kurallar:
  * robots.txt'ye uyulur (Crawl4AI `check_robots_txt`). Yasaklı sayfa için `engel="robots"` döner;
    ajan WebFetch'e, o da olmazsa Chrome yedeğine geçer (ör. Trendyol `/sr?`, Etsy `/search?q=` arama sayfaları).
  * Alan adı başına en az `ORAN_SN` saniye aralık (süreçler arası dosya kilidiyle).
  * Yerel/özel ağ adresleri (localhost, loopback, özel IP blokları, link-local; yazıcı, ERP) okunmaz;
    kullanıcı:parola@ içeren URL reddedilir.
  * Cloudflare/DataDome gibi bot engeli sezilirse `engel="bot"` döner → Chrome yedeği.

Kullanım:
    from coo.web_oku import oku
    oku("https://example.com")                             # {"basarili", "icerik" (markdown), ...}
    oku(url, bicim="links")                                # {"baglantilar": [{"url","metin","ic"}]}
    python -m coo.web_oku <url> [--bicim markdown|html|links] [--bekle 3] [--json]

Crawl4AI ayrı bir ortamda durabilir (`<WORKBENCH_ENVS>/.venv-crawl`, varsayılan `ortamlar/.venv-crawl`; kurulum
`requirements-crawl.txt`). Bot başka ortamdan çağırırsa `oku()` o ortamın Python'unu alt süreç olarak çalıştırır
(aynı sonuç sözlüğü).
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

PROGRAMLAR = Path(__file__).resolve().parents[1]
_ORTAMLAR = Path(os.environ.get("WORKBENCH_ENVS") or Path(os.environ.get("WORKBENCH_ROOT") or PROGRAMLAR) / "ortamlar")
PY_CRAWL = _ORTAMLAR.expanduser() / ".venv-crawl" / "bin" / "python"
ORAN_KLASORU = Path(os.environ.get("WORKBENCH_WEB_ORAN_KLASORU") or Path.home() / ".cache" / "workbench-web")
ORAN_SN = float(os.environ.get("WORKBENCH_WEB_ORAN_SN", "3"))
VARSAYILAN_ZAMAN_ASIMI_SN = 45
VARSAYILAN_MAKS_KARAKTER = 80_000
BICIMLER = ("markdown", "html", "links")
KAYNAK = "crawl4ai"

# Bot engeli / meydan okuma sayfası imleri (küçük harf aranır).
BOT_ENGEL_IMLERI = (
    "just a moment...",
    "cf-browser-verification",
    "challenge-platform",
    "attention required! | cloudflare",
    "checking your browser before accessing",
    "px-captcha",
    "captcha-delivery.com",
    "datadome",
    "pardon our interruption",
    "are you a robot",
    "robot or human",
    "verify you are human",
    "access denied",
    "request unsuccessful. incapsula",
)
ENGEL_DURUM_KODLARI = {401, 403, 429, 503}

# Ajan istemlerine eklenen ortak talimat (trend, pazar fiyatı, Reels trendi …). Firecrawl yalnız isteğe bağlı yedek.
WEB_OKUMA_SIRASI = (
    "Web sayfası OKUMA sırası: (a) yerel `mcp__workbench-web__web_oku` (Crawl4AI, "
    "ücretsiz; ürün URL'si toplamak için `web_baglantilar`) — MCP aracı yoksa Bash: `python3 -m coo.web_oku <url>`; "
    "(b) çıktı 'ENGEL: robots' derse ya da okunamazsa WebFetch; (c) 'ENGEL: bot' (Cloudflare/DataDome, ör. Etsy) "
    "derse Chrome yedeği (yetkin varsa). Arama/keşif için WebSearch; Trendyol `/sr?` ve Etsy `/search?q=` arama "
    "sayfaları robots.txt ile kapalıdır, kategori/ürün sayfalarını oku. Firecrawl varsayılan DEĞİL (kredili, "
    "isteğe bağlı yedek). Kaynak URL + erişim tarihi olarak web_oku çıktısının ilk satırındaki son URL ve zamanı yaz.\n"
)


class WebOkuHatasi(ValueError):
    """Geçersiz veya izin verilmeyen URL / biçim."""


# ---------------------------------------------------------------- denetimler

def url_denetle(url: str) -> str:
    """URL'yi doğrular ve normalleştirir. Yalnız herkese açık http(s) adresleri."""
    url = (url or "").strip()
    if not url:
        raise WebOkuHatasi("URL boş.")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.I):
        if re.match(r"^[a-z][a-z0-9+.-]*:(?!\d)", url, re.I):  # javascript:, data:, mailto: … (host:port değil)
            raise WebOkuHatasi(f"Yalnız http/https okunur (verilen: {url.split(':', 1)[0]}).")
        url = "https://" + url
    p = urllib.parse.urlsplit(url)
    if p.scheme.lower() not in ("http", "https"):
        raise WebOkuHatasi(f"Yalnız http/https okunur (verilen: {p.scheme}).")
    if p.username or p.password:
        raise WebOkuHatasi("Kullanıcı adı/parola içeren URL okunmaz.")
    host = (p.hostname or "").lower().rstrip(".")
    if not host:
        raise WebOkuHatasi("URL'de alan adı yok.")
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local") or host.endswith(".lan"):
        raise WebOkuHatasi(f"Yerel ağ adresi okunmaz: {host}")
    _ozel_ag_denetle(host)
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc, p.path or "/", p.query, ""))


def _ozel_ag_mi(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    return a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved or a.is_unspecified


def _ozel_ag_denetle(host: str) -> None:
    try:
        ipaddress.ip_address(host)
        adresler = [host]
    except ValueError:
        try:
            adresler = sorted({b[4][0] for b in socket.getaddrinfo(host, None)})
        except socket.gaierror:
            return  # çözülemeyen ad: tarayıcı zaten hata verecek
    for ip in adresler:
        if _ozel_ag_mi(ip.split("%", 1)[0]):
            raise WebOkuHatasi(f"Özel/yerel ağ adresi okunmaz: {host} → {ip}")


def bot_engeli_mi(durum_kodu: int | None, html: str, metin: str = "") -> bool:
    """Durum kodu + sayfa imlerinden bot engeli / meydan okuma sayfası sezgisi."""
    kucuk = f"{(html or '')[:20000]}\n{(metin or '')[:5000]}".lower()
    im = any(i in kucuk for i in BOT_ENGEL_IMLERI)
    if durum_kodu in ENGEL_DURUM_KODLARI:
        return True
    # 200 dönen meydan okuma sayfaları: im var ve içerik çok kısa
    return im and len((metin or "").strip()) < 1500


def oran_bekle(host: str, aralik_sn: float | None = None, klasor: Path | None = None) -> float:
    """Alan adı başına en az `aralik_sn` aralık; gerekiyorsa bekler. Beklenen süreyi döndürür."""
    aralik = ORAN_SN if aralik_sn is None else aralik_sn
    if aralik <= 0:
        return 0.0
    klasor = klasor or ORAN_KLASORU
    klasor.mkdir(parents=True, exist_ok=True)
    dosya = klasor / "oran.json"
    with open(klasor / "oran.kilit", "a+") as kilit:
        fcntl.flock(kilit, fcntl.LOCK_EX)
        try:
            kayit = json.loads(dosya.read_text(encoding="utf-8")) if dosya.exists() else {}
        except Exception:
            kayit = {}
        simdi = time.time()
        bekle = max(0.0, float(kayit.get(host, 0)) + aralik - simdi)
        if bekle:
            time.sleep(bekle)
        kayit[host] = time.time()
        esik = time.time() - 86400
        kayit = {h: t for h, t in kayit.items() if t > esik}
        dosya.write_text(json.dumps(kayit), encoding="utf-8")
    return bekle


# ---------------------------------------------------------------- sonuç biçimleme

def _bos_sonuc(url: str, bicim: str) -> dict[str, Any]:
    return {
        "url": url, "son_url": None, "basarili": False, "durum_kodu": None, "bicim": bicim, "baslik": None,
        "icerik": None, "baglantilar": None, "karakter": 0, "kesildi": False, "engel": None, "hata": None,
        "oneri": None, "kaynak": KAYNAK, "tarih": dt.datetime.now().isoformat(timespec="seconds"),
    }


def _baglantilari_duzle(baglantilar: dict | None, sinir: int = 500) -> list[dict[str, Any]]:
    cikti: list[dict[str, Any]] = []
    gorulen: set[str] = set()
    for tur, ic in (("internal", True), ("external", False)):
        for b in (baglantilar or {}).get(tur) or []:
            href = (b.get("href") if isinstance(b, dict) else str(b)) or ""
            if not href.startswith(("http://", "https://")) or href in gorulen:
                continue
            gorulen.add(href)
            metin = (b.get("text") or "").strip() if isinstance(b, dict) else ""
            cikti.append({"url": href, "metin": re.sub(r"\s+", " ", metin)[:200], "ic": ic})
            if len(cikti) >= sinir:
                return cikti
    return cikti


def sonucu_bicimle(url: str, bicim: str, r: Any, maks_karakter: int = VARSAYILAN_MAKS_KARAKTER) -> dict[str, Any]:
    """Crawl4AI CrawlResult → sonuç sözlüğü (bağımlılıksız; testlerde sahte nesneyle sınanır)."""
    s = _bos_sonuc(url, bicim)
    s["durum_kodu"] = getattr(r, "status_code", None)
    s["son_url"] = getattr(r, "redirected_url", None) or getattr(r, "url", None) or url
    meta = getattr(r, "metadata", None) or {}
    s["baslik"] = (meta.get("title") or None) if isinstance(meta, dict) else None
    hata = getattr(r, "error_message", None) or None
    html = getattr(r, "html", None) or ""
    md_nesne = getattr(r, "markdown", None)
    md = (getattr(md_nesne, "raw_markdown", None) if md_nesne is not None and not isinstance(md_nesne, str)
          else md_nesne) or ""

    if not getattr(r, "success", False):
        if hata and "robots.txt" in hata.lower():
            s["engel"] = "robots"
            s["hata"] = "robots.txt bu sayfanın otomatik okunmasını yasaklıyor."
            s["oneri"] = "WebFetch ile dene; olmazsa Chrome yedeği (izinli ajan). Ürün/kategori sayfası çoğu zaman açıktır."
            return s
        s["hata"] = hata or "Sayfa okunamadı."
        if bot_engeli_mi(s["durum_kodu"], html, md):
            s["engel"] = "bot"
            s["oneri"] = "Bot engeli: Chrome yedeğini kullan (claude-in-chrome, izinli ajan)."
        return s

    if bot_engeli_mi(s["durum_kodu"], html, md):
        s["engel"] = "bot"
        s["hata"] = f"Bot engeli / meydan okuma sayfası (HTTP {s['durum_kodu']})."
        s["oneri"] = "Bot engeli: Chrome yedeğini kullan (claude-in-chrome, izinli ajan)."
        return s

    if bicim == "links":
        s["baglantilar"] = _baglantilari_duzle(getattr(r, "links", None))
        s["karakter"] = len(s["baglantilar"])
    else:
        metin = md if bicim == "markdown" else (getattr(r, "cleaned_html", None) or html)
        if len(metin) > maks_karakter:
            metin, s["kesildi"] = metin[:maks_karakter], True
        s["icerik"] = metin
        s["karakter"] = len(metin)
        if not metin.strip():
            s["hata"] = "Sayfa boş döndü (JS ile geç yükleniyor olabilir; bekle_sn artır)."
            return s
    s["basarili"] = True
    return s


# ---------------------------------------------------------------- okuma

async def _oku_async(url: str, bicim: str, bekle_sn: float | None, zaman_asimi_sn: float,
                     maks_karakter: int) -> dict[str, Any]:
    os.environ.setdefault("CRAWL4AI_NO_CLOUD_NOTICE", "1")
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

    tarayici = BrowserConfig(headless=True, enable_stealth=True, verbose=False,
                             headers={"Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"})
    ayar = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        check_robots_txt=True,
        page_timeout=int(zaman_asimi_sn * 1000),
        wait_until="domcontentloaded",
        delay_before_return_html=2.0 if bekle_sn is None else float(bekle_sn),
        magic=True,
        remove_overlay_elements=True,
        scan_full_page=bicim != "html",
        verbose=False,
    )
    # Crawl4AI ilerleme satırlarını stdout'a basabilir; MCP stdio ve --json çıktısını bozmasın.
    with contextlib.redirect_stdout(sys.stderr):
        async with AsyncWebCrawler(config=tarayici) as c:
            r = await c.arun(url, config=ayar)
    return sonucu_bicimle(url, bicim, r, maks_karakter)


def _crawl4ai_var() -> bool:
    try:
        import crawl4ai  # noqa: F401
        return True
    except Exception:
        return False


def _alt_surecle_oku(url: str, bicim: str, bekle_sn: float | None, zaman_asimi_sn: float,
                     maks_karakter: int) -> dict[str, Any]:
    s = _bos_sonuc(url, bicim)
    if not PY_CRAWL.exists():
        s["hata"] = f"Crawl4AI ortamı yok: {PY_CRAWL} (requirements-crawl.txt ile kurun)."
        return s
    komut = [str(PY_CRAWL), "-m", "coo.web_oku", url, "--bicim", bicim, "--json",
             "--zaman-asimi", str(zaman_asimi_sn), "--maks-karakter", str(maks_karakter)]
    if bekle_sn is not None:
        komut += ["--bekle", str(bekle_sn)]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(x for x in (str(PROGRAMLAR), env.get("PYTHONPATH", "")) if x)
    env.setdefault("CRAWL4AI_NO_CLOUD_NOTICE", "1")
    try:
        p = subprocess.run(komut, capture_output=True, text=True, timeout=zaman_asimi_sn + 60, env=env,
                           cwd=str(PROGRAMLAR))
    except subprocess.TimeoutExpired:
        s["hata"] = f"Zaman aşımı ({zaman_asimi_sn:.0f} sn + 60)."
        return s
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        s["hata"] = f"Crawl4AI alt süreci çıktı vermedi: {(p.stderr or '')[-300:]}"
        return s


def oku(url: str, bicim: str = "markdown", bekle_sn: float | None = None, *,
        zaman_asimi_sn: float = VARSAYILAN_ZAMAN_ASIMI_SN,
        maks_karakter: int = VARSAYILAN_MAKS_KARAKTER) -> dict[str, Any]:
    """Tek sayfayı okur. bicim: markdown | html | links. Hiç istisna fırlatmaz; hata `hata` alanındadır."""
    if bicim not in BICIMLER:
        s = _bos_sonuc(url, bicim)
        s["hata"] = f"Geçersiz biçim: {bicim} (seçenekler: {', '.join(BICIMLER)})"
        return s
    try:
        temiz = url_denetle(url)
    except WebOkuHatasi as e:
        s = _bos_sonuc(url, bicim)
        s["hata"] = str(e)
        return s
    if not _crawl4ai_var():
        return _alt_surecle_oku(temiz, bicim, bekle_sn, zaman_asimi_sn, maks_karakter)
    oran_bekle(urllib.parse.urlsplit(temiz).hostname or "")
    import asyncio
    try:
        return asyncio.run(asyncio.wait_for(
            _oku_async(temiz, bicim, bekle_sn, zaman_asimi_sn, maks_karakter), timeout=zaman_asimi_sn + 30))
    except asyncio.TimeoutError:
        s = _bos_sonuc(temiz, bicim)
        s["hata"] = f"Zaman aşımı ({zaman_asimi_sn:.0f} sn)."
        return s
    except Exception as e:  # tarayıcı başlatma vb.
        s = _bos_sonuc(temiz, bicim)
        s["hata"] = f"{type(e).__name__}: {str(e)[:300]}"
        return s


async def oku_async(url: str, bicim: str = "markdown", bekle_sn: float | None = None, *,
                    zaman_asimi_sn: float = VARSAYILAN_ZAMAN_ASIMI_SN,
                    maks_karakter: int = VARSAYILAN_MAKS_KARAKTER) -> dict[str, Any]:
    """MCP sunucusu gibi zaten olay döngüsü içinde çalışanlar için (Crawl4AI kurulu ortamda)."""
    import asyncio
    if bicim not in BICIMLER:
        s = _bos_sonuc(url, bicim)
        s["hata"] = f"Geçersiz biçim: {bicim}"
        return s
    try:
        temiz = url_denetle(url)
    except WebOkuHatasi as e:
        s = _bos_sonuc(url, bicim)
        s["hata"] = str(e)
        return s
    await asyncio.to_thread(oran_bekle, urllib.parse.urlsplit(temiz).hostname or "")
    try:
        return await asyncio.wait_for(_oku_async(temiz, bicim, bekle_sn, zaman_asimi_sn, maks_karakter),
                                      timeout=zaman_asimi_sn + 30)
    except asyncio.TimeoutError:
        s = _bos_sonuc(temiz, bicim)
        s["hata"] = f"Zaman aşımı ({zaman_asimi_sn:.0f} sn)."
        return s
    except Exception as e:
        s = _bos_sonuc(temiz, bicim)
        s["hata"] = f"{type(e).__name__}: {str(e)[:300]}"
        return s


def ozet_metni(s: dict[str, Any]) -> str:
    """İnsan/ajan için okunur çıktı: başlık satırı + içerik veya bağlantı listesi."""
    bas = (f"# web_oku · {s.get('son_url') or s.get('url')} · HTTP {s.get('durum_kodu')} · {s.get('tarih')} "
           f"· kaynak: {s.get('kaynak')}")
    if not s.get("basarili"):
        return f"{bas}\nOKUNAMADI: {s.get('hata')}" + (f"\nENGEL: {s['engel']}" if s.get("engel") else "") + \
            (f"\nÖNERİ: {s['oneri']}" if s.get("oneri") else "")
    if s.get("bicim") == "links":
        satirlar = [f"- {b['url']}" + (f" — {b['metin']}" if b.get("metin") else "") for b in s["baglantilar"]]
        return f"{bas}\n{len(satirlar)} bağlantı\n" + "\n".join(satirlar)
    ek = "\n[… içerik kesildi]" if s.get("kesildi") else ""
    return f"{bas}\n{('Başlık: ' + s['baslik']) if s.get('baslik') else ''}\n\n{s.get('icerik') or ''}{ek}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m coo.web_oku", description="Crawl4AI ile tek sayfa okur (yalnız GET).")
    ap.add_argument("url")
    ap.add_argument("--bicim", choices=BICIMLER, default="markdown")
    ap.add_argument("--bekle", type=float, default=None, help="Sayfa yüklendikten sonra ek bekleme (sn)")
    ap.add_argument("--zaman-asimi", type=float, default=VARSAYILAN_ZAMAN_ASIMI_SN)
    ap.add_argument("--maks-karakter", type=int, default=VARSAYILAN_MAKS_KARAKTER)
    ap.add_argument("--json", action="store_true", help="Sonuç sözlüğünü tek satır JSON yaz")
    a = ap.parse_args(argv)
    s = oku(a.url, a.bicim, a.bekle, zaman_asimi_sn=a.zaman_asimi, maks_karakter=a.maks_karakter)
    print(json.dumps(s, ensure_ascii=False) if a.json else ozet_metni(s))
    return 0 if s.get("basarili") else 1


if __name__ == "__main__":
    sys.exit(main())
