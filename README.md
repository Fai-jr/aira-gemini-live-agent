<div align="center">

<h1>AIRA — AI Real-time Agent</h1>

**Control your entire desktop with just your voice.**<br/>
No mouse. No keyboard. No shortcuts. Just speak naturally — AIRA acts.

[![Gemini Live](https://img.shields.io/badge/Gemini_Live-2.0_Flash-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Playwright](https://img.shields.io/badge/Playwright-1.44-2EAD33?style=flat-square&logo=playwright&logoColor=white)](https://playwright.dev)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

---

*Built for the **Gemini Live Agent Challenge 2026***

</div>

---

## Overview

AIRA is a voice-first AI desktop agent that listens to you in real time and takes action. It combines **Google Gemini Live API** for bidirectional voice conversation, **Playwright** for browser automation, and **xdotool** for desktop app control — creating a seamless hands-free computing experience.

Speak naturally. AIRA understands intent, executes multi-step tasks, and remembers facts about you across sessions.

> *"Play Burna Boy on Spotify"* → Spotify opens, searches, and plays automatically  
> *"Search YouTube for lo-fi beats"* → Chrome opens a new tab and plays the first result  
> *"Open VS Code"* → VS Code launches in under a second  
> *"Next song"* → Spotify skips via keyboard control  
> *"Search Google for FastAPI tutorials"* → Chrome opens with results in a new tab  

---

## Architecture

![Architecture](docs/architecture.png)

AIRA has four layers. The **React frontend** captures microphone audio and streams it over a persistent WebSocket. The **FastAPI backend** classifies the voice intent and routes it to the correct agent — `browser_agent.py` for web tasks or `desktop_agent.py` for app control. **Gemini Live API** handles the bidirectional audio conversation. **PostgreSQL** stores users, session transcripts, and memories.

```
┌──────────────────────────────────────────────────────────────┐
│              Frontend  ·  React 19 + TypeScript + Vite       │
│        Voice UI  │  WebSocket Hook  │  Goal Panel  │  Memory │
└───────────────────────────┬──────────────────────────────────┘
                            │  WSS + PCM audio
┌───────────────────────────▼──────────────────────────────────┐
│              Backend  ·  FastAPI + Python 3.12               │
│                                                              │
│   voice.py  ──►  aira_agent.py  ──►  goal_planner.py        │
│        │               │                    │               │
│  gemini_live.py   browser_agent.py   desktop_agent.py       │
│  (Gemini WSS)     (Playwright)       (xdotool + wmctrl)     │
│        │               │                    │               │
│  memory_service.py     └────────────────────┘               │
│  gemini_vision.py           auth / security.py              │
└───────────────────────────┬──────────────────────────────────┘
                            │  SQLAlchemy async
┌───────────────────────────▼──────────────────────────────────┐
│              PostgreSQL 16  ·  Alembic migrations            │
│           users  │  sessions  │  memories (facts only)       │
└──────────────────────────────────────────────────────────────┘
         │                                    │
┌────────▼───────────┐            ┌───────────▼──────────────┐
│  Gemini Live API   │            │  Google Chrome           │
│  gemini-2.0-flash  │            │  Playwright CDP          │
│  Bidi audio+text   │            │  Real user profile       │
└────────────────────┘            └──────────────────────────┘
```

---

## Gesture Controls

![Gesture Map](docs/gesture-map.png)

AIRA supports hand gesture control via webcam. Vertical hand movement maps directly to page scroll direction, detected frame-by-frame and routed to `browser_agent.scroll()`.

| Gesture | Direction | Action |
|---|---|---|
| 🤚 Hand swipe up | ↑ Move hand upward | Scrolls active page up |
| 🤚 Hand swipe down | ↓ Move hand downward | Scrolls active page down |

**How it works:** The webcam captures hand position at 30fps. Y-axis movement is classified as an up or down swipe, then sent to the backend where `browser_agent.scroll()` executes a Playwright `window.scrollBy()` call on the active Chrome tab.

```
Webcam frame  →  Hand tracking  →  Y-axis classifier  →  browser_agent.scroll()  →  Chrome
```

---

## Voice Command Reference

AIRA classifies every utterance into one of four action types before executing.

| Intent | Example commands | Agent called |
|---|---|---|
| **Music** | "Play Burna Boy on Spotify", "Search YouTube for Drake" | `browser_agent` or `desktop_agent` |
| **App launch** | "Open VS Code", "Launch Telegram", "Open Gmail" | `desktop_agent.launch_app()` |
| **App control** | "Pause Spotify", "Next song", "Volume up", "Fullscreen VLC" | `desktop_agent.control_app()` |
| **Browser** | "Search Google for...", "Open youtube.com", "Go to GitHub" | `browser_agent` |

### Classification logic

```
User speaks
    │
    ▼
classify_command(user_text, aira_text)
    │
    ├── "play X on Spotify/YouTube"     → music
    ├── "open/launch X" (no song)       → app
    ├── "pause/next/volume/fullscreen"  → app (control_app)
    └── "search/find/navigate"          → browser
```

---

## Session Lifecycle

```
User opens AIRA in browser
  → Registers / logs in (JWT auth)
  → Clicks "Tap to Speak"
  → Grants microphone permission
      → Frontend opens WebSocket to FastAPI
      → AIRAAgent.initialize() loads memory context
      → GeminiLiveService connects to Gemini Live API (WSS, ping_interval=None)
      → Gemini responds: "Hi! How can I help you today?"
      → User speaks → PCM audio streamed to backend → forwarded to Gemini
      → Gemini returns audio + text transcript
      → voice.py classifies intent from transcript
      → browser_agent or desktop_agent executes action
      → Goal plan sent to frontend (AiraGoalPanel updates)
  → Session ends (user disconnects or says "end session")
      → Transcript analysed by Gemini for memorable facts
      → Facts (not habits or searches) stored in PostgreSQL
      → Session record saved with transcript + turn count
```

---

## Memory System

AIRA remembers facts about you across sessions — not search history or habits.

| Stored ✅ | Not stored ❌ |
|---|---|
| Your name | What you searched for |
| Preferred language | Music preferences |
| Occupation / context you share | App usage habits |
| Corrections you make | Browsing behaviour |

Memory is extracted by Gemini at session end from the transcript. Only `fact` and `correction` types are persisted. `habit` and `preference` types are explicitly filtered out.

---

## Supported Apps

AIRA can open 60+ apps. If the desktop app is not installed, it automatically opens the web version in Chrome.

| Category | Apps |
|---|---|
| **Code editors** | VS Code, Eclipse, Vim, Notepad++ |
| **Browsers** | Chrome, Firefox |
| **Office** | LibreOffice Writer/Calc/Impress, Word → Writer, Excel → Calc |
| **Music** | Spotify (/snap/bin/spotify), Rhythmbox, YouTube Music |
| **Communication** | Slack, Telegram, WhatsApp, Thunderbird, Zoom |
| **Media** | VLC, OBS Studio, OpenShot, Shotwell |
| **Dev tools** | Postman, MongoDB Compass, pgAdmin 4, gitg |
| **Google apps** | Gmail, Meet, Drive, Docs, Sheets, Calendar, Maps |
| **Social** | LinkedIn, Twitter, Instagram, Facebook, Netflix |
| **Productivity** | Notion, Trello, Figma, Asana, GitHub |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Voice AI | Google Gemini Live API (`gemini-2.0-flash-live-001`) |
| AI SDK | `google-genai`, `google-generativeai` |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| Backend | FastAPI 0.111, Python 3.12, WebSockets |
| Database | PostgreSQL 16, SQLAlchemy async, asyncpg, Alembic |
| Browser automation | Playwright 1.44, Google Chrome (persistent profile) |
| Desktop automation | xdotool, wmctrl (X11) |
| Auth | JWT (`python-jose`), bcrypt (`passlib`) |
| Deployment | Docker, Google Cloud Run, Firebase Hosting |

---

## Project Structure

```
aira-agent/
├── backend/
│   ├── agents/
│   │   ├── aira_agent.py          # Session orchestrator — memory + transcript
│   │   ├── browser_agent.py       # Playwright Chrome — new tab per search
│   │   ├── desktop_agent.py       # 60+ app launcher + xdotool control
│   │   └── goal_planner.py        # Multi-step action planner
│   ├── api/
│   │   ├── routes/
│   │   │   ├── voice.py           # WebSocket route + classify_command()
│   │   │   ├── browser.py         # BrowserAgent singleton
│   │   │   └── auth.py            # Register / login
│   │   └── deps.py
│   ├── core/
│   │   ├── config.py              # Pydantic settings
│   │   └── security.py            # JWT encode / decode
│   ├── models/
│   │   ├── user.py
│   │   ├── session.py
│   │   └── memory.py
│   ├── services/
│   │   ├── gemini_live.py         # Gemini Live WebSocket (ping_interval=None)
│   │   ├── gemini_vision.py       # Screen description via Gemini
│   │   └── memory_service.py      # Extract + store facts from transcript
│   ├── alembic/                   # DB migrations
│   ├── main.py                    # FastAPI app entry point
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/
    ├── src/
    │   ├── components/            # Voice UI, Goal panel, Memory viewer
    │   ├── hooks/                 # useWebSocket, useAudio
    │   └── pages/
    ├── public/
    ├── index.html
    └── package.json
```

---

## Quick Start

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.12+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| PostgreSQL | 16 | Local or Cloud SQL |
| Google Chrome | Latest | `/usr/bin/google-chrome` |
| Google AI Studio API key | — | Gemini Live access required |
| Linux + X11 | Ubuntu 22.04+ | xdotool requires X11 |

```bash
# System dependencies (Ubuntu / Debian)
sudo apt update && sudo apt install -y \
  xdotool wmctrl \
  google-chrome-stable \
  postgresql postgresql-contrib
```

---

### 1 — Clone

```bash
git clone https://github.com/your-username/aira-agent.git
cd aira-agent
```

---

### 2 — Backend

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

Create `backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/aira
SECRET_KEY=change-me-to-a-long-random-string
GOOGLE_API_KEY=AIza...your-key-here
GEMINI_LIVE_MODEL=gemini-2.0-flash-live-001
```

Create the database and run migrations:

```bash
# Create database
psql -U postgres -c "CREATE DATABASE aira;"

# Run migrations
alembic upgrade head
```

Start the backend:

```bash
# DISPLAY=:1 for headless servers; use DISPLAY=:0 on a desktop session
DISPLAY=:1 uvicorn main:app --port 8000
```

> **Tip:** If port 8000 is already in use: `fuser -k 8000/tcp && sleep 2`

---

### 3 — Chrome profile (first run only)

AIRA uses your real Chrome profile so YouTube and Spotify are already logged in:

```bash
cp -r ~/.config/google-chrome ~/.config/google-chrome-aira
```

---

### 4 — Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

Start the frontend:

```bash
npm run dev
```

Opens at **http://localhost:5173**

---

### 5 — Use AIRA

1. Go to **http://localhost:5173**
2. Click **Register** and create an account
3. Click **Tap to Speak**
4. Grant microphone access when prompted
5. Start speaking — AIRA will respond and act

---

### Docker (optional)

```bash
# Copy your .env files first, then:
docker compose up --build
```

---

## Reproducibility Checklist

Judges can verify AIRA is fully reproducible by following these steps:

- [ ] Clone the repo
- [ ] `pip install -r requirements.txt` — no missing packages
- [ ] `playwright install chromium` — browser installs cleanly
- [ ] `alembic upgrade head` — migrations run without errors
- [ ] `npm install` in `/frontend` — no dependency conflicts
- [ ] Backend starts on port 8000 with `uvicorn main:app --port 8000`
- [ ] Frontend starts on port 5173 with `npm run dev`
- [ ] Register a new user and complete a voice session
- [ ] Say "open Chrome" — browser launches
- [ ] Say "play Burna Boy on YouTube" — Chrome opens and plays

---

## Environment Variables

### Backend

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL async connection string |
| `SECRET_KEY` | ✅ | JWT signing secret (min 32 chars) |
| `GOOGLE_API_KEY` | ✅ | Gemini API key from AI Studio |
| `GEMINI_LIVE_MODEL` | ✅ | `gemini-2.0-flash-live-001` |

### Frontend

| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | ✅ | Backend base URL |
| `VITE_WS_URL` | ✅ | WebSocket base URL (use `wss://` in production) |

---

## Deployment (Google Cloud Run)

```bash
# 1. Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 2. Enable APIs
gcloud services enable run.googleapis.com sqladmin.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com

# 3. Build and push Docker image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/aira-backend ./backend

# 4. Deploy to Cloud Run
gcloud run deploy aira-backend \
  --image gcr.io/YOUR_PROJECT_ID/aira-backend \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8000 \
  --memory 2Gi \
  --set-env-vars GEMINI_LIVE_MODEL=gemini-2.0-flash-live-001 \
  --set-secrets GOOGLE_API_KEY=GOOGLE_API_KEY:latest,SECRET_KEY=SECRET_KEY:latest

# 5. Deploy frontend to Firebase Hosting
cd frontend && npm run build
firebase deploy --only hosting
```

---

## Known Limitations

- Requires **Linux with X11** — xdotool does not work on pure Wayland without XWayland
- **Desktop app control** (Spotify pause/next) requires the app window to be open and visible
- **Chrome profile copy** is required on first run for sites that need login (YouTube, Spotify web)
- Gemini Live API requires a key with **Live access enabled** in Google AI Studio
- The `--no-sandbox` Chrome flag is required when running as root or in containers

---

## Why AIRA Stands Out

| Capability | AIRA | Typical voice assistant |
|---|---|---|
| Real desktop control | ✅ Opens and controls any installed app | ❌ Web only |
| Persistent memory | ✅ Facts remembered across sessions | ❌ Session only |
| Multi-tab browser | ✅ New tab per search, old tabs preserved | ❌ Single tab |
| App fallback | ✅ Web version if desktop app not installed | ❌ Fails silently |
| Gesture input | ✅ Webcam scroll control | ❌ None |
| Music control | ✅ Auto-plays on YouTube, Spotify, Apple Music | ❌ Web search only |

---

## License

MIT © 2026