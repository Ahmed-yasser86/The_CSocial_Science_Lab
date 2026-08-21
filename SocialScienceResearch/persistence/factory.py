"""Repository container factory with backend dispatch.

``build_repositories`` returns the ``Repositories`` container selected by
``RepositorySettings.backend``: the Excel implementation (default) or the
PostgreSQL implementation. Both containers expose the same repository
interfaces so services and the API are backend-agnostic.
"""

from __future__ import annotations

from SocialScienceResearch.config.settings import RepositorySettings
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.persistence.excel_repository import build_excel_repositories


def build_repositories(
    settings: RepositorySettings | None = None,
) -> Repositories:
    """Build the repository container for the configured persistence backend."""
    repo_settings = settings or RepositorySettings()
    if repo_settings.backend == "sql":
        from SocialScienceResearch.persistence.sql.repositories import (
            build_sql_repositories,
        )

        return build_sql_repositories(
            database_url=repo_settings.database_url,
            transcripts_dir=repo_settings.transcripts_dir,
        )
    return build_excel_repositories(repo_settings)
