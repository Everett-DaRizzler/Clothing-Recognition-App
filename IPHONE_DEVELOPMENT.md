# iPhone + Expo Go + local backend development (Phase 4)

This guide runs the Phase 4 AI Wardrobe application entirely on the local network:

`iPhone → Expo Go → Wi-Fi → Windows PC → FastAPI → installed StyleWell 4B model → iPhone`

Nothing is deployed publicly. The backend is intended only for a trusted home/private LAN.

## Requirements

- Windows PC with Node.js and npm
- Python 3.11 virtual environment already present at `backend/.venv`
- Expo Go installed on the iPhone
- iPhone and PC connected to the same Wi-Fi network
- Existing StyleWell 4B model in the local Hugging Face cache

Verified repository versions:

- Expo SDK 53
- React Native 0.79.6
- Node.js 24.12.0
- npm 11.6.2
- Python 3.11.9
- FastAPI 0.141.1
- Backend host `0.0.0.0`
- Backend port `8000`

## 1. Find the Windows LAN address

In PowerShell:

```powershell
ipconfig
```

Use the IPv4 address under the active Wi-Fi adapter, not a virtual adapter address. It usually starts with `192.168.` or `10.` and can change after reconnecting to Wi-Fi or restarting the router.

## 2. Configure the mobile API URL

Expo reads public development variables from `mobile/.env.local`. This file is ignored by Git because the address is specific to this computer/network.

```text
EXPO_PUBLIC_API_URL=http://YOUR_WINDOWS_IPV4:8000
```

The actual address belongs only in the ignored `mobile/.env.local` file; do not commit it to the repository.

If the IPv4 address changes, update `mobile/.env.local`, stop Expo, and start Expo again. `EXPO_PUBLIC_*` values are bundled into the app and must never contain secrets.

## 3. Windows network and firewall

Before testing from the phone, confirm this trusted home Wi-Fi is classified as **Private** in:

`Windows Settings → Network & internet → Wi-Fi → your connected network → Network profile type → Private`

Do not do this on a public or untrusted Wi-Fi network.

Then open PowerShell **as Administrator** from the repository root and add this narrowly scoped inbound rule if it does not already exist:

```powershell
$wardrobePython = (Resolve-Path ".\backend\.venv\Scripts\python.exe").Path
New-NetFirewallRule -DisplayName "AI Wardrobe Backend (Private LAN)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -Program $wardrobePython -Profile Private -RemoteAddress LocalSubnet
Get-NetFirewallRule -DisplayName "AI Wardrobe Backend (Private LAN)"
```

This permits only the project's Python executable, TCP port 8000, Private networks, and devices on the local subnet. Do not disable Windows Firewall and do not forward port 8000 on the router.

To remove the rule later:

```powershell
Remove-NetFirewallRule -DisplayName "AI Wardrobe Backend (Private LAN)"
```

No firewall rule or network-profile change was made automatically.

## 4. Start the backend and existing AI environment

Open Terminal 1:

```powershell
cd "C:\Users\gpope\Documents\ChatGPT\Clothing Recognition App\backend"
.\.venv\Scripts\Activate.ps1
python -m wardrobe_backend
```

Expected output includes:

```text
Uvicorn running on http://0.0.0.0:8000
```

The backend and AI model use the same process. There is no separate model-server command. StyleWell loads from the existing local cache on the first analysis request, so the first request takes longer.

## 5. Test the backend

On the Windows PC, open:

```text
http://127.0.0.1:8000/health
```

Then open this in Safari on the iPhone, replacing the placeholder with the current Wi-Fi IPv4 address:

```text
http://YOUR_WINDOWS_IPV4:8000/health
```

A successful response includes `"status":"ok"`, `"modelId":"stylewell-4b"`, and `"modelCached":true`.

## 6. Start Expo

Open Terminal 2:

```powershell
cd "C:\Users\gpope\Documents\ChatGPT\Clothing Recognition App\mobile"
npm start
```

The project start script explicitly uses LAN mode. The equivalent direct command is:

```powershell
npx expo start --lan
```

Open Expo Go on the iPhone and scan the QR code shown by Expo. Keep both terminals open.

## 7. Test the app

