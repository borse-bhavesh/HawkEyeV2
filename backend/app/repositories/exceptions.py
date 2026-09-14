class RepositoryError(Exception):
    """Base class for repository exceptions."""
    pass

class RecordNotFoundError(RepositoryError):
    """Raised when a requested record is not found."""
    pass

class DuplicateRecordError(RepositoryError):
    """Raised when attempting to create a record that already exists."""
    pass
