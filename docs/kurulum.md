# Temiz Ubuntu'dan kurulum

Ubuntu 24.04 / 25.10 masaüstünde denendi. Her şey kendi masaüstü kullanıcınızla çalışır (root servisi yok).
English: [install.md](install.md)

## 1. Sistem paketleri

```bash
sudo apt update
sudo apt install -y git curl python3 python3-venv python3-pip ffmpeg
# önerilen
sudo apt install -y blender            # ya da Blender 4.x/5.x resmi arşivi
```

OrcaSlicer (önerilen, dilimleme için): OrcaSlicer sürüm sayfasından AppImage veya Flatpak kurun ve `PATH` üzerinde
bir `orcaslicer` komutu olsun (ör. `~/.local/bin/orcaslicer` sarmalayıcı betiği).

## 2. Claude Code CLI

```bash
curl -fsSL https://claude.ai/install.sh | bash     # ~/.local/bin/claude
claude                                             # bir kez giriş yapın (abonelik veya API anahtarı), sonra /exit
```

Bot, depo kökünden alt süreç olarak `claude -p --agent <ad> ...` çağırır; ajanlar bu depodaki `CLAUDE.md` ve
`.claude/` klasörünü okur.

## 3. Telegram botu

1. Telegram'da **@BotFather** → `/newbot` → ad ve kullanıcı adı seçin → **belirteci (token)** kopyalayın.
2. Yeni botunuza herhangi bir mesaj gönderin.
3. Tarayıcıda `https://api.telegram.org/bot<TOKEN>/getUpdates` adresini açın, `"chat":{"id": ...}` değerini not edin —
   bu sizin **sohbet kimliğinizdir**. Bot yalnız bu sohbete yanıt verir; kimlik yoksa başlamaz.

## 4. Depoyu indir ve kur

```bash
git clone <bu-depo> ~/workbench-bot && cd ~/workbench-bot
./install.sh
```

`install.sh` tekrar tekrar çalıştırılabilir. `.venv` oluşturur, `requirements-dev.txt` kurar, `veri/` (işletme
verisi, git dışı) klasörlerini açar, `.env` yoksa `.env.example`'dan kopyalar (`chmod 600`) ve
`systemd/workbench-bot.service.template` şablonundan `~/.config/systemd/user/workbench-bot.service` birimini kurar.

`.env` dosyasını doldurun:

```bash
nano .env      # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WORKBENCH_SHOP_NAME, WORKBENCH_SHOP_URL, PRINTER_IP ...
```

Kuralları kendinize uyarlayın: `CLAUDE.md`, `config/marka/marka-rehberi.md`, `config/renk_paleti.yaml`,
`config/orca/kategoriler.yaml` ve `config/bakim.yaml`.

## 5. Test ve başlatma

```bash
.venv/bin/python -m pytest -q
systemctl --user enable --now workbench-bot.service
journalctl --user -u workbench-bot -f          # günlük (ayrıca coo/loglar/coo_bot.log)
./saglik.sh                                    # sağlık kontrolü; ./saglik.sh --test testleri de çalıştırır
```

