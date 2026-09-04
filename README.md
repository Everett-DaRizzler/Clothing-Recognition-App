# AI Wardrobe — Phase 4 personalization prototype

This repository is a small, single-user prototype: an Expo phone client sends one clothing photo over local Wi-Fi to a FastAPI backend, which stores the original, preprocesses a working copy, runs `HelloWorld0204/Classification-StyleWell-model` locally, and lets the user save the reviewed analysis as a persistent digital wardrobe item.

The implementation uses `mobile/` for Expo, `backend/` for FastAPI, SQLite, Pillow, and filesystem storage, and a `ClothingAnalyzer` interface with StyleWell 4B as the active adapter. Phase 3 adds a deterministic outfit engine; Phase 4 adds a transparent local personalization layer that adjusts rankings without replacing base compatibility scoring.

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

The active model is already present in the local Hugging Face cache. The iPhone workflow does not download models; it only asks the local backend to run the installed StyleWell model. Find the computer's LAN IP with `ipconfig`, allow port 8000 through the Windows Firewall on Private networks, and keep the iPhone and computer on the same Wi-Fi.

## Wardrobe and outfit flows

The clothing flow is:

`My Wardrobe → Add Clothing → Take/Choose Photo → Analyze → Review/Edit → Save to Wardrobe → Browse/Search/Filter → Detail/Edit/Delete`

Wardrobe cards use the stored 320px thumbnails. Detail screens request the larger original image. Deleting a wardrobe item leaves the underlying image and AI analysis history intact, so an image cannot be accidentally destroyed with its clothing record.

The outfit flow is:

`My Wardrobe → Outfits → Generate Outfit → Choose occasion/style/season → View → Regenerate/replace → Save → Rate`

The **Build an Outfit Around This** action on a clothing detail screen starts specific-item generation. Saved outfits reference clothing item IDs; they do not duplicate clothing records. If an item is later deleted, the saved outfit remains readable and identifies the missing item so it can be replaced.

The Phase 4 flow is:

`Personalize → choose styles → Generate → Like / Not for me → Favorite items → Save → Wore This`

Explicit choices and learned signals are stored separately. Feedback creates soft style, color, and item signals; favorites receive a modest boost; recent combinations receive a bounded variety penalty. A new user with no preference data receives the normal Phase 3 ranking. The Developer Personalization Lab shows the actual local profile, feedback, history, item signals, and score reasons. Resetting learned preferences removes only learned signals.

The backend exposes:

- `GET /wardrobe?search=&category=` for structured search and category filtering
- `POST /wardrobe` for idempotent save-after-analysis
- `GET/PATCH/DELETE /wardrobe/{id}` for detail, editing, and deletion
- `GET /images/{image_id}/thumbnail` and `/original` for stored image variants
- `POST /outfits/generate` for deterministic role-based outfit generation
- `GET /outfits` and `GET /outfits/{id}` for saved outfits
- `POST /outfits` and `PATCH /outfits/{id}` for outfit persistence/editing
- `POST /outfits/{id}/replace` for replacing a top, bottom, shoes, outerwear, or accessory
- `PATCH /outfits/{id}/rating` for a 1–5 user rating
- `PATCH /wardrobe/{id}/favorite` to mark a clothing item as a favorite
- `GET/PATCH /personalization` to inspect or edit explicit preferences
- `POST /personalization/feedback` for like/dislike signals and optional reasons
- `POST /personalization/reset-learned` to clear learned signals only
- `POST /outfits/{id}/worn` to optionally record an outfit as worn
- `GET /developer/personalization-lab` for development-only personalization inspection
- `GET /developer/outfit-test-wardrobe` for fictional developer-only fixture data

User edits update the active wardrobe values while the original AI prediction remains in `ai_prediction_json`; each changed AI attribute also receives a separate correction-history record.

## Mobile

The phone UI has persistent icon-only bottom tabs: shirt = My Wardrobe, layers = My Outfits, and person = Profile. The top arrow returns to the previous in-app screen (disabled at a tab root); the gear opens Settings. All icons have screen-reader labels.

Midnight is the default dark theme. Choose Midnight, Daylight, or Evergreen under **Appearance** in either Profile or Settings. The choice applies to every screen and is remembered on that device/browser; it does not change wardrobe data. Style preferences are available from Profile or Settings, and the developer labs are under Settings.

```powershell
cd mobile
npm install
copy .env.example .env.local
# Edit EXPO_PUBLIC_API_URL to http://YOUR_LAN_IP:8000
npm start
```

Open the project on the physical iPhone, tap **Add Clothing**, take or choose one photo, tap **Analyze**, review the fields, and tap **Save to Wardrobe**. The app reports backend, timeout, upload, invalid-response, and inference errors. See [IPHONE_DEVELOPMENT.md](IPHONE_DEVELOPMENT.md) for the verified LAN, firewall, and Expo Go workflow.

## Tests

For the mobile theme-persistence regression tests, run `node --test tests/theme-storage.test.mjs` from `mobile` using Node 22.18+ (or Node 24+). The tests cover rapid changes, failed writes, and recovery without stale error messages.

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The suite covers image preparation, API health/CORS, ClothingItem persistence, duplicate-save prevention, search/filter, image association, edit/correction history, delete safety, color/pattern/style compatibility, scoring/ranking, regeneration diversity, specific-item generation, missing roles, fixture data, outfit persistence, ratings, replacement, deleted-item safety, and Phase 4 preferences, favorites, feedback, score bounds, variety, history, worn tracking, reset, and deletion behavior. From `mobile`, `npm exec tsc -- --noEmit` checks the Expo client and `npm exec expo-doctor` checks Expo compatibility.

## Benchmark

Add 30–50 photos through Developer AI Lab, run analysis, save each result, mark benchmark ground truth, and run `python -m wardrobe_backend.benchmark`. Ground truth and predictions are stored separately; corrections preserve both original and corrected values.

## Phase 4 limitations

One primary garment per image, local storage, no login, no cloud AI, no segmentation/object detection, no weather, no location, no calendar, no shopping links, and no machine-learning recommender. Personalization is intentionally deterministic, soft, and single-user. “Generated” and “saved” do not claim that an outfit was worn; only **Wore This** creates a worn event. The API is a trusted private-LAN development service; do not expose port 8000 to the public internet.
