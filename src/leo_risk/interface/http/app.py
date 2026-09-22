import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from leo_risk.infrastructure.logging.config import get_settings
from leo_risk.infrastructure.logging.logger import setup_logging
from leo_risk.interface.http.routes.health import router as health_router
from leo_risk.interface.http.routes.validate import router as validate_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting %s v%s [%s]", settings.app_name, settings.app_version, settings.environment)
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )
    app.include_router(health_router)
    if settings.debug:
        app.include_router(validate_router)
    return app


app = create_app()
