from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel

from api.deps import get_db, get_current_active_user
from models.user import User
from models.session import Session

router = APIRouter(prefix="/sessions", tags=["Sessions"])


class SessionCreateRequest(BaseModel):
    session_type: str = "voice"


class SessionUpdateRequest(BaseModel):
    status: Optional[str] = None
    transcript: Optional[str] = None
    current_goal: Optional[str] = None
    goal_steps: Optional[str] = None
    last_screenshot_description: Optional[str] = None
    total_turns: Optional[int] = None
    audio_duration_seconds: Optional[int] = None
    used_vision: Optional[bool] = None
    used_computer_use: Optional[bool] = None


class SessionResponse(BaseModel):
    id: str
    user_id: str
    status: str
    session_type: str
    current_goal: Optional[str]
    total_turns: int
    audio_duration_seconds: int
    used_vision: bool
    used_computer_use: bool
    started_at: datetime
    ended_at: Optional[datetime]

    class Config:
        from_attributes = True

@router.post(
    "/",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new AIRA session",
)
async def create_session(
    payload: SessionCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    session = Session(
        user_id=current_user.id,
        session_type=payload.session_type,
        status="active",
    )
    db.add(session)
    await db.flush()

    return SessionResponse(
        id=str(session.id),
        user_id=str(session.user_id),
        status=session.status,
        session_type=session.session_type,
        current_goal=session.current_goal,
        total_turns=session.total_turns,
        audio_duration_seconds=session.audio_duration_seconds,
        used_vision=session.used_vision,
        used_computer_use=session.used_computer_use,
        started_at=session.started_at,
        ended_at=session.ended_at,
    )


@router.get(
    "/",
    response_model=List[SessionResponse],
    summary="List all sessions for the current user",
)
async def list_sessions(
    session_status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[SessionResponse]:
    conditions = [Session.user_id == current_user.id]

    if session_status:
        conditions.append(Session.status == session_status)

    result = await db.execute(
        select(Session)
        .where(and_(*conditions))
        .order_by(Session.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sessions = result.scalars().all()

    return [
        SessionResponse(
            id=str(s.id),
            user_id=str(s.user_id),
            status=s.status,
            session_type=s.session_type,
            current_goal=s.current_goal,
            total_turns=s.total_turns,
            audio_duration_seconds=s.audio_duration_seconds,
            used_vision=s.used_vision,
            used_computer_use=s.used_computer_use,
            started_at=s.started_at,
            ended_at=s.ended_at,
        )
        for s in sessions
    ]


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get a specific session by ID",
)
async def get_session(
    session_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    result = await db.execute(
        select(Session).where(
            and_(Session.id == session_id, Session.user_id == current_user.id)
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return SessionResponse(
        id=str(session.id),
        user_id=str(session.user_id),
        status=session.status,
        session_type=session.session_type,
        current_goal=session.current_goal,
        total_turns=session.total_turns,
        audio_duration_seconds=session.audio_duration_seconds,
        used_vision=session.used_vision,
        used_computer_use=session.used_computer_use,
        started_at=session.started_at,
        ended_at=session.ended_at,
    )


@router.patch(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Update a session (e.g., end it, add transcript)",
)
async def update_session(
    session_id: UUID,
    payload: SessionUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    result = await db.execute(
        select(Session).where(
            and_(Session.id == session_id, Session.user_id == current_user.id)
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if payload.status is not None:
        session.status = payload.status
        if payload.status == "ended":
            session.ended_at = datetime.now(timezone.utc)
    if payload.transcript is not None:
        session.transcript = payload.transcript
    if payload.current_goal is not None:
        session.current_goal = payload.current_goal
    if payload.goal_steps is not None:
        session.goal_steps = payload.goal_steps
    if payload.last_screenshot_description is not None:
        session.last_screenshot_description = payload.last_screenshot_description
    if payload.total_turns is not None:
        session.total_turns = payload.total_turns
    if payload.audio_duration_seconds is not None:
        session.audio_duration_seconds = payload.audio_duration_seconds
    if payload.used_vision is not None:
        session.used_vision = payload.used_vision
    if payload.used_computer_use is not None:
        session.used_computer_use = payload.used_computer_use

    await db.flush()

    return SessionResponse(
        id=str(session.id),
        user_id=str(session.user_id),
        status=session.status,
        session_type=session.session_type,
        current_goal=session.current_goal,
        total_turns=session.total_turns,
        audio_duration_seconds=session.audio_duration_seconds,
        used_vision=session.used_vision,
        used_computer_use=session.used_computer_use,
        started_at=session.started_at,
        ended_at=session.ended_at,
    )