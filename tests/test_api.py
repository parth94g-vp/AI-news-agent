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
from tests.conftest import FakeLLM, FakeProvider
from tests.test_graph import LISTING


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.config.settings import Settings
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'api.db'}", news_min_interval=0, timezone="UTC")
    engine = get_engine(settings.database_url)
    init_db(engine)
    repo = NewsRepository(make_session_factory(engine))
    repo.seed_taxonomy()
    llm = FakeLLM()
    provider = FakeProvider(LISTING)
    services = Services(settings, repo, Dependencies(provider, llm, repo, settings),
                        __import__("app.assistant.news_assistant", fromlist=["NewsAssistant"]).NewsAssistant(repo, llm, settings), [])
    monkeypatch.setattr(deps_module, "_services", services)
    monkeypatch.setattr(deps_module, "get_services", lambda: services)
    monkeypatch.setattr(main_module, "get_services", lambda: services)
    with TestClient(main_module.app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["config_problems"] == []


def test_login_creates_and_reuses_user(client):
    r1 = client.post("/api/auth/login", json={"username": "alice"})
    r2 = client.post("/api/auth/login", json={"username": "alice"})
    assert r1.status_code == 200 and r1.json()["user_id"] == r2.json()["user_id"]
    assert client.post("/api/auth/login", json={"username": "!"}).status_code == 422


def test_taxonomy_lists_new_topics(client):
    data = client.get("/api/taxonomy").json()["taxonomy"]
    assert "Entertainment" in data and "Gaming" in data and "Artificial Intelligence" in data["Technology"]


def test_full_flow_preferences_refresh_digest_save_feedback_assistant(client):
    uid = client.post("/api/auth/login", json={"username": "bob"}).json()["user_id"]
    assert client.get(f"/api/users/{uid}/digest").status_code == 404
    prefs = {"Technology": ["Artificial Intelligence", "Cybersecurity"]}
    r = client.put(f"/api/users/{uid}/preferences", json={"preferences": prefs})
    assert r.status_code == 200 and r.json() == {"Technology": ["Artificial Intelligence", "Cybersecurity"]}

    r = client.post(f"/api/users/{uid}/refresh")
    assert r.status_code == 200 and r.json()["saved_count"] == 2 and r.json()["errors"] == []

    digest = client.get(f"/api/users/{uid}/digest").json()
    assert len(digest["entries"]) == 2 and digest["is_stale"] is False
    article_id = digest["entries"][0]["id"]

    r = client.post(f"/api/users/{uid}/articles/{article_id}/save")
    assert r.json() == {"saved": True}
    assert any(a["id"] == article_id for a in client.get(f"/api/users/{uid}/saved").json())
    assert client.post(f"/api/users/{uid}/articles/{article_id}/save").json() == {"saved": False}

    assert client.post(f"/api/users/{uid}/articles/{article_id}/feedback", json={"rating": 1}).status_code == 204
    assert client.post(f"/api/users/{uid}/articles/{article_id}/feedback", json={"rating": 9}).status_code == 422

    r = client.post(f"/api/users/{uid}/assistant", json={"question": "Which stories are related to OpenAI?"})
    assert r.status_code == 200 and r.json()["sources"]


def test_refresh_without_preferences_is_422(client):
    uid = client.post("/api/auth/login", json={"username": "nopref"}).json()["user_id"]
    assert client.post(f"/api/users/{uid}/refresh").status_code == 422


def test_set_email_endpoint(client):
    uid = client.post("/api/auth/login", json={"username": "withmail"}).json()["user_id"]
    assert client.put(f"/api/users/{uid}/email", json={"email": "me@example.com"}).status_code == 204
    assert client.put(f"/api/users/{uid}/email", json={"email": "not-an-email"}).status_code == 422
    assert client.put(f"/api/users/{uid}/email", json={"email": None}).status_code == 204


def test_trending_endpoint_reflects_spikes(client):
    uid = client.post("/api/auth/login", json={"username": "trend"}).json()["user_id"]
    client.put(f"/api/users/{uid}/preferences", json={"preferences": {"Technology": ["Artificial Intelligence", "Cybersecurity"]}})
    client.post(f"/api/users/{uid}/refresh")
    r = client.get("/api/trending")
    assert r.status_code == 200 and isinstance(r.json(), list)
