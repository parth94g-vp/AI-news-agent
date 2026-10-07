"""Password hashing, session tokens, and the sign-up/log-in/log-out flow.

Design notes:
- Passwords are hashed with bcrypt; only the hash is ever stored or compared.
- A successful sign-up or log-in returns an opaque session token (not a JWT) which the
  caller stores and sends back as `Authorization: Bearer <token>`. The token is looked up
  against the `user_sessions` table on every request - this makes logout and expiry trivial
  (just delete/age out a row), at the cost of one extra DB lookup per request, which is fine
  at this app's scale.
- Legacy accounts created before this feature existed have `password_hash IS NULL`. Signing
  up with that username is treated as "claiming" the existing account and setting its first
  password, rather than being rejected as already-taken.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker, Session

from app.database import models as m
from app.utils.timeutils import to_naive_utc, utcnow

SESSION_EXPIRY_DAYS = 30
_MIN_PASSWORD_LEN = 8
_MAX_PASSWORD_LEN = 72  # bcrypt silently ignores bytes beyond 72; reject earlier instead


class AuthError(ValueError):
    """Sign-up/log-in/log-out failed for a reason safe to show the user."""


@dataclass
class AuthResult:
    user_id: int
    username: str
    token: str


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:  # malformed stored hash
        return False


def _validate_password(password: str) -> None:
    if not isinstance(password, str) or len(password) < _MIN_PASSWORD_LEN:
        raise AuthError(f"Password must be at least {_MIN_PASSWORD_LEN} characters.")
    if len(password.encode("utf-8")) > _MAX_PASSWORD_LEN:
        raise AuthError("Password is too long.")


class AuthService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    def _issue_session(self, s: Session, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        s.add(m.UserSession(user_id=user_id, token=token,
                            expires_at=to_naive_utc(utcnow() + timedelta(days=SESSION_EXPIRY_DAYS))))
        return token

    def sign_up(self, username: str, password: str) -> AuthResult:
        _validate_password(password)
        s = self._sf()
        try:
            user = s.scalar(select(m.User).where(m.User.username == username))
            if user is not None and user.password_hash:
                raise AuthError("That username is taken. Try logging in instead.")
            if user is None:
                from app.database.repositories import _USERNAME_RE  # reuse the same validation
                if not _USERNAME_RE.match(username):
                    raise AuthError("Username must be 2-40 characters: letters, numbers, spaces, . _ -")
                user = m.User(username=username)
                s.add(user)
                s.flush()
            user.password_hash = _hash_password(password)  # new account, or claiming a legacy one
            token = self._issue_session(s, user.id)
            s.commit()
            return AuthResult(user.id, user.username, token)
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def log_in(self, username: str, password: str) -> AuthResult:
        s = self._sf()
        try:
            user = s.scalar(select(m.User).where(m.User.username == username))
            if user is None:
                raise AuthError("No account with that username. Try signing up instead.")
            if not user.password_hash:
                raise AuthError("This account hasn't set a password yet. Use Sign Up to set one.")
            if not _verify_password(password, user.password_hash):
                raise AuthError("Incorrect password.")
            token = self._issue_session(s, user.id)
            s.commit()
            return AuthResult(user.id, user.username, token)
        finally:
            s.close()

    def log_out(self, token: str) -> None:
        s = self._sf()
        try:
            session = s.scalar(select(m.UserSession).where(m.UserSession.token == token))
            if session is not None:
                s.delete(session)
                s.commit()
        finally:
            s.close()

    def authenticate(self, token: str | None) -> tuple[int, str] | None:
        """Returns (user_id, username) for a valid, unexpired token - else None."""
        if not token:
            return None
        s = self._sf()
        try:
            row = s.execute(
                select(m.UserSession.expires_at, m.User.id, m.User.username)
                .join(m.User, m.User.id == m.UserSession.user_id)
                .where(m.UserSession.token == token)
            ).first()
            if row is None:
                return None
            expires_at, user_id, username = row
            if to_naive_utc(utcnow()) > expires_at:
                return None
            return user_id, username
        finally:
            s.close()
