"""IN: relevant articles + preferences | DO: one LLM call per uncached article (most relevant
first, capped by MAX_ARTICLES_TO_SUMMARIZE) -> summary + importance; extractive fallback on failure
| OUT: articles with summary / importance."""
from __future__ import annotations

from app.config.settings import Settings
from app.graph.nodes.common import safe_node
from app.graph.state import NewsState
from app.schemas import WorkingArticle
from app.services.groq_service import LLMClient, LLMError
from app.utils.text import truncate

SYSTEM = """TASK: SUMMARIZE
Summarize the news article in 2-3 factual sentences (max 70 words) using ONLY the text provided.
Do not speculate or add outside knowledge. Also rate its importance from 1 (minor) to 10 (major, wide impact).
The reader is especially interested in: {interests}. Mention why the story matters to those interests only if the article supports it.
Return ONLY JSON: {{"summary": "<text>", "importance": <int 1-10>}}"""


def fallback_summary(a: WorkingArticle) -> str:
    return truncate(a.description or a.content, 280) or a.title


def _interests(prefs: dict[str, list[str]]) -> str:
    return ", ".join(s for subs in prefs.values() for s in subs) or "general news"


@safe_node("summarize_articles")
def summarize_articles(state: NewsState, *, llm: LLMClient, settings: Settings) -> dict:
    prefs = state["preferences"]
    articles = state.get("articles", [])
    todo = sorted((a for a in articles if not a.cached), key=lambda a: a.relevance, reverse=True)
    to_llm = {a.identity for a in todo[: settings.max_articles_to_summarize]}
    system = SYSTEM.format(interests=_interests(prefs))
    out: list[WorkingArticle] = []
    errors: list[str] = []
    ai = 0
    for art in articles:
        if art.cached:
            out.append(art)
            continue
        update: dict = {"summary": fallback_summary(art), "summary_source": "fallback",
                        "importance": round(0.3 + 0.4 * art.relevance, 3)}
        if art.identity in to_llm:
            user = f"Title: {art.title}\nSource: {art.source}\n\n{truncate(art.content, settings.max_content_chars)}"
            try:
                data = llm.complete_json(system, user)
                summary = str(data["summary"]).strip()
                if not summary:
                    raise ValueError("empty summary")
                update = {"summary": summary, "summary_source": "ai",
                          "importance": max(0.0, min(1.0, float(data.get("importance", 5)) / 10))}
                ai += 1
            except (LLMError, KeyError, TypeError, ValueError, AttributeError) as exc:
                errors.append(f"summarize[{art.title[:40]}]: {exc}")
        out.append(art.model_copy(update=update))
    return {"articles": out, "errors": errors,
            "stats": {"summarized_by_llm": ai, "summary_fallbacks": len([a for a in out if a.summary_source == 'fallback'])}}
