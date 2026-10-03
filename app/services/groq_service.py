"""Groq (llama-3.3-70b-versatile) access through LangChain, with retries and JSON parsing."""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Callable, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from app.logging_config import get_logger, log_event

logger = get_logger(__name__)


class LLMError(Exception):
    """LLM call failed after retries, or returned unusable output."""


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str: ...
    def complete_json(self, system: str, user: str) -> Any: ...


def extract_json(text: str) -> Any:
    """Parse JSON from a model reply, tolerating code fences and surrounding prose."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    for open_c, close_c in (("[", "]"), ("{", "}")):
        start, end = cleaned.find(open_c), cleaned.rfind(close_c)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise LLMError(f"model did not return valid JSON: {cleaned[:120]!r}")


def _retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status == 429 or status >= 500
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return any(k in name or k in msg for k in ("timeout", "connection", "rate", "overloaded", "temporar"))


class GroqService:
    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        *,
        timeout: float = 45.0,
        max_retries: int = 3,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if client is None:
            if not api_key:
                raise LLMError("GROQ_API_KEY is missing")
            from langchain_groq import ChatGroq

            client = ChatGroq(model=model, api_key=api_key, temperature=temperature,
                              max_tokens=max_tokens, timeout=timeout, max_retries=0)
        self._client = client
        self._max_retries = max_retries
        self._sleep = sleep
        self.model = model

    def complete(self, system: str, user: str) -> str:
        messages = [SystemMessage(content=system), HumanMessage(content=user)]
        for attempt in range(self._max_retries + 1):
            try:
                reply = self._client.invoke(messages)
                text = reply.content if isinstance(reply.content, str) else str(reply.content)
                if not text.strip():
                    raise LLMError("empty response from model")
                return text.strip()
            except LLMError:
                raise
            except Exception as exc:  # noqa: BLE001 - provider exceptions vary
                if attempt < self._max_retries and _retryable(exc):
                    wait = 2.0 * (2 ** attempt)
                    log_event(logger, "llm_retry", logging.WARNING, attempt=attempt + 1,
                              error=type(exc).__name__, wait=wait)
                    self._sleep(wait)
                    continue
                raise LLMError(f"Groq request failed: {type(exc).__name__}: {exc}") from exc
        raise LLMError("Groq request failed")  # pragma: no cover

    def complete_json(self, system: str, user: str) -> Any:
        return extract_json(self.complete(system, user))
