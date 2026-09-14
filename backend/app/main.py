import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.video import router as video_router
from app.api.routes.sessions import router as sessions_router
from app.core.config import settings
from app.core.logging import setup_logging


setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle handler.
    """

    logger.info(
        "HAWKEYE_STARTUP | version=%s | environment=%s",
        settings.app_version,
        settings.environment,
    )

    yield

    logger.info("HAWKEYE_SHUTDOWN")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AI-Based Intelligent Video Analytics Platform "
        "for Border Surveillance"
    ),
    lifespan=lifespan,
)

# Set up CORS for development (allowing frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://hawk-eye-v2.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
def root() -> dict:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "online",
    }


app.include_router(
    health_router,
    prefix=settings.api_prefix,
)

app.include_router(
    video_router,
    prefix=settings.api_prefix,
)

app.include_router(
    sessions_router,
    prefix=settings.api_prefix,
)