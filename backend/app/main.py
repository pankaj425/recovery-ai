from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import init_db
from app.core.exceptions import register_exception_handlers
from app.utils.logging_config import configure_logging
from app.utils.rate_limit import RateLimitMiddleware

logger = logging.getLogger("recoveryai.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    # Warm the ML artifact (trains deterministically on first run) and the demo user.
    from app.ml.model_registry import RecoveryProbabilityModel
    from app.services.auth_service import ensure_demo_user
    from app.core.database import SessionLocal

    RecoveryProbabilityModel.get()
    with SessionLocal() as db:
        ensure_demo_user(db)
    logger.info("RecoveryAI backend ready (env=%s)", settings.environment)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="1.0.0",
        description=(
            "AI-powered Revenue Recovery Platform: turns payment failures into "
            "prioritized, explainable recovery opportunities."
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
