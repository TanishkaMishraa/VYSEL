"""FastAPI application.

Run (from apps/api):  uvicorn app.main:app --reload --port 8000
Docs:                 http://localhost:8000/docs
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import auth, health, images, jobs, me, recommendations, reports, scans
from app.config import get_settings
from app.errors import register_error_handlers
from app.services.face_analysis import close_face_analyzer


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    close_face_analyzer()  # Release MediaPipe graphs (the model loads lazily on the first scan).


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = FastAPI(
        title="VYSEL API",
        version=__version__,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
        )
    register_error_handlers(app)
    app.include_router(health.router, prefix="/v1")
    app.include_router(jobs.router, prefix="/v1")
    app.include_router(auth.router, prefix="/v1")
    app.include_router(me.router, prefix="/v1")
    app.include_router(images.router, prefix="/v1")
    app.include_router(recommendations.router, prefix="/v1")
    app.include_router(reports.router, prefix="/v1")
    app.include_router(scans.router, prefix="/v1")
    return app


app = create_app()
