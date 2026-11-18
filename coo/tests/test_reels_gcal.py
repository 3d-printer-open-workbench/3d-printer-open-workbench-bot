import json

from coo import reels_takvim as rt

FIKIR = {"id": "ab12", "tarih": "2026-11-20", "saat": "19:30", "baslik": "Stand POV", "urun_ad": "Kulaklık Standı",
         "durum": "fikir", "kancalar": [{"tur": "soru", "metin": "Kolun masada mı?"}],
         "senaryo": [{"sure": "0-2 sn", "goruntu": "boş stant", "ekran_yazisi": "Kolun masada mı?"}],
         "cekim_talimati": ["dikey 9:16"], "aciklama": "Açıklama", "hashtagler": ["#3dbaski"],
         "trend": {"ad": "POV", "neden": "yükselişte"}}


def test_etkinlik_yukleri(tmp_path):
    y = rt.gcal_etkinlikleri([FIKIR, {"id": "x", "baslik": "tarihsiz"}, {**FIKIR, "id": "c", "durum": "iptal"}], tmp_path)
    assert len(y) == 1
    e = y[0]
    assert e["fid"] == "ab12" and e["eventId"] is None and e["startTime"] == "2026-11-20T19:30:00"
    assert e["endTime"] == "2026-11-20T20:15:00" and e["summary"] == "🎬 Reels: Stand POV · Kulaklık Standı"
    assert "Kolun masada mı?" in e["description"] and "dikey 9:16" in e["description"]


def test_var_olan_etkinlik_guncellenir(tmp_path):
    rt.klasor(tmp_path).mkdir(parents=True, exist_ok=True)
    rt.gcal_yolu(tmp_path).write_text(json.dumps({"ab12": "evt1"}))
    assert rt.gcal_etkinlikleri([FIKIR], tmp_path)[0]["eventId"] == "evt1"


def test_istem_davetsiz_ve_bildirimsiz(tmp_path):
    t = rt.gcal_istemi([FIKIR], tmp_path)
    assert "attendees YOK" in t and "NONE" in t and "GCAL_TAMAM" in t and str(rt.gcal_yolu(tmp_path)) in t
    assert rt.gcal_istemi([{"id": "x"}], tmp_path) is None


def test_bozuk_saat_varsayilan(tmp_path):
    assert rt.gcal_etkinlikleri([{**FIKIR, "saat": "akşam"}], tmp_path)[0]["startTime"] == "2026-11-20T10:00:00"
