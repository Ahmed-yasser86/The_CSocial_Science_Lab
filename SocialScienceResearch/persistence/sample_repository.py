"""Excel-backed repository for persisted research samples (B5).

Stores one row per ``Sample`` on a ``samples`` sheet plus an overflow sidecar
sheet of chunked member ids (ADR-0001 / ADR-0011). ``WorkbookStore`` methods
(``ensure_sheet`` / ``upsert_row`` / ``find_row`` / ``read_rows`` /
``row_exists``) and the serialization helpers (``headers_for`` /
``model_to_row`` / ``row_to_model``) do the actual storage so samples
round-trip through Excel like every other entity.

Overflow design
---------------
Excel cells hold ~32k chars (the store's safety margin is ``MAX_CELL_CHARS``).
A sample's member list is stored inline (as its JSON list) when it fits within
the per-cell budget. Otherwise member ids are newline-joined and chunked across
rows of a ``sample_members`` sidecar sheet, keyed by a composite
``chunk_key`` = ``{sample_id}::{chunk_index}`` with columns
``(chunk_key, sample_id, chunk_index, member_ids)``. The main ``samples`` row
records ``overflow=True`` with an empty member list; ``list_members``,
``get`` and ``list`` reassemble the ids in chunk order. Chunking is
idempotent per (sample_id, chunk_index); because samples are immutable
(ADR-0011) re-saves of the same id never happen through the API.

Deletion is the only mutation (ADR-0011). The store has no row-delete, so
deleting a sample persists a tombstone on a ``sample_tombstones`` sheet which
all read paths filter out - surviving workbook reopens and process restarts.
"""

from __future__ import annotations

import json

from SocialScienceResearch.domain.sample_models import Sample
from SocialScienceResearch.persistence.excel_workbook import WorkbookStore
from SocialScienceResearch.persistence.serialization import (
    headers_for,
    model_to_row,
    row_to_model,
)

#: Per-cell char budget for a member id list (inline JSON or a newline-joined
#: chunk). Safely below the Excel/store 32k-char limit.
_MAX_CELL_CHARS = 30000


class SampleRepository:
    """Store-backed repository for immutable samples."""

    _SHEET = "samples"
    _MODEL = Sample
    _KEY = "sample_id"
    _MEMBERS_SHEET = "sample_members"
    _MEMBERS_KEY = "chunk_key"
    _MEMBERS_COLUMNS = ["chunk_key", "sample_id", "chunk_index", "member_ids"]
    _TOMB_SHEET = "sample_tombstones"
    _TOMB_COLUMNS = ["sample_id"]

    def __init__(self, store: WorkbookStore) -> None:
        self._store = store
        store.ensure_sheet(self._SHEET, headers_for(Sample))
        store.ensure_sheet(self._MEMBERS_SHEET, self._MEMBERS_COLUMNS)
        store.ensure_sheet(self._TOMB_SHEET, self._TOMB_COLUMNS)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def save(self, sample: Sample) -> Sample:
        """Persist a sample; chunk the member list when it exceeds a cell.

        Returns the stored view of the sample (``overflow`` reflects whether
        the member list went to the chunked sidecar).
        """
        if self._needs_chunking(sample.member_ids):
            main = sample.model_copy(
                update={"overflow": True, "member_ids": []}
            )
            self._store.upsert_row(
                self._SHEET, self._KEY, headers_for(Sample), model_to_row(main)
            )
            self._write_chunks(sample.sample_id, sample.member_ids)
            return sample.model_copy(update={"overflow": True})
        stored = sample.model_copy(update={"overflow": False})
        self._store.upsert_row(
            self._SHEET, self._KEY, headers_for(Sample), model_to_row(stored)
        )
        return stored

    def delete(self, sample_id: str) -> bool:
        """Tombstone a sample. Returns ``False`` if it does not exist."""
        if sample_id in self._deleted_ids():
            return False
        if not self._store.row_exists(self._SHEET, self._KEY, sample_id):
            return False
        self._store.upsert_row(
            self._TOMB_SHEET,
            "sample_id",
            self._TOMB_COLUMNS,
            {"sample_id": sample_id},
        )
        return True

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def get(self, sample_id: str) -> Sample | None:
        """Return one sample (member ids reassembled), or ``None``."""
        if sample_id in self._deleted_ids():
            return None
        row = self._store.find_row(self._SHEET, self._KEY, sample_id)
        return self._reassemble(row) if row else None

    def list(self) -> list[Sample]:
        """Return all non-deleted samples, newest appended last."""
        deleted = self._deleted_ids()
        samples: list[Sample] = []
        for row in self._store.read_rows(self._SHEET, key_field=self._KEY):
            sample_id = row.get("sample_id")
            if not sample_id or sample_id in deleted:
                continue
            samples.append(self._reassemble(row))
        return samples

    def list_members(self, sample_id: str) -> list[str]:
        """Reassemble the full, ordered member id list of a sample."""
        if sample_id in self._deleted_ids():
            return []
        rows = self._store.read_rows(self._MEMBERS_SHEET, key_field=self._MEMBERS_KEY)
        chunks = [r for r in rows if r.get("sample_id") == sample_id]
        chunks.sort(key=lambda r: r.get("chunk_index") or 0)
        ids: list[str] = []
        for row in chunks:
            text = row.get("member_ids")
            if text:
                ids.extend(str(text).split("\n"))
        return ids

    # ------------------------------------------------------------------
    # Overflow helpers
    # ------------------------------------------------------------------
    @classmethod
    def _needs_chunking(cls, member_ids: list[str]) -> bool:
        """True when the JSON-encoded inline list would blow the cell budget."""
        return len(json.dumps(member_ids, ensure_ascii=False)) > _MAX_CELL_CHARS

    def _write_chunks(self, sample_id: str, member_ids: list[str]) -> None:
        for index, chunk in enumerate(self._chunk_ids(member_ids)):
            self._store.upsert_row(
                self._MEMBERS_SHEET,
                self._MEMBERS_KEY,
                self._MEMBERS_COLUMNS,
                {
                    "chunk_key": f"{sample_id}::{index}",
                    "sample_id": sample_id,
                    "chunk_index": index,
                    "member_ids": "\n".join(chunk),
                },
            )

    @classmethod
    def _chunk_ids(cls, member_ids: list[str]) -> list[list[str]]:
        """Split the id list so each newline-joined chunk fits a cell."""
        chunks: list[list[str]] = []
        current: list[str] = []
        size = 0
        for member_id in member_ids:
            cost = len(member_id) + (1 if current else 0)  # + newline separator
            if current and size + cost > _MAX_CELL_CHARS:
                chunks.append(current)
                current = []
                size = 0
                cost = len(member_id)
            current.append(member_id)
            size += cost
        if current:
            chunks.append(current)
        return chunks

    def _deleted_ids(self) -> set[str]:
        rows = self._store.read_rows(self._TOMB_SHEET, key_field="sample_id")
        return {r["sample_id"] for r in rows if r.get("sample_id")}

    def _reassemble(self, row: dict) -> Sample:
        sample = row_to_model(Sample, row)
        if sample.overflow:
            return sample.model_copy(
                update={"member_ids": self.list_members(sample.sample_id)}
            )
        return sample