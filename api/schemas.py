"""Request/response models for the HTTP API (kept separate from the internal app.schemas)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=72)


class AuthOut(BaseModel):
    user_id: int
    username: str
    token: str


class MeOut(BaseModel):
    user_id: int
    username: str


class EmailIn(BaseModel):
    email: str | None = Field(default=None, max_length=255)


class TrendingItemOut(BaseModel):
    topic: str
    subtopic: str
    today_count: int
    baseline_avg: float
    ratio: float


class PreferencesIn(BaseModel):
    preferences: dict[str, list[str]]


class TaxonomyOut(BaseModel):
    taxonomy: dict[str, list[str]]


class ArticleOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    url: str
    source: str
    author: str | None = None
    published_at: datetime | None = None
    image_url: str | None = None
    summary: str | None = None
    topic: str | None = None
    subtopic: str | None = None
    relevance: float | None = None
    rank_score: float | None = None
    saved: bool = False
    feedback: int | None = None


class DigestOut(BaseModel):
    digest_date: date
    overview: str | None = None
    is_stale: bool = False
    entries: list[ArticleOut] = Field(default_factory=list)


class RefreshOut(BaseModel):
    digest_date: date | None
    saved_count: int
    stats: dict
    errors: list[str]


class FeedbackIn(BaseModel):
    rating: int = Field(ge=-1, le=1)
    comment: str | None = None


class SaveOut(BaseModel):
    saved: bool


class AssistantIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class AssistantOut(BaseModel):
    answer: str
    sources: list[ArticleOut] = Field(default_factory=list)


class ErrorOut(BaseModel):
    detail: str
