"""IN: unique articles | DO: swap in already-summarized versions from SQLite |
OUT: articles (cached=True skip content fetch, classification and summarization)."""
from __future__ import annotations

from app.database.repositories import NewsRepository
from app.graph.nodes.common import safe_node
from app.graph.state import NewsState


@safe_node("check_cache")
def check_cache(state: NewsState, *, repo: NewsRepository) -> dict:
    articles = state.get("articles", [])
    cache = repo.find_cached([a.external_id for a in articles if a.external_id],
                             [a.url_hash for a in articles if a.url_hash])
    out = []
    for a in articles:
        hit = cache.get(a.external_id or "") or cache.get(a.url_hash or "")
        out.append(hit.model_copy(update={"hint_topic": a.hint_topic, "hint_subtopic": a.hint_subtopic}) if hit else a)
    hits = sum(1 for a in out if a.cached)
    return {"articles": out, "stats": {"cache_hits": hits}}
