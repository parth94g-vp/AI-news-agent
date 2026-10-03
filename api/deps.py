"""Shared FastAPI dependencies: one Services instance for the process lifetime."""
from __future__ import annotations

from fastapi import HTTPException

from app.bootstrap import Services, build_services

_services: Services | None = None


def get_services() -> Services:
    global _services
    if _services is None:
        _services = build_services()
    return _services


def require_pipeline(services: Services = None) -> Services:  # overridden via Depends in routers
    raise NotImplementedError
