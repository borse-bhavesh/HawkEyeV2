from fastapi import APIRouter

from app.core.config import settings
from app.db.database import check_database_connection

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check() -> dict:
    """
    Return backend and database health.
    """

    database_online = check_database_connection()

    return {
        "status": "online" if database_online else "degraded",
        "service": settings.app_name,
        "version": settings.app_version,
        "backend": "online",
        "database": "online" if database_online else "offline",
    }