"""Runs the news pipeline for every user with saved preferences, then emails each one
their digest (if they've set a notification email). Designed to run on a schedule
(a Render Cron Job, GitHub Actions, or a local cron/Task Scheduler entry) - not interactive.

    python scripts/run_scheduled_digest.py

Exit code is 0 if every user succeeded, 1 if anything failed (so the scheduler can alert on it).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import build_services  # noqa: E402
from app.logging_config import get_logger, log_event  # noqa: E402
from app.pipeline import run_pipeline  # noqa: E402
from app.services.email_service import EmailError, send_digest_email  # noqa: E402

logger = get_logger("scripts.scheduled_digest")


def main() -> int:
    services = build_services()
    if services.deps is None:
        log_event(logger, "scheduled_run_aborted", level=40, problems=services.config_problems)
        return 1

    users = services.repo.list_users_with_preferences()
    if not users:
        log_event(logger, "scheduled_run_no_users")
        return 0

    can_email = bool(services.settings.gmail_address and services.settings.gmail_app_password)
    if not can_email:
        log_event(logger, "scheduled_run_email_disabled",
                  note="GMAIL_ADDRESS/GMAIL_APP_PASSWORD not set - digests will be generated but not emailed")

    failures = 0
    for user_id, username, email in users:
        try:
            result = run_pipeline(user_id, services.deps)
            log_event(logger, "scheduled_pipeline_done", user=username, saved=result.saved_count,
                      errors=len(result.errors))
        except Exception as exc:  # noqa: BLE001 - one user's failure must not stop the others
            log_event(logger, "scheduled_pipeline_failed", level=40, user=username, error=str(exc))
            failures += 1
            continue

        if not email or not can_email:
            continue
        digest = services.repo.get_digest(user_id)
        try:
            send_digest_email(services.settings, email, username, digest)
        except EmailError as exc:
            log_event(logger, "scheduled_email_failed", level=30, user=username, error=str(exc))
            failures += 1

    log_event(logger, "scheduled_run_finished", users=len(users), failures=failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
