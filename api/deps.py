"""Shared FastAPI dependencies: one Services instance for the process lifetime, plus
token-based authentication."""
from __future__ import annotations

from fastapi import Header, HTTPException

from app.bootstrap import Services, build_services
from app.services.auth_service import AuthService

_services: Services | None = None
_auth: AuthService | None = None


def get_services() -> Services:
    global _services
    if _services is None:
        _services = build_services()
    return _services


def get_auth_service() -> AuthService:
    global _auth
    if _auth is None:
        _auth = AuthService(get_services().repo._sf)
    return _auth


def get_current_user(authorization: str | None = Header(default=None)) -> tuple[int, str]:
    """Extracts and validates the Bearer token. Raises 401 if missing/invalid/expired -
    this is what makes every route below require being logged in."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    identity = get_auth_service().authenticate(token)
    if identity is None:
        raise HTTPException(401, "Not authenticated. Please log in again.")
    return identity


def require_owner(user_id: int, current: tuple[int, str]) -> None:
    """Call this at the top of any /users/{user_id}/... route: ensures the logged-in
    user can only act on their own data, even if they edit the URL."""
    if user_id != current[0]:
        raise HTTPException(403, "You can only access your own data.")
