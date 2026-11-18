"""Yerel web okuyucu (coo.web_oku, Crawl4AI) — Firecrawl yerine.

Ağsız testler sahte CrawlResult ile çalışır (Crawl4AI test ortamında gerekmez). Gerçek ağ testi yalnız
WORKBENCH_AG_TESTI=1 ve .venv-crawl kuruluysa çalışır.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from coo import web_oku as w


@pytest.fixture(autouse=True)
def dns_yok(monkeypatch):
    """Testler DNS'e çıkmasın: herkese açık sahte adres döndür."""
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])


# ---------------------------------------------------------------- URL denetimi

@pytest.mark.parametrize("url,beklenen", [
    ("example.com", "https://example.com/"),
    ("https://www.trendyol.com/sr?q=a#x", "https://www.trendyol.com/sr?q=a"),
    ("HTTP://Etsy.com/listing/1", "http://Etsy.com/listing/1"),
])
def test_url_normallesir(url, beklenen):
    assert w.url_denetle(url) == beklenen


@pytest.mark.parametrize("url", [
    "", "ftp://x.com/a", "file:///etc/passwd", "javascript:alert(1)", "https://user:pw@x.com/",
    "http://localhost:8000/api", "http://127.0.0.1:8000/api/products", "http://172.31.255.1/",
    "http://10.0.0.1", "http://172.16.0.5/", "http://[::1]/", "http://169.254.169.254/latest/meta-data",
    "http://yazici.local/", "http://nas.lan/",
])
def test_yerel_ve_gecersiz_url_reddedilir(url):
    with pytest.raises(w.WebOkuHatasi):
        w.url_denetle(url)


