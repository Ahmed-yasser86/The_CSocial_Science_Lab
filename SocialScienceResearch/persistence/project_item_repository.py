"""Excel-backed repository for ProjectItems (research project sub-items).

A ProjectItem groups related samples and datasets within a project,
allowing researchers to organize their work into logical units.
"""

from __future__ import annotations

from SocialScienceResearch.domain.dataset_models import ProjectItem
from SocialScienceResearch.persistence.dataset_repository import blank_row
from SocialScienceResearch.persistence.excel_workbook import WorkbookStore
from SocialScienceResearch.persistence.serialization import (
    headers_for,
    model_to_row,
    row_to_model,
)

_PROJECT_ITEM_SHEET = "project_items"


class ProjectItemRepository:
    """Persisted ProjectItems, sheet ``project_items``."""

    def __init__(self, store: WorkbookStore) -> None:
        self._store = store
        store.ensure_sheet(_PROJECT_ITEM_SHEET, headers_for(ProjectItem))

    def save_item(self, item: ProjectItem) -> None:
        """Persist (upsert) a project item, idempotent by ``item_id``."""
        self._store.upsert_row(
            _PROJECT_ITEM_SHEET, "item_id", headers_for(ProjectItem), model_to_row(item)
        )

    def get_item(self, item_id: str) -> ProjectItem | None:
        row = self._store.find_row(_PROJECT_ITEM_SHEET, "item_id", item_id)
        if row is None or row.get("item_id") != item_id:
            return None
        return row_to_model(ProjectItem, row)  # type: ignore[return-value]

    def list_items(self, project_id: str | None = None) -> list[ProjectItem]:
        items = [
            row_to_model(ProjectItem, r)  # type: ignore[return-value]
            for r in self._store.read_rows(_PROJECT_ITEM_SHEET, key_field="item_id")
        ]
        if project_id:
            items = [i for i in items if i.project_id == project_id]
        return items

    def list_items_by_project(self, project_id: str) -> list[ProjectItem]:
        """List all items belonging to a project."""
        return self.list_items(project_id=project_id)

    def update_item(self, item: ProjectItem) -> None:
        self.save_item(item)

    def delete_item(self, item_id: str) -> None:
        blank_row(self._store, _PROJECT_ITEM_SHEET, "item_id", item_id)