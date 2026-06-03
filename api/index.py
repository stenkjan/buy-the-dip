"""Vercel serverless entrypoint for the bot control-plane API.

Vercel's native FastAPI builder imports the module-level ``app`` (an ASGI
instance, named via ``[tool.vercel] entrypoint = "api.index:app"`` in
pyproject) and serves every route through it directly — no ``api/`` rewrites.

Why a dedicated app instead of ``apps.api.main:app``: the deployed admin API is
control-plane only. The web dashboard reads *live* signals from the static
``signals.json`` on the ``data`` branch (see docs/roadmap.md), never from the
API's ``/signals`` route. Excluding that router keeps yfinance / strategies /
alpaca-py out of the serverless bundle — only the DB + bot CRUD path ships.
"""

from __future__ import annotations

import os
import sys

# Make the repo importable from the deployment root: ``apps`` is a package at
# the root, ``bot_core`` lives under ``src/`` (src layout, see pyproject).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from collections.abc import AsyncIterator  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from apps.api.routers import bots, health  # noqa: E402


def _ensure_schema() -> None:
    """Create tables on first cold start when a Postgres URL is configured.

    Serverless has no migration step, so the control-plane self-initializes its
    schema. ``create_all`` is idempotent (CREATE TABLE IF NOT EXISTS) and never
    drops or alters, so it's safe to run on every cold start. Skipped when no
    Postgres URL is set — we don't want to touch the read-only SQLite fallback.
    Failures are swallowed so /health stays up even if the DB is unreachable.
    """
    from bot_core.db import SQLModel
    from bot_core.db.session import get_engine, resolve_database_url

    if resolve_database_url().startswith("sqlite"):
        return
    try:
        # DDL goes over the direct (non-pooling) connection — pgbouncer's
        # transaction pooling doesn't tolerate CREATE TABLE well.
        SQLModel.metadata.create_all(get_engine(prefer_non_pooling=True))
    except Exception as exc:  # pragma: no cover - best-effort bootstrap
        print(f"[startup] schema bootstrap skipped: {exc!r}")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    _ensure_schema()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="buy-the-dip control-plane API",
        version="0.1.0",
        description="Bot control-plane (admin) API. Educational use only.",
        lifespan=lifespan,
    )

    # The frontend is a separate Vercel project, so it's cross-origin. Default
    # to the production web origin; override/extend via API_CORS_ORIGINS (comma
    # separated) for preview deploys and local dev.
    raw_origins = os.environ.get(
        "API_CORS_ORIGINS",
        "https://buy-the-dip-web.vercel.app,http://localhost:5173",
    )
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(bots.router)
    return app


app = create_app()
