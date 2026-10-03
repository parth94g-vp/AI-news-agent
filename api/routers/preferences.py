from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_services
from api.schemas import EmailIn, PreferencesIn
from app.bootstrap import Services

router = APIRouter(prefix="/api/users/{user_id}/preferences", tags=["preferences"])


@router.get("", response_model=dict[str, list[str]])
def get_preferences(user_id: int, services: Services = Depends(get_services)) -> dict[str, list[str]]:
    return services.repo.get_preferences(user_id)


@router.put("", response_model=dict[str, list[str]])
def set_preferences(user_id: int, body: PreferencesIn, services: Services = Depends(get_services)) -> dict[str, list[str]]:
    try:
        services.repo.set_preferences(user_id, body.preferences)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return services.repo.get_preferences(user_id)


profile_router = APIRouter(prefix="/api/users/{user_id}/email", tags=["preferences"])


@profile_router.get("", response_model=EmailIn)
def get_email(user_id: int, services: Services = Depends(get_services)) -> EmailIn:
    with services.repo.session() as s:
        from app.database import models as m
        user = s.get(m.User, user_id)
        if user is None:
            raise HTTPException(404, "No such user")
        return EmailIn(email=user.email)


@profile_router.put("", status_code=204)
def set_email(user_id: int, body: EmailIn, services: Services = Depends(get_services)) -> None:
    try:
        services.repo.set_email(user_id, body.email)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
