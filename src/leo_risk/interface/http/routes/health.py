import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from leo_risk.infrastructure.logging.config import get_settings

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

_start_time = datetime.now(timezone.utc)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, str | bool | float]:
    settings = get_settings()
    uptime = (datetime.now(timezone.utc) - _start_time).total_seconds()
    return {
        "status": "ready",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": uptime,
    }
