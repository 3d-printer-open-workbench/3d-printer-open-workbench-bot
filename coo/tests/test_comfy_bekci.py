from coo import qwen_edit


def test_bekci_bosta_esikten_sonra_kapatir(monkeypatch):
    kapatildi = []
    monkeypatch.setattr(qwen_edit, "comfy_pidleri", lambda: [123])
    monkeypatch.setattr(qwen_edit, "kuyruk_bos", lambda: True)
    monkeypatch.setattr(qwen_edit, "sunucu_kapat", lambda: kapatildi.append(1))
    durum: dict = {}
    assert qwen_edit.bosta_kapat_kontrol(durum, 0) is False  # ilk görüş: sayaç başlar
    assert qwen_edit.bosta_kapat_kontrol(durum, 599) is False
    assert qwen_edit.bosta_kapat_kontrol(durum, 600) is True
    assert kapatildi == [1] and durum == {}


def test_bekci_is_varken_sayaci_sifirlar(monkeypatch):
    bos = {"v": False}
    monkeypatch.setattr(qwen_edit, "comfy_pidleri", lambda: [123])
    monkeypatch.setattr(qwen_edit, "kuyruk_bos", lambda: bos["v"])
    monkeypatch.setattr(qwen_edit, "sunucu_kapat", lambda: (_ for _ in ()).throw(AssertionError("kapatmamalı")))
    durum: dict = {}
    qwen_edit.bosta_kapat_kontrol(durum, 0)
    qwen_edit.bosta_kapat_kontrol(durum, 500)  # iş var → son_is=500
    bos["v"] = True
    assert qwen_edit.bosta_kapat_kontrol(durum, 1000) is False  # 500 sn boş, eşik değil


def test_bekci_sunucu_yoksa_durumu_temizler(monkeypatch):
    monkeypatch.setattr(qwen_edit, "comfy_pidleri", lambda: [])
    durum = {"son_is": 5.0}
    assert qwen_edit.bosta_kapat_kontrol(durum, 10_000) is False and durum == {}


def test_ekran_var_soketten_tamamlar(monkeypatch):
    import coo.__main__ as ana
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(ana.Path, "exists", lambda self: str(self).endswith("wayland-0"))
    assert ana.ekran_var() is True
    assert ana.os.environ.get("WAYLAND_DISPLAY") == "wayland-0"
