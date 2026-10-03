"""News provider integration. ONLY this module knows FreeNewsAPI's wire format.

To swap providers, implement `NewsProvider` and return `ArticleData` objects.

FreeNewsAPI contract (https://www.freenewsapi.io/docs/):
  GET /v1/news     -> lightweight list: uuid, title, published_at, publisher
  GET /v1/details  -> full article: body, original_url, thumbnail, authors, topics
  Auth via `x-api-key` header. Free tier: 5,000 req/day, 2 req/sec.
"""
from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable

import requests

from app.logging_config import get_logger, log_event
from app.schemas import ArticleData
from app.utils.text import truncate

logger = get_logger(__name__)


class NewsAPIError(Exception):
    """Any provider failure (network, HTTP, malformed payload)."""


class NewsAPIAuthError(NewsAPIError):
    """Invalid / missing API key (do not retry)."""


class NewsAPIServerError(NewsAPIError):
    """HTTP 5xx from the provider (may be caused by an unsupported parameter)."""


class NewsAPIRateLimitError(NewsAPIError):
    """Rate limit still exceeded after retries."""


class NewsProvider(ABC):
    @abstractmethod
    def search(self, query: str, *, limit: int = 10, since: datetime | None = None) -> list[ArticleData]:
        """Discover recent articles matching `query` (metadata only is fine)."""

    @abstractmethod
    def fetch_content(self, article: ArticleData) -> ArticleData:
        """Return `article` enriched with body/url/etc. Raises NewsAPIError on failure."""


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _first_author(authors: Any) -> str | None:
    if not isinstance(authors, list):
        return None
    for a in authors:
        if isinstance(a, str) and a.strip() and not a.lower().startswith("http"):
            return a.strip()
    return None


