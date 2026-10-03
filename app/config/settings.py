"""Central configuration. All values come from environment variables / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _get(env: Mapping[str, str], name: str, default: str = "") -> str:
    value = (env.get(name) or default).strip()
    return "" if value.lower().startswith("your_") else value  # untouched .env.example placeholders


def _num(env: Mapping[str, str], name: str, default, cast=int):
    raw = _get(env, name)
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


def _resolve_db_url(url: str) -> str:
    """Make relative sqlite paths independent of the working directory."""
    prefix = "sqlite:///./"
    if url.startswith(prefix):
        return f"sqlite:///{(PROJECT_ROOT / url[len(prefix):]).as_posix()}"
    return url


@dataclass(frozen=True)
class Settings:
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    news_provider: str = ""  # "freenewsapi" | "newsdata"; empty = auto-detect from which key is set
    news_api_key: str = ""
    news_api_base_url: str = "https://api.freenewsapi.io"
    newsdata_api_key: str = ""
    newsdata_base_url: str = "https://newsdata.io/api/1"
    news_language: str = "en"
    news_country: str = ""
    news_order_by: str = ""
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'news_agent.db').as_posix()}"
    log_level: str = "INFO"
    timezone: str = "Asia/Kolkata"
    request_timeout: float = 15.0
    news_min_interval: float = 0.6  # free tier: 2 requests / second
    llm_timeout: float = 45.0
    llm_max_retries: int = 3
    lookback_hours: int = 48
    articles_per_query: int = 8
    queries_per_subtopic: int = 1
    max_articles_to_process: int = 60
    max_articles_to_summarize: int = 24
    relevance_threshold: float = 0.45
    dedupe_similarity: float = 0.85
    digest_per_subtopic: int = 5
    max_content_chars: int = 3500
    assistant_context_articles: int = 8
    assistant_window_hours: int = 36
    # Trending
    trending_baseline_days: int = 7
    trending_min_count: int = 3
    trending_ratio: float = 1.6
    # Email (Gmail SMTP)
    gmail_address: str = ""
    gmail_app_password: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        e = os.environ if env is None else env
        d = cls()
        return cls(
            groq_api_key=_get(e, "GROQ_API_KEY"),
            groq_model=_get(e, "GROQ_MODEL", d.groq_model),
            news_provider=_get(e, "NEWS_PROVIDER").lower(),
            news_api_key=_get(e, "FREENEWSAPI_API_KEY"),
            news_api_base_url=_get(e, "FREENEWSAPI_BASE_URL", d.news_api_base_url).rstrip("/"),
            newsdata_api_key=_get(e, "NEWSDATA_API_KEY"),
            newsdata_base_url=_get(e, "NEWSDATA_BASE_URL", d.newsdata_base_url).rstrip("/"),
            news_language=_get(e, "NEWS_LANGUAGE", d.news_language),
            news_country=_get(e, "NEWS_COUNTRY"),
            news_order_by=_get(e, "FREENEWSAPI_ORDER_BY"),
            database_url=_resolve_db_url(_get(e, "DATABASE_URL", "sqlite:///./data/news_agent.db")),
            log_level=_get(e, "LOG_LEVEL", d.log_level).upper(),
            timezone=_get(e, "TIMEZONE", d.timezone),
            request_timeout=_num(e, "REQUEST_TIMEOUT", d.request_timeout, float),
            news_min_interval=_num(e, "NEWS_MIN_INTERVAL", d.news_min_interval, float),
            llm_timeout=_num(e, "LLM_TIMEOUT", d.llm_timeout, float),
            llm_max_retries=_num(e, "LLM_MAX_RETRIES", d.llm_max_retries),
            lookback_hours=_num(e, "LOOKBACK_HOURS", d.lookback_hours),
            articles_per_query=_num(e, "ARTICLES_PER_QUERY", d.articles_per_query),
            queries_per_subtopic=_num(e, "QUERIES_PER_SUBTOPIC", d.queries_per_subtopic),
            max_articles_to_process=_num(e, "MAX_ARTICLES_TO_PROCESS", d.max_articles_to_process),
            max_articles_to_summarize=_num(e, "MAX_ARTICLES_TO_SUMMARIZE", d.max_articles_to_summarize),
            relevance_threshold=_num(e, "RELEVANCE_THRESHOLD", d.relevance_threshold, float),
            dedupe_similarity=_num(e, "DEDUPE_SIMILARITY", d.dedupe_similarity, float),
            digest_per_subtopic=_num(e, "DIGEST_PER_SUBTOPIC", d.digest_per_subtopic),
            max_content_chars=_num(e, "MAX_CONTENT_CHARS", d.max_content_chars),
            assistant_context_articles=_num(e, "ASSISTANT_CONTEXT_ARTICLES", d.assistant_context_articles),
            assistant_window_hours=_num(e, "ASSISTANT_WINDOW_HOURS", d.assistant_window_hours),
            trending_baseline_days=_num(e, "TRENDING_BASELINE_DAYS", d.trending_baseline_days),
            trending_min_count=_num(e, "TRENDING_MIN_COUNT", d.trending_min_count),
            trending_ratio=_num(e, "TRENDING_RATIO", d.trending_ratio, float),
            gmail_address=_get(e, "GMAIL_ADDRESS"),
            gmail_app_password=_get(e, "GMAIL_APP_PASSWORD"),
            smtp_host=_get(e, "SMTP_HOST", d.smtp_host),
            smtp_port=_num(e, "SMTP_PORT", d.smtp_port),
        )

    def require_email(self) -> None:
        if not self.gmail_address or not self.gmail_app_password:
            raise ConfigError("Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in your .env file.")

    def require_groq(self) -> None:
        if not self.groq_api_key:
            raise ConfigError("GROQ_API_KEY is not set. Add it to your .env file.")

    def require_news_api(self) -> None:
        if not self.news_api_key and not self.newsdata_api_key:
            raise ConfigError("Set either NEWSDATA_API_KEY or FREENEWSAPI_API_KEY in your .env file.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings.from_env()
