"""Sign-in. No password yet (item #7 will add proper accounts) - same behavior as the
Streamlit app: a username creates or finds a profile."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_services
from api.schemas import LoginRequest, UserOut
from app.bootstrap import Services

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, services: Services = Depends(get_services)) -> UserOut:
    try:
        user_id, username = services.repo.create_or_get_user(body.username)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return UserOut(user_id=user_id, username=username)
