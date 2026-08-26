"""Excel-backed repository for persisted collection jobs (plan J1).

Mirrors the minimal store-backed style of ``persistence.layer_repository``:
``CollectionJob`` rows are upserted by ``job_id`` into a dedicated
``collection_jobs`` sheet. Only milestones + terminal states are written, so
the sheet stays tiny even for long crawls.
"""

from __future__ import annotations

from SocialScienceResearch.domain.job_models import CollectionJob
from SocialScienceResearch.persistence.excel_workbook import WorkbookStore
from SocialScienceResearch.persistence.serialization import (
    headers_for,
    model_to_row,
    row_to_model,
)

_SHEET = "collection_jobs"


class ExcelJobRepository:
    def __init__(self, store: WorkbookStore) -> None:
        self._store = store
        store.ensure_sheet(_SHEET, headers_for(CollectionJob))

    def save_job(self, job: CollectionJob) -> None:
        self._store.upsert_row(
            _SHEET, "job_id", headers_for(CollectionJob), model_to_row(job)
        )

    def get_job(self, job_id: str) -> CollectionJob | None:
        row = self._store.find_row(_SHEET, "job_id", job_id)
        if row is None or row.get("job_id") != job_id:
            return None
        return row_to_model(CollectionJob, row)

    def list_jobs(
        self,
        kind: str | None = None,
        status: str | None = None,
    ) -> list[CollectionJob]:
        def _created_key(job: CollectionJob) -> str:
            return job.created_at.isoformat() if job.created_at else ""

        jobs = [
            row_to_model(CollectionJob, r)  # type: ignore[arg-type]
            for r in self._store.read_rows(_SHEET, key_field="job_id")
        ]
        if kind is not None:
            jobs = [j for j in jobs if j.kind == kind]
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=_created_key, reverse=True)
