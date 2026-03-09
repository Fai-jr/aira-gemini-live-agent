import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text, ForeignKey, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class Task(Base):
    __tablename__ = "tasks"

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

    # Parent task (for sub-tasks)
    parent_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Task content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Goal this task belongs to (high-level intent)
    goal: Mapped[str] = mapped_column(Text, nullable=True)

    # Status of task
    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
        index=True,
    )
    # Status values: pending | in_progress | completed | failed | skipped | cancelled

    # Task type determines which agent handles it
    task_type: Mapped[str] = mapped_column(
        String(50),
        default="general",
        nullable=False,
    )
    # Types: general | browser | vision | computer_use | search | form_fill

    # Order within a multi-step goal
    step_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Agent's plan (JSON string of planned actions)
    plan: Mapped[str] = mapped_column(Text, default="[]", nullable=False)

    # Result after completion
    result: Mapped[str] = mapped_column(Text, nullable=True)

    # Error message if failed
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # Whether this task was triggered by voice
    voice_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Session this task belongs to
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user = relationship("User", back_populates="tasks")
    subtasks = relationship("Task", backref="parent", remote_side=[id])

    def __repr__(self) -> str:
        return f"<Task id={self.id} title={self.title} status={self.status}>"