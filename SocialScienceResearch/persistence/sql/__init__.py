"""PostgreSQL persistence backend for the SocialScienceResearch module.

Replaces the Excel workbook + overflow sidecars with ``JSONB`` columns in a
PostgreSQL database (see ``docs/excel_to_postgres_migration.md``). Exposes the
same repository container built by ``excel_repository.build_excel_repositories``
so services and the API are unchanged.
"""

from __future__ import annotations

from .database import DEFAULT_DATABASE_URL, SqlDatabase, build_schema_sql
from .repositories import (
    SqlChannelRepository,
    SqlCollectionRunRepository,
    SqlCommentRepository,
    SqlDatasetRepository,
    SqlLayerRunRepository,
    SqlProjectItemRepository,
    SqlProjectRepository,
    SqlRecommendationRepository,
    SqlRepositories,
    SqlSampleRepository,
    SqlTranscriptRepository,
    SqlVideoRepository,
    build_sql_repositories,
)

__all__ = [
    "DEFAULT_DATABASE_URL",
    "SqlChannelRepository",
    "SqlCollectionRunRepository",
    "SqlCommentRepository",
    "SqlDatabase",
    "SqlDatasetRepository",
    "SqlLayerRunRepository",
    "SqlProjectItemRepository",
    "SqlProjectRepository",
    "SqlRecommendationRepository",
    "SqlRepositories",
    "SqlSampleRepository",
    "SqlTranscriptRepository",
    "SqlVideoRepository",
    "build_schema_sql",
    "build_sql_repositories",
]