def test_ozel_aga_cozulen_alan_adi_reddedilir(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.1.2.3", 0))])
    with pytest.raises(w.WebOkuHatasi, match="Özel"):
        w.url_denetle("https://kotu.example.com/")


def test_oku_gecersiz_url_ve_bicim_istisna_firlatmaz():
    s = w.oku("http://127.0.0.1:8000/api")
    assert s["basarili"] is False and "okunmaz" in s["hata"]
    s = w.oku("https://example.com", bicim="pdf")
    assert s["basarili"] is False and "Geçersiz biçim" in s["hata"]


# ---------------------------------------------------------------- bot engeli

def test_bot_engeli_sezgisi():
    assert w.bot_engeli_mi(403, "<html>x</html>")
    assert w.bot_engeli_mi(429, "")
    assert w.bot_engeli_mi(200, "<title>Just a moment...</title><div class=cf-browser-verification>", "Just a moment")
    assert not w.bot_engeli_mi(200, "<html>ürün</html>", "Örnek Kulaklık Standı ₺ 799.90")
    # Uzun gerçek içerikte geçen "datadome" betiği engel sayılmaz
    assert not w.bot_engeli_mi(200, "<script src=//js.datadome.co/tags.js>", "ürün " * 600)


# ---------------------------------------------------------------- sonuç biçimleme

def _sahte(**k):
    temel = dict(success=True, status_code=200, url="https://example.com/", redirected_url=None,
                 metadata={"title": "Example"}, error_message="", html="<html>ok</html>",
                 cleaned_html="<div>ok</div>", markdown=SimpleNamespace(raw_markdown="# Ürün\nÖrnek Stand ₺ 799.90"),
                 links={})
    temel.update(k)
    return SimpleNamespace(**temel)


def test_markdown_sonucu():
    s = w.sonucu_bicimle("https://example.com/", "markdown", _sahte())
    assert s["basarili"] and s["baslik"] == "Example" and "₺ 799.90" in s["icerik"]
    assert s["kaynak"] == "crawl4ai" and s["tarih"] and s["engel"] is None


def test_markdown_kesilir():
    s = w.sonucu_bicimle("u", "markdown", _sahte(markdown=SimpleNamespace(raw_markdown="a" * 500)), maks_karakter=100)
    assert s["kesildi"] and s["karakter"] == 100


def test_html_bicimi_temiz_html_dondurur():
    s = w.sonucu_bicimle("u", "html", _sahte())
    assert s["icerik"] == "<div>ok</div>"


def test_robots_engeli_webfetch_onerir():
    r = _sahte(success=False, status_code=403, error_message="Access denied by robots.txt", markdown=None)
    s = w.sonucu_bicimle("https://www.trendyol.com/sr?q=a", "markdown", r)
    assert s["engel"] == "robots" and not s["basarili"] and "WebFetch" in s["oneri"]


def test_bot_engeli_chrome_onerir():
    r = _sahte(success=False, status_code=403, error_message="Blocked by anti-bot protection: DataDome captcha",
               markdown=None, html="")
    s = w.sonucu_bicimle("https://www.etsy.com/market/x", "markdown", r)
    assert s["engel"] == "bot" and "Chrome" in s["oneri"]
    r = _sahte(html="<title>Just a moment...</title>", markdown=SimpleNamespace(raw_markdown="Just a moment..."))
    assert w.sonucu_bicimle("u", "markdown", r)["engel"] == "bot"


def test_baglantilar_duzlenir_ve_tekillesir():
    links = {"internal": [{"href": "https://example.com/a", "text": " Örnek  Stand "},
                          {"href": "https://example.com/a", "text": "kopya"},
                          {"href": "/goreli", "text": "x"}],
             "external": [{"href": "https://instagram.com/example", "text": ""}]}
    s = w.sonucu_bicimle("u", "links", _sahte(links=links))
    assert s["baglantilar"] == [
        {"url": "https://example.com/a", "metin": "Örnek Stand", "ic": True},
        {"url": "https://instagram.com/example", "metin": "", "ic": False},
    ]
    assert "2 bağlantı" in w.ozet_metni(s)


def test_ozet_metni_kaynak_ve_engel_satirlari():
    s = w.sonucu_bicimle("https://example.com/", "markdown", _sahte())
    ilk = w.ozet_metni(s).splitlines()[0]
    assert "example.com" in ilk and "HTTP 200" in ilk and "crawl4ai" in ilk
    r = _sahte(success=False, status_code=403, error_message="Access denied by robots.txt")
    m = w.ozet_metni(w.sonucu_bicimle("u", "markdown", r))
    assert "OKUNAMADI" in m and "ENGEL: robots" in m


# ---------------------------------------------------------------- oran sınırı

def test_oran_siniri_ayni_alan_adinda_bekletir(tmp_path, monkeypatch):
    uykular: list[float] = []
    monkeypatch.setattr(w.time, "sleep", lambda s: uykular.append(s))
    assert w.oran_bekle("etsy.com", 5, tmp_path) == 0
    assert w.oran_bekle("etsy.com", 5, tmp_path) > 4
    assert w.oran_bekle("trendyol.com", 5, tmp_path) == 0
    assert len(uykular) == 1
    assert set(json.loads((tmp_path / "oran.json").read_text())) == {"etsy.com", "trendyol.com"}


# ---------------------------------------------------------------- alt süreç (crawl4ai başka ortamda)

def test_crawl4ai_yoksa_venv_crawl_alt_sureci_cagrilir(monkeypatch, tmp_path):
    sahte_py = tmp_path / "python"
    sahte_py.write_text("")
    monkeypatch.setattr(w, "PY_CRAWL", sahte_py)
    monkeypatch.setattr(w, "_crawl4ai_var", lambda: False)
    cagri = {}

    def sahte_run(komut, **k):
        cagri["komut"] = komut
        cikti = dict(w._bos_sonuc("https://example.com/", "markdown"), basarili=True, icerik="x")
        return subprocess.CompletedProcess(komut, 0, stdout="log\n" + json.dumps(cikti), stderr="")

    monkeypatch.setattr(w.subprocess, "run", sahte_run)
    s = w.oku("example.com", bekle_sn=3)
    assert s["basarili"] and s["icerik"] == "x"
    k = cagri["komut"]
    assert k[:3] == [str(sahte_py), "-m", "coo.web_oku"] and "--json" in k and k[k.index("--bekle") + 1] == "3"


def test_venv_crawl_yoksa_aciklayici_hata(monkeypatch, tmp_path):
    monkeypatch.setattr(w, "PY_CRAWL", tmp_path / "yok" / "python")
    monkeypatch.setattr(w, "_crawl4ai_var", lambda: False)
    s = w.oku("https://example.com")
    assert not s["basarili"] and "requirements-crawl.txt" in s["hata"]


# ---------------------------------------------------------------- istemler

def test_istemler_once_yerel_web_oku_der(tmp_path):
    from coo.pazar_hatti import pazar_istemi
    from coo.__main__ import _trend_istemi
    for istem in (pazar_istemi("x", tmp_path), _trend_istemi("masa", "p1")):
        assert "mcp__workbench-web__web_oku" in istem
        i_yerel, i_fetch, i_chrome = istem.index("web_oku"), istem.index("WebFetch"), istem.index("Chrome")
        assert i_yerel < i_fetch < i_chrome
        assert "Firecrawl varsayılan DEĞİL" in istem


def test_mcp_kaydi_ve_izin():
    kok = Path(w.__file__).resolve().parents[1]
    mcp = json.loads((kok / ".mcp.json.example").read_text())["mcpServers"]["workbench-web"]
    assert mcp["args"] == ["-m", "coo.web_mcp"] and mcp["command"].endswith(".venv-crawl/bin/python")
    izin = json.loads((kok / ".claude" / "settings.json").read_text())["permissions"]["allow"]
    assert "mcp__workbench-web__*" in izin
    yetki = json.loads((kok / "config" / "guvenlik" / "ajan_yetkileri.json").read_text())
    import re
    assert not any(re.search(p, "mcp__workbench-web__web_oku") for p in yetki["dis_mcp_eylemleri"])


# ---------------------------------------------------------------- gerçek ağ (isteğe bağlı)

@pytest.mark.skipif(os.environ.get("WORKBENCH_AG_TESTI") != "1" or not w.PY_CRAWL.exists(),
                    reason="ağ testi: WORKBENCH_AG_TESTI=1 ve .venv-crawl gerekir")
def test_ag_ornek_site_okunur(monkeypatch):
    monkeypatch.undo()  # gerçek DNS
    s = w.oku("https://example.com", zaman_asimi_sn=40)
    assert s["basarili"], s["hata"]
    assert "Example Domain" in s["icerik"]
