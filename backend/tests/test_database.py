import os
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine

from app.core.config import Settings
from app.core.database import (
    get_engine,
    get_db_session,
    check_database_connectivity,
)


def test_database_url_configuration():
    """Ensure DATABASE_URL can be configured via environment without hardcoding."""
    test_url = "postgresql+psycopg://testuser:testpass@localhost:5432/testdb"
    
    with patch.dict(os.environ, {"DATABASE_URL": test_url}):
        # Need to create a fresh Settings instance to pick up the env var
        settings = Settings()
        assert settings.database_url == test_url


def test_engine_creation_uses_settings(monkeypatch):
    """Ensure the engine uses the configured DATABASE_URL."""
    test_url = "postgresql+psycopg://dummy:dummy@localhost:5432/dummy"
    
    mock_settings = Settings(database_url=test_url)
    monkeypatch.setattr("app.core.database.get_settings", lambda: mock_settings)
    
    engine = get_engine()
    # verify the engine's url string matches our test URL
    assert engine.url.render_as_string(hide_password=False) == test_url


def test_engine_creation_fails_without_url(monkeypatch):
    """Ensure engine creation fails if the database_url is empty."""
    mock_settings = Settings(database_url="")
    monkeypatch.setattr("app.core.database.get_settings", lambda: mock_settings)
    
    with pytest.raises(ValueError, match="DATABASE_URL is not configured"):
        get_engine()


def test_session_lifecycle_and_cleanup(monkeypatch):
    """Ensure the session dependency yields a session and then closes it."""
    mock_session = MagicMock()
    mock_session_local = MagicMock(return_value=mock_session)
    
    monkeypatch.setattr("app.core.database.SessionLocal", mock_session_local)
    
    # Iterate through the generator
    session_generator = get_db_session()
    
    # First next() yields the session
    yielded_session = next(session_generator)
    assert yielded_session is mock_session
    mock_session.close.assert_not_called()
    
    # Second next() triggers finally block and StopIteration
    with pytest.raises(StopIteration):
        next(session_generator)
        
    mock_session.close.assert_called_once()


def test_session_cleanup_on_exception(monkeypatch):
    """Ensure the session is closed even if an exception occurs during usage."""
    mock_session = MagicMock()
    mock_session_local = MagicMock(return_value=mock_session)
    
    monkeypatch.setattr("app.core.database.SessionLocal", mock_session_local)
    
    session_generator = get_db_session()
    yielded_session = next(session_generator)
    
    try:
        session_generator.throw(RuntimeError("Test error"))
    except RuntimeError:
        pass
        
    mock_session.close.assert_called_once()


def test_connectivity_success(monkeypatch):
    """Ensure health check returns True when connection succeeds."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    # Mock context manager behavior for with engine.connect()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    
    is_connected = check_database_connectivity(db_engine=mock_engine)
    
    assert is_connected is True
    mock_conn.execute.assert_called_once()


def test_connectivity_failure(monkeypatch):
    """Ensure health check returns False when connection fails."""
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = SQLAlchemyError("Connection failed")
    
    is_connected = check_database_connectivity(db_engine=mock_engine)
    
    assert is_connected is False


def test_real_database_connectivity():
    """
    Test real connectivity to the running PostgreSQL container.
    This expects the database_url to be valid and pointing to the dev DB.
    """
    # By default, config.py has a default URL pointing to localhost:5432
    # If the docker container is running, this should succeed.
    is_connected = check_database_connectivity()
    assert is_connected is True, "Could not connect to the local development database"
