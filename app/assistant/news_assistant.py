"""Q&A over the news already collected in SQLite (retrieval-augmented, citation-based).

Flow: plan (LLM, heuristic fallback) -> retrieve from SQLite -> answer strictly from context.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta

from app.config.settings import Settings
from app.database.repositories import NewsRepository
from app.logging_config import get_logger, log_event
from app.schemas import ArticleView
from app.services.groq_service import LLMClient, LLMError
from app.taxonomy import SUBTOPIC_TO_TOPIC, TAXONOMY, taxonomy_prompt
from app.utils.text import truncate
from app.utils.timeutils import format_local, utcnow

logger = get_logger(__name__)

PLAN_SYSTEM = f"""TASK: PLAN
Decide what news to retrieve to answer the user's question. Categories available (Topic > Subtopic):
{taxonomy_prompt()}
Return ONLY JSON: {{"topics": ["<Subtopic or Topic names that apply, may be empty>"],
"keywords": ["<specific entities / words to look for, lowercase>"],
"intent": "summary" | "compare" | "lookup" | "overview"}}"""

ANSWER_SYSTEM = """TASK: ANSWER
You are a news assistant. Answer the question using ONLY the numbered articles provided.
- Cite sources inline like [1] or [2][3] after each claim.
- If the articles do not contain the answer, say so plainly. Never use outside knowledge or guess.
- For comparisons, contrast the stories explicitly. For summaries, group related stories.
- Be concise (under 200 words unless the user asks for more)."""

_STOP = {"the", "a", "an", "of", "in", "on", "and", "or", "to", "is", "are", "was", "were", "what", "which", "who",
         "how", "about", "me", "show", "tell", "give", "today", "todays", "today's", "news", "stories", "story",
         "major", "latest", "any", "all", "from", "with", "for", "happened", "summarize", "summary", "compare",
         "related", "there", "this", "that", "please", "did", "do", "does", "us", "my", "top", "biggest", "main"}


@dataclass
class AssistantAnswer:
    answer: str
    sources: list[ArticleView] = field(default_factory=list)


@dataclass
class Plan:
    topics: list[str]
    keywords: list[str]
    intent: str = "lookup"


def heuristic_plan(question: str) -> Plan:
    q = question.lower()
    topics = [t for t, subs in TAXONOMY.items() if re.search(rf"\b{re.escape(t.lower())}\b", q)]
    for topic, subs in TAXONOMY.items():
        for sub, kws in subs.items():
            names = (sub, *kws)
            if any(re.search(rf"\b{re.escape(n.lower())}\b", q) for n in names):
                topics.append(sub)
    words = [w for w in re.findall(r"[a-z0-9][a-z0-9\-\.]+", q) if w not in _STOP and len(w) > 2]
    intent = "compare" if "compare" in q else "summary" if "summar" in q else "overview" if "major" in q else "lookup"
    return Plan(topics=list(dict.fromkeys(topics)), keywords=list(dict.fromkeys(words)), intent=intent)


class NewsAssistant:
    def __init__(self, repo: NewsRepository, llm: LLMClient, settings: Settings) -> None:
        self._repo, self._llm, self._s = repo, llm, settings

    def plan(self, question: str) -> Plan:
        base = heuristic_plan(question)
        try:
            data = self._llm.complete_json(PLAN_SYSTEM, question)
            topics = [t for t in data.get("topics", []) if t in SUBTOPIC_TO_TOPIC or t in TAXONOMY]
            kws = [str(k).lower() for k in data.get("keywords", []) if str(k).strip()]
            return Plan(topics=topics or base.topics, keywords=kws or base.keywords,
                        intent=str(data.get("intent", base.intent)))
        except (LLMError, AttributeError, TypeError, ValueError) as exc:
            log_event(logger, "assistant_plan_fallback", error=str(exc))
            return base

    def retrieve(self, plan: Plan, user_id: int | None = None) -> list[ArticleView]:
        since = utcnow() - timedelta(hours=self._s.assistant_window_hours)
        candidates = self._repo.recent_articles(since, user_id=user_id)
        wanted_subs = {t for t in plan.topics if t in SUBTOPIC_TO_TOPIC}
        wanted_topics = {t for t in plan.topics if t in TAXONOMY}
        scored: list[tuple[float, ArticleView]] = []
        for a in candidates:
            score = 0.0
            if a.subtopic in wanted_subs:
                score += 3
            if a.topic in wanted_topics:
                score += 2
            title, summ, body = a.title.lower(), (a.summary or "").lower(), (a.content or "").lower()
            for kw in plan.keywords:
                pat = rf"\b{re.escape(kw)}\b"
                score += 3 * bool(re.search(pat, title)) + 2 * bool(re.search(pat, summ)) + bool(re.search(pat, body))
            has_filter = bool(plan.topics or plan.keywords)
            if score > 0 or not has_filter:
                scored.append((score, a))
        scored.sort(key=lambda x: (x[0], x[1].published_at or utcnow().replace(year=2000)), reverse=True)
        return [a for _, a in scored[: self._s.assistant_context_articles]]

    def answer(self, question: str, user_id: int | None = None) -> AssistantAnswer:
        question = (question or "").strip()
        if len(question) < 3:
            raise ValueError("Please ask a longer question.")
        plan = self.plan(question)
        sources = self.retrieve(plan, user_id)
        log_event(logger, "assistant_retrieved", intent=plan.intent, topics=plan.topics,
                  keywords=plan.keywords[:8], sources=len(sources))
        if not sources:
            return AssistantAnswer(
                "I couldn't find anything about that in the news collected recently. "
                "Try refreshing your news, or ask about a topic you follow.")
        context = "\n\n".join(
            f"[{i}] {a.title}\nSource: {a.source} | {format_local(a.published_at, self._s.timezone)} | "
            f"{a.topic or 'Uncategorized'} > {a.subtopic or '-'}\nSummary: {a.summary or ''}\n"
            f"Excerpt: {truncate(a.content, 700)}" for i, a in enumerate(sources, 1))
        try:
            text = self._llm.complete(ANSWER_SYSTEM, f"Articles:\n{context}\n\nQuestion: {question}")
        except LLMError as exc:
            log_event(logger, "assistant_llm_failed", error=str(exc))
            listing = "\n".join(f"[{i}] {a.title} ({a.source})" for i, a in enumerate(sources, 1))
            return AssistantAnswer(f"The AI service is unavailable right now. Here are the most relevant stories:\n\n{listing}", sources)
        return AssistantAnswer(text, sources)
