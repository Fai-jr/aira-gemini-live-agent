import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from services.gemini_live import GeminiLiveService
from services.memory_service import MemoryService
from models.user import User

logger = logging.getLogger("aira.agent")


class AIRAAgent:
    """
    The central AIRA agent.
    Orchestrates the Gemini Live connection, memory injection,
    and routes tasks to the appropriate sub-agents.
    """

    def __init__(self, user: User, db: AsyncSession):
        self.user = user
        self.db = db
        self.memory_service = MemoryService(db)
        self.gemini_live: Optional[GeminiLiveService] = None
        self.session_transcript: list = []
        self.current_session_id: Optional[str] = None
        self.last_screen_context: str = ""  # tracks latest screen description for goal planner

    async def initialize(self, session_id: str) -> bool:
        """
        Prepare AIRA for a live session.
        Loads user memory and establishes the Gemini Live connection.
        """
        self.current_session_id = session_id

        # Load persistent memory context for this user
        memory_context = await self.memory_service.get_context_for_session(
            user_id=str(self.user.id)
        )
        logger.info(
            f"Loaded memory context for user {self.user.id}: "
            f"{len(memory_context)} characters"
        )

        # Build the Gemini Live service with user context
        self.gemini_live = GeminiLiveService(
            user_name=self.user.full_name.split()[0],
            memory_context=memory_context,
        )

        connected = await self.gemini_live.connect()
        if connected:
            logger.info(f"AIRA agent initialized for user {self.user.id}")
        else:
            logger.error(f"AIRA agent failed to connect for user {self.user.id}")

        return connected

    async def process_audio(self, audio_bytes: bytes) -> None:
        """Send a raw audio chunk from the user mic to Gemini."""
        if not self.gemini_live or not self.gemini_live.is_connected:
            raise RuntimeError("AIRA agent is not connected")
        await self.gemini_live.send_audio_chunk(audio_bytes)

    async def process_text(self, text: str) -> None:
        """Send a text message to AIRA (non-voice input or context injection)."""
        if not self.gemini_live or not self.gemini_live.is_connected:
            raise RuntimeError("AIRA agent is not connected")
        await self.gemini_live.send_text(text)

    async def inject_screen_context(self, description: str) -> None:
        """Tell AIRA what is on the user's screen right now."""
        self.last_screen_context = description  # store for goal planner context
        if not self.gemini_live or not self.gemini_live.is_connected:
            return
        await self.gemini_live.send_screen_context(description)

    def add_to_transcript(self, role: str, content: str) -> None:
        """Record a turn in the session transcript."""
        self.session_transcript.append({"role": role, "content": content})

    def get_transcript_text(self) -> str:
        """Return the full session transcript as a plain text string."""
        lines = []
        for turn in self.session_transcript:
            lines.append(f"{turn['role'].upper()}: {turn['content']}")
        return "\n".join(lines)

    async def end_session(self) -> int:
        """
        End the live session cleanly.
        Extracts and stores memories from the transcript.
        Returns the number of memories saved.
        """
        memories_saved = 0

        transcript_text = self.get_transcript_text()
        if transcript_text and self.current_session_id:
            memories_saved = await self.memory_service.extract_and_store_from_transcript(
                user_id=str(self.user.id),
                transcript=transcript_text,
                session_id=self.current_session_id,
            )

        if self.gemini_live:
            await self.gemini_live.disconnect()

        logger.info(
            f"Session ended for user {self.user.id}. "
            f"Memories saved: {memories_saved}"
        )
        return memories_saved

    async def interrupt(self) -> None:
        """Interrupt AIRA mid-response (user started speaking again)."""
        if self.gemini_live and self.gemini_live.is_connected:
            await self.gemini_live.interrupt()