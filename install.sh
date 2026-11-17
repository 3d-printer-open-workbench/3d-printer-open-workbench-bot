#!/usr/bin/env bash
# 3D Printer Open Workbench bot — idempotent installer (Ubuntu 22.04+/Debian; systemd user service).
#   ./install.sh              venv + deps + .env + systemd user unit (not started)
#   ./install.sh --start      ...and enable + start the service
#   ./install.sh --no-service skip the systemd unit
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
START=0; SERVICE=1
for a in "$@"; do
  case "$a" in
    --start) START=1 ;;
    --no-service) SERVICE=0 ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

command -v python3 >/dev/null || { echo "python3 not found (sudo apt install python3 python3-venv)" >&2; exit 1; }
python3 - <<'PY' || { echo "Python >= 3.11 required" >&2; exit 1; }
import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)
PY

say "Python virtual environment: $ROOT/.venv"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  python3 -m venv "$ROOT/.venv" || { echo "venv failed (sudo apt install python3-venv)" >&2; exit 1; }
fi
"$ROOT/.venv/bin/python" -m pip install -q --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -q -r "$ROOT/requirements-dev.txt"

say "Data folders"
mkdir -p "$ROOT/veri/00_Onay" "$ROOT/veri/01_Konsept_ve_ArGe/B2C_Oneriler" "$ROOT/veri/02_Urunler" \
         "$ROOT/veri/03_Magaza" "$ROOT/veri/04_Muhasebe_ve_Raporlar" "$ROOT/coo/loglar"

if [[ ! -f "$ROOT/.env" ]]; then
  say "Creating .env from .env.example (edit it: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID ...)"
  cp "$ROOT/.env.example" "$ROOT/.env"
  chmod 600 "$ROOT/.env"
else
  say ".env already exists — left unchanged"
fi

command -v claude >/dev/null || [[ -x "$HOME/.local/bin/claude" ]] || \
  echo "WARNING: Claude Code CLI not found. Install it and run 'claude' once to log in (see docs/install.md)."

if [[ $SERVICE -eq 1 ]]; then
  UNIT_DIR="$HOME/.config/systemd/user"
  mkdir -p "$UNIT_DIR"
  say "systemd user unit: $UNIT_DIR/workbench-bot.service"
  sed -e "s#@ROOT@#$ROOT#g" -e "s#@PYTHON@#$ROOT/.venv/bin/python#g" \
      "$ROOT/systemd/workbench-bot.service.template" > "$UNIT_DIR/workbench-bot.service.new"
  if ! cmp -s "$UNIT_DIR/workbench-bot.service.new" "$UNIT_DIR/workbench-bot.service" 2>/dev/null; then
    mv "$UNIT_DIR/workbench-bot.service.new" "$UNIT_DIR/workbench-bot.service"
  else
    rm -f "$UNIT_DIR/workbench-bot.service.new"
  fi
  systemctl --user daemon-reload || echo "WARNING: systemctl --user not available in this session"
  if [[ $START -eq 1 ]]; then
    systemctl --user enable --now workbench-bot.service
    systemctl --user --no-pager status workbench-bot.service | head -5 || true
  else
    echo "Start later with: systemctl --user enable --now workbench-bot.service"
  fi
fi

say "Done. Health check: ./saglik.sh   Tests: .venv/bin/python -m pytest -q"
