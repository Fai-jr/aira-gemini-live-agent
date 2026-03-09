import asyncio
import json
import logging
import base64
import re
import time
import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.deps import get_db
from core.security import decode_access_token
from agents.aira_agent import AIRAAgent
from agents.goal_planner import GoalPlanner
from models.user import User
from models.session import Session
from services.gemini_vision import GeminiVisionService
from api.routes.browser import get_browser_agent  # ← THE ONE TRUE BROWSER INSTANCE

logger = logging.getLogger("aira.voice_route")

router = APIRouter(prefix="/voice", tags=["Voice"])

# Module-level lock — prevents two concurrent turn_complete calls from both opening Chrome
_browser_open_lock = asyncio.Lock()
_last_executed_queries: dict[str, float] = {}
LAST_ACTION_COOLDOWN_SEC = 90


async def get_user_from_token(token: str, db: AsyncSession):
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


def extract_search_query(aira_text: str) -> str | None:
    quoted = re.findall(r'"([^"]+)"', aira_text)
    if quoted:
        return quoted[0]
    patterns = [
        r'search(?:ing)?\s+(?:google\s+)?for\s+(.+?)(?:\.|,|$)',
        r'look(?:ing)?\s+up\s+(.+?)(?:\.|,|$)',
        r'find(?:ing)?\s+(?:information\s+(?:on|about)\s+)?(.+?)(?:\.|,|$)',
        r'(?:open|opening|navigate|navigating)\s+(?:to\s+)?(.+?)(?:\.|,|$)',
        r'query[:\s]+(.+?)(?:\.|,|$)',
    ]
    for pattern in patterns:
        match = re.search(pattern, aira_text.lower())
        if match:
            query = match.group(1).strip().strip('"\'')
            if len(query) > 3:
                return query
    return None


def extract_url(aira_text: str) -> str | None:
    urls = re.findall(r'https?://[^\s,]+', aira_text)
    if urls:
        return urls[0]
    sites = re.findall(r'(?:open|go to|navigate to|visit)\s+([\w.]+\.(?:com|org|net|io|co))', aira_text.lower())
    if sites:
        return f"https://{sites[0]}"
    return None


@router.get("/status")
async def voice_status() -> dict:
    return {"status": "Voice WebSocket service is running"}


