"""Application service: run the LangGraph pipeline for one user."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.graph.graph import Dependencies, build_graph
from app.logging_config import get_logger, log_event

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    digest_date: date | None
    saved_count: int
    stats: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def run_pipeline(user_id: int, deps: Dependencies) -> PipelineResult:
    prefs = deps.repo.get_preferences(user_id)
    if not prefs:
        raise ValueError("Select at least one subtopic before refreshing your news.")
    graph = build_graph(deps)
    final = graph.invoke({"user_id": user_id, "preferences": prefs, "articles": [],
                          "digest": None, "errors": [], "stats": {}})
    digest = final.get("digest")
    result = PipelineResult(digest_date=digest.digest_date if digest else None,
                            saved_count=final.get("saved_count", 0),
                            stats=final.get("stats", {}), errors=final.get("errors", []))
    log_event(logger, "pipeline_finished", user_id=user_id, saved=result.saved_count,
              errors=len(result.errors), **{f"stat_{k}": v for k, v in result.stats.items()})
    return result
