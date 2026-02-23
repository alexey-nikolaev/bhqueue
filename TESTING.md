# Testing Setup Guide

## Quick Start (3 terminals needed)

### Terminal 1 - Start ngrok for Backend API
```bash
ngrok http 8000
```
**Note:** We have a static ngrok URL that stays the same:
`https://unswabbed-unrespectfully-sherell.ngrok-free.dev`

This URL is already configured in `frontend/src/config/api.ts` - no need to update it.

### Terminal 2 - Start Backend
```bash
cd /Users/alexey-nikolaev/Documents/GitHub/bhqueue/backend
python -m uvicorn app.main:app --reload
```

### Terminal 3 - Start Frontend (Expo)
```bash
cd /Users/alexey-nikolaev/Documents/GitHub/bhqueue/frontend
npx expo start --tunnel
```

## Connecting from iPhone

**Option 1:** Scan QR code shown in terminal with iPhone camera

**Option 2:** Open Expo Go app → the project appears in "Recently opened"

**Option 3:** If tunnel URL is known, enter it manually in Expo Go

## Troubleshooting Expo Tunnel

### "Cannot read properties of undefined (reading 'body')" or "remote gone away"

This error occurs when there's a conflict between the backend ngrok and Expo's internal ngrok.

**Solution:**
1. Stop the backend ngrok (Ctrl+C in Terminal 1)
2. Start Expo tunnel: `npx expo start --tunnel`
3. Once Expo tunnel is running, restart backend ngrok: `ngrok http 8000`

### "Install @expo/ngrok@^4.1.0"

Run:
```bash
cd frontend
npm install @expo/ngrok@4.1.0
```

### Port 8081 already in use

Kill existing Metro process:
```bash
lsof -ti:8081 | xargs kill -9
```

## Static URLs (Do Not Change)

- **Backend ngrok:** `https://unswabbed-unrespectfully-sherell.ngrok-free.dev`
- **Frontend API config:** Already points to the above URL

## Test Telegram Parsing

Before starting backend, run:
```bash
cd /Users/alexey-nikolaev/Documents/GitHub/bhqueue/backend
python -m scripts.test_telegram_parsing
```

## Seed Database (if needed)
```bash
cd /Users/alexey-nikolaev/Documents/GitHub/bhqueue/backend
python -m scripts.seed_data
```

## Test Credentials
- Email: alexey_nikolaev@ymail.com
- The app should auto-login if previously authenticated
