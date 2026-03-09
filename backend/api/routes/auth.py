from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr, field_validator

from api.deps import get_db, get_current_active_user
from core.security import hash_password, verify_password, create_access_token
from models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


# --------------------------------------------------------------------------
# Request / Response Schemas
# --------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Full name cannot be empty")
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    is_verified: bool
    preferred_voice: str
    language: str
    timezone: str
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    preferred_voice: str | None = None
    language: str | None = None
    timezone: str | None = None


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new AIRA user account",
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Creates a new user account and returns a JWT access token
    so the user is immediately logged in after registration.
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == payload.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()  # get the generated UUID before committing

    token = create_access_token(subject=str(user.id))

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive a JWT access token",
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticates the user with email and password.
    Returns a JWT token on success.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact support.",
        )

    # Update last seen
    user.last_seen_at = datetime.now(timezone.utc)

    token = create_access_token(subject=str(user.id))

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user's profile",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        preferred_voice=current_user.preferred_voice,
        language=current_user.language,
        timezone=current_user.timezone,
        created_at=current_user.created_at,
    )


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update the current user's profile preferences",
)
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.preferred_voice is not None:
        current_user.preferred_voice = payload.preferred_voice
    if payload.language is not None:
        current_user.language = payload.language
    if payload.timezone is not None:
        current_user.timezone = payload.timezone

    await db.flush()

    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        preferred_voice=current_user.preferred_voice,
        language=current_user.language,
        timezone=current_user.timezone,
        created_at=current_user.created_at,
    )