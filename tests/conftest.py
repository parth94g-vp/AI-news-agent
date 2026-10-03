from __future__ import annotations

import json
from datetime import timedelta

import pytest

from app.config.settings import Settings
from app.database.connection import get_engine, init_db, make_session_factory
from app.database.repositories import NewsRepository
from app.graph.graph import Dependencies
from app.schemas import ArticleData
from app.services.groq_service import LLMError
from app.services.news_api import NewsAPIError, NewsProvider
from app.utils.timeutils import utcnow

BODY = ("This is a long enough article body describing the story in detail, with plenty of facts "
        "about the subject so that summarization has real material to work with. ") * 3


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", news_min_interval=0, timezone="UTC")


@pytest.fixture
def repo(settings) -> NewsRepository:
    engine = get_engine(settings.database_url)
    init_db(engine)
    r = NewsRepository(make_session_factory(engine))
    r.seed_taxonomy()
    return r


class FakeLLM:
    """Deterministic stand-in for Groq. Dispatches on the TASK marker in the system prompt."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[str] = []

    def _task(self, system: str) -> str:
        return system.split("\n", 1)[0].replace("TASK:", "").strip()

    def complete_json(self, system: str, user: str):
        task = self._task(system)
        self.calls.append(task)
        if self.fail:
            raise LLMError("boom")
        if task == "CLASSIFY":
            items = json.loads(user)["articles"]
            out = []
            for it in items:
                t = it["title"].lower()
                sub = ("Artificial Intelligence" if "ai" in t.split() or "openai" in t else
                       "Cybersecurity" if "breach" in t else "Cricket" if "cricket" in t else "Other")
                topic = {"Artificial Intelligence": "Technology", "Cybersecurity": "Technology", "Cricket": "Sports"}.get(sub, "Other")
                out.append({"id": it["id"], "topic": topic, "subtopic": sub, "confidence": 0.9})
            return out
        if task == "SUMMARIZE":
            return {"summary": "A concise AI summary.", "importance": 8}
        if task == "PLAN":
            return {"topics": ["Artificial Intelligence"], "keywords": ["openai"], "intent": "lookup"}
        raise AssertionError(task)

    def complete(self, system: str, user: str) -> str:
        task = self._task(system)
        self.calls.append(task)
        if self.fail:
            raise LLMError("boom")
        return "Overview text." if task == "OVERVIEW" else "OpenAI shipped a model [1]."


class FakeProvider(NewsProvider):
    def __init__(self, listing: list[ArticleData], fail_search: bool = False):
        self.listing, self.fail_search = listing, fail_search
        self.detail_calls = 0

    def search(self, query, *, limit=10, since=None):
        if self.fail_search:
            raise NewsAPIError("down")
        return [a for a in self.listing if True][:limit]

    def fetch_content(self, article):
        self.detail_calls += 1
        return article.model_copy(update={"content": BODY, "url": f"https://news.example/{article.external_id}",
                                          "description": "desc"})


def listing_item(uuid: str, title: str, hours_ago: float = 2) -> ArticleData:
    return ArticleData(external_id=uuid, title=title, source="Wire", published_at=utcnow() - timedelta(hours=hours_ago))


@pytest.fixture
def user_id(repo) -> int:
    uid, _ = repo.create_or_get_user("alice")
    repo.set_preferences(uid, {"Technology": ["Artificial Intelligence", "Cybersecurity"]})
    return uid


@pytest.fixture
def make_deps(repo, settings):
    def _make(listing, llm=None, fail_search=False):
        provider = FakeProvider(listing, fail_search)
        return Dependencies(provider, llm or FakeLLM(), repo, settings), provider
    return _make