Bota `/start` gönderin. Oturum kapanınca da çalışsın isterseniz: `sudo loginctl enable-linger $USER`
(Chrome/Blender arayüz özelliklerini kullanıyorsanız Sorun giderme'deki DISPLAY notuna bakın).

## 6. İsteğe bağlı: ERP ve Studio

Kardeş depoları kendi README'lerine göre kurun:

- **3d-printer-open-workbench-erp** → REST `ERP_URL` (vars. `http://127.0.0.1:8000`), ajanlar için MCP sunucusu.
- **3d-printer-open-workbench-studio** → arayüz/MCP `STUDIO_URL` (vars. `http://127.0.0.1:7870`, MCP `/mcp`).

Ajanlara tanıtın:

```bash
cp .mcp.json.example .mcp.json   # yolları düzeltin; .mcp.json git dışıdır
claude mcp list                  # depo kökünde çalıştırın; iki sunucu da görünmeli
```

## 7. İsteğe bağlı: Chrome + Claude in Chrome + Google Flow

Bazı ajanlar (Google Flow'da konsept görsel/video, mağaza yükleme, Pinterest) **Claude in Chrome** eklentisiyle sizin
Chrome'unuzu kullanır. Google Chrome'u ve eklentiyi kurun, ajanların kullanacağı sitelere giriş yapın (giriş, ödeme ve
yayınlama adımları her zaman onayınız için durur). Kapatmak için `.env` içine `WORKBENCH_CLAUDE_CHROME=0` yazın.

## 8. İsteğe bağlı: ComfyUI (Qwen-Image-Edit) ve Hunyuan3D-2

NVIDIA GPU gerekir (12 GB VRAM önerilir). Depoda hiçbiri yoktur — indirir ve lisanslarını kendiniz kabul edersiniz.

```bash
mkdir -p yz-araclari && cd yz-araclari
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# İş akışının beklediği dosyalar (adlar coo/qwen_edit.py içinde: MODEL, LORA, METIN, VAE):
#   Qwen-Image-Edit-2511 GGUF               -> models/unet/          (ComfyUI-GGUF özel düğümü gerekir)
#   Lightning 4 adım LoRA                   -> models/loras/
#   Qwen2.5-VL metin kodlayıcı              -> models/text_encoders/
#   Qwen-Image VAE                          -> models/vae/
```

Hunyuan3D-2 (isteğe bağlı, görselden 3B): önce Tencent Hunyuan 3D Community License'ı okuyun — **AB, Birleşik Krallık
ve Güney Kore'de geçerli değildir**. Kullanma hakkınız varsa `yz-araclari/Hunyuan3D-2` altına indirin ve
gereksinimleriyle `ortamlar/.venv-ai3d` ortamını oluşturun. Model ağırlıkları `yz-araclari/modeller/huggingface`
altında önbelleğe alınır.

Ayrı sanal ortamlar isteğe bağlıdır: `ortamlar/.venv-cad`, `.venv-ai3d` veya `.venv-gorsel` varsa bot o işler için
onları, yoksa kendi `.venv`'ini kullanır.

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| Bot kapanıyor: `TELEGRAM_CHAT_ID ayarlı değil` | Sohbet kimliğinizi `.env`'e yazın (adım 3). |
| Bot yanıt vermiyor | `journalctl --user -u workbench-bot -n 50`; belirteci `./saglik.sh` ile kontrol edin; yalnız sizin sohbet kimliğinize yanıt verilir. |
| Chrome / Blender / Flow adımları "ekran yok" hatası veriyor | Servis **grafik oturumdan sonra** başlamalı ki `DISPLAY`/`WAYLAND_DISPLAY` olsun. Birim `After=graphical-session.target` ile sıralıdır; linger açıksa ve bot girişten önce başladıysa, giriş yaptıktan sonra `systemctl --user import-environment DISPLAY WAYLAND_DISPLAY XAUTHORITY && systemctl --user restart workbench-bot` çalıştırın (ya da oturum otomatik başlatmaya ekleyin). |
| YZ işlerinde masaüstü donuyor / bot öldürülüyor | Birim `MemoryMax=12G` / `MemoryHigh=10G` koyar. Küçük makinelerde düşürün (`systemctl --user edit workbench-bot` → `[Service] MemoryMax=8G`); çekirdek oturumunuz yerine kaçak alt süreçleri (ComfyUI, Blender) durdurur. |
| Serviste `claude: command not found` | Birim `PATH`'e `~/.local/bin` ekler; Claude Code'u yeniden kurun ya da oraya bağlantı verin. |
| ERP/Studio düğmeleri "ulaşılamadı" diyor | İsteğe bağlıdırlar; servisleri başlatın ya da yok sayın. `ERP_URL` / `STUDIO_URL` değerlerini kontrol edin. |
| Dilimleme: profil bulunamadı | Profiller `config/orca/` altında; başka yazıcı için README'deki "Dilimleme profilleri"ne bakın. |
| Yazıcı durumu "PRINTER_IP ayarlı değil" | `PRINTER_IP` girin (Elegoo Centauri Carbon gibi SDCP v3 yazıcılar). |
| Ajan işleri çok uzun sürüyor | Telegram'dan iptal edin (`/iptal`); kesin sınır için `WORKBENCH_CLAUDE_ZAMAN_ASIMI` (saniye). |

Güncelleme: `git pull && ./install.sh && systemctl --user restart workbench-bot`.
