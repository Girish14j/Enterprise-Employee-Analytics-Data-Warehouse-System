"""Project-wide exception hierarchy.

Every layer raises one of these so the UI can show a clear message without
knowing anything about SQLAlchemy, PyMySQL or MySQL error codes.
"""
from __future__ import annotations

from typing import Optional


class AppError(Exception):
    """Base class for all application errors."""


class ConfigurationError(AppError):
    """Missing or invalid environment / secrets configuration."""


class DatabaseError(AppError):
    """A database operation failed. ``code`` holds the MySQL error code if known."""

    def __init__(self, message: str, code: Optional[int] = None):
        super().__init__(message)
        self.code = code


class IntegrityViolationError(DatabaseError):
    """A constraint (PK, UNIQUE, FK, CHECK) was violated."""


class ValidationError(AppError):
    """User input / entity validation failed."""


class RecordNotFoundError(AppError):
    """The requested row does not exist."""


class DuplicateRecordError(AppError):
    """A row with the same business key already exists."""


class ETLError(AppError):
    """The OLTP -> Data Warehouse pipeline failed."""
