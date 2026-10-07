from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_user, get_services, require_owner
from api.schemas import EmailIn, PreferencesIn
from app.bootstrap import Services

router = APIRouter(prefix="/api/users/{user_id}/preferences", tags=["preferences"])


@router.get("", response_model=dict[str, list[str]])
def get_preferences(user_id: int, services: Services = Depends(get_services),
                    current: tuple[int, str] = Depends(get_current_user)) -> dict[str, list[str]]:
    require_owner(user_id, current)
    return services.repo.get_preferences(user_id)


@router.put("", response_model=dict[str, list[str]])
def set_preferences(user_id: int, body: PreferencesIn, services: Services = Depends(get_services),
                    current: tuple[int, str] = Depends(get_current_user)) -> dict[str, list[str]]:
    require_owner(user_id, current)
    try:
        services.repo.set_preferences(user_id, body.preferences)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return services.repo.get_preferences(user_id)


profile_router = APIRouter(prefix="/api/users/{user_id}/email", tags=["preferences"])


@profile_router.get("", response_model=EmailIn)
def get_email(user_id: int, services: Services = Depends(get_services),
             current: tuple[int, str] = Depends(get_current_user)) -> EmailIn:
    require_owner(user_id, current)
    with services.repo.session() as s:
        from app.database import models as m
        user = s.get(m.User, user_id)
        if user is None:
            raise HTTPException(404, "No such user")
        return EmailIn(email=user.email)


@profile_router.put("", status_code=204)
def set_email(user_id: int, body: EmailIn, services: Services = Depends(get_services),
             current: tuple[int, str] = Depends(get_current_user)) -> None:
    require_owner(user_id, current)
    try:
        services.repo.set_email(user_id, body.email)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
