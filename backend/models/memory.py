import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text, ForeignKey, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class Memory(Base):
    __tablename__ = "memories"

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

    # Memory classification
    memory_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    # Types: preference | fact | habit | goal | context | correction

    # The actual memory content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Short key for fast lookup (e.g., "user_name", "preferred_language")
    key: Mapped[str] = mapped_column(String(255), nullable=True, index=True)

    # Relevance score (0.0 to 1.0), used for retrieval ranking
    relevance_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    # Source context (which session created this memory)
    source_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Whether AIRA actively surfaces this memory
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user = relationship("User", back_populates="memories")

    def __repr__(self) -> str:
        return f"<Memory id={self.id} type={self.memory_type} key={self.key}>"