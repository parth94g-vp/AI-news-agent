"""IN: preferences | DO: one provider search per selected subtopic | OUT: articles (metadata only)."""
from __future__ import annotations

from datetime import timedelta

from app.config.settings import Settings
from app.graph.nodes.common import safe_node
from app.graph.state import NewsState
from app.schemas import WorkingArticle
from app.services.news_api import NewsAPIAuthError, NewsAPIError, NewsProvider
from app.taxonomy import TAXONOMY
from app.utils.timeutils import utcnow


@safe_node("discover_news")
def discover_news(state: NewsState, *, provider: NewsProvider, settings: Settings) -> dict:
    since = utcnow() - timedelta(hours=settings.lookback_hours)
    found: list[WorkingArticle] = []
    errors: list[str] = []
    for topic, subtopics in state["preferences"].items():
        for sub in subtopics:
            for query in TAXONOMY[topic][sub][: settings.queries_per_subtopic]:
                try:
                    items = provider.search(query, limit=settings.articles_per_query, since=since)
                except NewsAPIAuthError as exc:      # no point continuing
                    return {"articles": found, "errors": [f"discover_news: {exc}"]}
                except NewsAPIError as exc:          # one bad query must not sink the run
                    errors.append(f"discover_news[{sub}]: {exc}")
                    continue
                found.extend(WorkingArticle(**it.model_dump(), hint_topic=topic, hint_subtopic=sub) for it in items)
    return {"articles": found, "errors": errors, "stats": {"discovered": len(found)}}
