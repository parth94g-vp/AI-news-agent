"""Sign-up, log-in and log-out. See app.services.auth_service for how passwords and
sessions actually work."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from api.deps import get_auth_service, get_current_user
from api.schemas import AuthOut, LoginRequest, MeOut, SignupRequest
from app.services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=AuthOut)
def signup(body: SignupRequest, auth: AuthService = Depends(get_auth_service)) -> AuthOut:
    try:
        result = auth.sign_up(body.username.strip(), body.password)
    except AuthError as exc:
        raise HTTPException(422, str(exc)) from exc
    return AuthOut(user_id=result.user_id, username=result.username, token=result.token)


@router.post("/login", response_model=AuthOut)
def login(body: LoginRequest, auth: AuthService = Depends(get_auth_service)) -> AuthOut:
    try:
        result = auth.log_in(body.username.strip(), body.password)
    except AuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    return AuthOut(user_id=result.user_id, username=result.username, token=result.token)


@router.post("/logout", status_code=204)
def logout(authorization: str | None = Header(default=None), auth: AuthService = Depends(get_auth_service)) -> None:
    if authorization and authorization.lower().startswith("bearer "):
        auth.log_out(authorization[7:].strip())


@router.get("/me", response_model=MeOut)
def me(current: tuple[int, str] = Depends(get_current_user)) -> MeOut:
    """Lets the frontend verify a stored token is still valid on page load."""
    return MeOut(user_id=current[0], username=current[1])
