# Install from a clean Ubuntu

Tested on Ubuntu 24.04 / 25.10 desktop. Everything runs as your normal desktop user (no root service).
Türkçe: [kurulum.md](kurulum.md)

## 1. System packages

```bash
sudo apt update
sudo apt install -y git curl python3 python3-venv python3-pip ffmpeg
# recommended
sudo apt install -y blender            # or the official tarball for Blender 4.x/5.x
```

OrcaSlicer (recommended, used for slicing): install the AppImage or Flatpak from the OrcaSlicer releases page and make
sure an `orcaslicer` command is on your `PATH` (e.g. a wrapper script in `~/.local/bin/orcaslicer`).

## 2. Claude Code CLI

```bash
curl -fsSL https://claude.ai/install.sh | bash     # installs to ~/.local/bin/claude
claude                                             # log in once (subscription or API key), then /exit
```

The bot calls `claude -p --agent <name> ...` as a subprocess from the repository root, so the agents read
`CLAUDE.md` and `.claude/` from this repo.

## 3. Telegram bot

1. In Telegram, open **@BotFather** → `/newbot` → choose a name and username → copy the **token**.
2. Send any message to your new bot.
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and note `"chat":{"id": ...}` — that is your
   **chat id**. The bot only ever answers this chat and refuses to start without it.

## 4. Clone and install

```bash
git clone <this-repo> ~/workbench-bot && cd ~/workbench-bot
./install.sh
```

`install.sh` is idempotent. It creates `.venv`, installs `requirements-dev.txt`, creates `veri/` (your data
folder, git-ignored), copies `.env.example` → `.env` (only if missing, `chmod 600`) and installs the user unit
`~/.config/systemd/user/workbench-bot.service` from `systemd/workbench-bot.service.template`.

Edit `.env`:

```bash
nano .env      # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WORKBENCH_SHOP_NAME, WORKBENCH_SHOP_URL, PRINTER_IP ...
```

Then make the rules your own: edit `CLAUDE.md`, `config/marka/marka-rehberi.md`, `config/renk_paleti.yaml`,
`config/orca/kategoriler.yaml` and `config/bakim.yaml`.

## 5. Test and start

```bash
.venv/bin/python -m pytest -q
systemctl --user enable --now workbench-bot.service
journalctl --user -u workbench-bot -f          # logs (also coo/loglar/coo_bot.log)
./saglik.sh                                    # health check; ./saglik.sh --test also runs the tests
```

Send `/start` to the bot. To keep user services running after logout: `sudo loginctl enable-linger $USER`
(but see the DISPLAY note in Troubleshooting if you use Chrome/Blender GUI features).

## 6. Optional: ERP and Studio

Install the sibling repos following their READMEs:

- **3d-printer-open-workbench-erp** → REST at `ERP_URL` (default `http://127.0.0.1:8000`), MCP server for agents.
- **3d-printer-open-workbench-studio** → web UI/MCP at `STUDIO_URL` (default `http://127.0.0.1:7870`, MCP at `/mcp`).

Register them for the agents:

```bash
cp .mcp.json.example .mcp.json   # fix the paths; .mcp.json is git-ignored
claude mcp list                  # run from the repo root; both servers should be listed
```

## 7. Optional: Chrome + Claude in Chrome + Google Flow

Some agents (concept images and videos in Google Flow, store upload, Pinterest) drive your own Chrome through the
**Claude in Chrome** extension. Install Google Chrome, add the extension, sign in to the sites you want the agents to
use (you stay in control: logins, payments and publishing always stop for your confirmation).
Set `WORKBENCH_CLAUDE_CHROME=0` in `.env` to disable this.

## 8. Optional: ComfyUI (Qwen-Image-Edit) and Hunyuan3D-2

> Full guide (model links, versions, VRAM/RAM, Blender, troubleshooting): **[docs/local-ai.md](local-ai.md)**

Needs an NVIDIA GPU (12 GB VRAM recommended). Nothing is bundled — you download and accept the licenses.

```bash
mkdir -p yz-araclari && cd yz-araclari
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# The workflow expects (file names in coo/qwen_edit.py: MODEL, LORA, METIN, VAE):
#   a Qwen-Image-Edit-2511 GGUF quant      -> models/unet/       (needs the ComfyUI-GGUF custom node)
#   the Lightning 4-step LoRA              -> models/loras/
#   the Qwen2.5-VL text encoder            -> models/text_encoders/
#   the Qwen-Image VAE                     -> models/vae/
```

Hunyuan3D-2 (optional, AI image-to-3D): read the Tencent Hunyuan 3D Community License first — **it does not apply in
the EU, UK and South Korea**. If you may use it, clone it to `yz-araclari/Hunyuan3D-2` and create
`ortamlar/.venv-ai3d` with its requirements. Model weights are cached under `yz-araclari/modeller/huggingface`.

Separate virtual environments are optional: if `ortamlar/.venv-cad`, `.venv-ai3d` or `.venv-gorsel` exist, the bot
uses them for those jobs; otherwise it uses its own `.venv`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Bot exits: `TELEGRAM_CHAT_ID ayarlı değil` | Put your chat id in `.env` (step 3). |
| Bot does not answer | `journalctl --user -u workbench-bot -n 50`; check the token with `./saglik.sh`; only your chat id is answered. |
| Chrome / Blender / Flow steps fail with "no display" | The service must start **after the graphical session** so `DISPLAY`/`WAYLAND_DISPLAY` exist. The unit is ordered `After=graphical-session.target`; if you enabled linger and the bot started before login, run `systemctl --user import-environment DISPLAY WAYLAND_DISPLAY XAUTHORITY && systemctl --user restart workbench-bot` after logging in (or add it to your session autostart). |
| Desktop freezes during AI jobs / the bot gets killed | The unit sets `MemoryMax=12G` / `MemoryHigh=10G`. Lower them on small machines (`systemctl --user edit workbench-bot` → `[Service] MemoryMax=8G`) so the kernel kills runaway children (ComfyUI, Blender) instead of your session. |
| `claude: command not found` in the service | The unit adds `~/.local/bin` to `PATH`; reinstall Claude Code or symlink it there. |
| ERP/Studio buttons say unreachable | They are optional; start those services or ignore. Check `ERP_URL` / `STUDIO_URL`. |
| Slicing fails: profile not found | Profiles are in `config/orca/`; for another printer see "Slicer profiles" in the README. |
| Printer status "PRINTER_IP ayarlı değil" | Set `PRINTER_IP` (SDCP v3 printers such as Elegoo Centauri Carbon). |
| Agent runs take forever | Cancel from Telegram (`/iptal`); set `WORKBENCH_CLAUDE_ZAMAN_ASIMI` (seconds) for a hard limit. |

Update: `git pull && ./install.sh && systemctl --user restart workbench-bot`.
