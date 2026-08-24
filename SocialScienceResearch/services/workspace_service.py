"""Workspace service - registry, provisioning and activation (plan §2/§3).

A workspace is a fully isolated environment: its own PostgreSQL database plus
its own ``data_dir``. The registry is a small JSON document under the *root*
data dir (``workspaces/registry.json``) written atomically with the same
tmp+``os.replace`` pattern as :mod:`SocialScienceResearch.services.session_service`.

Isolation mechanism (decision (c) of ``CodingPlans/workspace_isolation_plan.md``):
every workspace entry carries its own ``database_url`` and ``data_dir``; no row
is ever shared because a connection points at exactly one database. The
existing production database + data dir are registered unchanged as the
renamable **Legacy** workspace on first run - nothing moves, nothing is copied,
nothing is deleted.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from SocialScienceResearch.config.settings import (
    RepositorySettings,
    SocialScienceSettings,
)
from SocialScienceResearch.domain.workspace_models import (
    ActiveWorkspacePointer,
    Workspace,
    WorkspaceStats,
)
from SocialScienceResearch.persistence.factory import build_repositories
from SocialScienceResearch.utils.idgen import utcnow

_LEGACY_NAME = "Legacy"


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Write JSON atomically (tmp file + ``os.replace``), creating parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict:
    """Tolerant read: missing or corrupt file means "no data"."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


