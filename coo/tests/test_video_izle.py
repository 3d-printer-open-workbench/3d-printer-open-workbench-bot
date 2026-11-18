import shutil
import subprocess

import pytest

import coo.video_izle as vi

VTT = """WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:03.000 align:start position:0%
All right, so<00:00:01.500><c> here</c><c> we</c>

00:00:03.000 --> 00:00:03.010 align:start position:0%
All right, so here we

00:00:03.010 --> 00:00:05.000 align:start position:0%
All right, so here we
are&nbsp;at the zoo

00:01:05.000 --> 00:01:07.000
and that's it
"""


def test_vtt_kayan_tekrarlari_ayiklar(tmp_path):
    p = tmp_path / "video.en.vtt"
    p.write_text(VTT)
    assert vi.vtt_oku(p) == [(1, "All right, so here we"), (3, "are at the zoo"), (65, "and that's it")]


def test_ad_ve_sure():
    assert vi._ad("Çok Renkli Baskı: AMS Ayarları!") == "cok-renkli-baski-ams-ayarlari"
    assert vi._ad("???") == "video"
    assert vi._sure(65) == "01:05"
    assert vi._sure(3725) == "1:02:05"


def test_transkript_altyazi_onceligi(tmp_path):
    (tmp_path / "video.en.vtt").write_text(VTT)
    (tmp_path / "video.tr.vtt").write_text(VTT.replace("and that's it", "hepsi bu"))
    satirlar, kaynak = vi.transkript(tmp_path / "video.mp4", tmp_path, None)
    assert kaynak == "site altyazısı (tr)"
    assert satirlar[-1] == (65, "hepsi bu")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg yok")
def test_yerel_video_kare_ve_pano(tmp_path):
    video = tmp_path / "deneme.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc=duration=12:size=320x240:rate=10", "-pix_fmt", "yuv420p", str(video)], check=True)
    klasor = vi.izle(str(video), tmp_path / "cikti", en_fazla=20)
    kareler = sorted((klasor / "kareler").glob("*.jpg"))
    assert 4 <= len(kareler) <= 20
    assert kareler[0].name.startswith("kare_001_00m00s")
    assert list((klasor / "panolar").glob("pano_*.jpg"))
    md = (klasor / "izle.md").read_text()
    assert "Transkript: ses yok" in md and video.exists()
