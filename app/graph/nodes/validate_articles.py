"""IN: articles | DO: drop malformed / stale / junk-titled items | OUT: filtered articles."""
from __future__ import annotations

from datetime import timedelta

from app.config.settings import Settings
from app.graph.nodes.common import safe_node
from app.graph.state import NewsState
from app.schemas import WorkingArticle
from app.utils.timeutils import utcnow

MIN_TITLE_CHARS = 15


def is_valid(article: WorkingArticle, settings: Settings) -> bool:
    title = article.title.strip()
    if len(title) < MIN_TITLE_CHARS or len(title.split()) < 3:
        return False
    if article.published_at is not None:
        if article.published_at < utcnow() - timedelta(hours=settings.lookback_hours * 2):
            return False
    return True


@safe_node("validate_articles")
def validate_articles(state: NewsState, *, settings: Settings) -> dict:
    articles = state.get("articles", [])
    kept = [a for a in articles if is_valid(a, settings)]
    return {"articles": kept, "stats": {"invalid_dropped": len(articles) - len(kept), "validated": len(kept)}}
