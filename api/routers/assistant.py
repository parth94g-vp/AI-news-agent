from __future__ import annotations

from fastapi.concurrency import run_in_threadpool

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_services
from api.routers.news import _article_out
from api.schemas import AssistantIn, AssistantOut
from app.bootstrap import Services

router = APIRouter(prefix="/api/users/{user_id}/assistant", tags=["assistant"])


@router.post("", response_model=AssistantOut)
async def ask(user_id: int, body: AssistantIn, services: Services = Depends(get_services)) -> AssistantOut:
    if services.assistant is None:
        raise HTTPException(503, f"Assistant is not configured: {'; '.join(services.config_problems)}")
    try:
        result = await run_in_threadpool(services.assistant.answer, body.question, user_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return AssistantOut(answer=result.answer, sources=[_article_out(a) for a in result.sources])
