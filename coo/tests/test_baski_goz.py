import io
import json

import coo.baski_goz as bg


def test_karar_ver():
    assert bg.karar_ver({"durum": "HATA", "guven": 0.9}, []) == "hata"
    assert bg.karar_ver({"durum": "HATA", "guven": 0.4}, []) is None          # düşük güven = şüphe
    assert bg.karar_ver({"durum": "SUPHELI", "guven": 0.6}, [{"durum": "NORMAL"}]) is None
    assert bg.karar_ver({"durum": "SUPHELI", "guven": 0.6}, [{"durum": "SUPHELI"}]) == "iki_supheli"
    assert bg.karar_ver({"durum": "HATA", "guven": 0.5}, [{"durum": "SUPHELI"}]) == "iki_supheli"
    assert bg.karar_ver({"durum": "NORMAL", "guven": 0.99}, [{"durum": "HATA"}]) is None


def test_ozet_satiri_markdown_guvenli():
    s = bg.ozet_satiri({"durum": "HATA", "sorun": "tabladan_kopma", "guven": 0.92, "aciklama": "parça *kaymış* _"})
    assert "🔴" in s and "tabladan kopma" in s and "%92" in s and "*kaymış*" not in s
    assert "yapılamadı" in bg.ozet_satiri({"durum": "BILINMIYOR", "hata": "x"})


def test_anahtarsiz(monkeypatch):
    monkeypatch.setattr(bg, "_ayar", lambda: ("", "m"))
    assert bg.kare_degerlendir(b"x", {})["durum"] == "BILINMIYOR"


def test_api_cagrisi(monkeypatch):
    gonderilen = {}

    class Yanit(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def sahte(istek, timeout=0):
        gonderilen["govde"] = json.loads(istek.data)
        gonderilen["anahtar"] = istek.headers.get("X-goog-api-key")
        cevap = {"candidates": [{"content": {"parts": [{"text": json.dumps(
            {"durum": "HATA", "sorun": "spagetti", "guven": 1.4, "aciklama": "filament yığını"})}]}}],
            "usageMetadata": {"promptTokenCount": 2600, "candidatesTokenCount": 50}}
        return Yanit(json.dumps(cevap).encode())

    monkeypatch.setattr(bg, "_ayar", lambda: ("ANAHTAR", "gemini-test"))
    monkeypatch.setattr(bg.urllib.request, "urlopen", sahte)
    s = bg.kare_degerlendir(b"simdi", {"urun": "saksı", "destek": True}, onceki=b"once", referans=b"ref")
    assert s["durum"] == "HATA" and s["guven"] == 1.0 and s["model"] == "gemini-test"
    parcalar = gonderilen["govde"]["contents"][0]["parts"]
    assert len(parcalar) == 4 and "spagetti sanma" in parcalar[-1]["text"]
    assert gonderilen["govde"]["generationConfig"]["responseMimeType"] == "application/json"
    assert gonderilen["anahtar"] == "ANAHTAR"


def test_kaydet(tmp_path, monkeypatch):
    monkeypatch.setattr(bg, "KAYIT_KLASORU", tmp_path)
    k = bg.kaydet("ECC_0.4_saksı v2.gcode", {"durum": "HATA", "guven": 0.9}, b"jpg")
    assert (k / "kontrol.jsonl").exists() and list(k.glob("*-HATA.jpg"))
