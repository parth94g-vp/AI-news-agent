"""IN: relevant articles | DO: fetch body + URL from the provider (details endpoint) for uncached
articles only, most relevant first, capped at MAX_ARTICLES_TO_PROCESS; re-dedupe by URL
| OUT: articles with content. Irrelevant/duplicate articles never cost a details request."""
from __future__ import annotations

from app.config.settings import Settings
from app.graph.nodes.common import safe_node
from app.graph.nodes.deduplicate import dedupe_articles
from app.graph.state import NewsState
from app.services.news_api import NewsAPIAuthError, NewsAPIError, NewsProvider
from app.utils.timeutils import utcnow

MIN_BODY_CHARS = 40  # NewsData.io's free tier gives a description, not a full body


@safe_node("fetch_content")
def fetch_content(state: NewsState, *, provider: NewsProvider, settings: Settings) -> dict:
    articles = state.get("articles", [])
    cached = [a for a in articles if a.cached]
    fresh = sorted((a for a in articles if not a.cached),
                   key=lambda a: (a.relevance, a.published_at or utcnow().replace(year=2000)), reverse=True)
    budget = max(0, settings.max_articles_to_process - len(cached))
    errors: list[str] = []
    enriched = []
    for art in fresh[:budget]:
        try:
            full = provider.fetch_content(art)
        except NewsAPIAuthError as exc:
            errors.append(f"fetch_content: {exc}")
            break
        except NewsAPIError as exc:
            errors.append(f"fetch_content[{art.title[:40]}]: {exc}")
            continue
        if not full.url or len(full.content or "") < MIN_BODY_CHARS:
            continue  # nothing to summarize / link to
        enriched.append(full)
    result = dedupe_articles(cached + enriched, settings.dedupe_similarity)  # same URL, different uuid
    return {"articles": result, "errors": errors,
            "stats": {"content_fetched": len(enriched), "skipped_over_cap": max(0, len(fresh) - budget)}}
