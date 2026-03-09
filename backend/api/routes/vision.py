import base64
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_current_active_user
from agents.vision_agent import VisionAgent
from models.user import User

logger = logging.getLogger("aira.vision_route")

router = APIRouter(prefix="/vision", tags=["Vision"])

vision_agent = VisionAgent()


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------

class ScreenshotRequest(BaseModel):
    image_base64: str
    query: Optional[str] = None


class DescribeResponse(BaseModel):
    description: str
    query: Optional[str] = None


class AppInfoResponse(BaseModel):
    app_name: str
    app_type: str
    current_url: Optional[str]
    page_title: str
    primary_action: str


class FormFieldsResponse(BaseModel):
    fields: list


class ActionsResponse(BaseModel):
    actions: list


class FindElementRequest(BaseModel):
    image_base64: str
    element_description: str


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@router.post(
    "/describe",
    response_model=DescribeResponse,
    summary="Describe what is on screen",
)
async def describe_screen(
    payload: ScreenshotRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DescribeResponse:
    """
    Send a base64 screenshot and get a natural language description
    of what is visible. Optionally answer a specific question about it.
    """
    try:
        image_bytes = base64.b64decode(payload.image_base64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 image data",
        )

    description = await vision_agent.describe_screen(
        image_bytes=image_bytes,
        user_query=payload.query,
    )

    return DescribeResponse(description=description, query=payload.query)


@router.post(
    "/app-info",
    response_model=AppInfoResponse,
    summary="Identify the current application or website",
)
async def get_app_info(
    payload: ScreenshotRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AppInfoResponse:
    try:
        image_bytes = base64.b64decode(payload.image_base64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 image data",
        )

    info = await vision_agent.identify_current_app(image_bytes)
    return AppInfoResponse(**info)


@router.post(
    "/form-fields",
    response_model=FormFieldsResponse,
    summary="Extract form fields from a screenshot",
)
async def extract_form_fields(
    payload: ScreenshotRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> FormFieldsResponse:
    try:
        image_bytes = base64.b64decode(payload.image_base64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 image data",
        )

    result = await vision_agent.extract_form_fields(image_bytes)
    return FormFieldsResponse(fields=result.get("fields", []))


@router.post(
    "/suggest-actions",
    response_model=ActionsResponse,
    summary="Get suggested actions based on current screen",
)
async def suggest_actions(
    payload: ScreenshotRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ActionsResponse:
    try:
        image_bytes = base64.b64decode(payload.image_base64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 image data",
        )

    actions = await vision_agent.suggest_next_actions(image_bytes)
    return ActionsResponse(actions=actions)


@router.post(
    "/find-element",
    summary="Find a specific UI element on screen",
)
async def find_element(
    payload: FindElementRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        image_bytes = base64.b64decode(payload.image_base64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 image data",
        )

    result = await vision_agent.find_element(
        image_bytes=image_bytes,
        element_description=payload.element_description,
    )
    return result


@router.post(
    "/extract-text",
    summary="Extract all text from a screenshot",
)
async def extract_text(
    payload: ScreenshotRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        image_bytes = base64.b64decode(payload.image_base64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 image data",
        )

    text = await vision_agent.extract_text_from_screen(image_bytes)
    return {"text": text}