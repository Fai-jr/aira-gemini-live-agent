import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text, ForeignKey, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Session metadata
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
    )  # active | ended | error

    session_type: Mapped[str] = mapped_column(
        String(30),
        default="voice",
        nullable=False,
    )  # voice | vision | goal | computer_use

    # Transcript stored as JSON string (array of message objects)
    transcript: Mapped[str] = mapped_column(Text, default="[]", nullable=False)

    # Goal/task context
    current_goal: Mapped[str] = mapped_column(Text, nullable=True)
    goal_steps: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON

    # Screen context
    last_screenshot_description: Mapped[str] = mapped_column(Text, nullable=True)

    # Metrics
    total_turns: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    audio_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Did the session use vision/computer-use
    used_vision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used_computer_use: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    ended_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<Session id={self.id} user_id={self.user_id} status={self.status}>"