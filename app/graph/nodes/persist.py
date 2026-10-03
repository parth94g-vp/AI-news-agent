"""IN: articles + digest | DO: one SQLite transaction (articles, topics, history, overview) | OUT: saved_count."""
from __future__ import annotations

from app.database.repositories import NewsRepository
from app.graph.nodes.common import safe_node
from app.graph.state import NewsState


@safe_node("persist_digest")
def persist_digest(state: NewsState, *, repo: NewsRepository) -> dict:
    digest = state.get("digest")
    if digest is None:
        return {"saved_count": 0}
    n = repo.save_digest(state["user_id"], state.get("articles", []), digest)
    return {"saved_count": n, "stats": {"saved_to_db": n}}
