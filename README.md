# 3D Printer Open Workbench — Bot

> 3D Printer Open Workbench: **Bot + agents** · [ERP](https://github.com/3d-printer-open-workbench/3d-printer-open-workbench-erp) · [Studio](https://github.com/3d-printer-open-workbench/3d-printer-open-workbench-studio)

[Türkçe](README.tr.md) · [Install guide](docs/install.md) · [Kurulum rehberi](docs/kurulum.md) · License: MIT

A Telegram-run assistant for a small 3D-printing business. You chat with one Telegram bot (the "COO"); behind it,
a team of [Claude Code](https://docs.claude.com/en/docs/claude-code) agents researches trends, turns an idea into a
printable product, slices it in OrcaSlicer, prepares store listings and social content, and keeps the books in an
optional ERP. Every step that spends money, publishes something or touches the printer waits for **your approval**.

> The bot's own UI and most agent prompts are in **Turkish** (it was built for a Turkish shop). Code identifiers are
> Turkish too. Translating the prompts in `.claude/agents/` and the bot strings is a welcome contribution.

## What it does

| Area | What happens | Who does it |
|---|---|---|
| Trends & ideas | Live market research (Etsy, marketplaces, Pinterest, Printables/MakerWorld) with source URLs and dates; a visual catalog you pick from | `trend-researcher` (Sonnet) |
| Product pipeline | Concept → 3D model (CAD / Studio generators / optional AI 3D) → geometry quality gate → colors → slicing (3MF) | `cad-artist`, `mesh-validator`, `slicer-engineer` |
| Pricing & stock | BOM, cost, price suggestions, purchases, quotes (PDF) via the ERP | `finance-tracker`, `support-responder` |
| Store | SEO copy, gallery order, upload checklist; browser upload with Claude in Chrome after your OK | `cmo-store-director`, `seo-copywriter` |
| Social | Poster with a size/material band printed from real data, Pinterest Pins, Reels/TikTok scripts and edits from real footage | `pinterest-curator`, `reels-tiktok-strategist`, `visual-storyteller` |
| Printer | Read-only status, camera, file upload, optional AI print-failure warning, two-step emergency stop | bot (`coo/yazici.py`, `coo/baski_goz.py`) |
| Oversight | CEO/CTO/CMO agents (Opus) review Sonnet output before it reaches you | `ceo-orchestrator`, `cto-architect`, `cmo-store-director` |

21 agents live in [`.claude/agents/`](.claude/agents); the model per agent is set in `coo/__main__.py → AJAN_MODELLERI`.

## Architecture

```mermaid
flowchart LR
    U[You on Telegram] <-->|Bot API, one chat id| B[COO bot<br/>python -m coo]
    B -->|claude -p --agent ...| C[Claude Code CLI<br/>+ .claude/agents]
    C -->|MCP optional| E[(workbench-erp<br/>3d-printer-open-workbench-erp)]
    C -->|MCP optional| S[workbench-studio<br/>3d-printer-open-workbench-studio]
    B -->|REST ERP_URL| E
    B -->|STUDIO_URL| S
    B --> O[OrcaSlicer CLI]
    B --> BL[Blender / build123d]
    B -.optional.-> AI[ComfyUI + Qwen-Image-Edit<br/>Hunyuan3D-2]
    B -.optional.-> G[Gemini API<br/>print watch]
    C -.optional --chrome.-> CH[Claude in Chrome<br/>Google Flow, store upload]
    B -->|SDCP v3, read-only + stop| P[Printer on LAN]
    B --> D[(veri/ — your data<br/>git-ignored)]
```

Repository layout:

```
coo/                 the bot package (python -m coo) and its tests (coo/tests)
.claude/agents/      agent definitions (Markdown + front matter)
.claude/commands/    slash commands for interactive Claude Code sessions (/ceo, /cto, /cmo, /ikas-yukle)
config/              Orca categories & profiles, social/Flow guides, color palette, maintenance plan,
                     concept library (neutral sample) and brand guide (neutral sample)
systemd/             user-service template
docs/                install guides (EN/TR)
veri/                your business data — created by install.sh, never committed
CLAUDE.md            rules every agent reads — rewrite it for your business
```

## Requirements

- Linux with systemd (tested on Ubuntu 24.04+), Python **3.11+**
- [Claude Code CLI](https://docs.claude.com/en/docs/claude-code), logged in (a Claude subscription or API key)
- A Telegram account and a bot token from **@BotFather**
- Recommended: OrcaSlicer (CLI used for slicing), Blender 4+/5 (previews, color renders), FFmpeg (video edits)
- Optional: NVIDIA GPU with 12 GB+ VRAM for ComfyUI/Qwen-Image-Edit and Hunyuan3D-2; Google Chrome with the
  Claude in Chrome extension (Google Flow, store upload); a Gemini API key (print-failure watch, free tier)
- Optional sibling repos: **3d-printer-open-workbench-erp** (costs, BOM, stock, quotes) and
  **3d-printer-open-workbench-studio** (parametric generators, `print_check`)

## Quick start

```bash
git clone <this-repo> 3d-printer-open-workbench-bot && cd 3d-printer-open-workbench-bot
./install.sh                 # venv, deps, .env, systemd user unit (idempotent)
nano .env                    # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WORKBENCH_SHOP_NAME ...
claude                       # once, to log in; then /exit
.venv/bin/python -m pytest -q
systemctl --user enable --now workbench-bot.service
./saglik.sh                  # health check
```

Send `/start` to your bot. Full walkthrough from a clean Ubuntu: [docs/install.md](docs/install.md).

## Configuration

All settings are environment variables read from `.env` (see [`.env.example`](.env.example)):

| Variable | Meaning |
|---|---|
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | required; the bot answers only this chat and refuses to start without it |
| `WORKBENCH_SHOP_NAME`, `WORKBENCH_SHOP_URL`, `WORKBENCH_PINTEREST_URL` | shop identity on posters, PDF quotes, captions |
| `PRINTER_IP` | SDCP v3 printer on the LAN (e.g. Elegoo Centauri Carbon); read-only + two-step stop |
| `ERP_URL`, `STUDIO_URL` | optional sibling services |
| `GEMINI_API_KEY` | optional; AI print-failure watch and end-of-print report |
| `WORKBENCH_CLAUDE_CHROME` | `0` disables `--chrome` for agents |
| `WORKBENCH_CLAUDE_PERMISSION_MODE` | permission mode for headless agents (default `bypassPermissions`) |
| `WORKBENCH_DATA`, `WORKBENCH_CONFIG`, `WORKBENCH_ENVS`, `WORKBENCH_AI_TOOLS` | path overrides |

Business-specific content you should edit: `CLAUDE.md`, `config/marka/marka-rehberi.md`,
`config/konseptler/*.md`, `config/renk_paleti.yaml`, `config/orca/kategoriler.yaml`, `config/bakim.yaml`.

### Talking to the ERP and Studio (both optional)

- **REST:** the bot calls the ERP at `ERP_URL` (default `http://127.0.0.1:8000`) for stock, queue, prices and print
  accounting, and opens Studio pages at `STUDIO_URL` (default `http://127.0.0.1:7870`).
- **MCP:** agents use the ERP and Studio tools through Claude Code MCP servers named **`workbench-erp`** and
  **`workbench-studio`**. Copy [`.mcp.json.example`](.mcp.json.example) to `.mcp.json` and fix the paths; tool
  permissions are pre-allowed in `.claude/settings.json` (`mcp__workbench-erp__*`, `mcp__workbench-studio__*`).
- Without them the bot still runs; ERP/Studio buttons report that the service is unreachable.

### Slicer profiles

`config/orca/` ships only the category table `kategoriler.yaml`. Machine, filament and process profiles are
derived from OrcaSlicer's vendor presets (AGPL-3.0), so they are **not** included. Copy OrcaSlicer's
`resources/profiles/<Vendor>` and `OrcaFilamentLibrary` folders into `config/orca/kaynak/` (git-ignored); the bot
then generates flattened profiles under `config/orca/` on first slice. The defaults target an Elegoo Centauri Carbon
0.4 mm nozzle; for another printer adjust `TABAN_PROSES`/`MAKINE` in `coo/orca_dilim.py`.

## Safety rules (built in)

- **The bot never starts a print.** It only reads status/camera, uploads files, and can send a *stop* after a
  two-step confirmation from you. The AI print watch only warns.
- **Approvals are yours:** concept choice, content, price, store upload, applying slicer suggestions, purchases and
  quotes. Agents prepare; you confirm in Telegram.
- **No invented data:** prices, reviews and sales figures must come with an opened source URL and date; sizes and
  materials on images are printed deterministically from real data, never drawn by AI.
- **Secrets stay in `.env`** (git-ignored, `chmod 600`). Nothing secret goes into the repo or chat logs.
- **Locked to one chat.** Agents run headless with tool access (`bypassPermissions` by default), so only your chat
  id may command the bot. Run it under your normal desktop user, never as root; consider a dedicated user account
  and a stricter `WORKBENCH_CLAUDE_PERMISSION_MODE` plus deny rules in `.claude/settings.json`.

## Third-party software and models (not bundled)

This repository contains only the bot code, agent prompts and sample configuration. You download and accept the
licenses of everything else yourself:

- **ComfyUI** — GPL-3.0. Installed separately; the bot talks to it as an external process.
- **Qwen-Image-Edit** weights (and its text encoder / VAE) — Apache-2.0 at the time of writing; check the model
  card on Hugging Face before downloading.
- **Hunyuan3D-2** (Tencent) — *Tencent Hunyuan 3D Community License*. Its territory clause **excludes the European
  Union, the United Kingdom and South Korea**, and it has usage/scale restrictions. Check whether you may use it
  before downloading; the pipeline works without it (CAD/Studio routes).
- **OrcaSlicer** — AGPL-3.0. The flattened profile JSON files in `config/orca/` are derived from OrcaSlicer's
  bundled vendor profiles; vendor resources themselves are not redistributed.
- **Blender** (GPL), **FFmpeg** (LGPL/GPL), **Claude Code** (Anthropic terms), **Google Gemini / Flow** (Google
  terms), **Telegram Bot API** (Telegram terms).
- Python packages listed in `requirements.txt` under their own licenses.

## Disclaimer

This is an independent open-source project, not affiliated with or endorsed by Anthropic, Telegram, Google, Elegoo,
OrcaSlicer, Tencent, Alibaba/Qwen or any store platform. It automates parts of a real business but comes **without
any warranty** (see [LICENSE](LICENSE)). You are responsible for printer safety, model and content licenses,
marketplace rules, tax and consumer law in your country, and for every action you approve. AI agents make mistakes:
review their output before it reaches customers.
