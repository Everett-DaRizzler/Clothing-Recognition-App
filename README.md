# AI Wardrobe — Phase 1 local vision prototype

This repository is a small, single-user prototype: an Expo phone client sends one clothing photo over local Wi-Fi to a FastAPI backend, which stores the original, preprocesses a working copy, and runs `HelloWorld0204/Classification-StyleWell-model` locally.

The repository was empty (Git only), so there was no frontend, backend, database, package manager, or convention to preserve. The implementation uses `mobile/` for Expo, `backend/` for FastAPI, SQLite, Pillow, and filesystem storage, and a `ClothingAnalyzer` interface with only the Qwen3-VL 2B adapter implemented.

## Model and hardware check

The active model is `HelloWorld0204/Classification-StyleWell-model`, a Qwen3-VL-4B fine-tune for garment analysis. Its repository contains about 8.88 GB of BF16 safetensors and recommends 6 GB+ VRAM; this computer has 64 GiB RAM and an RTX 3080 with 10 GiB VRAM. Qwen3-VL 2B and Qwen3-VL 8B remain metadata-only and are not loaded.

## Backend

Install Python 3.11+, then in PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
# Install a CUDA-compatible PyTorch build appropriate for your driver, then:
pip install -r requirements.txt
copy .env.example .env
python -m wardrobe_backend --check-hardware
python -m wardrobe_backend
```

The first inference downloads only the requested model into the Hugging Face cache. To pre-download it explicitly, use `python -m wardrobe_backend --download-model`. Find the computer's LAN IP with `ipconfig`, allow port 8000 through the Windows Firewall on Private networks, and keep the iPhone and computer on the same Wi-Fi.

## Mobile

```powershell
cd mobile
npm install
copy .env.example .env
# Edit EXPO_PUBLIC_API_URL to http://YOUR_LAN_IP:8000
npx expo start
```

Open the project on the physical iPhone, take or choose one photo, and tap Analyze. The app reports backend, timeout, upload, invalid-response, and inference errors.

## Benchmark

Add 30–50 photos through Developer AI Lab, run analysis, save each result, mark benchmark ground truth, and run `python -m wardrobe_backend.benchmark`. Ground truth and predictions are stored separately; corrections preserve both original and corrected values.

## Limitations

One primary garment per image, local storage, no login, no cloud AI, no segmentation/object detection, and no outfit recommendations. The API is intentionally a trusted private-LAN development service; do not expose port 8000 to the public internet. Next step: label real clothing photos, run evaluation, and decide whether the 2B model is good enough before considering any future model.
