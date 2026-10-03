"""IN: summarized articles | DO: rank_score = 0.5*relevance + 0.3*importance + 0.2*recency | OUT: sorted articles."""
from __future__ import annotations

from app.graph.nodes.common import safe_node
from app.graph.state import NewsState
from app.schemas import WorkingArticle
from app.utils.timeutils import utcnow

W_RELEVANCE, W_IMPORTANCE, W_RECENCY = 0.5, 0.3, 0.2


def recency_score(article: WorkingArticle) -> float:
    if article.published_at is None:
        return 0.3
    age_hours = max(0.0, (utcnow() - article.published_at).total_seconds() / 3600)
    return 1.0 / (1.0 + age_hours / 24.0)


@safe_node("rank_articles")
def rank_articles(state: NewsState) -> dict:
    ranked = [a.model_copy(update={"rank_score": round(
        W_RELEVANCE * a.relevance + W_IMPORTANCE * a.importance + W_RECENCY * recency_score(a), 4)})
        for a in state.get("articles", [])]
    ranked.sort(key=lambda a: a.rank_score, reverse=True)
    return {"articles": ranked, "stats": {"ranked": len(ranked)}}