1. Open the **Settings gear → AI lab**.
2. Confirm the displayed backend URL matches the computer's current IPv4 address.
3. Tap **Test Backend Connection** and confirm the green **Connected** status.
4. Tap the **My Wardrobe shirt icon → Add clothing**, then **Take Photo** or **Choose From Photos**.
5. Use one clearly visible clothing item.
6. Tap **Analyze**.
7. Wait while the installed StyleWell model runs locally.
8. Review the detected fields and edit any obvious mistakes.
9. Tap **Save to Wardrobe** and confirm **Added to wardrobe.**
10. Search/filter the wardrobe card, open it, edit it, and delete it when finished.
11. Tap the **My Outfits** layers icon and tap **Generate Outfit**.
12. Choose an occasion, style, and season, then tap **Generate Outfit**.
13. Confirm every displayed piece is from the wardrobe, review the explanation and score, and tap **Regenerate**.
14. Save the generated outfit, open it under **Saved Outfits**, rate it, and use **Replace** on a piece.
15. Open a clothing detail screen and use **Build an Outfit Around This** to verify specific-item generation.
16. Open the **Profile person icon → Style preferences**, choose styles you like and styles you do not usually wear, and save.
17. Generate an outfit, tap **Like** or **Not for me**, and optionally choose a dislike reason.
18. Mark a wardrobe item as a favorite, generate again, and inspect the score explanation.
19. Save an outfit, open it under **Saved Outfits**, and tap **Wore This** if appropriate.
20. Open **Settings gear → Personalization lab** to inspect explicit choices, learned signals, feedback, favorites, history, and score reasons.
21. Use **Reset Learned Preferences** and confirm learned signals disappear while explicit choices and wardrobe records remain.

The outfit engine does not call the StyleWell model again. It uses saved structured attributes and stored thumbnails, so generation should be much faster than photo analysis.

## 8. Developer Outfit Lab

From **Developer AI Lab**, tap **Open Developer Outfit Lab**. This uses 10 fictional clothing items and never inserts them into the real wardrobe. Generate a fixture outfit to inspect:

- color, style, occasion, season, pattern, and completeness scores
- total score and candidate count
- rejection reasons such as occasion mismatch or a role already being filled

Use this screen when tuning scoring rules without photographing additional clothing.

## 9. Phase 4 personalization lab

From the **Profile person icon**, tap **Style preferences**. The screen uses normal language and does not require a questionnaire. The recommendation score remains anchored to the Phase 3 base score; preference changes are a bounded bonus or penalty. The developer lab inspects local signals and is not a second model or a cloud service.

## Troubleshooting

### Safari cannot open `/health`

- Confirm the iPhone and PC are on the same Wi-Fi and neither device is using a VPN.
- Re-run `ipconfig`; update `mobile/.env.local` if the IPv4 address changed.
- Confirm the backend terminal says `0.0.0.0:8000`.
- Change the trusted Wi-Fi profile to Private and add the narrow firewall rule above.
- Some guest Wi-Fi networks enable client isolation; use the main home network instead.

### Expo Go cannot open the project

- Confirm the phone and PC are on the same Wi-Fi.
- Restart Metro with `npx expo start --lan --clear`.
- Expo tunnel fallback is `npx expo start --tunnel`, but it only tunnels the Expo development server. It does not make the local AI backend reachable; the iPhone must still reach `http://YOUR_WINDOWS_IPV4:8000`.

### Backend connection test fails

- Check the exact URL shown in Developer AI Lab.
- Confirm the backend is running and port 8000 is not being used by another process.
- Test the same `/health` URL in iPhone Safari.
- Restart Expo after changing `mobile/.env.local`.

### Analysis fails or times out

- Keep the backend terminal visible and look for a clear server error.
- The first request loads StyleWell and can take longer because some model layers are CPU-offloaded on this GPU.
- Do not start multiple backend instances; each instance would try to load another model copy.
- Confirm the model remains in the local Hugging Face cache. No additional model is needed.

### Wardrobe items do not appear

- Confirm the save confirmation appeared after analysis.
- Return to **My Wardrobe** and wait for the refresh to finish.
- Check that the backend is still running; saved items are stored in `backend/data/wardrobe.sqlite3`.
- The image files remain under `backend/data/images`; the app uses thumbnails for the grid and originals for details.

### CORS

The FastAPI development CORS policy accepts HTTP origins from localhost and RFC1918 private-LAN addresses only. Expo Go's native networking is not browser CORS-restricted, but the policy also supports local Expo web development. CORS is not authentication: any device that can reach this development API can call it, so keep the Windows network profile and firewall rule limited to a trusted Private LAN and never expose or port-forward port 8000.

## Start here

**Terminal 1**

```powershell
cd "C:\Users\gpope\Documents\ChatGPT\Clothing Recognition App\backend"
.\.venv\Scripts\Activate.ps1
python -m wardrobe_backend
```

**Terminal 2**

```powershell
cd "C:\Users\gpope\Documents\ChatGPT\Clothing Recognition App\mobile"
npm start
```

Then open Expo Go → open the project → Settings gear → AI lab → Test Backend Connection. Next tap My Wardrobe shirt icon → Add clothing → Take Photo or Choose From Photos → Analyze.
