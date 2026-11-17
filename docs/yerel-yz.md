# Yerel yapay zekâ kurulumu (isteğe bağlı)

Bot, bulut YZ'ye ek olarak üç yerel aracı kullanabilir. Hiçbiri zorunlu değildir; kurulu değilse ilgili adım
"araç yok" der, bot çalışmaya devam eder. Model dosyaları depoda **yoktur** — lisanslarını okuyup kendiniz indirirsiniz.

| Araç | Ne işe yarar | Hangi modül | Lisans |
|---|---|---|---|
| **ComfyUI + Qwen-Image-Edit-2511** | Ürün render'ından gerçekçi stüdyo/vitrin görseli; konseptten ön/yan/arka görünüm | `coo/qwen_edit.py`, `coo/studyo_qwen.py`, `coo/ai3d_gorusler.py` | ComfyUI GPL-3.0; Qwen modelleri Apache 2.0 |
| **Hunyuan3D-2 (mini / mv)** | Görselden 3B mesh (figür, saksı, dekor gibi organik formlar) | `coo/ai3d_mesh.py`, `coo/ai3d_hazirla.py` | Tencent Hunyuan 3D Community License — **AB, Birleşik Krallık ve Güney Kore'de geçerli değil** |
| **Blender (≥ 4.x)** | YZ mesh'ini basılabilir yapar (su geçirmezlik, et kalınlığı), 4 yönden önizleme | `coo/blender_onar.py`, `coo/blender_gorunus.py` | GPL (ayrı program) |

Akış: konsept görseli → Qwen ile ön/sol/arka görünüm → Hunyuan3D-2mv (3 tohum, siluete en uygun seçilir) →
`ai3d_hazirla` (taban düzleme, drenaj) → Blender onarım → kalite kapısı → önizleme.

## Donanım

| | En az | Önerilen |
|---|---|---|
| GPU | NVIDIA 8 GB VRAM (Qwen `--lowvram` ile, Hunyuan mini/mv aşamalı yükleme ile) | 12 GB VRAM |
| RAM | 32 GB | 32–64 GB |
| Disk | ~35 GB (Qwen ~20 GB, Hunyuan ~10 GB, ortamlar) | SSD |

**RAM uyarısı:** 8–12 GB kartta ComfyUI modelin bir kısmını RAM'de tutar (~18 GB). Bot bunu yönetir: ComfyUI
gerektiğinde açılır, kuyruğu **10 dk boş kalınca kendiliğinden kapanır**, bellek biterse çekirdek masaüstü yerine
**önce ComfyUI'yi** sonlandırır (`oom_score_adj=1000`). Servis biriminde `MemoryMax` sınırı da vardır
(`systemctl --user edit workbench-bot` ile makinenize göre ayarlayın). Hunyuan'ı çalıştırmadan önce ComfyUI
otomatik kapatılır.

Klasörler `WORKBENCH_AI_TOOLS` (varsayılan: depo kökünde `yz-araclari/`) ve `WORKBENCH_ENVS` (varsayılan
`ortamlar/`) ile değiştirilebilir. Aşağıdaki komutlar depo kökünden çalıştırılır.

## 1. ComfyUI + Qwen-Image-Edit-2511

```bash
mkdir -p yz-araclari && cd yz-araclari
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python3 -m venv .venv
.venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
.venv/bin/pip install -r requirements.txt

# GGUF modelleri yükleyen özel düğüm
git clone https://github.com/city96/ComfyUI-GGUF.git custom_nodes/ComfyUI-GGUF
.venv/bin/pip install -r custom_nodes/ComfyUI-GGUF/requirements.txt

# Model dosyaları (adlar coo/qwen_edit.py içindeki MODEL, LORA, METIN, VAE ile birebir aynı olmalı)
HF=https://huggingface.co
wget -P models/unet          $HF/unsloth/Qwen-Image-Edit-2511-GGUF/resolve/main/qwen-image-edit-2511-Q4_K_M.gguf
wget -P models/loras         $HF/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors
wget -P models/text_encoders $HF/Comfy-Org/Qwen-Image/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors
wget -P models/vae           $HF/Comfy-Org/Qwen-Image/resolve/main/split_files/vae/qwen_image_vae.safetensors
cd ../..
```

ComfyUI'yi elle başlatmanız gerekmez: bot `127.0.0.1:8188` üzerinde `--lowvram` ile kendisi açar.

**Deneme:**

```bash
python3 -m coo.qwen_edit --girdi urun.png --cikti deneme.png --istem "Studio product photo on a white sweep, soft light"
python3 -m coo.qwen_edit --kapat   # sunucuyu kapatır (pkill kullanmayın, yalnız ComfyUI süreçleri hedeflenir)
```

İlk çalıştırma modelleri yüklediği için 1–2 dk sürer; sonraki kareler 8 GB kartta ~70 sn.

## 2. Hunyuan3D-2 (yalnız şekil)

Önce lisansı okuyun: <https://github.com/Tencent-Hunyuan/Hunyuan3D-2>. Kullanım hakkınız yoksa bu adımı atlayın;
bot parametrik ürünler için build123d/OpenSCAD rotasını kullanmaya devam eder.

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

- Doku (texture) modülü **gerekmez**; yalnız şekil üretilir, renk filamentten gelir.
- Ağırlıklar (`tencent/Hunyuan3D-2mini`, `tencent/Hunyuan3D-2mv`) ilk kullanımda `yz-araclari/modeller/huggingface`
  altına iner (`HF_HOME` bot tarafından ayarlanır).
- **8 GB kart:** mv modeli tek seferde GPU'ya sığmaz; `ai3d_mesh.py` modeli CPU'da yükleyip aşamalara göre GPU'ya
  taşır (tepe ~2.7 GB, tohum başına ~150 sn).
- Sürüm sabitlemeleri önemlidir: daha yeni `transformers`/`diffusers` sürümleri Hunyuan3D-2 ile uyumsuzdur.

**Deneme:**

```bash
ortamlar/.venv-ai3d/bin/python coo/ai3d_mesh.py konsept.png cikti/ --model mini --yukseklik-mm 120
```

## 3. Blender

```bash
sudo snap install blender --classic     # ya da blender.org'dan indirip PATH'e ekleyin
blender -b -P coo/blender_onar.py -- --girdi ham.stl --cikti onarilmis.stl --rapor rapor.json --min-kalinlik 1.0
blender -b -P coo/blender_gorunus.py -- onarilmis.stl onizleme.png
```

Varsayılan kalınlık eşikleri 0.4 mm nozul içindir (`--min-kalinlik 1.0`, saksı haznesi `--hazne-duvar 2.0`).

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| `ComfyUI başlatılamadı` | `yz-araclari/ComfyUI/comfy_workbench.log` dosyasına bakın; çoğunlukla eksik model dosyası ya da ComfyUI-GGUF düğümü kurulmamıştır. |
| `UnetLoaderGGUF` bulunamadı | ComfyUI-GGUF `custom_nodes/` altına klonlanmamış ya da gereksinimleri kurulmamış. |
| Masaüstü donuyor / oturum kapanıyor | RAM yetersiz. `MemoryMax` değerini düşürün, aynı anda tarayıcıda ağır sekmeleri kapatın; ComfyUI 10 dk boşta kalınca kendisi kapanır. |
| Hunyuan `CUDA out of memory` | Masaüstü VRAM tutuyor; `--octree 256` ve `--adim 30` ile deneyin ya da `--model mini` kullanın. |
| Hunyuan import hatası | `transformers<4.50`, `diffusers<0.33`, `huggingface_hub<0.30` sabitlemelerini kontrol edin. |
