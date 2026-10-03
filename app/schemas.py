"""Typed data objects shared across layers (provider-agnostic)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.utils.text import url_hash as _url_hash


class ArticleData(BaseModel):
    """Normalized article. The rest of the app never sees provider payloads.

    `url` is optional because some providers (FreeNewsAPI) only return it from the
    details endpoint; it is guaranteed once the content-fetch stage has run.
    """

    external_id: str | None = None
    title: str
    description: str | None = None
    content: str | None = None
    url: str | None = None
    source: str = "Unknown"
    author: str | None = None
    published_at: datetime | None = None
    image_url: str | None = None
    provider_topics: list[str] = Field(default_factory=list)

    @property
    def url_hash(self) -> str | None:
        return _url_hash(self.url) if self.url else None

    @property
    def identity(self) -> str:
        return self.external_id or self.url_hash or self.title


class WorkingArticle(ArticleData):
    """An article as it flows through the LangGraph pipeline."""

    hint_topic: str | None = None       # topic of the query that discovered it
    hint_subtopic: str | None = None
    topic: str | None = None
    subtopic: str | None = None
    confidence: float = 0.0
    relevance: float = 0.0              # 0..1 for the current user
    importance: float = 0.0             # 0..1 from the LLM
    summary: str | None = None
    summary_source: str | None = None   # "ai" | "fallback"
    rank_score: float = 0.0
    cached: bool = False                # loaded from SQLite: skip LLM stages


class DigestSection(BaseModel):
    topic: str
    subtopic: str
    article_keys: list[str]


class Digest(BaseModel):
    digest_date: date
    overview: str | None = None
    sections: list[DigestSection] = Field(default_factory=list)


class ArticleView(BaseModel):
    """Read model returned by the repository for the UI and assistant."""

    id: int
    title: str
    description: str | None = None
    content: str | None = None
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


class DigestView(BaseModel):
    digest_date: date
    overview: str | None = None
    entries: list[ArticleView] = Field(default_factory=list)


class TrendingItem(BaseModel):
    topic: str
    subtopic: str
    today_count: int
    baseline_avg: float
    ratio: float
