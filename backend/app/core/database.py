from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings


def get_engine():
    """
    Creates and returns a new SQLAlchemy engine based on current settings.
    This allows test configurations to easily override the engine.
    """
    settings = get_settings()
    # We allow tests to pass a different database_url if needed via env, 
    # but the settings object already provides it.
    if not settings.database_url:
        raise ValueError("DATABASE_URL is not configured")
        
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,  # Verify connections before using them
        pool_size=5,
        max_overflow=10
    )


# Application's default engine
engine = get_engine()

# Factory for creating new sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Generator[Session, None, None]:
    """
    Dependency/context manager that provides a database session.
    Ensures the session is closed after use.
    Suitable for FastAPI Depends() or contextlib.contextmanager.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connectivity(db_engine=None) -> bool:
    """
    Checks if the database is reachable and accepting connections.
    Uses the provided engine or falls back to the default application engine.
    """
    target_engine = db_engine or engine
    try:
        with target_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return True
    except SQLAlchemyError:
        return False
