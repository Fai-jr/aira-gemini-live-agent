import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from datetime import datetime, timezone

from models.memory import Memory
from models.user import User

logger = logging.getLogger("aira.memory_service")


class MemoryService:
    """
    Handles all persistent memory operations for AIRA.
    Memory is what makes AIRA feel like she truly knows the user.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_context_for_session(self, user_id: str, limit: int = 20) -> str:
        """
        Retrieve the most relevant memories for a user and format them
        as a context string to inject into AIRA's system prompt.
        This is what gives AIRA her persistent memory across sessions.
        """
        try:
            result = await self.db.execute(
                select(Memory)
                .where(
                    and_(
                        Memory.user_id == user_id,
                        Memory.is_deleted == False,  # noqa: E712
                    )
                )
                .order_by(
                    Memory.is_pinned.desc(),
                    Memory.relevance_score.desc(),
                    Memory.updated_at.desc(),
                )
                .limit(limit)
            )
            memories = result.scalars().all()

            if not memories:
                return ""

            lines = []
            for m in memories:
                if m.key:
                    lines.append(f"- [{m.memory_type}] {m.key}: {m.content}")
                else:
                    lines.append(f"- [{m.memory_type}] {m.content}")

            # Update last accessed timestamps
            for m in memories:
                m.last_accessed_at = datetime.now(timezone.utc)
            await self.db.flush()

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to retrieve memory context: {e}")
            return ""

    async def store_memory(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        key: Optional[str] = None,
        source_session_id: Optional[str] = None,
        relevance_score: float = 1.0,
    ) -> Optional[Memory]:
        """
        Store a new memory for the user.
        Called during and after sessions when AIRA learns something new.
        """
        try:
            # If a key is provided, update existing memory with same key
            if key:
                result = await self.db.execute(
                    select(Memory).where(
                        and_(
                            Memory.user_id == user_id,
                            Memory.key == key,
                            Memory.is_deleted == False,  # noqa: E712
                        )
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    existing.content = content
                    existing.relevance_score = relevance_score
                    existing.updated_at = datetime.now(timezone.utc)
                    await self.db.flush()
                    logger.info(f"Updated memory key='{key}' for user {user_id}")
                    return existing

            memory = Memory(
                user_id=user_id,
                memory_type=memory_type,
                content=content,
                key=key,
                source_session_id=source_session_id,
                relevance_score=relevance_score,
            )
            self.db.add(memory)
            await self.db.flush()
            logger.info(f"Stored new memory type='{memory_type}' for user {user_id}")
            return memory

        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return None

    async def extract_and_store_from_transcript(
        self,
        user_id: str,
        transcript: str,
        session_id: Optional[str] = None,
    ) -> int:
        """
        After a session ends, analyze the transcript and automatically
        extract useful memories (preferences, facts, corrections).
        Returns the number of memories stored.
        """
        import google.generativeai as genai
        from core.config import settings
        import json

        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_VISION_MODEL)

        prompt = (
            "Analyze this conversation transcript between a user and an AI assistant named AIRA. "
            "Extract important facts, preferences, corrections, and habits the user revealed. "
            "Return a JSON array of memory objects. Each object must have: "
            '{"type": "preference|fact|habit|correction", "key": "short_snake_case_key", '
            '"content": "clear description of what to remember"}. '
            "Only include genuinely useful persistent information. "
            "Do NOT save anything about screen contents, screenshots, or what was visible on screen. "
            "Do NOT save temporary visual context from screen sharing sessions. "
            "Do NOT save greetings, small talk, or one-time session context. "
            "Return only valid JSON, no explanation.\n\n"
            f"Transcript:\n{transcript}"
        )

        try:
            response = model.generate_content(prompt)
            raw = response.text.strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            memories_data = json.loads(raw)
            count = 0

            for item in memories_data:
                memory_type = item.get("type", "fact")
                key = item.get("key")
                content = item.get("content", "")

                if content:
                    await self.store_memory(
                        user_id=user_id,
                        memory_type=memory_type,
                        content=content,
                        key=key,
                        source_session_id=session_id,
                    )
                    count += 1

            logger.info(f"Extracted {count} memories from transcript for user {user_id}")
            return count

        except Exception as e:
            logger.error(f"Memory extraction from transcript failed: {e}")
            return 0