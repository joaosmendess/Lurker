"""FastAPI application: creates the app and registers the routers.

Run: uvicorn app.main:app --reload   (docs at http://localhost:8000/docs)
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.routers import applications, collect, companies, jobs, profile, resume, scoring

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


# Lifespan: code before "yield" runs at startup, after it at shutdown
# (like IHostedService StartAsync/StopAsync). FastAPI requires it to be async;
# "async def" is a coroutine, the equivalent of an async Task method in C#.
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Lurker", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[get_settings().frontend_origin],  # only the local frontend
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(jobs.router)
    app.include_router(applications.router)
    app.include_router(profile.router)
    app.include_router(companies.router)
    app.include_router(collect.router)
    app.include_router(resume.router)
    app.include_router(resume.status_router)
    app.include_router(scoring.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
