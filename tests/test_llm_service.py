import pytest

from app.services.groq_service import GroqService, LLMError, extract_json


class Reply:
    def __init__(self, content): self.content = content


class Client:
    def __init__(self, *items): self.items, self.n = list(items), 0

    def invoke(self, messages):
        self.n += 1
        it = self.items.pop(0)
        if isinstance(it, Exception):
            raise it
        return Reply(it)


class RateLimited(Exception):
    status_code = 429


def svc(*items, retries=2):
    c = Client(*items)
    return GroqService("k", client=c, max_retries=retries, sleep=lambda _: None), c


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! [1, 2] hope that helps') == [1, 2]
    with pytest.raises(LLMError):
        extract_json("no json here")


def test_retries_on_rate_limit_then_succeeds():
    s, c = svc(RateLimited("slow down"), "ok")
    assert s.complete("sys", "hi") == "ok" and c.n == 2


def test_non_retryable_error_fails_fast():
    class Bad(Exception): status_code = 400
    s, c = svc(Bad("nope"), "ok")
    with pytest.raises(LLMError):
        s.complete("s", "u")
    assert c.n == 1


def test_gives_up_after_retries():
    s, c = svc(RateLimited(), RateLimited(), RateLimited(), retries=2)
    with pytest.raises(LLMError):
        s.complete("s", "u")
    assert c.n == 3
