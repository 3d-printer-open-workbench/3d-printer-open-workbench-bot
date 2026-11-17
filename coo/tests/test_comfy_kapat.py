"""ComfyUI kapatma yalnız gerçek sunucu sürecini hedeflemeli (pkill -f Claude ajanını da öldürüyordu)."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from coo import qwen_edit


def test_yalniz_comfyui_sureci_secilir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(qwen_edit, "COMFY", tmp_path)
    (tmp_path / "main.py").write_text("import time\ntime.sleep(60)\n")
    sahte = subprocess.Popen([sys.executable, "main.py", "--listen", "127.0.0.1", "--port", "8188"], cwd=tmp_path)
    # Komut metninde aynı ifade geçen başka bir süreç (Claude ajanının istemi gibi) dokunulmamalı.
    masum = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)",
                              "pkill -f 'main.py --listen 127.0.0.1 --port 8188'"])
    try:
        time.sleep(0.3)
        assert qwen_edit.comfy_pidleri() == [sahte.pid]
        qwen_edit.sunucu_kapat(bekle=5)
        assert sahte.wait(timeout=5) is not None
        assert masum.poll() is None
    finally:
        for p in (sahte, masum):
            p.kill()
