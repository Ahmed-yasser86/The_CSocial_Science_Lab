"""Error types for the persistence layer."""

from __future__ import annotations


class RepositoryError(Exception):
    """Base class for all persistence/repository errors."""


class PersistenceError(RepositoryError):
    """Raised when a storage operation fails (e.g. Excel write failure)."""


class DuplicateKeyError(RepositoryError):
    """Raised when a strict insert violates a unique key constraint."""
