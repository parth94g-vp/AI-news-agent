"""SQLAlchemy 2.0 models. Datetimes are stored as naive UTC."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (Date, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferences: Mapped[list["UserPreference"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Topic(TimestampMixin, Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    subtopics: Mapped[list["Subtopic"]] = relationship(back_populates="topic", cascade="all, delete-orphan")


class Subtopic(TimestampMixin, Base):
    __tablename__ = "subtopics"
    __table_args__ = (UniqueConstraint("topic_id", "name", name="uq_subtopic_topic_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    topic: Mapped[Topic] = relationship(back_populates="subtopics")


class UserPreference(TimestampMixin, Base):
    __tablename__ = "user_preferences"
    __table_args__ = (UniqueConstraint("user_id", "subtopic_id", name="uq_pref_user_subtopic"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subtopic_id: Mapped[int] = mapped_column(ForeignKey("subtopics.id", ondelete="CASCADE"))
    user: Mapped[User] = relationship(back_populates="preferences")
    subtopic: Mapped[Subtopic] = relationship()


class Article(TimestampMixin, Base):
    __tablename__ = "articles"
    __table_args__ = (Index("ix_articles_published", "published_at"), Index("ix_articles_fetched", "fetched_at"))
    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(Text)
    title_norm: Mapped[str] = mapped_column(String(300), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(200), default="Unknown")
    author: Mapped[str | None] = mapped_column(String(300), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_source: Mapped[str | None] = mapped_column(String(16), nullable=True)  # ai | fallback
    importance: Mapped[float] = mapped_column(Float, default=0.0)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    topics: Mapped[list["ArticleTopic"]] = relationship(back_populates="article", cascade="all, delete-orphan")


class ArticleTopic(TimestampMixin, Base):
    __tablename__ = "article_topics"
    __table_args__ = (UniqueConstraint("article_id", "subtopic_id", name="uq_article_subtopic"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    subtopic_id: Mapped[int] = mapped_column(ForeignKey("subtopics.id", ondelete="CASCADE"), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    article: Mapped[Article] = relationship(back_populates="topics")
    subtopic: Mapped[Subtopic] = relationship()


class NewsHistory(TimestampMixin, Base):
    """One row per article shown in a user's digest for a given day."""
    __tablename__ = "news_history"
    __table_args__ = (
        UniqueConstraint("user_id", "article_id", "digest_date", name="uq_history_user_article_day"),
        Index("ix_history_user_date", "user_id", "digest_date"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    subtopic_id: Mapped[int] = mapped_column(ForeignKey("subtopics.id", ondelete="CASCADE"))
    digest_date: Mapped[date] = mapped_column(Date)
    relevance: Mapped[float] = mapped_column(Float, default=0.0)
    rank_score: Mapped[float] = mapped_column(Float, default=0.0)
    position: Mapped[int] = mapped_column(Integer, default=0)


class DigestOverview(TimestampMixin, Base):
    __tablename__ = "digest_overviews"
    __table_args__ = (UniqueConstraint("user_id", "digest_date", name="uq_overview_user_day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    digest_date: Mapped[date] = mapped_column(Date)
    overview: Mapped[str] = mapped_column(Text)


class SavedArticle(TimestampMixin, Base):
    __tablename__ = "saved_articles"
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_saved_user_article"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))


class Feedback(TimestampMixin, Base):
    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_feedback_user_article"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer)  # +1 helpful / -1 not helpful
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
