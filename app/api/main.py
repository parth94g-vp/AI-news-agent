"""FastAPI backend for the React frontend. A thin HTTP layer: every endpoint calls
straight into the existing app.bootstrap / app.pipeline / app.database.repositories /
app.assistant code, unchanged. No business logic lives here.

Run:  uvicorn app.api.main:app --reload --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.schemas import (AssistantRequest, AssistantResponseModel, CreateUserRequest,
                             FeedbackRequest, PreferencesRequest, RefreshResponse,
                             SavedToggleResponse, UserResponse)
from app.bootstrap import build_services
from app.logging_config import get_logger, log_event
from app.pipeline import run_pipeline
from app.schemas import DigestView
from app.taxonomy import TAXONOMY

logger = get_logger(__name__)
app = FastAPI(title="AI News Agent API", version="1.0")

# Local dev: Vite's default port, plus 127.0.0.1 variants. Tighten this before deploying publicly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

svc = build_services()


def _news_disabled() -> None:
    if svc.deps is None:
        raise HTTPException(503, "News/LLM not configured on the server: " + "; ".join(svc.config_problems))


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "config_problems": svc.config_problems}


@app.get("/api/taxonomy")
def taxonomy() -> dict:
    return {topic: list(subs) for topic, subs in TAXONOMY.items()}


@app.post("/api/users", response_model=UserResponse)
def create_user(body: CreateUserRequest) -> UserResponse:
    try:
        uid, uname = svc.repo.create_or_get_user(body.username)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return UserResponse(user_id=uid, username=uname)


@app.get("/api/users/{user_id}/preferences")
def get_preferences(user_id: int) -> dict:
    return svc.repo.get_preferences(user_id)


@app.put("/api/users/{user_id}/preferences")
def set_preferences(user_id: int, body: PreferencesRequest) -> dict:
    try:
        svc.repo.set_preferences(user_id, body.preferences)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return svc.repo.get_preferences(user_id)


@app.post("/api/users/{user_id}/refresh", response_model=RefreshResponse)
def refresh_news(user_id: int) -> RefreshResponse:
    """Synchronous: can take 30-90s depending on how many subtopics are selected."""
    _news_disabled()
    try:
        result = run_pipeline(user_id, svc.deps)
    except ValueError as exc:  # e.g. no preferences selected
        raise HTTPException(400, str(exc)) from exc
    log_event(logger, "api_refresh", user_id=user_id, saved=result.saved_count)
    return RefreshResponse(saved_count=result.saved_count,
                           digest_date=result.digest_date.isoformat() if result.digest_date else None,
                           stats=result.stats, errors=result.errors)


@app.get("/api/users/{user_id}/digest", response_model=DigestView | None)
def get_digest(user_id: int, date: str | None = None) -> DigestView | None:
    from datetime import date as date_cls
    digest_date = date_cls.fromisoformat(date) if date else None
    return svc.repo.get_digest(user_id, digest_date)


@app.get("/api/users/{user_id}/saved")
def list_saved(user_id: int) -> list:
    return svc.repo.list_saved(user_id)


@app.post("/api/users/{user_id}/articles/{article_id}/save", response_model=SavedToggleResponse)
def toggle_saved(user_id: int, article_id: int) -> SavedToggleResponse:
    saved = svc.repo.toggle_saved(user_id, article_id)
    return SavedToggleResponse(article_id=article_id, saved=saved)


@app.post("/api/users/{user_id}/articles/{article_id}/feedback")
def set_feedback(user_id: int, article_id: int, body: FeedbackRequest) -> dict:
    if body.rating not in (-1, 1):
        raise HTTPException(400, "rating must be +1 or -1")
    svc.repo.set_feedback(user_id, article_id, body.rating, body.comment)
    return {"ok": True}


@app.post("/api/users/{user_id}/assistant", response_model=AssistantResponseModel)
def ask_assistant(user_id: int, body: AssistantRequest) -> AssistantResponseModel:
    _news_disabled()
    try:
        result = svc.assistant.answer(body.question, user_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    sources = [{"id": s.id, "title": s.title, "url": s.url, "source": s.source} for s in result.sources]
    return AssistantResponseModel(answer=result.answer, sources=sources)
