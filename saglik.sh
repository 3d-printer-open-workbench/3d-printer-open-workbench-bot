#!/usr/bin/env bash
# Sağlık kontrolü / health check — tries each component and prints ✅/❌. Never prints secret values.
#   ./saglik.sh          quick check
#   ./saglik.sh --test   + unit tests
set -uo pipefail
KOK="$(cd "$(dirname "$0")" && pwd)"
PY="$KOK/.venv/bin/python"; [[ -x "$PY" ]] || PY=python3
O="${WORKBENCH_ENVS:-$KOK/ortamlar}"; YZ="${WORKBENCH_AI_TOOLS:-$KOK/yz-araclari}"
export WORKBENCH_ROOT="$KOK" PYTHONPATH="$KOK" HF_HOME="${HF_HOME:-$YZ/modeller/huggingface}"
cd "$KOK"
ERP="$("$PY" -c 'from coo.ayar import ERP_URL_VARSAYILAN as u; print(u)' 2>/dev/null || echo http://127.0.0.1:8000)"
STU="$("$PY" -c 'from coo.ayar import STUDIO_URL as u; print(u)' 2>/dev/null || echo http://127.0.0.1:7870)"
HATA=0; UYARI=0
kontrol() { local ad="$1"; shift; if out=$("$@" 2>&1); then echo "✅ $ad ${out:+— $out}"; else echo "❌ $ad — ${out:0:200}"; HATA=$((HATA+1)); fi; }
istege() { local ad="$1"; shift; if out=$("$@" 2>&1); then echo "✅ $ad ${out:+— $out}"; else echo "⚪ $ad (optional) — ${out:0:120}"; UYARI=$((UYARI+1)); fi; }

echo "Health check — $KOK"
kontrol "service workbench-bot" systemctl --user is-active workbench-bot
kontrol "Claude Code CLI" bash -c "command -v claude || ls \$HOME/.local/bin/claude"
kontrol "Telegram bot" "$PY" -c "
import json,urllib.request; from coo.ayar import ayarlari_yukle; a=ayarlari_yukle()
assert a.telegram_bot_token, 'TELEGRAM_BOT_TOKEN missing'
d=json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{a.telegram_bot_token}/getMe',timeout=10)); print('@'+d['result']['username'])"
istege "ERP API ($ERP)" bash -c "curl -sf -m 5 '$ERP/api/filaments' | '$PY' -c 'import json,sys; print(len(json.load(sys.stdin)),\"filaments\")'"
istege "Studio ($STU)" bash -c "curl -s -m 5 -o /dev/null -w '%{http_code}' '$STU/' | grep -qE '200|30[0-9]' && echo up"
istege "Gemini API" "$PY" -c "
import os,json,urllib.request; import coo.ayar
k=os.environ.get('GEMINI_API_KEY'); assert k, 'GEMINI_API_KEY empty'
r=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models?pageSize=5',headers={'x-goog-api-key':k})
json.load(urllib.request.urlopen(r,timeout=15)); print('ok')"
istege "Printer (SDCP)" "$PY" -c "from coo.yazici import yazici_durumu_oku; d=yazici_durumu_oku(); assert d.bagli, d.hata_mesaji or 'not connected'; print(d.durum_adi)"
istege "GPU" bash -c "nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader"
istege "OrcaSlicer" "$PY" -c "from coo.orca_dilim import ORCA_BIN; import os; assert os.path.exists(ORCA_BIN), ORCA_BIN; print(ORCA_BIN)"
istege "Blender" bash -c "blender --version 2>/dev/null | head -1 | grep ."
istege "env ai3d (Hunyuan3D)" "$O/.venv-ai3d/bin/python" -c "import hy3dgen, torch; print('cuda' if torch.cuda.is_available() else 'cpu')"
istege "env cad (build123d)" "$O/.venv-cad/bin/python" -c "import build123d, trimesh; print('ok')"
istege "usage test (MuJoCo/CoACD/fcl)" env MUJOCO_GL=egl "$O/.venv-cad/bin/python" -c "import mujoco, coacd, fcl, shapely; m=mujoco.MjModel.from_xml_string('<mujoco/>'); mujoco.Renderer(m, 8, 8); print('mujoco', mujoco.__version__, '· EGL ok')"
istege "env video (yt-dlp/whisper)" "$O/.venv-video/bin/python" -c "import yt_dlp, faster_whisper; print('ok')"
istege "ComfyUI" "$YZ/ComfyUI/.venv/bin/python" -c "import torch; print('ok')"
kontrol "Agent models" "$PY" -c "from coo.__main__ import AJAN_MODELLERI as A; print(sum(v=='opus' for v in A.values()),'opus /',sum(v=='sonnet' for v in A.values()),'sonnet')"
if [[ "${1:-}" == "--test" ]]; then
  kontrol "unit tests" bash -c "'$PY' -m pytest coo/tests -q -p no:cacheprovider 2>&1 | tail -1"
fi
echo; [[ $HATA -eq 0 ]] && echo "🟢 Core OK ($UYARI optional component(s) missing)." || echo "🔴 $HATA problem(s)."
exit $HATA
