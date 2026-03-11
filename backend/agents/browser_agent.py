import asyncio
import base64
import logging
import os
import re
import subprocess
from urllib.parse import quote_plus
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

logger = logging.getLogger("aira.browser")

os.environ.setdefault("DISPLAY", ":1")


class BrowserAgent:
    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_running = False
        self._start_lock = asyncio.Lock()

    async def start(self) -> bool:
        try:
            await self._cleanup_dead()
            os.environ["DISPLAY"] = os.environ.get("DISPLAY", ":1")

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                env={"DISPLAY": os.environ.get("DISPLAY", ":1")},
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--start-maximized",
                    "--disable-infobars",
                    "--disable-blink-features=AutomationControlled",
                    "--autoplay-policy=no-user-gesture-required",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--disable-features=site-per-process",
                ],
            )

            self._context = await self._browser.new_context(
                viewport=None,
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="America/New_York",
                permissions=["geolocation"],
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )

            await self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                window.chrome = { runtime: {} };
            """)

            self._page = await self._context.new_page()
            self._is_running = True
            await self._bring_to_front()

            logger.info(f"Browser started on DISPLAY={os.environ.get('DISPLAY')}")
            return True
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            self._is_running = False
            return False

    async def _bring_to_front(self):
        try:
            if self._page:
                await self._page.bring_to_front()
            await asyncio.sleep(0.3)
            for cmd in [
                ["wmctrl", "-a", "Chromium"],
                ["xdotool", "search", "--name", "Chromium", "windowactivate"],
            ]:
                try:
                    subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":1")},
                    )
                except FileNotFoundError:
                    pass
        except Exception as e:
            logger.debug(f"bring_to_front: {e}")

    async def keep_alive(self):
        """Prevent Chrome from throttling or pausing the tab."""
        try:
            if self._page:
                await self._page.bring_to_front()
                await self._page.evaluate("""
                    () => {
                        window.focus();
                        const video = document.querySelector('video');
                        if (video && video.paused) {
                            video.play().catch(() => {});
                        }
                    }
                """)
        except Exception as e:
            logger.debug(f"keep_alive: {e}")

    async def play_youtube(self, query: str) -> dict:
        """Search YouTube and show results — user picks and plays manually."""
        await self._ensure_running()
        try:
            query = query.strip().rstrip('.,!?')
            search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
            logger.info(f"YouTube search results: {search_url}")
            await self._page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
            await self._page.bring_to_front()
            await self._page.wait_for_selector("ytd-video-renderer", timeout=15000)
            title = await self._page.title()
            logger.info(f"Showing results for: {query}")
            return {"success": True, "url": self._page.url, "title": title}
        except Exception as e:
            logger.error(f"play_youtube failed: {e}")
            return {"success": False, "error": str(e)}

    async def _cleanup_dead(self):
        for obj, method in [
            (self._context, "close"),
            (self._browser, "close"),
            (self._playwright, "stop"),
        ]:
            try:
                if obj:
                    await getattr(obj, method)()
            except Exception:
                pass
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._is_running = False

    async def stop(self):
        await self._cleanup_dead()
        logger.info("Browser agent stopped")

    async def _is_page_alive(self) -> bool:
        if not self._page:
            return False
        try:
            await self._page.evaluate("() => true")
            return True
        except Exception:
            return False

    async def _ensure_running(self):
        async with self._start_lock:
            if not await self._is_page_alive():
                logger.info("Browser not alive — restarting...")
                self._is_running = False
                await self.start()
            else:
                await self._bring_to_front()

    @property
    def is_running(self) -> bool:
        return self._is_running and self._page is not None

    async def search_google(self, query: str) -> dict:
        """Navigate directly to Google search results URL — no typing, no redirects."""
        await self._ensure_running()
        try:
            query = query.strip().rstrip('.,!?')
            search_url = f"https://www.google.com/search?q={quote_plus(query)}"
            logger.info(f"Navigating directly to: {search_url}")
            await self._page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
            await self._page.bring_to_front()
            await asyncio.sleep(0.5)
            title = await self._page.title()
            final_url = self._page.url
            logger.info(f"Search landed on: {final_url}")
            return {"success": True, "query": query, "url": final_url, "title": title}
        except Exception as e:
            logger.error(f"search_google failed: {e}")
            return {"success": False, "error": str(e)}

    async def navigate(self, url: str) -> dict:
        await self._ensure_running()
        try:
            if not url.startswith("http"):
                url = f"https://{url}"
            await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await self._page.bring_to_front()
            await asyncio.sleep(0.5)
            title = await self._page.title()
            return {"success": True, "url": self._page.url, "title": title}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click(self, selector: str = None, text: str = None) -> dict:
        await self._ensure_running()
        try:
            if text:
                element = await self._page.wait_for_selector(f"text={text}", timeout=5000)
            elif selector:
                element = await self._page.wait_for_selector(selector, timeout=5000)
            else:
                return {"success": False, "error": "Must provide selector or text"}
            await element.click()
            await asyncio.sleep(0.5)
            return {"success": True, "action": "click", "target": text or selector}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def type_text(self, selector: str, text: str, clear_first: bool = True) -> dict:
        await self._ensure_running()
        try:
            element = await self._page.wait_for_selector(selector, timeout=5000)
            await element.click()
            if clear_first:
                await element.fill("")
            await element.type(text, delay=50)
            return {"success": True, "action": "type", "text": text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def scroll(self, direction: str = "down", amount: int = 400) -> dict:
        await self._ensure_running()
        try:
            delta = amount if direction == "down" else -amount
            await self._page.evaluate(f"window.scrollBy(0, {delta})")
            return {"success": True, "direction": direction}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_page_text(self) -> dict:
        await self._ensure_running()
        try:
            text = await self._page.evaluate("""
                () => {
                    const els = document.querySelectorAll('p,h1,h2,h3,h4,li,td,span');
                    const seen = new Set();
                    const out = [];
                    for (const el of els) {
                        const t = el.innerText?.trim();
                        if (t && t.length > 10 && !seen.has(t)) { seen.add(t); out.push(t); }
                    }
                    return out.slice(0, 100).join('\\n');
                }
            """)
            return {"success": True, "text": text[:3000], "url": self._page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def screenshot(self) -> dict:
        await self._ensure_running()
        try:
            img_bytes = await self._page.screenshot(type="png")
            return {"success": True, "image_base64": base64.b64encode(img_bytes).decode()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_current_url(self) -> str:
        try:
            return self._page.url if self._page else ""
        except Exception:
            return ""

    async def get_page_title(self) -> str:
        try:
            return await self._page.title() if self._page else ""
        except Exception:
            return ""

    async def fill_form_field(self, label_text: str, value: str) -> dict:
        await self._ensure_running()
        try:
            filled = await self._page.evaluate("""
                (labelText, value) => {
                    const label = Array.from(document.querySelectorAll('label'))
                        .find(l => l.textContent.toLowerCase().includes(labelText.toLowerCase()));
                    if (label) {
                        const input = label.control || document.getElementById(label.htmlFor)
                            || label.querySelector('input,textarea,select');
                        if (input) {
                            input.value = value;
                            input.dispatchEvent(new Event('input', {bubbles:true}));
                            input.dispatchEvent(new Event('change', {bubbles:true}));
                            return true;
                        }
                    }
                    return false;
                }
            """, label_text, value)
            if filled:
                return {"success": True, "field": label_text, "value": value}
            return {"success": False, "error": f"Field '{label_text}' not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def youtube_search(self, query: str) -> dict:
        await self._ensure_running()
        try:
            query = query.strip().rstrip('.,!?')
            url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
            await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await self._page.bring_to_front()
            await asyncio.sleep(1)
            return {"success": True, "query": query, "url": self._page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def google_maps_search(self, location: str) -> dict:
        await self._ensure_running()
        try:
            url = f"https://www.google.com/maps/search/{quote_plus(location)}"
            await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await self._page.bring_to_front()
            await asyncio.sleep(2)
            return {"success": True, "location": location, "url": self._page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def execute_step(self, step: dict) -> dict:
        await self._ensure_running()
        step_type = step.get("type", "general")
        action = step.get("action", "").lower()
        details = step.get("details", "")

        try:
            if step_type == "browser" or any(w in action for w in ["open", "navigate", "go to"]):
                url = details if details.startswith("http") else f"https://{details}" if details else "https://google.com"
                return await self.navigate(url)
            elif step_type == "search" or "search" in action:
                query = details or action.replace("search for", "").replace("search", "").strip()
                if "youtube" in action or "youtube" in details:
                    return await self.youtube_search(query)
                elif "maps" in action or "maps" in details:
                    return await self.google_maps_search(query)
                else:
                    return await self.search_google(query)
            elif step_type == "form_fill" or any(w in action for w in ["fill", "type", "enter"]):
                if details:
                    parts = details.split(":", 1)
                    if len(parts) == 2:
                        return await self.fill_form_field(parts[0].strip(), parts[1].strip())
                return {"success": True, "skipped": True}
            elif any(w in action for w in ["click", "select", "press"]):
                target = details or action.replace("click", "").replace("select", "").strip()
                return await self.click(text=target)
            elif "scroll" in action:
                return await self.scroll("down" if "down" in action else "up")
            elif step_type == "vision" or "screenshot" in action:
                return await self.screenshot()
            else:
                return {"success": True, "action": action, "note": "Step acknowledged"}
        except Exception as e:
            logger.error(f"Step execution error: {e}")
            return {"success": False, "error": str(e)}