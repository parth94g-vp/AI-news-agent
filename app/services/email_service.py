"""Sends the daily digest by email via Gmail SMTP (STARTTLS, port 587).

Gmail requires an "app password" (not your normal login password) for SMTP:
Google Account -> Security -> 2-Step Verification -> App passwords.
"""
from __future__ import annotations

import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable

from app.config.settings import Settings
from app.logging_config import get_logger, log_event
from app.schemas import ArticleView, DigestView

logger = get_logger(__name__)


class EmailError(Exception):
    """The digest could not be emailed (missing config, empty digest, or SMTP failure)."""


def _article_html(a: ArticleView) -> str:
    return (
        '<li style="margin:0 0 14px 0;">'
        f'<a href="{html.escape(a.url)}" style="font-weight:600;color:#1a2b4c;text-decoration:none;font-size:15px;">'
        f'{html.escape(a.title)}</a><br>'
        f'<span style="color:#7a8699;font-size:12px;">{html.escape(a.source)}</span><br>'
        f'<span style="color:#333;font-size:13px;line-height:1.4;">{html.escape(a.summary or "")}</span></li>'
    )


def render_digest_html(username: str, digest: DigestView) -> str:
    by_topic: dict[str, list[ArticleView]] = {}
    for e in digest.entries:
        by_topic.setdefault(e.topic or "Other", []).append(e)
    sections = "".join(
        f'<h3 style="margin:24px 0 8px 0;color:#1a2b4c;font-size:17px;">{html.escape(topic)}</h3>'
        f'<ul style="list-style:none;padding:0;margin:0;">{"".join(_article_html(a) for a in arts)}</ul>'
        for topic, arts in by_topic.items()
    )
    overview = (f'<p style="font-size:14px;color:#333;background:#f3f6fb;padding:12px 16px;border-radius:10px;">'
                f'{html.escape(digest.overview)}</p>' if digest.overview else "")
    return f"""<div style="font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:auto;padding:16px;">
      <h2 style="color:#1a2b4c;">Hi {html.escape(username)}, here's your news for {digest.digest_date:%A, %d %B %Y}</h2>
      {overview}
      {sections}
      <p style="color:#9aa5b5;font-size:11px;margin-top:28px;border-top:1px solid #eee;padding-top:12px;">
        Sent automatically by your AI News Agent.</p>
    </div>"""


def send_digest_email(
    settings: Settings,
    to_email: str,
    username: str,
    digest: DigestView | None,
    *,
    smtp_factory: Callable[[str, int], smtplib.SMTP] | None = None,
) -> None:
    """Raises EmailError on any failure; never raises for an empty digest, just skips (no EmailError)
    is NOT raised there - caller decides whether 'nothing to send' is worth logging."""
    if not settings.gmail_address or not settings.gmail_app_password:
        raise EmailError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD not configured")
    if digest is None or not digest.entries:
        raise EmailError("nothing to send: today's digest is empty")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your news digest - {digest.digest_date:%d %b %Y}"
    msg["From"] = settings.gmail_address
    msg["To"] = to_email
    msg.attach(MIMEText(render_digest_html(username, digest), "html"))

    factory = smtp_factory or smtplib.SMTP
    try:
        with factory(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.gmail_address, settings.gmail_app_password)
            server.sendmail(settings.gmail_address, [to_email], msg.as_string())
    except smtplib.SMTPAuthenticationError as exc:
        raise EmailError("Gmail rejected the login - check GMAIL_ADDRESS and the app password") from exc
    except smtplib.SMTPException as exc:
        raise EmailError(f"SMTP error: {exc}") from exc
    except OSError as exc:  # network/DNS failure
        raise EmailError(f"could not reach {settings.smtp_host}:{settings.smtp_port}: {exc}") from exc
    log_event(logger, "digest_emailed", to=to_email, articles=len(digest.entries))
