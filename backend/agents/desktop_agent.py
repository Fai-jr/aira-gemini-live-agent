"""
desktop_agent.py
Launches desktop applications (hardcoded + dynamic discovery) and handles music.
"""
import asyncio
import glob
import logging
import os
import re
import shutil
import subprocess
from urllib.parse import quote_plus
from typing import Optional

logger = logging.getLogger("aira.desktop")

APP_LAUNCH_MAP = {
    "vscode":             ["code"],
    "vs code":            ["code"],
    "visual studio code": ["code"],
    "code":               ["code"],
    "eclipse":            ["eclipse"],
    "notepad++":          ["notepad-plus-plus"],
    "notepad":            ["notepad-plus-plus"],
    "firefox":            ["firefox"],
    "edge":               ["flatpak", "run", "com.microsoft.Edge"],
    "microsoft edge":     ["flatpak", "run", "com.microsoft.Edge"],
    "libreoffice writer": ["libreoffice", "--writer"],
    "libreoffice calc":   ["libreoffice", "--calc"],
    "libreoffice impress":["libreoffice", "--impress"],
    "libreoffice draw":   ["libreoffice", "--draw"],
    "libreoffice":        ["libreoffice"],
    "writer":             ["libreoffice", "--writer"],
    "calc":               ["libreoffice", "--calc"],
    "spreadsheet":        ["libreoffice", "--calc"],
    "impress":            ["libreoffice", "--impress"],
    "presentation":       ["libreoffice", "--impress"],
    "draw":               ["libreoffice", "--draw"],
    "obs studio":         ["obs"],
    "obs":                ["obs"],
    "file manager":       ["nautilus"],
    "files":              ["nautilus"],
    "nautilus":           ["nautilus"],
    "terminal":           ["gnome-terminal"],
    "console":            ["gnome-terminal"],
    "system settings":    ["gnome-control-center"],
    "settings":           ["gnome-control-center"],
    "text editor":        ["gedit"],
    "gedit":              ["gedit"],
}

MUSIC_PLATFORMS = {
    "youtube music": "https://music.youtube.com/search?q={query}",
    "youtube":       "https://www.youtube.com/results?search_query={query}",
    "spotify":       "https://open.spotify.com/search/{query}",
}

_STOP_WORDS = {
    "open", "launch", "start", "run", "please", "aira", "can", "you",
    "the", "a", "an", "me", "my", "for", "and", "or", "it", "this",
    "that", "app", "application", "program", "software", "window",
    "file", "folder", "document", "browser",
}


def _scan_desktop_files() -> dict:
    """Scan all .desktop files and return {name_lower: [exec_cmd, ...]}"""
    discovered: dict[str, list[str]] = {}
    search_dirs = [
        "/usr/share/applications",
        "/usr/local/share/applications",
        os.path.expanduser("~/.local/share/applications"),
        "/var/lib/flatpak/exports/share/applications",
        "/var/lib/snapd/desktop/applications",
    ]
    for d in search_dirs:
        for path in glob.glob(f"{d}/*.desktop"):
            name, exec_cmd, nodisplay = None, None, False
            try:
                with open(path, encoding="utf-8", errors="ignore") as f:
                    in_entry = False
                    for line in f:
                        line = line.strip()
                        if line == "[Desktop Entry]":
                            in_entry = True
                        elif line.startswith("[") and line != "[Desktop Entry]":
                            in_entry = False
                        if not in_entry:
                            continue
                        if line.startswith("Name=") and not name:
                            name = line[5:].strip()
                        elif line.startswith("Exec=") and not exec_cmd:
                            exec_cmd = line[5:].strip()
                        elif line.lower() == "nodisplay=true":
                            nodisplay = True
            except Exception:
                continue
            if not name or not exec_cmd or nodisplay:
                continue
            clean = re.sub(r"%[fFuUdDnNickvm]", "", exec_cmd).strip()
            clean = re.sub(r"^env\s+\S+=\S+\s+", "", clean)
            parts = clean.split()
            if not parts:
                continue
            key = name.lower().strip()
            if key and key not in _STOP_WORDS:
                discovered[key] = parts
    logger.info(f"Dynamic app discovery: {len(discovered)} apps found")
    return discovered


class DesktopAgent:
    """Launches local desktop apps (hardcoded + dynamic) and opens music in browser."""

    def __init__(self):
        self._display = os.environ.get("DISPLAY", ":1")
        self._dynamic: dict[str, list[str]] = _scan_desktop_files()

    def _run(self, cmd: list[str]) -> bool:
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env={**os.environ, "DISPLAY": self._display},
                start_new_session=True,
            )
            logger.info(f"Launched: {' '.join(cmd)}")
            return True
        except FileNotFoundError:
            logger.warning(f"Command not found: {cmd[0]}")
            return False
        except Exception as e:
            logger.error(f"Launch failed for {cmd}: {e}")
            return False

    def detect_app(self, text: str) -> Optional[str]:
        t = text.lower().strip()
        for key in sorted(APP_LAUNCH_MAP.keys(), key=len, reverse=True):
            if key in t:
                return key
        for key in sorted(self._dynamic.keys(), key=len, reverse=True):
            if len(key) < 3:
                continue
            if key in t:
                return f"__dynamic__{key}"
        words = [w.strip(".,!?") for w in t.split() if w not in _STOP_WORDS and len(w) > 2]
        for word in words:
            if shutil.which(word):
                return f"__binary__{word}"
        return None

    def detect_music_platform(self, text: str) -> Optional[str]:
        t = text.lower()
        for platform in sorted(MUSIC_PLATFORMS.keys(), key=len, reverse=True):
            if platform in t:
                return platform
        return None

    async def launch_app(self, app_key: str) -> dict:
        if not app_key:
            return {"success": False, "error": "No app key provided"}
        if app_key.startswith("__dynamic__"):
            name = app_key[len("__dynamic__"):]
            cmd = self._dynamic.get(name)
            display_name = name
        elif app_key.startswith("__binary__"):
            name = app_key[len("__binary__"):]
            cmd = [name]
            display_name = name
        else:
            cmd = APP_LAUNCH_MAP.get(app_key)
            display_name = app_key
        if not cmd:
            return {"success": False, "error": f"No launch command for '{display_name}'"}
        success = self._run(cmd)
        return {"success": success, "app": display_name, "action": "launched" if success else "failed"}

    def get_music_url(self, platform: str, query: str) -> str:
        template = MUSIC_PLATFORMS.get(platform, MUSIC_PLATFORMS["youtube"])
        return template.format(query=quote_plus(query.strip().rstrip(".,!?")))

    async def open_music(self, platform: str, query: str, browser_agent) -> dict:
        url = self.get_music_url(platform, query)
        logger.info(f"Opening music: platform={platform} query={query} url={url}")
        try:
            if not browser_agent.is_running:
                await browser_agent.start()
            result = await browser_agent.navigate(url)
            if not result.get("success"):
                return {**result, "platform": platform, "query": query}
            page = browser_agent._page
            selectors = {
                "youtube":       "ytd-video-renderer #video-title",
                "youtube music": "ytmusic-responsive-list-item-renderer",
                "spotify":       "[data-testid='tracklist-row']",
            }
            sel = selectors.get(platform, "ytd-video-renderer #video-title")
            try:
                await page.wait_for_selector(sel, timeout=8000)
                await page.click(sel)
                logger.info(f"Clicked first result on {platform}")
            except Exception as ce:
                logger.warning(f"Could not click first result: {ce}")
            return {**result, "platform": platform, "query": query}
        except Exception as e:
            logger.error(f"Music open failed: {e}")
            return {"success": False, "error": str(e)}