"""Digest retrieval + triggering a refresh (runs the same LangGraph pipeline as the CLI/Streamlit app)."""
from __future__ import annotations

from fastapi.concurrency import run_in_threadpool

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_services
from api.schemas import ArticleOut, DigestOut, RefreshOut, TrendingItemOut
from app.bootstrap import Services
from app.pipeline import run_pipeline
from app.utils.timeutils import local_today

router = APIRouter(prefix="/api/users/{user_id}", tags=["news"])
trending_router = APIRouter(prefix="/api/trending", tags=["news"])


def _article_out(a) -> ArticleOut:  # app.schemas.ArticleView -> API ArticleOut
    return ArticleOut(**a.model_dump())


@router.get("/digest", response_model=DigestOut)
def get_digest(user_id: int, services: Services = Depends(get_services)) -> DigestOut:
    digest = services.repo.get_digest(user_id)
    if digest is None:
        raise HTTPException(404, "No digest yet. Call /refresh first.")
    return DigestOut(digest_date=digest.digest_date, overview=digest.overview,
                     is_stale=digest.digest_date != local_today(services.settings.timezone),
                     entries=[_article_out(e) for e in digest.entries])


@router.post("/refresh", response_model=RefreshOut)
async def refresh_news(user_id: int, services: Services = Depends(get_services)) -> RefreshOut:
    if services.deps is None:
        raise HTTPException(503, f"News agent is not configured: {'; '.join(services.config_problems)}")
    try:
        result = await run_in_threadpool(run_pipeline, user_id, services.deps)
    except ValueError as exc:  # e.g. no preferences selected
        raise HTTPException(422, str(exc)) from exc
    return RefreshOut(digest_date=result.digest_date, saved_count=result.saved_count,
                      stats=result.stats, errors=result.errors)


@trending_router.get("", response_model=list[TrendingItemOut])
def get_trending(services: Services = Depends(get_services)) -> list[TrendingItemOut]:
    s = services.settings
    items = services.repo.get_trending_subtopics(s.trending_baseline_days, s.trending_min_count, s.trending_ratio)
    return [TrendingItemOut(**i.model_dump()) for i in items]
