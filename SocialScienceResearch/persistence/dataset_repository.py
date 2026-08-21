"""Excel-backed repository for datasets and their chunked members.

A *minimal store-backed* implementation (mirroring the shared behaviour of
``_ExcelEntityRepository`` in ``persistence.excel_repository``, which is not
edited here): it goes straight to ``WorkbookStore`` and the
``persistence.serialization`` helpers.

Member lists are persisted as **chunked row projections** (ADR-0001: a single
Excel cell must stay below ~32k chars). Each ``dataset_members`` row carries a
bounded JSON array of member ``{variable: value}`` dicts under ``member_json``,
keyed by ``{dataset_id}::{chunk_index}``. Datasets whose members span more than
one chunk are flagged via ``Dataset.overflow``.

Delete is implemented by *blanking* rows in place (the store offers no delete
API): ``read_rows`` skips fully-blank rows and the ``get_*`` methods guard on
the key column, so a blanked slot can never re-surface as an entity. The one
deliberate private coupling is ``WorkbookStore._wb`` - clearing cells cannot be
expressed through the store's public API without editing ``excel_workbook.py``
(out of scope), and the store's documented single-writer, in-memory model makes
direct cell writes safe.
"""

from __future__ import annotations

import json
from typing import Any

from SocialScienceResearch.domain.dataset_models import Dataset as NewDataset
from SocialScienceResearch.persistence.excel_workbook import WorkbookStore
from SocialScienceResearch.persistence.serialization import (
    headers_for,
    model_to_row,
    row_to_model,
)

_DATASET_LEGACY_SHEET = "datasets"
_NEW_DATASET_SHEET = "combined_datasets"
_MEMBERS_SHEET = "dataset_members"
_MEMBER_HEADERS = ["row_id", "dataset_id", "chunk_index", "member_json"]

_MAX_CHUNK_CHARS = 28000


def blank_row(store: WorkbookStore, sheet: str, key_field: str, key: Any) -> None:
    if key is None:
        return
    location = store._ensure_index(sheet, key_field).get(str(key))
    if location is None:
        return
    sheet_name, excel_row = location
    ws = store._wb[sheet_name]
    headers = store._headers.get(sheet, [])
    for column in range(1, len(headers) + 1):
        cell = ws.cell(row=excel_row, column=column)
        cell.value = None


class DatasetRepository:
    def __init__(self, store: WorkbookStore) -> None:
        self._store = store
        store.ensure_sheet(_DATASET_LEGACY_SHEET, headers_for(NewDataset))
        store.ensure_sheet(_NEW_DATASET_SHEET, headers_for(NewDataset))
        store.ensure_sheet(_MEMBERS_SHEET, _MEMBER_HEADERS)

    def upsert_dataset(self, dataset: NewDataset) -> None:
        self._store.upsert_row(
            _NEW_DATASET_SHEET, "dataset_id", headers_for(NewDataset), model_to_row(dataset)
        )

    def get_dataset(self, dataset_id: str) -> NewDataset | None:
        row = self._store.find_row(_NEW_DATASET_SHEET, "dataset_id", dataset_id)
        if row is None or row.get("dataset_id") != dataset_id:
            return None
        return row_to_model(NewDataset, row)

    def list_datasets(self) -> list[NewDataset]:
        return [
            row_to_model(NewDataset, r)
            for r in self._store.read_rows(_NEW_DATASET_SHEET, key_field="dataset_id")
        ]

    def delete_dataset(self, dataset_id: str) -> None:
        blank_row(self._store, _NEW_DATASET_SHEET, "dataset_id", dataset_id)

    def save_dataset(self, dataset) -> None:
        self.upsert_dataset(dataset)

    def get_dataset_raw(self, dataset_id: str):
        row = self._store.find_row(_DATASET_LEGACY_SHEET, "dataset_id", dataset_id)
        if row is None or row.get("dataset_id") != dataset_id:
            return None
        return row_to_model(NewDataset, row)

    def list_datasets_raw(self):
        return [
            row_to_model(NewDataset, r)
            for r in self._store.read_rows(_DATASET_LEGACY_SHEET, key_field="dataset_id")
        ]

    def save_members(self, dataset_id: str, members: list[dict[str, Any]]) -> int:
        self._clear_dataset_members(dataset_id)
        chunks = self._chunk_members(members)
        for index, payload in enumerate(chunks):
            row_id = f"{dataset_id}::{index}"
            self._store.upsert_row(
                _MEMBERS_SHEET,
                "row_id",
                _MEMBER_HEADERS,
                {
                    "row_id": row_id,
                    "dataset_id": dataset_id,
                    "chunk_index": index,
                    "member_json": payload,
                },
            )
        return len(chunks)

    def list_members(self, dataset_id: str) -> list[dict[str, Any]]:
        members: list[dict[str, Any]] = []
        for row in self._store.read_rows(_MEMBERS_SHEET, key_field="row_id"):
            if row.get("dataset_id") != dataset_id:
                continue
            payload = row.get("member_json")
            if payload:
                members.extend(json.loads(payload))
        return members

    def dataset_member_count(self, dataset_id: str) -> int:
        count = 0
        for row in self._store.read_rows(_MEMBERS_SHEET, key_field="row_id"):
            if row.get("dataset_id") != dataset_id:
                continue
            payload = row.get("member_json")
            if payload:
                count += len(json.loads(payload))
        return count

    @classmethod
    def _chunk_members(cls, members: list[dict[str, Any]]) -> list[str]:
        chunks: list[str] = []
        current: list[dict[str, Any]] = []
        size = 0
        for member in members:
            encoded = json.dumps(member, ensure_ascii=False, default=str)
            if current and size + len(encoded) + 2 > _MAX_CHUNK_CHARS:
                chunks.append(json.dumps(current, ensure_ascii=False, default=str))
                current, size = [], 0
            current.append(member)
            size += len(encoded) + 2
        if current:
            chunks.append(json.dumps(current, ensure_ascii=False, default=str))
        return chunks

    def _clear_dataset_members(self, dataset_id: str) -> None:
        members = self._store.read_rows(_MEMBERS_SHEET, key_field="row_id")
        for row in members:
            if row.get("dataset_id") == dataset_id:
                blank_row(self._store, _MEMBERS_SHEET, "row_id", row.get("row_id"))