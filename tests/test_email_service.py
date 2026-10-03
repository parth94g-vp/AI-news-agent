from __future__ import annotations

import pytest

from app.schemas import ArticleView, DigestView
from app.services.email_service import EmailError, render_digest_html, send_digest_email
from app.utils.timeutils import utcnow


def make_digest():
    return DigestView(
        digest_date=utcnow().date(), overview="Big day in tech.",
        entries=[ArticleView(id=1, title="OpenAI ships new model", url="https://n.example/1",
                             source="Wire", summary="A new model launched.", topic="Technology")])


class FakeSMTP:
    instances = []

    def __init__(self, host, port):
        self.host, self.port = host, port
        self.started_tls = False
        self.logged_in = None
        self.sent = None
        FakeSMTP.instances.append(self)

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def starttls(self): self.started_tls = True
    def login(self, user, pw): self.logged_in = (user, pw)
    def sendmail(self, from_addr, to, msg): self.sent = (from_addr, to, msg)


@pytest.fixture(autouse=True)
def _reset():
    FakeSMTP.instances.clear()
    yield


def test_render_html_escapes_and_includes_content():
    html = render_digest_html("Al<ice>", make_digest())
    assert "Al&lt;ice&gt;" in html and "OpenAI ships new model" in html and "Technology" in html


def test_send_digest_email_happy_path(settings):
    s = settings.__class__(**{**settings.__dict__, "gmail_address": "me@gmail.com", "gmail_app_password": "app-pass"})
    send_digest_email(s, "friend@example.com", "Alice", make_digest(), smtp_factory=FakeSMTP)
    sent = FakeSMTP.instances[0]
    assert sent.started_tls and sent.logged_in == ("me@gmail.com", "app-pass")
    assert sent.sent[0] == "me@gmail.com" and sent.sent[1] == ["friend@example.com"]
    assert "OpenAI ships new model" in sent.sent[2]


def test_send_digest_email_requires_config(settings):
    with pytest.raises(EmailError, match="not configured"):
        send_digest_email(settings, "x@example.com", "Alice", make_digest(), smtp_factory=FakeSMTP)


def test_send_digest_email_rejects_empty_digest(settings):
    s = settings.__class__(**{**settings.__dict__, "gmail_address": "me@gmail.com", "gmail_app_password": "p"})
    empty = DigestView(digest_date=utcnow().date(), entries=[])
    with pytest.raises(EmailError, match="empty"):
        send_digest_email(s, "x@example.com", "Alice", empty, smtp_factory=FakeSMTP)
    with pytest.raises(EmailError, match="empty"):
        send_digest_email(s, "x@example.com", "Alice", None, smtp_factory=FakeSMTP)


def test_send_digest_email_wraps_auth_error(settings):
    import smtplib
    class BadAuthSMTP(FakeSMTP):
        def login(self, user, pw): raise smtplib.SMTPAuthenticationError(535, b"bad creds")
    s = settings.__class__(**{**settings.__dict__, "gmail_address": "me@gmail.com", "gmail_app_password": "wrong"})
    with pytest.raises(EmailError, match="rejected the login"):
        send_digest_email(s, "x@example.com", "Alice", make_digest(), smtp_factory=BadAuthSMTP)


def test_send_digest_email_wraps_network_error(settings):
    def broken_factory(host, port): raise OSError("no route to host")
    s = settings.__class__(**{**settings.__dict__, "gmail_address": "me@gmail.com", "gmail_app_password": "p"})
    with pytest.raises(EmailError, match="could not reach"):
        send_digest_email(s, "x@example.com", "Alice", make_digest(), smtp_factory=broken_factory)
