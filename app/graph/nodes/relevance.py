"""IN: classified articles + preferences | DO: heuristic relevance score (no LLM); drop articles
below RELEVANCE_THRESHOLD so they never reach the summarizer | OUT: relevant articles."""
from __future__ import annotations

from app.config.settings import Settings
from app.graph.nodes.common import safe_node
from app.graph.state import NewsState
from app.schemas import WorkingArticle
from app.taxonomy import TAXONOMY


def score_relevance(article: WorkingArticle, prefs: dict[str, list[str]]) -> float:
    if not article.topic or not article.subtopic:
        return 0.0
    if article.subtopic in prefs.get(article.topic, []):
        match = 1.0                      # exactly what the user picked
    elif article.topic in prefs:
        match = 0.3                      # same topic, different subtopic
    else:
        return 0.0
    text = f"{article.title} {article.description or ''}".lower()
    hits = sum(1 for kw in TAXONOMY[article.topic][article.subtopic] if kw.lower() in text)
    return round(0.6 * match + 0.25 * min(1.0, hits / 2) + 0.15 * article.confidence, 3)


@safe_node("calculate_relevance")
def calculate_relevance(state: NewsState, *, settings: Settings) -> dict:
    prefs = state["preferences"]
    articles = state.get("articles", [])
    scored = [a.model_copy(update={"relevance": score_relevance(a, prefs)}) for a in articles]
    kept = [a for a in scored if a.relevance >= settings.relevance_threshold]
    return {"articles": kept, "stats": {"irrelevant_dropped": len(scored) - len(kept), "relevant": len(kept)}}
