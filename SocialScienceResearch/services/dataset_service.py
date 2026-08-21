"""Dataset construction, quality and export service (B7).

A dataset is a *materialized, immutable row set* from the corpus:

* :meth:`create_dataset` snapshots the whole ``entity_type`` population;
* :meth:`create_from_project` snapshots the rows matching a persisted
  :class:`Project`'s research query, projected onto its ``variable_selection``
  (or all reported columns when none is chosen).

Rows are resolved through ``QueryService.resolve_latest_rows`` (observed
metrics resolved to their *latest* observation) and, for project datasets,
filtered by ``domain.query.evaluate_query`` over ``QueryGroup`` semantics.
Member ids are the entity's id field of each row (``video_id``/``comment_id``/
``channel_id``/``recommended_video_id``); members are persisted as chunked row
projections (see ``DatasetRepository``). With ``include_raw=True`` the per-
member ``raw_json`` payloads are snapshotted to a JSON sidecar per dataset
under ``{data_dir}/raw`` (never inside Excel, following the transcript-artifact
precedent).
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

from SocialScienceResearch.config.settings import SocialScienceSettings
from SocialScienceResearch.domain.dataset_models import (
    ColumnCoverage,
    Dataset,
    DatasetQualityReport,
    UpdateProjectRequest,
)
from SocialScienceResearch.domain.query import (
    QueryContext,
    QueryGroup,
    evaluate_query,
)
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.quality_service import QualityService
from SocialScienceResearch.services.query_service import QueryService
from SocialScienceResearch.utils.idgen import new_id, utcnow

#: id field of the member row per entity (mirrors what resolve_latest_rows emits).
_ID_FIELD: dict[str, str] = {
    "video": "video_id",
    "comment": "comment_id",
    "channel": "channel_id",
    "recommendation": "recommended_video_id",
    "author": "author_id",
}


class DatasetService:
    """Build, inspect, quality-check and export materialized datasets."""

    def __init__(
        self,
        repos: Repositories,
        settings: SocialScienceSettings | None = None,
    ) -> None:
        self._repos = repos
        self._settings = settings or SocialScienceSettings()
        self._datasets = repos.datasets
        self._projects = repos.projects
        self._quality = QualityService(repos)
        self._query = QueryService(repos, settings)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def create_dataset(
        self,
        name: str,
        description: str | None = None,
        entity_type: str = "video",
        include_raw: bool = False,
        run_ids: list[str] | None = None,
        channel_ids: list[str] | None = None,
        video_ids: list[str] | None = None,
        member_ids: list[str] | None = None,
        criteria: dict | None = None,
        variable_selection: list[str] | None = None,
        lineage: dict | None = None,
    ) -> Dataset:
        """Snapshot the whole ``entity_type`` population as a dataset.

        When ``channel_ids`` or ``video_ids`` are provided, the population is
        scoped to those ids. ``member_ids`` further restricts to the exact
        entity ids supplied (used to materialize a sampling result into a
        dataset). ``criteria`` (a QueryGroup dict) can further filter
        the rows. ``variable_selection`` overrides the default column set.
        ``run_ids`` scopes recommendation rows to edges observed in those runs
        (so per-run datasets are honest slices, not whole-population
        snapshots). ``lineage`` records the provenance of the dataset (e.g.
        which run/action triggered its creation).
        """
        entity = self._entity(entity_type)
        rows = self._query.resolve_latest_rows(entity, run_ids=run_ids)

        if channel_ids:
            rows = [r for r in rows if r.get("channel_id") in channel_ids]
        if video_ids:
            rows = [r for r in rows if r.get("video_id") in video_ids]
        if member_ids:
            id_field = _ID_FIELD[entity]
            member_set = set(member_ids)
            rows = [r for r in rows if r.get(id_field) in member_set]
        if criteria:
            root = QueryGroup.model_validate(criteria)
            rows = evaluate_query(entity, root, rows)
        if variable_selection is not None:
            columns = variable_selection
        else:
            columns = None

        return self._register(
            name=name,
            description=description,
            entity=entity,
            rows=rows,
            columns=columns,
            project_id=None,
            query_hash=None,
            include_raw=include_raw,
            run_ids=run_ids or [],
            channel_ids=channel_ids or [],
            video_ids=video_ids or [],
            member_ids=member_ids or [],
            criteria=criteria,
            variable_selection=variable_selection or [],
            lineage=lineage,
        )

    def create_from_project(
        self,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
        include_raw: bool = False,
        entity_type: str | None = None,
    ) -> Dataset:
        """Build a dataset from a persisted project's research query + selection.

        Honors the project's ``research_query`` by reconstructing the
        ``domain.query.QueryGroup`` tree and running ``evaluate_query`` over the
        resolved population; ``variable_selection`` (when non-empty) chooses
        which columns persist. ``name``/``description`` default to the project's.
        """
        project = self._projects.get_project(project_id)
        if project is None:
            raise ValueError(f"Project {project_id!r} not found")

        query = project.research_query
        if query:
            entity = self._entity(entity_type or query.get("entity"))
            root = QueryGroup(**query["root"])
            rows = self._query.resolve_latest_rows(
                entity,
                context=(
                    QueryContext(**query["query_context"])
                    if query.get("query_context") is not None
                    else None
                ),
            )
            matched = evaluate_query(entity, root, rows)
            query_hash = _query_digest(query)
        else:
            entity = self._entity(entity_type or "")
            rows = self._query.resolve_latest_rows(entity)
            matched = rows
            query_hash = None

        return self._register(
            name=name or project.name,
            description=description or project.description,
            entity=entity,
            rows=matched,
            columns=project.variable_selection or None,
            project_id=project_id,
            query_hash=query_hash,
            include_raw=include_raw,
            run_ids=[],
            channel_ids=[],
            video_ids=[],
            member_ids=[],
            criteria=None,
            variable_selection=project.variable_selection or [],
        )

    # ------------------------------------------------------------------
    # Read / delete
    # ------------------------------------------------------------------
    def list_datasets(self) -> list[Dataset]:
        return self._datasets.list_datasets()

    def get_dataset(self, dataset_id: str) -> Dataset:
        dataset = self._datasets.get_dataset(dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {dataset_id!r} not found")
        return dataset

    def delete_dataset(self, dataset_id: str) -> None:
        self.get_dataset(dataset_id)
        self._datasets.delete_dataset(dataset_id)

    def members(self, dataset_id: str) -> list[dict[str, Any]]:
        """Return the member row projections of a dataset (id-field present)."""
        self.get_dataset(dataset_id)
        return self._datasets.list_members(dataset_id)

    def member_count(self, dataset_id: str) -> int:
        return self._datasets.dataset_member_count(dataset_id)

    # ------------------------------------------------------------------
    # Quality
    # ------------------------------------------------------------------
    def quality(self, dataset_id: str) -> DatasetQualityReport:
        """Missing-value matrix (share of None per stored column) + coverage.

        ``QualityService.coverage()``/``dataset_summary()`` texture is reused
        for the corpus-level summary embedded in ``corpus``; the column matrix
        is computed over the dataset's stored member projections.
        """
        dataset = self.get_dataset(dataset_id)
        members = self._datasets.list_members(dataset_id)
        total = len(members)
        columns: list[str] = list(dataset.source_projection.get("columns") or [])
        if not columns:
            for member in members:
                for key in member:
                    if key not in columns:
                        columns.append(key)

        column_stats: list[ColumnCoverage] = []
        present_total = 0
        for column in columns:
            present = sum(1 for m in members if m.get(column) is not None)
            missing = total - present
            column_stats.append(
                ColumnCoverage(
                    name=column,
                    present=present,
                    missing=missing,
                    missing_share=round(missing / total, 4) if total else 0.0,
                )
            )
            present_total += present
        cells = total * len(columns)
        return DatasetQualityReport(
            dataset_id=dataset_id,
            columns=column_stats,
            overall_coverage=(
                round(present_total / cells, 4) if cells else 1.0
            ),
            generated_at=utcnow(),
            corpus=self._quality.dataset_summary(),
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def export(
        self, dataset_id: str, format: str = "csv"
    ) -> tuple[str, str, str]:
        """Serialize member rows; returns ``(filename, content, media_type)``."""
        fmt = format.strip().lower()
        if fmt not in ("csv", "json"):
            raise ValueError(
                f"unsupported export format {format!r}; expected 'csv' or 'json'"
            )
        dataset = self.get_dataset(dataset_id)
        members = self._datasets.list_members(dataset_id)
        columns: list[str] = list(
            dataset.source_projection.get("columns")
            or _union_columns(members)
        )

        if fmt == "csv":
            buffer = StringIO()
            writer = csv.writer(buffer, dialect="excel")
            writer.writerow(columns)
            for member in members:
                writer.writerow([_csv_cell(member.get(column)) for column in columns])
            return (
                f"{dataset_id}.csv",
                buffer.getvalue(),
                "text/csv",
            )
        payload = {
            "dataset": dataset.model_dump(mode="json"),
            "columns": columns,
            "members": members,
        }
        return (
            f"{dataset_id}.json",
            json.dumps(payload, ensure_ascii=False, default=str),
            "application/json",
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _register(
        self,
        *,
        name: str,
        description: str | None,
        entity: str,
        rows: list[dict[str, Any]],
        columns: list[str] | None,
        project_id: str | None,
        query_hash: str | None,
        include_raw: bool,
        run_ids: list[str],
        channel_ids: list[str],
        video_ids: list[str],
        member_ids: list[str],
        criteria: dict | None,
        variable_selection: list[str],
        lineage: dict | None = None,
    ) -> Dataset:
        id_field = _ID_FIELD[entity]
        if columns is None:
            columns = list(rows[0].keys()) if rows else []
        # The entity id is always the first persisted column - it is the row's
        # membership key, not an analysis variable, so it survives selection.
        persisted = [
            id_field,
            *[column for column in columns if column != id_field],
        ]
        members = [
            {column: row.get(column) for column in persisted} for row in rows
        ]

        dataset_id = new_id("dst")
        chunks = self._datasets.save_members(dataset_id, members)
        dataset = Dataset(
            dataset_id=dataset_id,
            name=name,
            description=description,
            entity_type=entity,
            created_at=utcnow(),
            created_by_run_id=self._last_run_id(),
            source_projection={
                "entity": entity,
                "id_field": id_field,
                "columns": persisted,
                "include_raw": include_raw,
                "project_id": project_id,
                "query_hash": query_hash,
                "row_count": len(members),
                "variable_selection": columns,
                "scope": {
                    "run_ids": run_ids,
                    "channel_ids": channel_ids,
                    "video_ids": video_ids,
                    "member_ids": member_ids,
                },
                "criteria": criteria,
                "lineage": lineage,
            },
            member_count=len(members),
            overflow=chunks > 1,
        )
        self._datasets.save_dataset(dataset)
        if include_raw:
            self._snapshot_raw(dataset_id, entity, id_field, members)
        return dataset

    def _snapshot_raw(
        self,
        dataset_id: str,
        entity: str,
        id_field: str,
        members: list[dict[str, Any]],
    ) -> Path:
        """Write per-member raw payloads to ``{data_dir}/raw/{dataset_id}.json``."""
        raw: dict[str, Any] = {}
        for member in members:
            member_id = member.get(id_field)
            if member_id is None:
                continue
            payload = self._raw_for(entity, str(member_id))
            if payload is not None:
                raw[str(member_id)] = payload
        raw_dir = Path(self._settings.repository.data_dir) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        path = raw_dir / f"{dataset_id}.json"
        path.write_text(
            json.dumps(raw, ensure_ascii=False, default=str), encoding="utf-8"
        )
        return path

    def _raw_for(self, entity: str, entity_id: str) -> dict[str, Any] | None:
        if entity == "video":
            video = self._repos.videos.get_video(entity_id)
            return video.raw_json if video else None
        if entity == "channel":
            channel = self._repos.channels.get_channel(entity_id)
            return channel.raw_json if channel else None
        if entity == "comment":
            comment = self._repos.comments.get_comment(entity_id)
            return comment.raw_json if comment else None
        for edge in self._repos.recommendations.list_recommendation_edges():
            if edge.recommended_video_id == entity_id:
                return edge.raw_json
        return None

    def _last_run_id(self) -> str | None:
        runs = self._repos.runs.list_runs()
        if not runs:
            return None
        return max(runs, key=lambda r: r.started_at).run_id

    @staticmethod
    def _entity(entity_type: str | None) -> str:
        entity = (entity_type or "").strip().lower()
        if entity not in _ID_FIELD:
            raise ValueError(
                f"Unknown entity {entity_type!r}; expected one of "
                f"{sorted(_ID_FIELD)}"
            )
        return entity


def _query_digest(query: dict[str, Any]) -> str:
    """Short content hash of a project's research query (spec_hash style)."""
    canonical = json.dumps(query, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _union_columns(members: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for member in members:
        for key in member:
            if key not in columns:
                columns.append(key)
    return columns


def _csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value