@router.websocket("/stream")
async def voice_stream(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    await websocket.accept()

    user = await get_user_from_token(token, db)
    if not user:
        await websocket.send_json({"type": "error", "message": "Invalid authentication token"})
        await websocket.close(code=4001)
        return

    db_session = Session(user_id=user.id, session_type="voice", status="active")
    db.add(db_session)
    await db.flush()
    session_id = str(db_session.id)

    agent = AIRAAgent(user=user, db=db)
    connected = await agent.initialize(session_id=session_id)

    if not connected:
        await websocket.send_json({"type": "error", "message": "AIRA failed to connect to Gemini."})
        await websocket.close(code=4002)
        return

    await websocket.send_json({
        "type": "session_started",
        "session_id": session_id,
        "message": f"Hello {user.full_name.split()[0]}, I am AIRA. How can I help you?",
        "interruptions_enabled": True,
    })

    goal_planner = GoalPlanner()
    vision_service = GeminiVisionService()

    # ── Single browser instance shared across the whole app ──
    browser = get_browser_agent()

    aira_text_buffer: list[str] = []
    last_user_message: list[str] = [""]
    browser_action_fired: list[bool] = [False]
    allow_interruptions: list[bool] = [True]
    aira_is_processing: list[bool] = [False]

    async def handle_turn_complete():
        full_text = " ".join(aira_text_buffer).strip()
        aira_text_buffer.clear()
        aira_is_processing[0] = False

        if not full_text:
            return

        logger.info(f"AIRA turn complete. Response: {full_text[:100]}")

        async with _browser_open_lock:
            # Double-check inside lock — second concurrent call exits here
            if browser_action_fired[0]:
                logger.info("Browser already opened for this command — skipping duplicate")
                return

            action_words = [
                "search", "google", "searching", "look up", "looking up",
                "find", "finding", "open", "opening", "navigate", "navigating",
                "browse", "browsing", "youtube", "maps", "website", "url",
                "going to", "i'll", "i will", "let me", "initiating",
                "executing", "pulling up", "loading", "accessing",
            ]
            if not any(w in full_text.lower() for w in action_words):
                return

            query = extract_search_query(full_text)
            url = extract_url(full_text)
            action_key = last_user_message[0].strip().lower() or query or url or full_text[:60]

            now = time.time()
            if now - _last_executed_queries.get(action_key, 0) < LAST_ACTION_COOLDOWN_SEC:
                logger.info(f"Cooldown active for '{action_key}' — skipping")
                return

            # Set flag and timestamp INSIDE lock before any await
            browser_action_fired[0] = True
            _last_executed_queries[action_key] = now
            stale = [k for k, v in _last_executed_queries.items() if now - v > 300]
            for k in stale:
                del _last_executed_queries[k]

        # ── Execute browser action OUTSIDE lock ──
        logger.info(f"Opening Chrome: query={query} url={url}")
        try:
            # Ensure browser is started
            if not browser.is_running:
                await browser.start()

            if "youtube" in full_text.lower() and query:
                result = await browser.youtube_search(query)
            elif url:
                result = await browser.navigate(url)
            elif query:
                result = await browser.search_google(query)
            else:
                fallback = last_user_message[0] or "search"
                result = await browser.search_google(fallback)

            logger.info(f"Browser result: {result}")

            if result.get("success"):
                await websocket.send_json({
                    "type": "goal_plan",
                    "plan": {
                        "goal_summary": query or last_user_message[0] or "Browser search",
                        "requires_confirmation": False,
                        "steps": [{
                            "step": 1,
                            "action": f"Search: {query or last_user_message[0]}",
                            "type": "search",
                            "details": query or last_user_message[0],
                            "status": "completed",
                        }],
                    },
                })
            else:
                browser_action_fired[0] = False
                _last_executed_queries.pop(action_key, None)

        except Exception as e:
            logger.error(f"Browser action failed: {e}")
            browser_action_fired[0] = False
            _last_executed_queries.pop(action_key, None)

    async def stream_gemini_responses():
        try:
            async for response in agent.gemini_live.receive_responses():
                rtype = response.get("type")

                if rtype == "audio":
                    aira_is_processing[0] = True
                    await websocket.send_json({
                        "type": "audio",
                        "data": base64.b64encode(response["data"]).decode("utf-8"),
                        "mime_type": "audio/pcm;rate=24000",
                    })

                elif rtype == "text":
                    aira_is_processing[0] = True
                    text = response["data"]
                    agent.add_to_transcript("aira", text)
                    aira_text_buffer.append(text)
                    await websocket.send_json({
                        "type": "transcript",
                        "role": "aira",
                        "text": text,
                    })

                elif rtype == "user_transcript":
                    user_text = response["data"]
                    last_user_message[0] = user_text
                    browser_action_fired[0] = False
                    agent.add_to_transcript("user", user_text)
                    await websocket.send_json({
                        "type": "transcript",
                        "role": "user",
                        "text": user_text,
                    })

                elif rtype == "turn_complete":
                    await handle_turn_complete()
                    await websocket.send_json({"type": "turn_complete"})

                elif rtype == "interrupted":
                    aira_text_buffer.clear()
                    aira_is_processing[0] = False
                    await websocket.send_json({"type": "interrupted"})

                elif rtype in ("connection_closed", "error"):
                    await websocket.send_json({
                        "type": "error",
                        "message": response.get("message", "Connection lost"),
                    })
                    break

        except Exception as e:
            logger.error(f"Gemini stream error: {e}")

    response_task = asyncio.create_task(stream_gemini_responses())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = message.get("type")

            if msg_type == "audio":
                if aira_is_processing[0] and not allow_interruptions[0]:
                    continue
                audio_bytes = base64.b64decode(message["data"])
                await agent.process_audio(audio_bytes)

            elif msg_type == "set_interruptions":
                allow_interruptions[0] = bool(message.get("enabled", True))
                await websocket.send_json({
                    "type": "interruptions_updated",
                    "enabled": allow_interruptions[0],
                })

            elif msg_type == "text":
                user_text = message.get("data", "").strip()
                if user_text:
                    last_user_message[0] = user_text
                    browser_action_fired[0] = False
                    agent.add_to_transcript("user", user_text)
                    await websocket.send_json({
                        "type": "transcript",
                        "role": "user",
                        "text": user_text,
                    })
                    await agent.process_text(user_text)

            elif msg_type == "screen_context":
                data = message.get("data", "")
                if message.get("is_image"):
                    image_bytes = base64.b64decode(data)
                    description = await vision_service.describe_screenshot(image_bytes)
                    await agent.inject_screen_context(description)
                    await websocket.send_json({"type": "screen_analyzed", "description": description})
                else:
                    await agent.inject_screen_context(data)

            elif msg_type == "interrupt":
                if allow_interruptions[0]:
                    await agent.interrupt()

            elif msg_type == "end_session":
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"Voice stream error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        response_task.cancel()
        try:
            await response_task
        except asyncio.CancelledError:
            pass

        memories_saved = await agent.end_session()
        agent.last_screen_context = ""

        from datetime import datetime, timezone
        db_session.status = "ended"
        db_session.ended_at = datetime.now(timezone.utc)
        db_session.transcript = json.dumps(agent.session_transcript)
        db_session.total_turns = len(agent.session_transcript)
        await db.flush()

        try:
            await websocket.send_json({"type": "session_ended", "memories_saved": memories_saved})
        except Exception:
            pass

        logger.info(f"Session {session_id} ended.")