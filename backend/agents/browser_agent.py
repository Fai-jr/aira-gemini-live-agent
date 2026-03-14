import asyncio
import base64
import logging
import os
import subprocess
from urllib.parse import quote_plus
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

logger = logging.getLogger("aira.browser")

os.environ.setdefault("DISPLAY", ":1")

CHROME_BIN     = "/usr/bin/google-chrome"
CHROME_PROFILE = os.path.expanduser("~/.config/google-chrome-aira")


class BrowserAgent:

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser:    Optional[Browser] = None
        self._context:    Optional[BrowserContext] = None
        self._page:       Optional[Page] = None
        self._is_running  = False
        self._start_lock  = asyncio.Lock()

    # ------------------------------------------------------------------ #
    #  INTERNAL HELPERS                                                    #
    # ------------------------------------------------------------------ #

    def _find_executable(self) -> str:
        for path in [CHROME_BIN, "/usr/bin/google-chrome-stable"]:
            if os.path.exists(path):
                return path
        raise FileNotFoundError("Google Chrome not found")

    async def _activate_audio(self):
        """Simulate real user gesture to unlock autoplay."""
        try:
            if self._page:
                await self._page.mouse.click(640, 400)
                await asyncio.sleep(0.3)
        except Exception:
            pass

    async def _is_page_alive(self) -> bool:
        if not self._page:
            return False
        try:
            await self._page.evaluate("() => true")
            return True
        except Exception:
            return False

    async def _bring_to_front(self):
        try:
            if self._page:
                await self._page.bring_to_front()
            await asyncio.sleep(0.3)
            for cmd in [
                ["wmctrl", "-a", "Chrome"],
                ["xdotool", "search", "--name", "Chrome", "windowactivate"],
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
        except Exception:
            pass

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
        self._browser    = None
        self._context    = None
        self._page       = None
        self._is_running = False

    async def _get_page(self) -> Page:
        async with self._start_lock:
            if not await self._is_page_alive():
                logger.info("Page not alive — (re)starting browser...")
                await self._cleanup_dead()
                await self._start_internal()
            return self._page

    async def _ensure_profile(self):
        """Copy real Chrome profile if the AIRA copy doesn't exist yet."""
        real = os.path.expanduser("~/.config/google-chrome")
        if not os.path.exists(CHROME_PROFILE):
            if os.path.exists(real):
                logger.info(f"Copying Chrome profile to {CHROME_PROFILE} ...")
                subprocess.run(["cp", "-r", real, CHROME_PROFILE],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logger.info("Profile copy done")
            else:
                os.makedirs(CHROME_PROFILE, exist_ok=True)

    async def _start_internal(self, browser: str = "chrome"):
        os.environ["DISPLAY"] = os.environ.get("DISPLAY", ":1")
        await self._ensure_profile()

        subprocess.run(["pkill", "-f", "google-chrome"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await asyncio.sleep(2)

        self._playwright = await async_playwright().start()
        executable = self._find_executable()

        args = [
            "--disable-dev-shm-usage",
            "--start-maximized",
            "--disable-infobars",
            "--disable-blink-features=AutomationControlled",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=site-per-process",
            "--enable-audio",
            "--allow-running-insecure-content",
            "--use-fake-ui-for-media-stream",
            "--disable-web-security",
        ]

        env = {
            "DISPLAY":                  os.environ.get("DISPLAY", ":1"),
            "XDG_RUNTIME_DIR":          os.environ.get("XDG_RUNTIME_DIR",
                                            f"/run/user/{os.getuid()}"),
            "HOME":                     os.path.expanduser("~"),
            "USER":                     os.environ.get("USER", ""),
            "DBUS_SESSION_BUS_ADDRESS": os.environ.get("DBUS_SESSION_BUS_ADDRESS", ""),
        }

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE,
            executable_path=executable,
            headless=False,
            args=args,
            env=env,
            viewport=None,
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation", "microphone", "camera"],
            ignore_default_args=["--enable-automation"],
        )

        self._browser = self._context.browser

        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
            window.chrome = { runtime: {} };
        """)

        await asyncio.sleep(1)

        pages = self._context.pages
        if pages:
            self._page = pages[0]
            for extra in pages[1:]:
                try:
                    await extra.close()
                except Exception:
                    pass
        else:
            self._page = await self._context.new_page()

        self._is_running = True
        await self._bring_to_front()
        logger.info(f"Chrome started | profile={CHROME_PROFILE}")

    # ------------------------------------------------------------------ #
    #  PUBLIC API                                                          #
    # ------------------------------------------------------------------ #

    async def start(self, browser: str = "chrome") -> bool:
        try:
            async with self._start_lock:
                if await self._is_page_alive():
                    return True
                await self._cleanup_dead()
                await self._start_internal(browser)
            return True
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            self._is_running = False
            return False

    async def stop(self):
        await self._cleanup_dead()
        logger.info("Browser agent stopped")

    @property
    def is_running(self) -> bool:
        return self._is_running and self._page is not None

    async def keep_alive(self):
        try:
            page = await self._get_page()
            await page.bring_to_front()
            await page.evaluate("() => { window.focus(); }")
        except Exception as e:
            logger.debug(f"keep_alive: {e}")

    # ------------------------------------------------------------------ #
    #  NAVIGATION                                                          #
    # ------------------------------------------------------------------ #

    async def navigate(self, url: str) -> dict:
        page = await self._get_page()
        try:
            if not url.startswith("http"):
                url = f"https://{url}"
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            await page.bring_to_front()
            await asyncio.sleep(1)
            await self._activate_audio()
            title = await page.title()
            return {"success": True, "url": page.url, "title": title}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def search_google(self, query: str) -> dict:
        page = await self._get_page()
        try:
            query = query.strip().rstrip('.,!?')
            url = f"https://www.google.com/search?q={quote_plus(query)}"
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.bring_to_front()
            title = await page.title()
            return {"success": True, "query": query, "url": page.url, "title": title}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def youtube_search(self, query: str) -> dict:
        """Search YouTube and auto-click first result so it plays with audio."""
        query = query.strip().rstrip('.,!?')
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        logger.info(f"YouTube search → {url}")
        page = await self._get_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            await page.bring_to_front()
            await asyncio.sleep(2)

            first = await page.query_selector("ytd-video-renderer a#video-title")
            if first:
                await first.click()
                await asyncio.sleep(3)
                await self._activate_audio()
                logger.info("Clicked first YouTube result + activated audio")
            else:
                logger.warning("No video result found — showing results page")

            title = await page.title()
            return {"success": True, "query": query, "url": page.url, "title": title}
        except Exception as e:
            logger.error(f"youtube_search failed: {e}")
            self._page = None
            return {"success": False, "error": str(e)}

    async def play_youtube(self, query: str) -> dict:
        """Alias — plays first YouTube result."""
        return await self.youtube_search(query)

    async def spotify_search(self, query: str) -> dict:
        """Search Spotify and auto-click first track result."""
        query = query.strip().rstrip('.,!?')
        url = f"https://open.spotify.com/search/{quote_plus(query)}"
        logger.info(f"Spotify search → {url}")
        page = await self._get_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            await page.bring_to_front()
            await asyncio.sleep(3)

            # Wait for search results to load fully
            await asyncio.sleep(2)

            played = False
            try:
                # Find all track rows in the search results (not liked songs)
                # Spotify search results show tracks under a "Songs" section
                rows = await page.query_selector_all("div[data-testid='tracklist-row']")
                logger.info(f"Spotify: found {len(rows)} track rows")

                if rows:
                    # Click the first row to select it, then double-click to play
                    await rows[0].click()
                    await asyncio.sleep(0.3)
                    await rows[0].dblclick()
                    await asyncio.sleep(1)
                    played = True
                    logger.info("Spotify: double-clicked first search result track")
            except Exception as e:
                logger.warning(f"Spotify row click failed: {e}")

            if not played:
                try:
                    # Fallback: click the play button in the top bar if visible
                    btn = await page.query_selector("button[data-testid='play-button']")
                    if btn:
                        await btn.click()
                        played = True
                        logger.info("Spotify: clicked play-button fallback")
                except Exception:
                    pass

            title = await page.title()
            return {"success": True, "query": query, "url": page.url, "title": title}
        except Exception as e:
            logger.error(f"spotify_search failed: {e}")
            self._page = None
            return {"success": False, "error": str(e)}

    async def apple_music_search(self, query: str) -> dict:
        """Search Apple Music and auto-click first track result."""
        query = query.strip().rstrip('.,!?')
        url = f"https://music.apple.com/us/search?term={quote_plus(query)}"
        logger.info(f"Apple Music search → {url}")
        page = await self._get_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            await page.bring_to_front()
            await asyncio.sleep(3)

            played = False
            selectors = [
                "button.product-lockup__play-button",
                "button[aria-label='Play']",
                ".track-lockup__play-button",
                "li.songs-list-row button",
            ]
            for sel in selectors:
                try:
                    el = await page.wait_for_selector(sel, timeout=3000)
                    if el:
                        await el.click()
                        await asyncio.sleep(1)
                        played = True
                        logger.info(f"Apple Music auto-clicked: {sel}")
                        break
                except Exception:
                    continue

            title = await page.title()
            return {"success": True, "query": query, "url": page.url, "title": title}
        except Exception as e:
            logger.error(f"apple_music_search failed: {e}")
            self._page = None
            return {"success": False, "error": str(e)}

    async def google_maps_search(self, location: str) -> dict:
        page = await self._get_page()
        try:
            url = f"https://www.google.com/maps/search/{quote_plus(location)}"
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.bring_to_front()
            await asyncio.sleep(2)
            return {"success": True, "location": location, "url": page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click(self, selector: str = None, text: str = None) -> dict:
        page = await self._get_page()
        try:
            if text:
                element = await page.wait_for_selector(f"text={text}", timeout=5000)
            elif selector:
                element = await page.wait_for_selector(selector, timeout=5000)
            else:
                return {"success": False, "error": "Must provide selector or text"}
            await element.click()
            await asyncio.sleep(0.5)
            return {"success": True, "action": "click", "target": text or selector}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def type_text(self, selector: str, text: str, clear_first: bool = True) -> dict:
        page = await self._get_page()
        try:
            element = await page.wait_for_selector(selector, timeout=5000)
            await element.click()
            if clear_first:
                await element.fill("")
            await element.type(text, delay=50)
            return {"success": True, "action": "type", "text": text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def scroll(self, direction: str = "down", amount: int = 400) -> dict:
        page = await self._get_page()
        try:
            delta = amount if direction == "down" else -amount
            await page.evaluate(f"window.scrollBy(0, {delta})")
            return {"success": True, "direction": direction}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_page_text(self) -> dict:
        page = await self._get_page()
        try:
            text = await page.evaluate("""
                () => {
                    const els = document.querySelectorAll('p,h1,h2,h3,h4,li,td,span');
                    const seen = new Set();
                    const out = [];
                    for (const el of els) {
                        const t = el.innerText?.trim();
                        if (t && t.length > 10 && !seen.has(t)) {
                            seen.add(t); out.push(t);
                        }
                    }
                    return out.slice(0, 100).join('\\n');
                }
            """)
            return {"success": True, "text": text[:3000], "url": page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def screenshot(self) -> dict:
        page = await self._get_page()
        try:
            img_bytes = await page.screenshot(type="png")
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
        page = await self._get_page()
        try:
            filled = await page.evaluate("""
                (labelText, value) => {
                    const label = Array.from(document.querySelectorAll('label'))
                        .find(l => l.textContent.toLowerCase()
                        .includes(labelText.toLowerCase()));
                    if (label) {
                        const input = label.control
                            || document.getElementById(label.htmlFor)
                            || label.querySelector('input,textarea,select');
                        if (input) {
                            input.value = value;
                            input.dispatchEvent(new Event('input',  {bubbles:true}));
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

    async def execute_step(self, step: dict) -> dict:
        step_type = step.get("type", "general")
        action    = step.get("action", "").lower()
        details   = step.get("details", "")
        try:
            if step_type == "browser" or any(w in action for w in ["open", "navigate", "go to"]):
                url = (details if details.startswith("http")
                       else f"https://{details}" if details else "https://google.com")
                return await self.navigate(url)
            elif step_type == "search" or "search" in action:
                query = details or action.replace("search for", "").replace("search", "").strip()
                if "youtube" in action or "youtube" in details.lower():
                    return await self.youtube_search(query)
                elif "spotify" in action or "spotify" in details.lower():
                    return await self.spotify_search(query)
                elif "apple music" in action or "apple music" in details.lower():
                    return await self.apple_music_search(query)
                elif "maps" in action or "maps" in details.lower():
                    return await self.google_maps_search(query)
                else:
                    return await self.search_google(query)
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

    async def _ensure_running(self):
        await self._get_page()