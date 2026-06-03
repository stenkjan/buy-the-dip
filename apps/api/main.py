from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import backtest, bots, control, health, signals, sweep


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # On SQLite (local/dev) auto-create the tables so the admin endpoints work
    # out of the box. On Postgres the schema is owned by Alembic migrations, so
    # we never create_all there (it would race the `alembic upgrade` step).
    try:
        from sqlmodel import SQLModel

        from bot_core.db import models  # noqa: F401 — registers tables
        from bot_core.db.session import get_engine

        engine = get_engine()
        if engine.url.get_backend_name() == "sqlite":
            SQLModel.metadata.create_all(engine)
    except Exception as exc:  # never block startup on DB issues
        import logging

        logging.getLogger("buy-the-dip").warning("table bootstrap skipped: %s", exc)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="buy-the-dip API",
        version="0.1.0",
        description="Signal API for the modular buy-the-dip bot. Educational use only.",
        lifespan=lifespan,
    )

    raw_origins = os.environ.get("API_CORS_ORIGINS", "http://localhost:5173")
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(signals.router)
    app.include_router(bots.router)
    app.include_router(backtest.router)
    app.include_router(control.router)
    app.include_router(sweep.router)
    return app


app = create_app()
