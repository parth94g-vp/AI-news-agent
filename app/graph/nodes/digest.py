"""IN: ranked articles + preferences | DO: group top-N per subtopic (taxonomy order) and ask the LLM
for a short personalized overview (optional; failure is non-fatal) | OUT: Digest."""
from __future__ import annotations

from app.config.settings import Settings
from app.graph.nodes.common import safe_node
from app.graph.state import NewsState
from app.schemas import Digest, DigestSection
from app.services.groq_service import LLMClient, LLMError
from app.taxonomy import TAXONOMY
from app.utils.text import truncate
from app.utils.timeutils import local_today

SYSTEM = """TASK: OVERVIEW
Write a 3-4 sentence personalized morning briefing overview from the numbered stories below.
Use ONLY facts in the stories; do not invent details. Plain prose, no bullet points, no headings."""


@safe_node("generate_digest")
def generate_digest(state: NewsState, *, llm: LLMClient | None, settings: Settings) -> dict:
    articles = state.get("articles", [])
    sections: list[DigestSection] = []
    for topic, subs in TAXONOMY.items():
        for sub in subs:
            group = [a for a in articles if a.topic == topic and a.subtopic == sub]  # already rank-sorted
            if group:
                sections.append(DigestSection(topic=topic, subtopic=sub,
                                              article_keys=[a.identity for a in group[: settings.digest_per_subtopic]]))
    overview = None
    errors: list[str] = []
    if llm is not None and articles:
        top = articles[:8]
        stories = "\n".join(f"[{i + 1}] {a.title}: {truncate(a.summary, 220)}" for i, a in enumerate(top))
        try:
            overview = llm.complete(SYSTEM, stories)
        except LLMError as exc:
            errors.append(f"generate_digest: overview skipped: {exc}")
    digest = Digest(digest_date=local_today(settings.timezone), overview=overview, sections=sections)
    return {"digest": digest, "errors": errors,
            "stats": {"digest_sections": len(sections), "digest_articles": sum(len(s.article_keys) for s in sections)}}
