# Local AI setup (optional)

Besides cloud AI, the bot can use three local tools. None is required: if a tool is missing, that step reports
"tool not available" and the bot keeps running. Model files are **not** in this repo — read their licenses and
download them yourself.

| Tool | What it does | Module | License |
|---|---|---|---|
| **ComfyUI + Qwen-Image-Edit-2511** | Photoreal studio/showcase images from the product render; front/side/back views from a concept | `coo/qwen_edit.py`, `coo/studyo_qwen.py`, `coo/ai3d_gorusler.py` | ComfyUI GPL-3.0; Qwen models Apache 2.0 |
| **Hunyuan3D-2 (mini / mv)** | Image-to-3D mesh for organic shapes (figures, planters, decor) | `coo/ai3d_mesh.py`, `coo/ai3d_hazirla.py` | Tencent Hunyuan 3D Community License — **not valid in the EU, UK and South Korea** |
| **Blender (≥ 4.x)** | Makes the AI mesh printable (watertight, wall thickness) and renders a 4-view preview | `coo/blender_onar.py`, `coo/blender_gorunus.py` | GPL (separate program) |

Pipeline: concept image → Qwen front/left/back views → Hunyuan3D-2mv (3 seeds, best silhouette match wins) →
`ai3d_hazirla` (flat base, drainage) → Blender repair → quality gate → preview.

## Hardware

| | Minimum | Recommended |
|---|---|---|
| GPU | NVIDIA 8 GB VRAM (Qwen with `--lowvram`, Hunyuan mini/mv with staged loading) | 12 GB VRAM |
| RAM | 32 GB | 32–64 GB |
| Disk | ~35 GB (Qwen ~20 GB, Hunyuan ~10 GB, envs) | SSD |

**RAM warning:** on 8–12 GB cards ComfyUI keeps part of the model in system RAM (~18 GB). The bot manages this:
ComfyUI starts on demand, **shuts itself down after 10 minutes with an empty queue**, and if memory runs out the
kernel kills **ComfyUI first** instead of your desktop (`oom_score_adj=1000`). The service unit also sets
`MemoryMax` (tune it with `systemctl --user edit workbench-bot`). ComfyUI is closed automatically before Hunyuan runs.

Folders can be changed with `WORKBENCH_AI_TOOLS` (default `yz-araclari/` in the repo root) and `WORKBENCH_ENVS`
(default `ortamlar/`). Run the commands below from the repo root.

## 1. ComfyUI + Qwen-Image-Edit-2511

```bash
mkdir -p yz-araclari && cd yz-araclari
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python3 -m venv .venv
.venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
.venv/bin/pip install -r requirements.txt

# custom node that loads GGUF models
git clone https://github.com/city96/ComfyUI-GGUF.git custom_nodes/ComfyUI-GGUF
.venv/bin/pip install -r custom_nodes/ComfyUI-GGUF/requirements.txt

# model files (names must match MODEL, LORA, METIN, VAE in coo/qwen_edit.py)
HF=https://huggingface.co
wget -P models/unet          $HF/unsloth/Qwen-Image-Edit-2511-GGUF/resolve/main/qwen-image-edit-2511-Q4_K_M.gguf
wget -P models/loras         $HF/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors
wget -P models/text_encoders $HF/Comfy-Org/Qwen-Image/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors
wget -P models/vae           $HF/Comfy-Org/Qwen-Image/resolve/main/split_files/vae/qwen_image_vae.safetensors
cd ../..
```

You don't start ComfyUI yourself: the bot launches it on `127.0.0.1:8188` with `--lowvram`.

**Test:**

```bash
python3 -m coo.qwen_edit --girdi product.png --cikti test.png --istem "Studio product photo on a white sweep, soft light"
python3 -m coo.qwen_edit --kapat   # stops the server (don't use pkill; only ComfyUI processes are targeted)
```

The first run loads the models (1–2 min); later frames take ~70 s on an 8 GB card.

## 2. Hunyuan3D-2 (shape only)

Read the license first: <https://github.com/Tencent-Hunyuan/Hunyuan3D-2>. If you may not use it, skip this step;
the bot keeps using the build123d/OpenSCAD route for parametric products.

```bash
cd yz-araclari
git clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git
cd ..
python3.11 -m venv ortamlar/.venv-ai3d
ortamlar/.venv-ai3d/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
ortamlar/.venv-ai3d/bin/pip install -r yz-araclari/Hunyuan3D-2/requirements.txt
ortamlar/.venv-ai3d/bin/pip install "transformers<4.50" "diffusers<0.33" "huggingface_hub<0.30" trimesh
ortamlar/.venv-ai3d/bin/pip install -e yz-araclari/Hunyuan3D-2
```

- The texture module is **not needed**; only shape is generated, colour comes from the filament.
- Weights (`tencent/Hunyuan3D-2mini`, `tencent/Hunyuan3D-2mv`) download on first use into
  `yz-araclari/modeller/huggingface` (the bot sets `HF_HOME`).
- **8 GB cards:** the mv model doesn't fit on the GPU at once; `ai3d_mesh.py` loads it on CPU and moves each stage
  to the GPU (peak ~2.7 GB, ~150 s per seed).
- The version pins matter: newer `transformers`/`diffusers` break Hunyuan3D-2.

**Test:**

```bash
ortamlar/.venv-ai3d/bin/python coo/ai3d_mesh.py concept.png out/ --model mini --yukseklik-mm 120
```

## 3. Blender

```bash
sudo snap install blender --classic     # or download from blender.org and add it to PATH
blender -b -P coo/blender_onar.py -- --girdi raw.stl --cikti fixed.stl --rapor report.json --min-kalinlik 1.0
blender -b -P coo/blender_gorunus.py -- fixed.stl preview.png
```

Default thickness thresholds target a 0.4 mm nozzle (`--min-kalinlik 1.0`, planter wall `--hazne-duvar 2.0`).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ComfyUI başlatılamadı` (could not start) | Check `yz-araclari/ComfyUI/comfy_workbench.log`; usually a missing model file or the ComfyUI-GGUF node. |
| `UnetLoaderGGUF` not found | ComfyUI-GGUF isn't cloned into `custom_nodes/` or its requirements aren't installed. |
| Desktop freezes / session logs out | Not enough RAM. Lower `MemoryMax`, close heavy browser tabs; ComfyUI stops itself after 10 idle minutes. |
| Hunyuan `CUDA out of memory` | The desktop holds VRAM; try `--octree 256` and `--adim 30`, or `--model mini`. |
| Hunyuan import error | Check the `transformers<4.50`, `diffusers<0.33`, `huggingface_hub<0.30` pins. |
