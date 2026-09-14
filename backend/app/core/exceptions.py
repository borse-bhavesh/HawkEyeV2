class HawkeyeException(Exception):
    """Base exception for HAWKEYE application errors."""


class DatabaseConnectionError(HawkeyeException):
    """Raised when the database cannot be reached."""