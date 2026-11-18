"""workbench-web MCP sunucusu (stdio) — yerel Crawl4AI ile salt-okur web araçları (Firecrawl yerine).

Araçlar (hepsi yalnız GET; form gönderme, oturum, tıklama yok):
  web_oku(url, bekle_sn)          → sayfanın markdown'ı (ürün adı, fiyat, rozet, yorum sayısı vb. görünür metin)
  web_html(url, bekle_sn)         → temizlenmiş HTML (JSON-LD/tablo gibi yapı gerektiğinde)
  web_baglantilar(url, bekle_sn)  → sayfadaki mutlak bağlantılar (ürün URL'lerini toplamak için)

Sıra (ajan istemleri): önce web_oku → robots/hata olursa WebFetch → bot engeli (Cloudflare/DataDome) olursa
Chrome yedeği (yalnız Chrome yetkili ajan). Çalıştırma: `.venv-crawl/bin/python -m coo.web_mcp`
(`.mcp.json.example` → `workbench-web`).
"""

from __future__ import annotations

import os

os.environ.setdefault("CRAWL4AI_NO_CLOUD_NOTICE", "1")

from mcp.server.mcpserver import MCPServer  # noqa: E402

from coo.web_oku import oku_async, ozet_metni  # noqa: E402

mcp = MCPServer("workbench-web")


@mcp.tool()
async def web_oku(url: str, bekle_sn: float | None = None) -> str:
    """Bir web sayfasını yerel Crawl4AI (gerçek Chromium) ile okuyup markdown döndürür. Yalnız okur (GET).

    Pazar/fiyat/trend araştırmasında ürün ve kategori sayfaları için ilk tercih budur. Çıktının ilk satırı
    son URL, HTTP kodu ve erişim zamanını verir (kaynak + tarih olarak kaydet). 'ENGEL: robots' → WebFetch dene;
    'ENGEL: bot' → Chrome yedeği. bekle_sn: geç yüklenen (JS) sayfalarda ek bekleme, varsayılan 2 sn.
    """
    return ozet_metni(await oku_async(url, "markdown", bekle_sn))


@mcp.tool()
async def web_html(url: str, bekle_sn: float | None = None) -> str:
    """Sayfanın temizlenmiş HTML'ini döndürür (yapısal veri/tablo gerektiğinde). Yalnız okur (GET)."""
    return ozet_metni(await oku_async(url, "html", bekle_sn))


@mcp.tool()
async def web_baglantilar(url: str, bekle_sn: float | None = None) -> str:
    """Sayfadaki mutlak bağlantıları (URL — metin) listeler; ürün sayfası URL'lerini toplamak için. Yalnız okur."""
    return ozet_metni(await oku_async(url, "links", bekle_sn))


if __name__ == "__main__":
    mcp.run()
