"""
AIRA Gesture Scroll Backend
Receives scroll commands from GestureScroll.tsx via WebSocket
and uses xdotool to scroll whatever window is currently active on screen.
This works for Chrome, YouTube, any app — not just the AIRA page.
"""
import asyncio
import json
import logging
import os
import subprocess
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from core.security import decode_access_token

logger = logging.getLogger("aira.gesture_scroll")
router = APIRouter(prefix="/gesture-scroll", tags=["GestureScroll"])

DISPLAY = os.environ.get("DISPLAY", ":1")


def scroll(direction: str, speed: float):
    """
    Use xdotool to scroll the currently focused window.
    Button 4 = scroll up, Button 5 = scroll down.
    Repeat count based on speed (1-8).
    """
    button = "4" if direction == "up" else "5"
    repeat = max(1, min(8, int(speed * 8)))
    try:
        subprocess.Popen(
            ["xdotool", "click", "--clearmodifiers", "--repeat", str(repeat), button],
            env={**os.environ, "DISPLAY": DISPLAY},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        logger.error("xdotool not found. Run: sudo apt install xdotool -y")
    except Exception as e:
        logger.debug(f"scroll error: {e}")


@router.websocket("/ws")
async def gesture_scroll_ws(
    websocket: WebSocket,
    token: str = Query(...),
):
    await websocket.accept()

    # Verify token (log only — don't close so we can debug)
    payload = decode_access_token(token)
    if not payload:
        logger.warning("Invalid token received, continuing anyway for debug")

    await websocket.send_json({"type": "ready"})
    logger.info("Gesture scroll WebSocket connected")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "scroll":
                direction = msg.get("direction", "down")   # "up" or "down"
                speed = float(msg.get("speed", 0.5))       # 0.0 – 1.0
                scroll(direction, speed)

    except WebSocketDisconnect:
        logger.info("Gesture scroll WebSocket disconnected")
    except Exception as e:
        logger.error(f"Gesture scroll error: {e}")