from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_scheduled_digest as sched  # noqa: E402

from app.assistant.news_assistant import NewsAssistant
from app.bootstrap import Services
from app.graph.graph import Dependencies
from tests.conftest import FakeLLM, FakeProvider
from tests.test_graph import LISTING


def make_services(repo, settings, with_email_creds=True):
    s = settings.__class__(**{**settings.__dict__, "gmail_address": "me@gmail.com" if with_email_creds else "",
                              "gmail_app_password": "p" if with_email_creds else ""})
    deps = Dependencies(FakeProvider(LISTING), FakeLLM(), repo, s)
    return Services(s, repo, deps, NewsAssistant(repo, FakeLLM(), s), [])


def test_no_users_returns_zero(repo, settings, monkeypatch):
    monkeypatch.setattr(sched, "build_services", lambda: make_services(repo, settings))
    assert sched.main() == 0


def test_runs_pipeline_and_emails_users_with_email(repo, settings, monkeypatch):
    uid, _ = repo.create_or_get_user("alice")
    repo.set_preferences(uid, {"Technology": ["Artificial Intelligence"]})
    repo.set_email(uid, "alice@example.com")
    uid2, _ = repo.create_or_get_user("bob")  # has preferences, no email -> pipeline runs, no email attempt
    repo.set_preferences(uid2, {"Sports": ["Cricket"]})

    sent = []
    monkeypatch.setattr(sched, "build_services", lambda: make_services(repo, settings))
    monkeypatch.setattr(sched, "send_digest_email", lambda s, email, name, digest: sent.append((email, name)))

    assert sched.main() == 0
    assert sent == [("alice@example.com", "alice")]
    assert repo.get_digest(uid) is not None and repo.get_digest(uid2) is not None


def test_users_without_preferences_are_skipped_entirely(repo, settings, monkeypatch):
    repo.create_or_get_user("nopref")
    calls = []
    services = make_services(repo, settings)
    monkeypatch.setattr(sched, "build_services", lambda: services)
    # run_pipeline should never be called for a user with no preferences
    import app.pipeline as pipeline_module
    original = pipeline_module.run_pipeline
    def spy(user_id, deps):
        calls.append(user_id)
        return original(user_id, deps)
    monkeypatch.setattr(sched, "run_pipeline", spy)
    assert sched.main() == 0 and calls == []


def test_one_users_failure_does_not_stop_others(repo, settings, monkeypatch):
    uid1, _ = repo.create_or_get_user("broken")
    repo.set_preferences(uid1, {"Technology": ["Artificial Intelligence"]})
    uid2, _ = repo.create_or_get_user("fine")
    repo.set_preferences(uid2, {"Sports": ["Cricket"]})

    services = make_services(repo, settings)
    monkeypatch.setattr(sched, "build_services", lambda: services)

    def flaky(user_id, deps):
        if user_id == uid1:
            raise RuntimeError("boom")
        from app.pipeline import run_pipeline as real
        return real(user_id, deps)
    monkeypatch.setattr(sched, "run_pipeline", flaky)

    assert sched.main() == 1  # failures happened
    assert repo.get_digest(uid2) is not None  # but the other user still got their digest


def test_email_disabled_still_runs_pipelines(repo, settings, monkeypatch):
    uid, _ = repo.create_or_get_user("alice")
    repo.set_preferences(uid, {"Technology": ["Artificial Intelligence"]})
    repo.set_email(uid, "alice@example.com")
    monkeypatch.setattr(sched, "build_services", lambda: make_services(repo, settings, with_email_creds=False))
    calls = []
    monkeypatch.setattr(sched, "send_digest_email", lambda *a, **k: calls.append(1))
    assert sched.main() == 0 and calls == [] and repo.get_digest(uid) is not None


def test_config_not_ready_aborts(repo, settings, monkeypatch):
    broken = Services(settings, repo, None, None, ["GROQ_API_KEY is missing in .env"])
    monkeypatch.setattr(sched, "build_services", lambda: broken)
    assert sched.main() == 1
