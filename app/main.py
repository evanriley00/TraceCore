from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.health import router as health_router
from app.api.routes.queries import router as queries_router
from app.api.routes.ui import router as ui_router
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_session_factory, init_database
from app.services.cache import DecisionCache, RateLimiter


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    static_dir = Path(__file__).resolve().parent / "static"
    engine = build_engine(resolved_settings.database_url)
    session_factory = build_session_factory(engine)
    cache = DecisionCache(resolved_settings.redis_url)
    rate_limiter = RateLimiter(cache, resolved_settings.rate_limit_per_minute)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_database(engine)
        yield
        cache.close()
        engine.dispose()

    app = FastAPI(title=resolved_settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.cache = cache
    app.state.rate_limiter = rate_limiter
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    app.include_router(ui_router)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(queries_router)
    app.include_router(feedback_router)

    return app


app = create_app()
