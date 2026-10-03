from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_services
from api.routers.news import _article_out
from api.schemas import ArticleOut, FeedbackIn, SaveOut
from app.bootstrap import Services

router = APIRouter(prefix="/api/users/{user_id}", tags=["articles"])


@router.get("/saved", response_model=list[ArticleOut])
def list_saved(user_id: int, services: Services = Depends(get_services)) -> list[ArticleOut]:
    return [_article_out(a) for a in services.repo.list_saved(user_id)]


@router.post("/articles/{article_id}/save", response_model=SaveOut)
def toggle_save(user_id: int, article_id: int, services: Services = Depends(get_services)) -> SaveOut:
    return SaveOut(saved=services.repo.toggle_saved(user_id, article_id))


@router.post("/articles/{article_id}/feedback", status_code=204)
def set_feedback(user_id: int, article_id: int, body: FeedbackIn, services: Services = Depends(get_services)) -> None:
    try:
        services.repo.set_feedback(user_id, article_id, body.rating, body.comment)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
