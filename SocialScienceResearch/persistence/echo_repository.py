"""Excel-backed repository for echo-chamber detections (echo plan §4).

Mirrors the minimal store-backed style of ``persistence.layer_repository``:
``EchoDetection`` rows are upserted by ``detection_id`` into a dedicated
``echo_detections`` sheet. The append-only per-layer timeline lives inside
the row (JSON-encoded list) so a detection is one read.
"""

from __future__ import annotations

from SocialScienceResearch.domain.echo_models import EchoDetection
from SocialScienceResearch.persistence.excel_workbook import WorkbookStore
from SocialScienceResearch.persistence.serialization import (
    headers_for,
    model_to_row,
    row_to_model,
)

_SHEET = "echo_detections"


class ExcelEchoDetectionRepository:
    def __init__(self, store: WorkbookStore) -> None:
        self._store = store
        store.ensure_sheet(_SHEET, headers_for(EchoDetection))

    def save_detection(self, detection: EchoDetection) -> None:
        self._store.upsert_row(
            _SHEET,
            "detection_id",
            headers_for(EchoDetection),
            model_to_row(detection),
        )

    def get_detection(self, detection_id: str) -> EchoDetection | None:
        row = self._store.find_row(_SHEET, "detection_id", detection_id)
        if row is None or row.get("detection_id") != detection_id:
            return None
        return row_to_model(EchoDetection, row)

    def list_detections(self) -> list[EchoDetection]:
        detections = [
            row_to_model(EchoDetection, r)  # type: ignore[arg-type]
            for r in self._store.read_rows(_SHEET, key_field="detection_id")
        ]
        return sorted(
            detections,
            key=lambda d: d.created_at.isoformat() if d.created_at else "",
            reverse=True,
        )