class WorkspaceService:
    """CRUD + activation over the workspace registry."""

    def __init__(self, settings: SocialScienceSettings | None = None) -> None:
        self._settings = settings or SocialScienceSettings()
        self._root = Path(self._settings.repository.data_dir)
        self._dir = self._root / "workspaces"
        self._registry_path = self._dir / "registry.json"
        self._active_path = self._dir / "active.json"

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    @property
    def registry_path(self) -> Path:
        return self._registry_path

    @property
    def workspaces_root(self) -> Path:
        return self._dir

    def _workspace_entry(self, workspace: Workspace) -> dict:
        return workspace.model_dump(mode="json")

    # ------------------------------------------------------------------
    # Registry IO
    # ------------------------------------------------------------------
    def _load_registry(self) -> list[Workspace]:
        raw = _read_json(self._registry_path)
        entries = raw.get("workspaces", [])
        workspaces: list[Workspace] = []
        for entry in entries:
            if isinstance(entry, dict):
                try:
                    workspaces.append(Workspace.model_validate(entry))
                except ValueError:
                    continue
        return workspaces

    def _save_registry(self, workspaces: list[Workspace]) -> None:
        _atomic_write_json(
            self._registry_path,
            {
                "workspaces": [self._workspace_entry(w) for w in workspaces],
            },
        )

    def _load_active(self) -> str | None:
        raw = _read_json(self._active_path)
        value = raw.get("workspace_id")
        return value if isinstance(value, str) and value else None

    def _save_active(self, workspace_id: str | None) -> None:
        pointer = ActiveWorkspacePointer(
            workspace_id=workspace_id, updated_at=utcnow()
        )
        _atomic_write_json(self._active_path, pointer.model_dump(mode="json"))

    # ------------------------------------------------------------------
    # Bootstrap (Legacy migration)
    # ------------------------------------------------------------------
    def bootstrap(self) -> Workspace | None:
        """Register the existing default DB/data dir as Legacy on first run.

        Idempotent: when a registry already exists this is a no-op, so calling
        it on every startup never touches production data.
        """
        if self._registry_path.exists():
            return None
        now = utcnow()
        repo = self._settings.repository
        legacy = Workspace(
            workspace_id="ws_legacy",
            name=_LEGACY_NAME,
            research_topic=None,
            database_url=repo.database_url,
            data_dir=str(self._root),
            created_at=now,
            last_opened_at=now,
            is_legacy=True,
        )
        self._save_registry([legacy])
        if self._load_active() is None:
            self._save_active(legacy.workspace_id)
        return legacy

    def ensure_legacy_registered(self) -> bool:
        """True when the Legacy entry exists after :meth:`bootstrap`."""
        self.bootstrap()
        return any(w.is_legacy for w in self._load_registry())

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def list_workspaces(self) -> list[Workspace]:
        return sorted(self._load_registry(), key=lambda w: w.created_at)

    def get(self, workspace_id: str) -> Workspace:
        for workspace in self._load_registry():
            if workspace.workspace_id == workspace_id:
                return workspace
        raise KeyError(f"Workspace {workspace_id!r} not found")

    def create(
        self, name: str, *, research_topic: str | None = None
    ) -> Workspace:
        """Provision a NEW isolated workspace: fresh DB + schema + data dir."""
        workspace_id = f"ws_{secrets.token_hex(4)}"
        database_url = self._provision_database(workspace_id)
        data_dir = self._dir / workspace_id / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        now = utcnow()
        workspace = Workspace(
            workspace_id=workspace_id,
            name=name,
            database_url=database_url,
            data_dir=str(data_dir),
            research_topic=research_topic,
            created_at=now,
            last_opened_at=now,
            is_legacy=False,
        )
        workspaces = self._load_registry()
        workspaces.append(workspace)
        self._save_registry(workspaces)
        return workspace

    def update(self, workspace_id: str, changes: dict) -> Workspace:
        """Apply an explicit ``{field: value}`` dict (caller owns patch semantics)."""
        workspaces = self._load_registry()
        for index, workspace in enumerate(workspaces):
            if workspace.workspace_id != workspace_id:
                continue
            updates = {
                key: value
                for key, value in changes.items()
                if key in {"name", "research_topic"}
            }
            workspaces[index] = workspace.model_copy(update=updates)
            self._save_registry(workspaces)
            return workspaces[index]
        raise KeyError(f"Workspace {workspace_id!r} not found")

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------
    def active_workspace_id(self) -> str | None:
        return self._load_active()

    def activate(self, workspace_id: str) -> Workspace:
        """Point the server at ``workspace_id`` (idempotent pointer update).

        Also defensively clears the class-level graph / overlap caches: they
        have no workspace dimension, so a switch must never leave stale entries
        behind (plan §2.3 step 4, pitfalls R1/A1).
        """
        workspace = self.get(workspace_id)
        self._save_active(workspace.workspace_id)
        workspaces = self._load_registry()
        bumped = workspace
        for index, entry in enumerate(workspaces):
            if entry.workspace_id == workspace.workspace_id:
                bumped = entry.model_copy(update={"last_opened_at": utcnow()})
                workspaces[index] = bumped
        self._save_registry(workspaces)
        self._clear_shared_caches()
        return bumped

    def deactivate(self) -> None:
        """Clear the active pointer (chooser state); per-workspace session
        files stay intact."""
        self._save_active(None)
        self._clear_shared_caches()

    @staticmethod
    def _clear_shared_caches() -> None:
        from SocialScienceResearch.services.commenter_overlap_service import (
            CommenterOverlapService,
        )
        from SocialScienceResearch.services.recommendation_graph_service import (
            RecommendationGraphService,
        )

        RecommendationGraphService.clear_graph_cache()
        CommenterOverlapService.clear_overlap_cache()

    # ------------------------------------------------------------------
    # Provisioning helpers
    # ------------------------------------------------------------------
    def repository_settings(self, workspace: Workspace) -> RepositorySettings:
        """Per-workspace persistence settings (same backend conventions)."""
        base = self._settings.repository
        return RepositorySettings(
            data_dir=workspace.data_dir,
            dataset_name=base.dataset_name,
            max_rows_per_sheet=base.max_rows_per_sheet,
            flush_every=base.flush_every,
            backend=base.backend,
            database_url=workspace.database_url,
        )

    def _sibling_database_url(self, workspace_id: str) -> str:
        """Derive ``<dbname>__<workspace_id>`` from the configured base URL."""
        parts = urlsplit(self._settings.repository.database_url)
        base_db = parts.path.lstrip("/") or "social_science"
        parts = parts._replace(path=f"/{base_db}__{workspace_id}")
        return urlunsplit(parts)

    def _provision_database(self, workspace_id: str) -> str:
        """Create the workspace's empty database and ensure its schema.

        The CREATE DATABASE statement runs over an autocommit admin connection
        to the same server (``postgres`` maintenance database). An existing
        database with the target name is adopted (idempotent re-provision).
        """
        database_url = self._sibling_database_url(workspace_id)
        import psycopg

        parts = urlsplit(database_url)
        admin_parts = parts._replace(path="/postgres")
        admin_url = urlunsplit(admin_parts)
        db_name = parts.path.lstrip("/")
        try:
            with psycopg.connect(admin_url, autocommit=True) as conn:
                conn.execute(f'CREATE DATABASE "{db_name}"')
        except psycopg.errors.DuplicateDatabase:
            pass
        from SocialScienceResearch.persistence.sql.database import SqlDatabase

        db = SqlDatabase(database_url)
        try:
            db.create_schema()
        finally:
            db.close()
        return database_url

    # ------------------------------------------------------------------
    # Stats (without activating)
    # ------------------------------------------------------------------
    def stats(self, workspace: Workspace) -> WorkspaceStats:
        """Volume counters computed through a short-lived repository binding.

        Bounded + sequential: each call opens one pool, materializes the
        counts and closes it again; the single uvicorn worker serves these
        one card at a time.
        """
        repos = build_repositories(self.repository_settings(workspace))
        try:
            return WorkspaceStats(
                runs=len(repos.runs.list_runs()),
                videos=len(repos.videos.list_videos()),
                channels=len(repos.channels.list_channels()),
                comments=len(repos.comments.list_comments()),
                datasets=len(repos.datasets.list_datasets()),
                samples=len(repos.samples.list()),
                projects=len(repos.projects.list_projects()),
            )
        finally:
            store = getattr(repos, "store", None)
            if store is not None:
                store.close()

