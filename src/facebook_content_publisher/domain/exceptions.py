"""Domain-specific errors."""


class EntityNotFoundError(LookupError):
    """Raised when a requested entity does not exist."""


class DuplicateEntityError(ValueError):
    """Raised when a unique business key already exists."""
