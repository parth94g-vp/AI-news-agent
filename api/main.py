"""FastAPI backend for the React frontend. Wraps the SAME agent logic used by the
CLI (app.basic_agent) and the Streamlit app (app.ui.streamlit_app) - nothing about the
LangGraph pipeline, database, or taxonomy changes here.

    uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import get_services
from api.routers import articles, assistant, auth, news, preferences, taxonomy


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_services()  # fail fast / seed taxonomy at startup rather than on first request
    yield


app = FastAPI(title="AI News Agent API", version="1.0.0", lifespan=lifespan)

_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, taxonomy.router, preferences.router, preferences.profile_router,
         news.router, news.trending_router, articles.router, assistant.router):
    app.include_router(r)


@app.get("/api/health")
def health() -> dict:
    services = get_services()
    return {"status": "ok", "config_problems": services.config_problems}
