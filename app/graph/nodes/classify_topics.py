"""IN: articles (titles; bodies are not fetched yet) | DO: batched LLM classification into taxonomy (uncached only); falls back to the
discovery hint if the LLM fails | OUT: articles with topic/subtopic/confidence; 'Other' dropped."""
from __future__ import annotations

import json

from app.graph.nodes.common import safe_node
from app.graph.state import NewsState
from app.schemas import WorkingArticle
from app.services.groq_service import LLMClient, LLMError
from app.taxonomy import SUBTOPIC_TO_TOPIC, taxonomy_prompt
from app.utils.text import truncate

BATCH_SIZE = 10

SYSTEM = f"""TASK: CLASSIFY
You classify news articles into exactly one category from this fixed list (Topic > Subtopic):
{taxonomy_prompt()}

Rules:
- Choose the single best subtopic for each article. If nothing fits, use "Other" for both fields.
- confidence is a number between 0 and 1.
Return ONLY a JSON array, one element per input article:
[{{"id": <int>, "topic": "<Topic>", "subtopic": "<Subtopic>", "confidence": <float>}}]"""


def _apply(article: WorkingArticle, item: dict | None) -> WorkingArticle | None:
    """Validate the LLM's answer; fall back to the discovery hint if it is unusable."""
    sub = (item or {}).get("subtopic")
    if sub in SUBTOPIC_TO_TOPIC:
        try:
            conf = max(0.0, min(1.0, float(item.get("confidence", 0.7))))
        except (TypeError, ValueError):
            conf = 0.7
        return article.model_copy(update={"topic": SUBTOPIC_TO_TOPIC[sub], "subtopic": sub, "confidence": conf})
    if item is not None and str(sub).lower() == "other":
        return None  # model says it fits nothing we track
    if article.hint_subtopic:
        return article.model_copy(update={"topic": article.hint_topic, "subtopic": article.hint_subtopic,
                                          "confidence": 0.5})
    return None


@safe_node("classify_topics")
def classify_topics(state: NewsState, *, llm: LLMClient) -> dict:
    articles = state.get("articles", [])
    todo = [a for a in articles if not a.cached]
    results: dict[str, WorkingArticle | None] = {}
    errors: list[str] = []
    llm_calls = 0
    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start : start + BATCH_SIZE]
        payload = json.dumps({"articles": [
            {"id": i, "title": a.title, "snippet": truncate(a.description or a.content, 240)}
            for i, a in enumerate(batch)]}, ensure_ascii=False)
        answers: dict[int, dict] = {}
        try:
            llm_calls += 1
            parsed = llm.complete_json(SYSTEM, payload)
            if isinstance(parsed, dict):
                parsed = parsed.get("articles") or parsed.get("results") or []
            answers = {int(x["id"]): x for x in parsed if isinstance(x, dict) and "id" in x}
        except (LLMError, ValueError, TypeError) as exc:
            errors.append(f"classify_topics: {exc}")
        for i, art in enumerate(batch):
            results[art.identity] = _apply(art, answers.get(i))
    out = [a if a.cached else results.get(a.identity) for a in articles]
    out = [a for a in out if a is not None]
    return {"articles": out, "errors": errors,
            "stats": {"classified": len(todo), "classify_llm_calls": llm_calls, "off_taxonomy_dropped": len(articles) - len(out)}}
