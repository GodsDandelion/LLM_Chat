from contextlib import asynccontextmanager
import logging
from pathlib import Path

import redis.asyncio as redis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.core.config import get_settings

logger = logging.getLogger(__name__)
STATIC_UI_DIR = Path(__file__).resolve().parent.parent / "static" / "ui"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield
    finally:
        await app.state.redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="LLM Chat API", version="0.1.0", lifespan=lifespan)
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.warning("Database error on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Database error. Start PostgreSQL (e.g. docker compose up -d), "
                    "check DATABASE_URL in .env, then run: alembic upgrade head"
                ),
            },
        )

    @app.get("/api-info")
    async def api_info() -> dict[str, str]:
        return {
            "name": app.title,
            "version": app.version,
            "ui": "/ui/",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "health": "/health",
        }

    @app.get("/")
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/ui/", status_code=307)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    app.include_router(api_router)

    if STATIC_UI_DIR.is_dir():
        app.mount("/ui", StaticFiles(directory=str(STATIC_UI_DIR), html=True), name="ui")

    return app


app = create_app()
