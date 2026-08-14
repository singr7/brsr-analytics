from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as redis
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.app.core.config import get_settings
from api.app.core.logging import configure_logging
from api.app.core.middleware import RequestIDMiddleware
from api.app.db.session import create_engine, create_session_factory
from api.app.routers.auth import router as auth_router
from api.app.routers.health import router as health_router
from api.app.routers.orgs import admin_router
from api.app.routers.orgs import router as orgs_router
from api.app.routers.tracking import router as tracking_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_engine(settings)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = redis.from_url(settings.redis_url)  # type: ignore[no-untyped-call]
    structlog.get_logger().info("application_started", environment=settings.app_env)
    yield
    await app.state.redis.aclose()
    await engine.dispose()


app = FastAPI(title="BRSR Lens API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(orgs_router)
app.include_router(admin_router)
app.include_router(tracking_router)
