"""Builds shared services once (used by the Streamlit UI and scripts)."""
from __future__ import annotations

from dataclasses import dataclass

from app.assistant.news_assistant import NewsAssistant
from app.config.settings import Settings, get_settings
from app.database.connection import get_engine, init_db, make_session_factory
from app.database.repositories import NewsRepository
from app.graph.graph import Dependencies
from app.logging_config import setup_logging
from app.services.groq_service import GroqService
from app.services.news_api import build_provider


@dataclass
class Services:
    settings: Settings
    repo: NewsRepository
    deps: Dependencies | None       # None when API keys are missing
    assistant: NewsAssistant | None
    config_problems: list[str]


def build_services(settings: Settings | None = None) -> Services:
    settings = settings or get_settings()
    setup_logging(settings.log_level)
    engine = get_engine(settings.database_url)
    init_db(engine)
    repo = NewsRepository(make_session_factory(engine))
    repo.seed_taxonomy()
    problems: list[str] = []
    if not settings.groq_api_key:
        problems.append("GROQ_API_KEY is missing in .env")
    if not settings.news_api_key and not settings.newsdata_api_key:
        problems.append("Set NEWSDATA_API_KEY (or FREENEWSAPI_API_KEY) in .env")
    if problems:
        return Services(settings, repo, None, None, problems)
    llm = GroqService(settings.groq_api_key, settings.groq_model, timeout=settings.llm_timeout,
                      max_retries=settings.llm_max_retries)
    try:
        provider = build_provider(settings)
    except (ValueError, Exception) as exc:  # noqa: BLE001 - surface as a config problem, not a crash
        return Services(settings, repo, None, None, [f"News provider config error: {exc}"])
    return Services(settings, repo, Dependencies(provider, llm, repo, settings),
                    NewsAssistant(repo, llm, settings), [])
