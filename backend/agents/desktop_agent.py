"""
desktop_agent.py
Launches desktop applications and handles music playback via browser.
Place in: backend/agents/desktop_agent.py
"""
import asyncio
import logging
import os
import subprocess
from urllib.parse import quote_plus
from typing import Optional

logger = logging.getLogger("aira.desktop")

# Map of app names → how to launch them
# Keys are lowercase keywords AIRA might say
APP_LAUNCH_MAP = {
    # Editors / IDEs
    "vscode":       ["code"],
    "vs code":      ["code"],
    "visual studio code": ["code"],
    "code":         ["code"],
    "eclipse":      ["eclipse"],
    "notepad":      ["notepad-plus-plus"],
    "notepad++":    ["notepad-plus-plus"],

    # Browsers
    "firefox":      ["firefox"],
    "edge":         ["flatpak", "run", "com.microsoft.Edge"],
    "microsoft edge": ["flatpak", "run", "com.microsoft.Edge"],
    "chrome":       None,  # handled by browser_agent

    # Office
    "libreoffice":  ["libreoffice"],
    "writer":       ["libreoffice", "--writer"],
    "libreoffice writer": ["libreoffice", "--writer"],
    "calc":         ["libreoffice", "--calc"],
    "libreoffice calc": ["libreoffice", "--calc"],
    "spreadsheet":  ["libreoffice", "--calc"],
    "impress":      ["libreoffice", "--impress"],
    "libreoffice impress": ["libreoffice", "--impress"],
    "presentation": ["libreoffice", "--impress"],
    "draw":         ["libreoffice", "--draw"],

    # Media / Streaming
    "obs":          ["obs"],
    "obs studio":   ["obs"],

    # File manager
    "files":        ["nautilus"],
    "file manager": ["nautilus"],
    "nautilus":     ["nautilus"],

    # Terminal
    "terminal":     ["gnome-terminal"],
    "console":      ["gnome-terminal"],

    # Settings
    "settings":     ["gnome-control-center"],
    "system settings": ["gnome-control-center"],

    # Text editor
    "text editor":  ["gedit"],
    "gedit":        ["gedit"],
}

# Music platform keywords → search URL template
MUSIC_PLATFORMS = {
    "youtube music": "https://music.youtube.com/search?q={query}",
    "youtube":       "https://www.youtube.com/results?search_query={query}",
    "spotify":       "https://open.spotify.com/search/{query}",
}


class DesktopAgent:
    """Launches local desktop apps and opens music platforms in the browser."""

    def __init__(self):
        self._display = os.environ.get("DISPLAY", ":1")

    def _run(self, cmd: list[str]) -> bool:
        """Launch a process detached from the backend."""
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
        """
        Given AIRA's response or the user's command text,
        return the matched app key or None.
        """
        text_lower = text.lower()
        # Longest match first to avoid "code" matching "vs code"
        for key in sorted(APP_LAUNCH_MAP.keys(), key=len, reverse=True):
            if key in text_lower:
                return key
        return None

    def detect_music_platform(self, text: str) -> Optional[str]:
        """Return the music platform key found in text, or None."""
        text_lower = text.lower()
        for platform in sorted(MUSIC_PLATFORMS.keys(), key=len, reverse=True):
            if platform in text_lower:
                return platform
        return None

    async def launch_app(self, app_key: str) -> dict:
        """Launch a desktop app by its key."""
        cmd = APP_LAUNCH_MAP.get(app_key)
        if cmd is None:
            return {"success": False, "error": f"No launch command for '{app_key}'"}
        success = self._run(cmd)
        return {
            "success": success,
            "app": app_key,
            "action": "launched" if success else "failed",
        }

    def get_music_url(self, platform: str, query: str) -> str:
        """Build the search URL for a music platform."""
        template = MUSIC_PLATFORMS.get(platform, MUSIC_PLATFORMS["youtube"])
        return template.format(query=quote_plus(query.strip().rstrip(".,!?")))

    async def open_music(self, platform: str, query: str, browser_agent) -> dict:
        """
        Open a music search on the given platform using the shared browser.
        Falls back to YouTube if platform not found.
        """
        url = self.get_music_url(platform, query)
        logger.info(f"Opening music: platform={platform} query={query} url={url}")
        try:
            if not browser_agent.is_running:
                await browser_agent.start()
            result = await browser_agent.navigate(url)
            return {**result, "platform": platform, "query": query}
        except Exception as e:
            logger.error(f"Music open failed: {e}")
            return {"success": False, "error": str(e)}