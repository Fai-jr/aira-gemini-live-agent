from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel

from api.deps import get_db, get_current_active_user
from models.user import User
from models.memory import Memory

router = APIRouter(prefix="/memory", tags=["Memory"])


class MemoryCreateRequest(BaseModel):
    memory_type: str
    content: str
    key: Optional[str] = None
    is_pinned: bool = False


class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = None
    is_pinned: Optional[bool] = None
    relevance_score: Optional[float] = None


class MemoryResponse(BaseModel):
    id: str
    memory_type: str
    content: str
    key: Optional[str]
    relevance_score: float
    is_pinned: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get(
    "/",
    response_model=List[MemoryResponse],
    summary="Retrieve all memories for the current user",
)
async def list_memories(
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    pinned_only: bool = Query(False, description="Return only pinned memories"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[MemoryResponse]:
    conditions = [
        Memory.user_id == current_user.id,
        Memory.is_deleted == False,  # noqa: E712
    ]

    if memory_type:
        conditions.append(Memory.memory_type == memory_type)
    if pinned_only:
        conditions.append(Memory.is_pinned == True)  # noqa: E712

    result = await db.execute(
        select(Memory)
        .where(and_(*conditions))
        .order_by(Memory.is_pinned.desc(), Memory.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    memories = result.scalars().all()

    return [
        MemoryResponse(
            id=str(m.id),
            memory_type=m.memory_type,
            content=m.content,
            key=m.key,
            relevance_score=m.relevance_score,
            is_pinned=m.is_pinned,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in memories
    ]


@router.post(
    "/",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Store a new memory for the current user",
)
async def create_memory(
    payload: MemoryCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MemoryResponse:
    memory = Memory(
        user_id=current_user.id,
        memory_type=payload.memory_type,
        content=payload.content,
        key=payload.key,
        is_pinned=payload.is_pinned,
    )
    db.add(memory)
    await db.flush()

    return MemoryResponse(
        id=str(memory.id),
        memory_type=memory.memory_type,
        content=memory.content,
        key=memory.key,
        relevance_score=memory.relevance_score,
        is_pinned=memory.is_pinned,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.patch(
    "/{memory_id}",
    response_model=MemoryResponse,
    summary="Update a specific memory",
)
async def update_memory(
    memory_id: UUID,
    payload: MemoryUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MemoryResponse:
    result = await db.execute(
        select(Memory).where(
            and_(Memory.id == memory_id, Memory.user_id == current_user.id)
        )
    )
    memory = result.scalar_one_or_none()

    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")

    if payload.content is not None:
        memory.content = payload.content
    if payload.is_pinned is not None:
        memory.is_pinned = payload.is_pinned
    if payload.relevance_score is not None:
        memory.relevance_score = payload.relevance_score

    memory.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return MemoryResponse(
        id=str(memory.id),
        memory_type=memory.memory_type,
        content=memory.content,
        key=memory.key,
        relevance_score=memory.relevance_score,
        is_pinned=memory.is_pinned,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a specific memory",
)
async def delete_memory(
    memory_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Memory).where(
            and_(Memory.id == memory_id, Memory.user_id == current_user.id)
        )
    )
    memory = result.scalar_one_or_none()

    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")

    memory.is_deleted = True
    await db.flush()