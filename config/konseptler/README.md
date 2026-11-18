# Concepts / Konseptler

A *concept* is a reusable visual style for posters, Pins and short videos. Each concept is one Markdown file in this
folder: YAML front matter + the image prompt (body). The bot lists every `*.md` here (files under `arsiv/` are
archived and not listed). You can also add a concept from Telegram (paste: first line = name, then the prompt).

Front matter keys:

| key | meaning |
|---|---|
| `ad` | slug (file name without `.md`) |
| `baslik` | display name |
| `aciklama` | one-line description |
| `oranlar` | aspect ratios to produce, e.g. `["3:4", "9:16"]` |
| `video` | also produce a short video from the poster |
| `bilgi_katmani` | `teknik_poster` → size/material text is rendered from real data (never drawn by AI) |
| `poster_motoru` | poster engine for a `teknik_poster` concept: `yerel` (default — local SVG template `teknik-poster-sablon.svg` rendered by `coo/poster_sablon.py` with Inkscape), `canva` (your Canva master, needs `teknik-poster-canva.yaml`) or `flow` (Flow raw poster + info band by `coo/teknik_poster.py`) |
| `referanslar` | optional style reference images, paths relative to this folder (e.g. `referans/<ad>/poster.jpg`) |
| `video_istemi` | prompt for the image-to-video step |

`teknik-poster.md` is a neutral sample. Put your own brand concepts and reference images here; they are your IP —
keep them out of public forks if you wish (`config/konseptler/referans/` is git-ignored by default).
