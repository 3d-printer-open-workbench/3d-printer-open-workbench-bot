"""Bot ajan başlatırken güvenlik: gizli ortam değişkenleri geçmez, yalıtım (sandbox) ayarı verilir, Chrome yalnız
yetkili ajana açılır."""
from __future__ import annotations

import coo.__main__ as cm


def test_gizli_ortam_ajana_gecmez(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "sahte-token-123456")
    monkeypatch.setenv("GEMINI_API_KEY", "sahte-anahtar-123456")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    _, env = cm._claude_komut_ve_ortam("claude", "trend-researcher", "x")
    assert "TELEGRAM_BOT_TOKEN" not in env and "GEMINI_API_KEY" not in env
    assert env["WORKBENCH_BOT_AJAN"] == "trend-researcher"


def test_sandbox_ayari_verilir_ve_kapatilabilir(monkeypatch):
    monkeypatch.setattr(cm, "ajan_yetkisi", lambda ajan: {"sandbox": True})
    komut, _ = cm._claude_komut_ve_ortam("claude", "cad-artist", "x")
    assert "--settings" in komut and komut[komut.index("--settings") + 1].endswith("ajan_sandbox.json")
    monkeypatch.setenv("WORKBENCH_SANDBOX", "0")
    komut, _ = cm._claude_komut_ve_ortam("claude", "cad-artist", "x")
    assert "--settings" not in komut


def test_chrome_yalniz_yetkili_ajana(monkeypatch):
    monkeypatch.setattr(cm, "ekran_var", lambda: True)
    monkeypatch.setenv("WORKBENCH_CLAUDE_CHROME", "1")
    assert "--chrome" in cm._claude_komut_ve_ortam("claude", "cmo-store-director", "x")[0]
    assert "--chrome" not in cm._claude_komut_ve_ortam("claude", "finance-tracker", "x")[0]
    assert "--chrome" not in cm._claude_komut_ve_ortam("claude", "bilinmeyen-ajan", "x")[0]


def test_sandbox_tabloda_kapaliysa_verilmez(monkeypatch):
    monkeypatch.setattr(cm, "ajan_yetkisi", lambda ajan: {"sandbox": False})
    assert "--settings" not in cm._claude_komut_ve_ortam("claude", "cad-artist", "x")[0]
