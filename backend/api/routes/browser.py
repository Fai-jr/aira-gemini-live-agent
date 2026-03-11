import logging
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from api.deps import get_current_active_user
from models.user import User
from agents.browser_agent import BrowserAgent

logger = logging.getLogger("aira.browser_routes")

router = APIRouter(prefix="/browser", tags=["Browser"])

# Module-level singleton — guaranteed same instance everywhere
_browser_agent: BrowserAgent = BrowserAgent()


def get_browser_agent() -> BrowserAgent:
    return _browser_agent


class NavigateRequest(BaseModel):
    url: str

class SearchRequest(BaseModel):
    query: str
    engine: str = "google"

class ClickRequest(BaseModel):
    selector: Optional[str] = None
    text: Optional[str] = None

class TypeRequest(BaseModel):
    selector: str
    text: str
    clear_first: bool = True

class ScrollRequest(BaseModel):
    direction: str = "down"
    amount: int = 400

class FillFieldRequest(BaseModel):
    label: str
    value: str

class ExecuteStepRequest(BaseModel):
    step: dict


@router.post("/start")
async def start_browser(current_user: User = Depends(get_current_active_user)):
    if _browser_agent.is_running:
        return {"status": "already_running"}
    success = await _browser_agent.start()
    return {"status": "started" if success else "failed"}

@router.post("/stop")
async def stop_browser(current_user: User = Depends(get_current_active_user)):
    await _browser_agent.stop()
    return {"status": "stopped"}

@router.get("/status")
async def browser_status(current_user: User = Depends(get_current_active_user)):
    url = await _browser_agent.get_current_url() if _browser_agent.is_running else ""
    title = await _browser_agent.get_page_title() if _browser_agent.is_running else ""
    return {"is_running": _browser_agent.is_running, "current_url": url, "page_title": title}

@router.post("/navigate")
async def navigate(payload: NavigateRequest, current_user: User = Depends(get_current_active_user)):
    return await _browser_agent.navigate(payload.url)

@router.post("/search")
async def search(payload: SearchRequest, current_user: User = Depends(get_current_active_user)):
    if payload.engine == "youtube":
        return await _browser_agent.youtube_search(payload.query)
    elif payload.engine == "maps":
        return await _browser_agent.google_maps_search(payload.query)
    else:
        return await _browser_agent.search_google(payload.query)

@router.post("/click")
async def click(payload: ClickRequest, current_user: User = Depends(get_current_active_user)):
    return await _browser_agent.click(selector=payload.selector, text=payload.text)

@router.post("/type")
async def type_text(payload: TypeRequest, current_user: User = Depends(get_current_active_user)):
    return await _browser_agent.type_text(payload.selector, payload.text, payload.clear_first)

@router.post("/scroll")
async def scroll(payload: ScrollRequest, current_user: User = Depends(get_current_active_user)):
    return await _browser_agent.scroll(payload.direction, payload.amount)

@router.post("/fill-field")
async def fill_field(payload: FillFieldRequest, current_user: User = Depends(get_current_active_user)):
    return await _browser_agent.fill_form_field(payload.label, payload.value)

@router.post("/screenshot")
async def screenshot(current_user: User = Depends(get_current_active_user)):
    return await _browser_agent.screenshot()

@router.get("/page-text")
async def page_text(current_user: User = Depends(get_current_active_user)):
    return await _browser_agent.get_page_text()

@router.post("/execute-step")
async def execute_step(payload: ExecuteStepRequest, current_user: User = Depends(get_current_active_user)):
    return await _browser_agent.execute_step(payload.step)
