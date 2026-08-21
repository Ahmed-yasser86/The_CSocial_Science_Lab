"""Persistence layer: repository interfaces and the Excel implementation.

Importing from this package exposes the interfaces (``persistence.base``) and
the concrete Excel repositories (``persistence.excel_repository``). Services
should depend on the interfaces so a SQL backend can replace Excel later.
"""

from __future__ import annotations

from .base import (
    ChannelRepository,
    CollectionRunRepository,
    CommentRepository,
    RecommendationRepository,
    Repositories,
    UpsertResult,
    VideoRepository,
)
from .errors import DuplicateKeyError, PersistenceError, RepositoryError
from .excel_repository import (
    ExcelChannelRepository,
    ExcelCollectionRunRepository,
    ExcelCommentRepository,
    ExcelRecommendationRepository,
    ExcelRepositories,
    ExcelVideoRepository,
    build_excel_repositories,
)
from .excel_workbook import WorkbookStore

__all__ = [
    "ChannelRepository",
    "CollectionRunRepository",
    "CommentRepository",
    "DuplicateKeyError",
    "ExcelChannelRepository",
    "ExcelCollectionRunRepository",
    "ExcelCommentRepository",
    "ExcelRecommendationRepository",
    "ExcelRepositories",
    "ExcelVideoRepository",
    "PersistenceError",
    "RecommendationRepository",
    "Repositories",
    "RepositoryError",
    "UpsertResult",
    "VideoRepository",
    "WorkbookStore",
    "build_excel_repositories",
]
