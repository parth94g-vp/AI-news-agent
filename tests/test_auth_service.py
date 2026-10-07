from __future__ import annotations

import pytest

from app.services.auth_service import AuthError, AuthService


@pytest.fixture
def auth(repo):
    return AuthService(repo._sf)  # reuse the same session factory as the repo fixture


def test_sign_up_then_authenticate(auth):
    result = auth.sign_up("alice", "correct-horse")
    assert result.username == "alice" and result.token
    identity = auth.authenticate(result.token)
    assert identity == (result.user_id, "alice")


def test_sign_up_rejects_short_password(auth):
    with pytest.raises(AuthError, match="at least 8"):
        auth.sign_up("alice", "short")


def test_sign_up_rejects_taken_username(auth):
    auth.sign_up("alice", "correct-horse")
    with pytest.raises(AuthError, match="taken"):
        auth.sign_up("alice", "another-password")


def test_sign_up_rejects_invalid_username(auth):
    with pytest.raises(AuthError, match="2-40 characters"):
        auth.sign_up("!!!", "correct-horse")


def test_log_in_wrong_password_rejected(auth):
    auth.sign_up("alice", "correct-horse")
    with pytest.raises(AuthError, match="Incorrect password"):
        auth.log_in("alice", "wrong-password")


def test_log_in_unknown_username_rejected(auth):
    with pytest.raises(AuthError, match="No account"):
        auth.log_in("ghost", "whatever123")


def test_log_in_succeeds_with_correct_password(auth):
    auth.sign_up("alice", "correct-horse")
    result = auth.log_in("alice", "correct-horse")
    assert auth.authenticate(result.token) is not None


def test_passwords_are_never_stored_in_plaintext(auth, repo):
    auth.sign_up("alice", "correct-horse-battery")
    with repo.session() as s:
        from app.database import models as m
        user = s.query(m.User).filter_by(username="alice").first()
        assert user.password_hash != "correct-horse-battery"
        assert user.password_hash.startswith("$2b$")  # bcrypt hash format


def test_legacy_account_without_password_can_be_claimed_via_signup(auth, repo):
    uid, _ = repo.create_or_get_user("legacyuser")  # simulates a pre-password-feature account
    assert repo.get_preferences(uid) == {}  # sanity: it's a real pre-existing account
    result = auth.sign_up("legacyuser", "new-password-123")
    assert result.user_id == uid  # SAME account, not a new one
    assert auth.log_in("legacyuser", "new-password-123").user_id == uid


def test_legacy_account_cannot_log_in_before_claiming(auth, repo):
    repo.create_or_get_user("legacyuser")
    with pytest.raises(AuthError, match="hasn't set a password"):
        auth.log_in("legacyuser", "whatever123")


def test_logout_invalidates_token(auth):
    result = auth.sign_up("alice", "correct-horse")
    auth.log_out(result.token)
    assert auth.authenticate(result.token) is None


def test_authenticate_rejects_garbage_or_missing_token(auth):
    assert auth.authenticate("not-a-real-token") is None
    assert auth.authenticate(None) is None
    assert auth.authenticate("") is None


def test_expired_session_is_rejected(auth, repo):
    result = auth.sign_up("alice", "correct-horse")
    from app.database import models as m
    from datetime import timedelta
    from app.utils.timeutils import utcnow, to_naive_utc
    with repo.session() as s:
        session = s.query(m.UserSession).filter_by(token=result.token).first()
        session.expires_at = to_naive_utc(utcnow() - timedelta(days=1))  # force it into the past
    assert auth.authenticate(result.token) is None


def test_two_sessions_for_same_user_are_independent(auth):
    device1 = auth.log_in("alice", "x") if False else auth.sign_up("alice", "correct-horse")
    device2 = auth.log_in("alice", "correct-horse")
    assert device1.token != device2.token
    auth.log_out(device1.token)
    assert auth.authenticate(device1.token) is None
    assert auth.authenticate(device2.token) is not None  # logging out one device doesn't kill the other
