from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import backtest, bots, health, signals


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # startup hook (warm caches, validate config). teardown after yield.
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
    return app


app = create_app()
