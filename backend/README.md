# AIRA - AI Real-time Agent

AIRA is a next-generation multimodal AI agent built for the Gemini Live Agent Challenge 2026.
It listens, sees, speaks, remembers, and acts - just like a real intelligent assistant but far more powerful.

## Architecture

- Frontend: React + TypeScript (Vite) — Web
- Mobile: Expo (React Native) — iOS and Android
- Backend: Python FastAPI
- AI: Google Gemini Live API + Gemini 2.0 Flash (ADK)
- Database: PostgreSQL (persistent memory)
- Browser Automation: Playwright
- Deployment: Google Cloud Run

## Project Structure

```
aira/
  backend/     Python FastAPI backend
  frontend/    React TypeScript web app
  mobile/      Expo React Native mobile app
  shared/      Shared types and utilities
```

## Backend Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ running locally
- Google Cloud project with Gemini API enabled

### Installation

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### Database Setup

```bash
# Create the database in PostgreSQL
psql -U postgres -c "CREATE DATABASE aira_db;"

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your PostgreSQL credentials and Google API key

# Run migrations
alembic upgrade head
```

### Running the Backend

```bash
uvicorn main:app --reload --port 8000
```

Visit http://localhost:8000/docs for the interactive API documentation.

## Build Steps

| Step | Feature |
|------|---------|
| Step 2 (current) | Backend foundation - Auth, DB, Models, REST API |
| Step 3 | Gemini Live API WebSocket voice streaming |
| Step 4 | Frontend - AIRA Orb UI + voice interface |
| Step 5 | Vision agent + screenshot understanding |
| Step 6 | Goal planner + multi-step workflows |
| Step 7 | Memory service integration |
| Step 8 | Google Cloud Run deployment |
| Step 9 | Computer Use agent - screen control |

## Competition

Gemini Live Agent Challenge 2026 - Deadline: March 16, 2026