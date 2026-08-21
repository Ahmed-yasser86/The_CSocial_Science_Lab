"""Excel-backed repository for layer-run anchor records.

A *minimal store-backed* implementation (mirroring the shared behaviour of
``_ExcelEntityRepository`` in ``persistence.excel_repository``): it goes
straight to ``WorkbookStore`` and the ``persistence.serialization`` helpers.
``LayerRun`` records are upserted by ``layer_run_id`` into a dedicated
``layer_runs`` sheet.
"""

from __future__ import annotations

from SocialScienceResearch.domain.layer_models import LayerRun
from SocialScienceResearch.persistence.excel_workbook import WorkbookStore
from SocialScienceResearch.persistence.serialization import (
    headers_for,
    model_to_row,
    row_to_model,
)

_SHEET = "layer_runs"


class LayerRunRepository:
    def __init__(self, store: WorkbookStore) -> None:
        self._store = store
        store.ensure_sheet(_SHEET, headers_for(LayerRun))

    def save_layer_run(self, layer_run: LayerRun) -> None:
        self._store.upsert_row(
            _SHEET, "layer_run_id", headers_for(LayerRun), model_to_row(layer_run)
        )

    def get_layer_run(self, layer_run_id: str) -> LayerRun | None:
        row = self._store.find_row(_SHEET, "layer_run_id", layer_run_id)
        if row is None or row.get("layer_run_id") != layer_run_id:
            return None
        return row_to_model(LayerRun, row)

    def list_layer_runs(self) -> list[LayerRun]:
        return [
            row_to_model(LayerRun, r)
            for r in self._store.read_rows(_SHEET, key_field="layer_run_id")
        ]
