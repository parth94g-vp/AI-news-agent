"""Typed LangGraph state.

Every node receives the full state and returns a *partial* dict; LangGraph merges it:
  - `articles`  : no reducer -> a node's returned list REPLACES the previous list
  - `errors`    : operator.add -> errors from every node accumulate
  - `stats`     : merged dict -> each node reports its own counters
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from app.schemas import Digest, WorkingArticle


def merge_stats(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    return {**(left or {}), **(right or {})}


class NewsState(TypedDict, total=False):
    user_id: int
    preferences: dict[str, list[str]]           # topic -> selected subtopics
    articles: list[WorkingArticle]
    digest: Digest | None
    saved_count: int
    errors: Annotated[list[str], operator.add]
    stats: Annotated[dict[str, Any], merge_stats]
