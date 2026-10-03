"""Request/response models for the API. Internal objects (ArticleView, DigestView, Digest)
are already Pydantic models and are reused directly where possible."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CreateUserRequest(BaseModel):
    username: str


class UserResponse(BaseModel):
    user_id: int
    username: str


class PreferencesRequest(BaseModel):
    preferences: dict[str, list[str]] = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    rating: int  # +1 or -1
    comment: str | None = None


class AssistantRequest(BaseModel):
    question: str


class AssistantResponseModel(BaseModel):
    answer: str
    sources: list[dict]


class RefreshResponse(BaseModel):
    saved_count: int
    digest_date: str | None
    stats: dict
    errors: list[str]


class SavedToggleResponse(BaseModel):
    article_id: int
    saved: bool


class ErrorResponse(BaseModel):
    detail: str
