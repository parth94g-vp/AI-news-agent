import pytest
import requests

from app.services.news_api import (FreeNewsApiProvider, NewsAPIAuthError, NewsAPIError, NewsAPIRateLimitError)
from app.schemas import ArticleData


class Resp:
    def __init__(self, status=200, payload=None, headers=None, bad_json=False):
        self.status_code, self._p, self.headers, self._bad = status, payload, headers or {}, bad_json
        self.text = "err"

    def json(self):
        if self._bad:
            raise ValueError("bad")
        return self._p


class Session:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers, timeout))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def provider(*responses, retries=2):
    s = Session(*responses)
    return FreeNewsApiProvider("k", min_interval=0, max_retries=retries, session=s, sleep=lambda _: None), s


LISTING = {"data": [
    {"uuid": "u1", "title": "AI breakthrough announced", "published_at": "2026-04-03T04:51:12.000Z", "publisher": "Guardian"},
    {"uuid": None, "title": "malformed"}, "junk", {"uuid": "u3", "title": ""},
]}


def test_search_parses_and_skips_malformed():
    p, s = provider(Resp(payload=LISTING))
    arts = p.search("ai", limit=5)
    assert [a.external_id for a in arts] == ["u1"] and arts[0].source == "Guardian"
    assert s.calls[0][2]["x-api-key"] == "k" and s.calls[0][3] == 15.0


def test_empty_results():
    p, _ = provider(Resp(payload={"data": []}))
    assert p.search("ai") == []


def test_rate_limit_retries_then_succeeds():
    p, s = provider(Resp(429, headers={"Retry-After": "1"}), Resp(payload={"data": []}))
    assert p.search("ai") == [] and len(s.calls) == 2


def test_rate_limit_exhausted():
    p, _ = provider(Resp(429), Resp(429), retries=1)
    with pytest.raises(NewsAPIRateLimitError):
        p.search("ai")


def test_auth_error_not_retried():
    p, s = provider(Resp(401))
    with pytest.raises(NewsAPIAuthError):
        p.search("ai")
    assert len(s.calls) == 1


def test_timeout_and_malformed_json():
    p, _ = provider(requests.Timeout(), requests.Timeout(), requests.Timeout(), retries=2)
    with pytest.raises(NewsAPIError):
        p.search("ai")
    p2, _ = provider(Resp(bad_json=True))
    with pytest.raises(NewsAPIError):
        p2.search("ai")
    p3, _ = provider(Resp(payload={"nope": 1}))
    with pytest.raises(NewsAPIError):
        p3.search("ai")


def test_fetch_content_normalizes_details():
    details = {"data": {"uuid": "u1", "publisher": "The Guardian", "authors": ["https://x/profile", "Jane Doe"],
                        "topics": ["tech"], "original_url": "https://g.co/a", "thumbnail": "https://g.co/i.jpg",
                        "body": "Body text " * 20}}
    p, _ = provider(Resp(payload=details))
    out = p.fetch_content(ArticleData(external_id="u1", title="AI breakthrough"))
    assert out.url == "https://g.co/a" and out.author == "Jane Doe" and out.source == "The Guardian"
    assert out.description and out.content.startswith("Body text")


def test_empty_query_rejected():
    p, _ = provider()
    with pytest.raises(ValueError):
        p.search("  ")


def test_search_uses_in_title_not_removed_q_param():
    p, s = provider(Resp(payload={"data": []}))
    p.search("artificial intelligence")
    params = s.calls[0][1]
    assert params["in_title"] == "artificial intelligence" and "q" not in params


def test_search_degrades_params_on_server_error():
    ok = Resp(payload={"data": [{"uuid": "u1", "title": "AI breakthrough announced today",
                                 "published_at": "2999-01-01T00:00:00Z", "publisher": "X"}]})
    p, s = provider(Resp(500), Resp(500), Resp(500), Resp(500), ok)  # variant1 x2, variant2 x2, variant3 ok
    from datetime import datetime, timezone
    arts = p.search("ai", limit=5, since=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert len(arts) == 1
    assert "published_after" in s.calls[0][1] and "published_after" not in s.calls[2][1]
    assert "page_size" not in s.calls[4][1]


def test_search_filters_old_articles_client_side():
    from datetime import datetime, timezone
    old = {"uuid": "u1", "title": "Old story about AI models", "published_at": "2020-01-01T00:00:00Z"}
    p, _ = provider(Resp(payload={"data": [old]}))
    assert p.search("ai", since=datetime(2026, 1, 1, tzinfo=timezone.utc)) == []



from app.services.news_api import NewsDataIoProvider, build_provider  # noqa: E402


def nd_provider(*responses, retries=2):
    s = Session(*responses)
    return NewsDataIoProvider("k", min_interval=0, max_retries=retries, session=s, sleep=lambda _: None), s


ND_ITEM = {"article_id": "a1", "title": "AI breakthrough announced", "link": "https://n.example/1",
           "description": "A short description of the story.", "content": "ONLY AVAILABLE IN PAID PLANS",
           "pubDate": "2026-04-03 04:51:12", "source_id": "guardian", "source_name": "The Guardian",
           "creator": ["Jane Doe"], "image_url": "https://n.example/1.jpg"}


def test_newsdata_parses_and_falls_back_to_description_as_content():
    p, s = nd_provider(Resp(payload={"status": "success", "results": [ND_ITEM]}))
    arts = p.search("ai")
    assert len(arts) == 1
    a = arts[0]
    assert a.external_id == "a1" and a.url == "https://n.example/1" and a.source == "The Guardian"
    assert a.content == "A short description of the story." and a.author == "Jane Doe"
    assert s.calls[0][1]["apikey"] == "k" and s.calls[0][1]["qInTitle"] == "ai"


def test_newsdata_auth_error():
    p, _ = nd_provider(Resp(401, payload={"status": "error", "results": {"message": "Invalid API key", "code": "x"}}))
    with pytest.raises(NewsAPIAuthError):
        p.search("ai")


def test_newsdata_fetch_content_is_noop():
    p, _ = nd_provider()
    art = ArticleData(title="t", url="https://x", content="c")
    assert p.fetch_content(art) is art


def test_newsdata_skips_malformed_items():
    p, s = nd_provider(Resp(payload={"status": "success", "results": [{"title": "no link"}, ND_ITEM]}))
    assert len(p.search("ai")) == 1


def test_build_provider_auto_detects_newsdata(settings):
    from dataclasses import replace
    s = replace(settings, newsdata_api_key="k", news_api_key="")
    assert isinstance(build_provider(s), NewsDataIoProvider)


def test_build_provider_defaults_to_freenewsapi(settings):
    from dataclasses import replace
    s = replace(settings, news_api_key="k", newsdata_api_key="")
    from app.services.news_api import FreeNewsApiProvider
    assert isinstance(build_provider(s), FreeNewsApiProvider)
