"""All persistence logic. Returns DTOs (never live ORM objects) to callers."""
from __future__ import annotations

import re
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Iterator

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.database import models as m
from app.logging_config import get_logger, log_event
from app.schemas import ArticleView, Digest, DigestView, TrendingItem, WorkingArticle
from app.taxonomy import TAXONOMY, validate_preferences
from app.utils.text import normalize_title, url_hash
from app.utils.timeutils import ensure_utc, to_naive_utc, utcnow

logger = get_logger(__name__)
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_. \-]{2,40}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class NewsRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Transaction scope: commit on success, roll back on any error."""
        s = self._sf()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    # ------------------------------------------------------------ taxonomy
    def seed_taxonomy(self) -> None:
        with self.session() as s:
            for tname, subs in TAXONOMY.items():
                topic = s.scalar(select(m.Topic).where(m.Topic.name == tname))
                if topic is None:
                    topic = m.Topic(name=tname)
                    s.add(topic)
                    s.flush()
                existing = {x.name for x in s.scalars(select(m.Subtopic).where(m.Subtopic.topic_id == topic.id))}
                for sname in subs:
                    if sname not in existing:
                        s.add(m.Subtopic(topic_id=topic.id, name=sname))

    def _subtopic_ids(self, s: Session) -> dict[str, int]:
        return {name: sid for name, sid in s.execute(select(m.Subtopic.name, m.Subtopic.id))}

    # --------------------------------------------------------------- users
    def create_or_get_user(self, username: str) -> tuple[int, str]:
        name = (username or "").strip()
        if not _USERNAME_RE.match(name):
            raise ValueError("Username must be 2-40 characters: letters, numbers, spaces, . _ -")
        for _ in range(2):
            try:
                with self.session() as s:
                    user = s.scalar(select(m.User).where(m.User.username == name))
                    if user is None:
                        user = m.User(username=name)
                        s.add(user)
                        s.flush()
                        log_event(logger, "user_created", username=name)
                    return user.id, user.username
            except IntegrityError:  # concurrent creation: retry as a read
                continue
        raise RuntimeError("could not create user")

    def set_email(self, user_id: int, email: str | None) -> None:
        email = (email or "").strip() or None
        if email and not _EMAIL_RE.match(email):
            raise ValueError("That doesn't look like a valid email address.")
        with self.session() as s:
            user = s.get(m.User, user_id)
            if user is None:
                raise ValueError(f"No such user: {user_id}")
            user.email = email

    def list_users_with_preferences(self) -> list[tuple[int, str, str | None]]:
        """(user_id, username, email) for every user who has selected at least one subtopic.
        Used by the scheduled job: no point running the pipeline for someone with no preferences."""
        with self.session() as s:
            rows = s.execute(
                select(m.User.id, m.User.username, m.User.email)
                .join(m.UserPreference, m.UserPreference.user_id == m.User.id)
                .distinct()
            ).all()
            return [(uid, uname, email) for uid, uname, email in rows]

    def set_preferences(self, user_id: int, prefs: dict[str, list[str]]) -> None:
        clean = validate_preferences(prefs)
        with self.session() as s:
            ids = self._subtopic_ids(s)
            s.execute(delete(m.UserPreference).where(m.UserPreference.user_id == user_id))
            for subs in clean.values():
                for sub in subs:
                    s.add(m.UserPreference(user_id=user_id, subtopic_id=ids[sub]))

    def get_preferences(self, user_id: int) -> dict[str, list[str]]:
        with self.session() as s:
            rows = s.execute(
                select(m.Topic.name, m.Subtopic.name)
                .join(m.Subtopic, m.Subtopic.topic_id == m.Topic.id)
                .join(m.UserPreference, m.UserPreference.subtopic_id == m.Subtopic.id)
                .where(m.UserPreference.user_id == user_id)
            ).all()
        chosen: dict[str, set[str]] = {}
        for t, sub in rows:
            chosen.setdefault(t, set()).add(sub)
        return {t: [x for x in TAXONOMY[t] if x in subs] for t, subs in chosen.items()}

    # ------------------------------------------------------------ articles
    def find_cached(self, external_ids: list[str], hashes: list[str]) -> dict[str, WorkingArticle]:
        """Articles already processed with an AI summary, keyed by external id / url hash."""
        if not external_ids and not hashes:
            return {}
        with self.session() as s:
            rows = s.scalars(
                select(m.Article).where(
                    m.Article.summary_source == "ai",
                    (m.Article.external_id.in_(external_ids)) | (m.Article.url_hash.in_(hashes)),
                )
            ).all()
            best = self._best_topics(s, [r.id for r in rows])
            out: dict[str, WorkingArticle] = {}
            for r in rows:
                if r.id not in best:
                    continue
                topic, sub, conf = best[r.id]
                wa = WorkingArticle(
                    external_id=r.external_id, title=r.title, description=r.description, content=r.content,
                    url=r.url, source=r.source, author=r.author, image_url=r.image_url,
                    published_at=ensure_utc(r.published_at), topic=topic, subtopic=sub, confidence=conf,
                    summary=r.summary, summary_source="ai", importance=r.importance, cached=True,
                )
                if r.external_id:
                    out[r.external_id] = wa
                out[r.url_hash] = wa
            return out

    def _best_topics(self, s: Session, article_ids: list[int]) -> dict[int, tuple[str, str, float]]:
        if not article_ids:
            return {}
        rows = s.execute(
            select(m.ArticleTopic.article_id, m.Topic.name, m.Subtopic.name, m.ArticleTopic.confidence)
            .join(m.Subtopic, m.Subtopic.id == m.ArticleTopic.subtopic_id)
            .join(m.Topic, m.Topic.id == m.Subtopic.topic_id)
            .where(m.ArticleTopic.article_id.in_(article_ids))
            .order_by(m.ArticleTopic.confidence)
        ).all()
        return {aid: (t, sub, conf) for aid, t, sub, conf in rows}  # highest confidence wins

    def _upsert_article(self, s: Session, a: WorkingArticle) -> m.Article:
        if not a.url:
            raise ValueError(f"article without url cannot be stored: {a.title!r}")
        h = a.url_hash
        def lookup() -> m.Article | None:
            row = s.scalar(select(m.Article).where(m.Article.external_id == a.external_id)) if a.external_id else None
            return row or s.scalar(select(m.Article).where(m.Article.url_hash == h))

        row = lookup()
        if row is None:
            row = m.Article(
                external_id=a.external_id, url=a.url, url_hash=h, title=a.title,
                title_norm=normalize_title(a.title)[:300], description=a.description, content=a.content,
                source=a.source, author=a.author, published_at=to_naive_utc(a.published_at),
                image_url=a.image_url, summary=a.summary, summary_source=a.summary_source,
                importance=a.importance,
            )
            try:
                with s.begin_nested():
                    s.add(row)
                    s.flush()
                return row
            except IntegrityError:  # inserted concurrently: fall through to update
                row = lookup()
                if row is None:
                    raise
        row.content = row.content or a.content
        row.description = row.description or a.description
        row.image_url = row.image_url or a.image_url
        if a.summary and (a.summary_source == "ai" or not row.summary):
            row.summary, row.summary_source, row.importance = a.summary, a.summary_source, a.importance
        s.flush()
        return row

    def save_digest(self, user_id: int, articles: list[WorkingArticle], digest: Digest) -> int:
        """Persist articles, their classification, the user's history and overview in ONE transaction."""
        by_key = {a.identity: a for a in articles}
        with self.session() as s:
            sub_ids = self._subtopic_ids(s)
            row_ids: dict[str, int] = {}
            for a in articles:
                row = self._upsert_article(s, a)
                row_ids[a.identity] = row.id
                if a.subtopic in sub_ids and not a.cached:
                    link = s.scalar(select(m.ArticleTopic).where(
                        m.ArticleTopic.article_id == row.id, m.ArticleTopic.subtopic_id == sub_ids[a.subtopic]))
                    if link is None:
                        s.add(m.ArticleTopic(article_id=row.id, subtopic_id=sub_ids[a.subtopic], confidence=a.confidence))
                    else:
                        link.confidence = max(link.confidence, a.confidence)
            s.execute(delete(m.NewsHistory).where(
                m.NewsHistory.user_id == user_id, m.NewsHistory.digest_date == digest.digest_date))
            position = 0
            for section in digest.sections:
                for key in section.article_keys:
                    a = by_key.get(key)
                    if a is None or key not in row_ids or section.subtopic not in sub_ids:
                        continue
                    s.add(m.NewsHistory(
                        user_id=user_id, article_id=row_ids[key], subtopic_id=sub_ids[section.subtopic],
                        digest_date=digest.digest_date, relevance=a.relevance, rank_score=a.rank_score,
                        position=position))
                    position += 1
            existing = s.scalar(select(m.DigestOverview).where(
                m.DigestOverview.user_id == user_id, m.DigestOverview.digest_date == digest.digest_date))
            if digest.overview:
                if existing:
                    existing.overview = digest.overview
                else:
                    s.add(m.DigestOverview(user_id=user_id, digest_date=digest.digest_date, overview=digest.overview))
            elif existing:
                s.delete(existing)
            log_event(logger, "digest_saved", user_id=user_id, articles=len(articles), in_digest=position)
            return position

    # ---------------------------------------------------------------- views
    def _views(self, s: Session, articles: list[m.Article], user_id: int | None,
               overrides: dict[int, dict] | None = None) -> list[ArticleView]:
        ids = [a.id for a in articles]
        best = self._best_topics(s, ids)
        saved: set[int] = set()
        fb: dict[int, int] = {}
        if user_id is not None and ids:
            saved = set(s.scalars(select(m.SavedArticle.article_id).where(
                m.SavedArticle.user_id == user_id, m.SavedArticle.article_id.in_(ids))))
            fb = dict(s.execute(select(m.Feedback.article_id, m.Feedback.rating).where(
                m.Feedback.user_id == user_id, m.Feedback.article_id.in_(ids))).all())
        views = []
        for a in articles:
            topic, sub, _ = best.get(a.id, (None, None, 0.0))
            extra = {"topic": topic, "subtopic": sub, **(overrides or {}).get(a.id, {})}
            views.append(ArticleView(
                id=a.id, title=a.title, description=a.description, content=a.content, url=a.url,
                source=a.source, author=a.author, published_at=ensure_utc(a.published_at),
                image_url=a.image_url, summary=a.summary or a.description, saved=a.id in saved,
                feedback=fb.get(a.id), **extra))
        return views

    def get_digest(self, user_id: int, digest_date: date | None = None) -> DigestView | None:
        """Digest for a date, or the user's most recent one when `digest_date` is None."""
        with self.session() as s:
            if digest_date is None:
                digest_date = s.scalar(select(m.NewsHistory.digest_date).where(
                    m.NewsHistory.user_id == user_id).order_by(m.NewsHistory.digest_date.desc()).limit(1))
                if digest_date is None:
                    return None
            rows = s.execute(
                select(m.NewsHistory, m.Article, m.Subtopic.name, m.Topic.name)
                .join(m.Article, m.Article.id == m.NewsHistory.article_id)
                .join(m.Subtopic, m.Subtopic.id == m.NewsHistory.subtopic_id)
                .join(m.Topic, m.Topic.id == m.Subtopic.topic_id)
                .where(m.NewsHistory.user_id == user_id, m.NewsHistory.digest_date == digest_date)
                .order_by(m.NewsHistory.position)
            ).all()
            if not rows:
                return None
            overrides = {h.article_id: {"topic": t, "subtopic": sub, "relevance": h.relevance,
                                        "rank_score": h.rank_score} for h, _, sub, t in rows}
            entries = self._views(s, [a for _, a, _, _ in rows], user_id, overrides)
            overview = s.scalar(select(m.DigestOverview.overview).where(
                m.DigestOverview.user_id == user_id, m.DigestOverview.digest_date == digest_date))
            return DigestView(digest_date=digest_date, overview=overview, entries=entries)

    def recent_articles(self, since: datetime, limit: int = 300, user_id: int | None = None) -> list[ArticleView]:
        with self.session() as s:
            rows = s.scalars(select(m.Article).where(m.Article.fetched_at >= to_naive_utc(since))
                             .order_by(m.Article.published_at.desc()).limit(limit)).all()
            return self._views(s, list(rows), user_id)

    # ------------------------------------------------- bookmarks / feedback
    def toggle_saved(self, user_id: int, article_id: int) -> bool:
        """Returns True if the article is saved after the call."""
        with self.session() as s:
            row = s.scalar(select(m.SavedArticle).where(
                m.SavedArticle.user_id == user_id, m.SavedArticle.article_id == article_id))
            if row:
                s.delete(row)
                return False
            s.add(m.SavedArticle(user_id=user_id, article_id=article_id))
            return True

    def list_saved(self, user_id: int) -> list[ArticleView]:
        with self.session() as s:
            arts = s.scalars(select(m.Article).join(m.SavedArticle, m.SavedArticle.article_id == m.Article.id)
                             .where(m.SavedArticle.user_id == user_id)
                             .order_by(m.SavedArticle.created_at.desc())).all()
            return self._views(s, list(arts), user_id)

    def set_feedback(self, user_id: int, article_id: int, rating: int, comment: str | None = None) -> None:
        if rating not in (-1, 1):
            raise ValueError("rating must be +1 or -1")
        comment = (comment or "").strip()[:1000] or None
        with self.session() as s:
            row = s.scalar(select(m.Feedback).where(
                m.Feedback.user_id == user_id, m.Feedback.article_id == article_id))
            if row:
                row.rating, row.comment = rating, comment
            else:
                s.add(m.Feedback(user_id=user_id, article_id=article_id, rating=rating, comment=comment))


    # --------------------------------------------------------------- trending
    def get_trending_subtopics(self, baseline_days: int = 7, min_count: int = 3,
                                ratio_threshold: float = 1.6) -> list[TrendingItem]:
        """Subtopics with unusually many articles TODAY vs. their recent daily average.

        Global (not per-user): based on every article collected, regardless of who it was
        discovered for. 'Today' and 'recent' are both bucketed by the day the article was
        first fetched (UTC date), so this reflects collection activity, not publish time.
        """
        with self.session() as s:
            since = to_naive_utc(utcnow() - timedelta(days=baseline_days + 1))
            rows = s.execute(
                select(m.Topic.name, m.Subtopic.name, m.Article.fetched_at, m.Article.id)
                .join(m.ArticleTopic, m.ArticleTopic.subtopic_id == m.Subtopic.id)
                .join(m.Article, m.Article.id == m.ArticleTopic.article_id)
                .join(m.Topic, m.Topic.id == m.Subtopic.topic_id)
                .where(m.Article.fetched_at >= since)
            ).all()
        today = utcnow().date()
        counts: dict[tuple[str, str], dict[date, set[int]]] = {}
        for topic, sub, fetched_at, article_id in rows:
            day = ensure_utc(fetched_at).date() if fetched_at.tzinfo is None else fetched_at.date()
            counts.setdefault((topic, sub), {}).setdefault(day, set()).add(article_id)
        trending: list[TrendingItem] = []
        for (topic, sub), by_day in counts.items():
            today_count = len(by_day.get(today, set()))
            past_days = [len(ids) for day, ids in by_day.items() if day != today]
            baseline = sum(past_days) / len(past_days) if past_days else 0.0
            if today_count < min_count:
                continue
            ratio = today_count / baseline if baseline > 0 else float(today_count)
            if ratio >= ratio_threshold:
                trending.append(TrendingItem(topic=topic, subtopic=sub, today_count=today_count,
                                             baseline_avg=round(baseline, 1), ratio=round(ratio, 2)))
        trending.sort(key=lambda t: t.ratio, reverse=True)
        return trending