class FreeNewsApiProvider(NewsProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.freenewsapi.io",
        *,
        timeout: float = 15.0,
        language: str = "en",
        country: str = "",
        order_by: str = "",
        min_interval: float = 0.6,
        max_retries: int = 3,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise NewsAPIAuthError("FREENEWSAPI_API_KEY is missing")
        self._base = base_url.rstrip("/")
        self._headers = {"x-api-key": api_key, "Accept": "application/json"}
        self._timeout = timeout
        self._language, self._country, self._order_by = language, country, order_by
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._session = session or requests.Session()
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last_call = 0.0

    # ---------------------------------------------------------------- HTTP
    def _throttle(self) -> None:
        with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                self._sleep(wait)
            self._last_call = time.monotonic()

    def _get(self, path: str, params: dict[str, Any], max_retries: int | None = None) -> dict[str, Any]:
        url = f"{self._base}{path}"
        last_error = "unknown error"
        retries = self._max_retries if max_retries is None else max_retries
        for attempt in range(retries + 1):
            self._throttle()
            backoff = 1.5 * (2 ** attempt)
            try:
                resp = self._session.get(url, params=params, headers=self._headers, timeout=self._timeout)
            except requests.Timeout:
                last_error = "request timed out"
            except requests.RequestException as exc:
                raise NewsAPIError(f"network error calling {path}: {exc}") from exc
            else:
                status = resp.status_code
                if status in (401, 403):
                    raise NewsAPIAuthError(f"{path}: authentication failed (HTTP {status})")
                if status == 429:
                    last_error = "rate limited (HTTP 429)"
                    try:
                        backoff = max(backoff, float(resp.headers.get("Retry-After", 0)))
                    except ValueError:
                        pass
                    if attempt >= retries:
                        raise NewsAPIRateLimitError(f"{path}: {last_error}")
                elif status >= 500:
                    last_error = f"server error (HTTP {status})"
                elif status >= 400:
                    raise NewsAPIError(f"{path}: HTTP {status}: {truncate(resp.text, 200)}")
                else:
                    try:
                        payload = resp.json()
                    except ValueError as exc:
                        raise NewsAPIError(f"{path}: response was not valid JSON") from exc
                    if not isinstance(payload, dict) or "data" not in payload:
                        raise NewsAPIError(f"{path}: unexpected response shape")
                    return payload
            if attempt < retries:
                log_event(logger, "news_api_retry", logging.WARNING, path=path, attempt=attempt + 1,
                          reason=last_error, wait=backoff)
                self._sleep(backoff)
        exc_type = NewsAPIServerError if last_error.startswith("server error") else NewsAPIError
        raise exc_type(f"{path}: {last_error} after {retries + 1} attempts")

    # ------------------------------------------------------------ Provider
    def search(self, query: str, *, limit: int = 10, since: datetime | None = None) -> list[ArticleData]:
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        base: dict[str, Any] = {"in_title": query.strip(), "language": self._language}
        if self._country:
            base["country"] = self._country
        if self._order_by:
            base["order_by"] = self._order_by
        optional: dict[str, Any] = {"page_size": max(1, limit)}
        if since:
            optional["published_after"] = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # If the API answers 5xx, retry with fewer optional parameters (dates are then filtered client-side).
        variants = [{**base, **optional},
                    {**base, **{k: v for k, v in optional.items() if k != "published_after"}},
                    dict(base)]
        payload: dict[str, Any] | None = None
        for i, params in enumerate(variants):
            last = i == len(variants) - 1
            try:
                payload = self._get("/v1/news", params, max_retries=None if last else 1)
                if i:
                    log_event(logger, "news_search_degraded", logging.WARNING, query=query, dropped=sorted(set(variants[0]) - set(params)))
                break
            except NewsAPIServerError:
                if last:
                    raise
        items = (payload or {}).get("data")
        if not isinstance(items, list):
            raise NewsAPIError("/v1/news: 'data' is not a list")
        articles: list[ArticleData] = []
        for item in items:
            art = self._parse_listing(item)
            if art and (since is None or art.published_at is None or art.published_at >= since):
                articles.append(art)
        log_event(logger, "news_search", query=query, returned=len(items), parsed=len(articles))
        return articles[:limit]

    def fetch_content(self, article: ArticleData) -> ArticleData:
        if not article.external_id:
            raise NewsAPIError("cannot fetch details without an external_id")
        payload = self._get("/v1/details", {"uuid": article.external_id})
        data = payload.get("data")
        if not isinstance(data, dict):
            raise NewsAPIError("/v1/details: 'data' is not an object")
        body = data.get("body") if isinstance(data.get("body"), str) else None
        update: dict[str, Any] = {
            "content": body,
            "url": data.get("original_url") if isinstance(data.get("original_url"), str) else article.url,
            "image_url": data.get("thumbnail") if isinstance(data.get("thumbnail"), str) else article.image_url,
            "author": _first_author(data.get("authors")) or article.author,
            "provider_topics": [t for t in data.get("topics", []) if isinstance(t, str)],
            "published_at": _parse_dt(data.get("published_at")) or article.published_at,
        }
        if not article.description and body:
            update["description"] = truncate(body, 300)
        if isinstance(data.get("publisher"), str) and data["publisher"]:
            update["source"] = data["publisher"]
        return article.model_copy(update=update)

    # -------------------------------------------------------------- parsing
    @staticmethod
    def _parse_listing(item: Any) -> ArticleData | None:
        if not isinstance(item, dict):
            return None
        title, uuid = item.get("title"), item.get("uuid")
        if not isinstance(title, str) or not title.strip() or not isinstance(uuid, str):
            return None
        publisher = item.get("publisher")
        return ArticleData(
            external_id=uuid,
            title=title.strip(),
            source=publisher.strip() if isinstance(publisher, str) and publisher.strip() else "Unknown",
            published_at=_parse_dt(item.get("published_at")),
        )


class NewsDataIoProvider(NewsProvider):
    """https://newsdata.io/documentation - free tier: 200 credits/day, ~10 articles/credit.

    The /latest endpoint already returns description + link + image in one call, so
    `fetch_content` is a no-op here: there is no separate "full body" endpoint on the free plan.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://newsdata.io/api/1",
        *,
        timeout: float = 15.0,
        language: str = "en",
        country: str = "",
        min_interval: float = 1.0,
        max_retries: int = 3,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise NewsAPIAuthError("NEWSDATA_API_KEY is missing")
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._language, self._country = language, country
        self._min_interval, self._max_retries = min_interval, max_retries
        self._session = session or requests.Session()
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last_call = 0.0

    def _throttle(self) -> None:
        with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                self._sleep(wait)
            self._last_call = time.monotonic()

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base}{path}"
        params = {**params, "apikey": self._api_key}
        last_error = "unknown error"
        for attempt in range(self._max_retries + 1):
            self._throttle()
            backoff = 1.5 * (2 ** attempt)
            try:
                resp = self._session.get(url, params=params, timeout=self._timeout)
            except requests.Timeout:
                last_error = "request timed out"
            except requests.RequestException as exc:
                raise NewsAPIError(f"network error calling {path}: {exc}") from exc
            else:
                status = resp.status_code
                try:
                    payload = resp.json()
                except ValueError:
                    payload = None
                server_msg = (payload or {}).get("results", {}) if isinstance(payload, dict) else {}
                msg = server_msg.get("message") if isinstance(server_msg, dict) else None
                if status in (401, 403) or (isinstance(payload, dict) and payload.get("status") == "error"
                                            and (status in (401, 403) or "key" in (msg or "").lower())):
                    raise NewsAPIAuthError(f"{path}: authentication failed: {msg or f'HTTP {status}'}")
                if status == 429 or (msg and "rate" in msg.lower()):
                    last_error = f"rate limited: {msg or 'HTTP 429'}"
                    if attempt >= self._max_retries:
                        raise NewsAPIRateLimitError(f"{path}: {last_error}")
                elif status >= 500:
                    last_error = f"server error (HTTP {status})"
                elif status >= 400 or (isinstance(payload, dict) and payload.get("status") == "error"):
                    raise NewsAPIError(f"{path}: {msg or f'HTTP {status}: {truncate(resp.text, 200)}'}")
                elif payload is None:
                    raise NewsAPIError(f"{path}: response was not valid JSON")
                elif "results" not in payload:
                    raise NewsAPIError(f"{path}: unexpected response shape")
                else:
                    return payload
            if attempt < self._max_retries:
                log_event(logger, "news_api_retry", logging.WARNING, path=path, attempt=attempt + 1,
                          reason=last_error, wait=backoff)
                self._sleep(backoff)
        exc_type = NewsAPIServerError if last_error.startswith("server error") else NewsAPIError
        raise exc_type(f"{path}: {last_error} after {self._max_retries + 1} attempts")

    def search(self, query: str, *, limit: int = 10, since: datetime | None = None) -> list[ArticleData]:
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        params: dict[str, Any] = {"qInTitle": query.strip(), "language": self._language}
        if self._country:
            params["country"] = self._country
        payload = self._get("/latest", params)
        items = payload.get("results")
        if not isinstance(items, list):
            raise NewsAPIError("/latest: 'results' is not a list")
        articles: list[ArticleData] = []
        for item in items:
            art = self._parse(item)
            if art and (since is None or art.published_at is None or art.published_at >= since):
                articles.append(art)
        log_event(logger, "news_search", query=query, returned=len(items), parsed=len(articles))
        return articles[:limit]

    def fetch_content(self, article: ArticleData) -> ArticleData:
        return article  # the /latest call already returned everything the free plan offers

    @staticmethod
    def _parse(item: Any) -> ArticleData | None:
        if not isinstance(item, dict):
            return None
        title, link = item.get("title"), item.get("link")
        if not isinstance(title, str) or not title.strip() or not isinstance(link, str) or not link.strip():
            return None
        description = item.get("description") if isinstance(item.get("description"), str) else None
        content = item.get("content")
        if not isinstance(content, str) or not content.strip() or "ONLY AVAILABLE IN PAID PLANS" in content:
            content = description  # free tier: no separate full body, use the description as the article text
        pub = item.get("pubDate")
        published_at = None
        if isinstance(pub, str) and pub.strip():
            try:
                published_at = datetime.strptime(pub.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except ValueError:
                published_at = _parse_dt(pub)
        creators = item.get("creator")
        author = creators[0].strip() if isinstance(creators, list) and creators and isinstance(creators[0], str) else None
        source = item.get("source_name") or item.get("source_id")
        return ArticleData(
            external_id=item.get("article_id") if isinstance(item.get("article_id"), str) else None,
            title=title.strip(), description=description, content=content, url=link.strip(),
            source=source.strip() if isinstance(source, str) and source.strip() else "Unknown",
            author=author, published_at=published_at,
            image_url=item.get("image_url") if isinstance(item.get("image_url"), str) else None,
        )


def build_provider(settings: "Settings") -> NewsProvider:  # noqa: F821 - avoid import cycle; typed via duck-typing
    """Pick the configured news provider. NEWS_PROVIDER=freenewsapi|newsdata, or auto-detected from keys."""
    choice = (settings.news_provider or "").strip().lower()
    if not choice:
        choice = "newsdata" if settings.newsdata_api_key else "freenewsapi"
    if choice == "newsdata":
        return NewsDataIoProvider(settings.newsdata_api_key, settings.newsdata_base_url,
                                  timeout=settings.request_timeout, language=settings.news_language,
                                  country=settings.news_country, min_interval=settings.news_min_interval)
    if choice == "freenewsapi":
        return FreeNewsApiProvider(settings.news_api_key, settings.news_api_base_url,
                                   timeout=settings.request_timeout, language=settings.news_language,
                                   country=settings.news_country, order_by=settings.news_order_by,
                                   min_interval=settings.news_min_interval)
    raise ValueError(f"Unknown NEWS_PROVIDER: {choice!r} (expected 'freenewsapi' or 'newsdata')")
