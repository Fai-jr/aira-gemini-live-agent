
# AIRA – AI Real-time Agent

Next-generation voice-controlled AI agent with:

- Real-time voice conversation (Gemini Live API)

- Screen understanding & vision

- Browser automation & control (Playwright)

- Goal planning & multi-step task execution

Tech stack:

- Backend: Python + FastAPI + Gemini API

- Frontend: React + TypeScript + Vite

- Browser control: Playwright (Chromium)

## Setup

```bash

# Backend

cd backend

python -m venv venv

source venv/bin/activate

pip install -r requirements.txt

DISPLAY=:1 uvicorn main:app --port 8000

# Frontend

cd ../frontend   # or wherever your client/ folder is

npm install

npm run dev

