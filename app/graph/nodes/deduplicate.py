"""IN: articles | DO: remove duplicates (URL, normalized title, fuzzy title = same story
from another outlet) | OUT: unique articles. Pure Python: no LLM tokens spent on duplicates."""
from __future__ import annotations

from app.config.settings import Settings
from app.graph.nodes.common import safe_node
from app.graph.state import NewsState
from app.schemas import WorkingArticle
from app.utils.text import normalize_title, titles_similar


def dedupe_articles(articles: list[WorkingArticle], similarity: float = 0.85) -> list[WorkingArticle]:
    kept: list[WorkingArticle] = []
    norms: list[str] = []
    seen_ids: dict[str, int] = {}
    for art in articles:
        norm = normalize_title(art.title)
        idx = seen_ids.get(art.external_id or "") if art.external_id else None
        if idx is None and art.url_hash:
            idx = seen_ids.get(art.url_hash)
        if idx is None:
            idx = next((i for i, n in enumerate(norms) if titles_similar(norm, n, similarity)), None)
        if idx is not None:
            # duplicate: keep whichever version has more content, remember subtopic hint
            if len(art.content or "") > len(kept[idx].content or ""):
                kept[idx] = art.model_copy(update={"hint_topic": kept[idx].hint_topic,
                                                   "hint_subtopic": kept[idx].hint_subtopic})
            continue
        kept.append(art)
        norms.append(norm)
        if art.external_id:
            seen_ids[art.external_id] = len(kept) - 1
        if art.url_hash:
            seen_ids[art.url_hash] = len(kept) - 1
    return kept


@safe_node("deduplicate")
def deduplicate(state: NewsState, *, settings: Settings) -> dict:
    articles = state.get("articles", [])
    kept = dedupe_articles(articles, settings.dedupe_similarity)
    return {"articles": kept, "stats": {"duplicates_removed": len(articles) - len(kept), "unique": len(kept)}}
