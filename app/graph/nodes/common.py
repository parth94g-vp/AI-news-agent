from __future__ import annotations

import functools
import logging
from typing import Callable

from app.graph.state import NewsState
from app.logging_config import get_logger, log_event

logger = get_logger("app.graph")


def safe_node(name: str) -> Callable:
    """Turn any exception inside a node into a recorded error instead of a crash.

    The node returns only `{"errors": [...]}`, so the previous `articles` stay in
    state and the pipeline degrades gracefully instead of aborting.
    """
    def decorator(fn: Callable[..., dict]) -> Callable[..., dict]:
        @functools.wraps(fn)
        def wrapper(state: NewsState, *args, **kwargs) -> dict:
            try:
                result = fn(state, *args, **kwargs)
                stats = result.get("stats", {})
                log_event(logger, "node_finished", node=name, **{f"stat_{k}": v for k, v in stats.items()})
                return result
            except Exception as exc:  # noqa: BLE001
                log_event(logger, "node_failed", logging.ERROR, node=name, error=f"{type(exc).__name__}: {exc}")
                return {"errors": [f"{name}: {type(exc).__name__}: {exc}"]}
        return wrapper
    return decorator
