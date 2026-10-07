"""End-to-end check of the FastAPI layer against a temp DB and fake provider/LLM."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api.deps as deps_module
import api.main as main_module
from app.bootstrap import Services
from app.database.connection import get_engine, init_db, make_session_factory
from app.database.repositories import NewsRepository
from app.graph.graph import Dependencies
from app.services.auth_service import AuthService
from tests.conftest import FakeLLM, FakeProvider
from tests.test_graph import LISTING


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.config.settings import Settings
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'api.db'}", news_min_interval=0, timezone="UTC")
    engine = get_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)
    repo = NewsRepository(session_factory)
    repo.seed_taxonomy()
    llm = FakeLLM()
    provider = FakeProvider(LISTING)
    services = Services(settings, repo, Dependencies(provider, llm, repo, settings),
                        __import__("app.assistant.news_assistant", fromlist=["NewsAssistant"]).NewsAssistant(repo, llm, settings), [])
    # Setting the module-level state directly (not just replacing the function) is what makes
    # every router's `Depends(get_services)` / `Depends(get_auth_service)` pick up this test's
    # instances, since those functions read these globals at call time regardless of which
    # module imported a reference to the function itself.
    monkeypatch.setattr(deps_module, "_services", services)
    monkeypatch.setattr(deps_module, "_auth", AuthService(session_factory))
    monkeypatch.setattr(main_module, "get_services", lambda: services)
    with TestClient(main_module.app) as c:
        yield c


def signup(client, username, password="testpass123"):
    r = client.post("/api/auth/signup", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    data = r.json()
    return data["user_id"], {"Authorization": f"Bearer {data['token']}"}


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["config_problems"] == []


def test_taxonomy_lists_new_topics(client):
    data = client.get("/api/taxonomy").json()["taxonomy"]
    assert "Entertainment" in data and "Gaming" in data and "Artificial Intelligence" in data["Technology"]


# --------------------------------------------------------------------------- auth


def test_signup_then_me_reflects_identity(client):
    uid, headers = signup(client, "alice")
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200 and r.json() == {"user_id": uid, "username": "alice"}


def test_signup_rejects_short_password(client):
    r = client.post("/api/auth/signup", json={"username": "alice", "password": "short"})
    assert r.status_code == 422


def test_signup_then_login_with_same_credentials(client):
    signup(client, "alice", "correct-horse")
    r = client.post("/api/auth/login", json={"username": "alice", "password": "correct-horse"})
    assert r.status_code == 200 and r.json()["username"] == "alice"


def test_login_wrong_password_rejected(client):
    signup(client, "alice", "correct-horse")
    r = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user_rejected(client):
    assert client.post("/api/auth/login", json={"username": "ghost", "password": "whatever1"}).status_code == 401


def test_every_data_endpoint_requires_a_token(client):
    uid, _ = signup(client, "alice")
    assert client.get(f"/api/users/{uid}/digest").status_code == 401
    assert client.get(f"/api/users/{uid}/preferences").status_code == 401
    assert client.get(f"/api/users/{uid}/saved").status_code == 401
    assert client.get("/api/trending").status_code == 401


def test_bad_token_is_rejected(client):
    uid, _ = signup(client, "alice")
    bad = {"Authorization": "Bearer not-a-real-token"}
    assert client.get(f"/api/users/{uid}/preferences", headers=bad).status_code == 401


def test_user_cannot_access_another_users_data(client):
    uid_a, headers_a = signup(client, "alice")
    uid_b, headers_b = signup(client, "bob")
    # alice's token, but bob's user_id in the URL - must be refused
    assert client.get(f"/api/users/{uid_b}/preferences", headers=headers_a).status_code == 403
    assert client.put(f"/api/users/{uid_b}/preferences", headers=headers_a,
                      json={"preferences": {"Sports": ["Cricket"]}}).status_code == 403
    assert client.post(f"/api/users/{uid_b}/refresh", headers=headers_a).status_code == 403
    # each can still access their own
    assert client.get(f"/api/users/{uid_a}/preferences", headers=headers_a).status_code == 200
    assert client.get(f"/api/users/{uid_b}/preferences", headers=headers_b).status_code == 200


def test_logout_invalidates_the_token(client):
    uid, headers = signup(client, "alice")
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get(f"/api/users/{uid}/preferences", headers=headers).status_code == 401


def test_legacy_account_can_be_claimed_and_then_logged_into(client):
    # Simulate an account created before this feature existed: no password at all.
    from app.database import models as m
    with __import__("api.deps", fromlist=["_services"])._services.repo.session() as s:
        s.add(m.User(username="legacyuser"))
    assert client.post("/api/auth/login", json={"username": "legacyuser", "password": "anything1"}).status_code == 401
    r = client.post("/api/auth/signup", json={"username": "legacyuser", "password": "new-password-1"})
    assert r.status_code == 200
    r2 = client.post("/api/auth/login", json={"username": "legacyuser", "password": "new-password-1"})
    assert r2.status_code == 200 and r2.json()["user_id"] == r.json()["user_id"]


def test_signup_rejects_already_claimed_username(client):
    signup(client, "alice", "correct-horse")
    r = client.post("/api/auth/signup", json={"username": "alice", "password": "another-one-1"})
    assert r.status_code == 422


# --------------------------------------------------------------------------- data flow (authenticated)


def test_full_flow_preferences_refresh_digest_save_feedback_assistant(client):
    uid, headers = signup(client, "bob")
    assert client.get(f"/api/users/{uid}/digest", headers=headers).status_code == 404
    prefs = {"Technology": ["Artificial Intelligence", "Cybersecurity"]}
    r = client.put(f"/api/users/{uid}/preferences", headers=headers, json={"preferences": prefs})
    assert r.status_code == 200 and r.json() == {"Technology": ["Artificial Intelligence", "Cybersecurity"]}

    r = client.post(f"/api/users/{uid}/refresh", headers=headers)
    assert r.status_code == 200 and r.json()["saved_count"] == 2 and r.json()["errors"] == []

    digest = client.get(f"/api/users/{uid}/digest", headers=headers).json()
    assert len(digest["entries"]) == 2 and digest["is_stale"] is False
    article_id = digest["entries"][0]["id"]

    r = client.post(f"/api/users/{uid}/articles/{article_id}/save", headers=headers)
    assert r.json() == {"saved": True}
    assert any(a["id"] == article_id for a in client.get(f"/api/users/{uid}/saved", headers=headers).json())
    assert client.post(f"/api/users/{uid}/articles/{article_id}/save", headers=headers).json() == {"saved": False}

    assert client.post(f"/api/users/{uid}/articles/{article_id}/feedback", headers=headers,
                       json={"rating": 1}).status_code == 204
    assert client.post(f"/api/users/{uid}/articles/{article_id}/feedback", headers=headers,
                       json={"rating": 9}).status_code == 422

    r = client.post(f"/api/users/{uid}/assistant", headers=headers,
                    json={"question": "Which stories are related to OpenAI?"})
    assert r.status_code == 200 and r.json()["sources"]


def test_refresh_without_preferences_is_422(client):
    uid, headers = signup(client, "nopref")
    assert client.post(f"/api/users/{uid}/refresh", headers=headers).status_code == 422


def test_set_email_endpoint(client):
    uid, headers = signup(client, "withmail")
    assert client.put(f"/api/users/{uid}/email", headers=headers, json={"email": "me@example.com"}).status_code == 204
    assert client.put(f"/api/users/{uid}/email", headers=headers, json={"email": "not-an-email"}).status_code == 422
    assert client.put(f"/api/users/{uid}/email", headers=headers, json={"email": None}).status_code == 204


def test_trending_endpoint_reflects_spikes(client):
    uid, headers = signup(client, "trend")
    client.put(f"/api/users/{uid}/preferences", headers=headers,
              json={"preferences": {"Technology": ["Artificial Intelligence", "Cybersecurity"]}})
    client.post(f"/api/users/{uid}/refresh", headers=headers)
    r = client.get("/api/trending", headers=headers)
    assert r.status_code == 200 and isinstance(r.json(), list)
