"""Persisted research sample models (B5).

Domain models for immutable, reproducible samples (ADR-0011): population
definition + hash, criteria JSON, seed and member list are recorded at
creation; deletion is the only mutation.

Excel has a ~32k-char cell limit, so large member lists are persisted via a
chunked overflow mechanism (ADR-0001): member ids are newline-joined and split
across ``(sample_id, chunk_index)`` rows of a sidecar sheet (see
``persistence/sample_repository``). The ``overflow`` flag records whether a
sample used that path; ``member_ids`` is always the full, ordered list once a
sample is read back.

Request models deny unknown fields (``extra="forbid"``) so bad payloads fail
fast; the ``Sample`` domain/response model allows extras (``extra="allow"``)
so API responses stay forward-compatible.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from SocialScienceResearch.utils.idgen import utcnow


class Sample(BaseModel):
    """An immutable, persisted research sample (ADR-0011).

    ``sample_id`` is stable forever; there is deliberately no update endpoint.
    ``member_ids`` holds the full ordered membership (reassembled from the
    chunked sidecar when ``overflow`` is true), and ``criteria_json`` records
    the exact criteria so the sample can be audited and reproduced.

    The ``labels`` field supports three namespaces:
    - ``system``: auto-populated provenance (created_at, created_by, source_corpus, collection_run_id)
    - ``research``: researcher-defined design metadata (research_question, methodology, population, sampling_frame, notes)
    - ``custom``: arbitrary key-value pairs created by the researcher

    The ``scope`` field tracks the data-space boundaries of this sample
    (channel_ids, video_ids, author_ids, date_from, date_to) for reproducibility.
    """

    model_config = ConfigDict(extra="allow")

    sample_id: str
    entity_type: str  # 'video' | 'comment' | 'channel' | 'recommendation'
    strategy: str
    population_query_hash: str = ""
    population_size: int
    sample_size: int
    seed: int | None = None
    criteria_json: dict[str, Any] = Field(default_factory=dict)
    member_ids: list[str] = Field(default_factory=list)
    overflow: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    created_by_run_id: str | None = None

    scope: dict[str, Any] = Field(default_factory=dict)
    filters_applied: dict[str, Any] = Field(default_factory=dict)
    labels: dict[str, Any] = Field(default_factory=dict)


class CreateSampleRequest(BaseModel):
    """Body of ``POST {prefix}/samples`` (mirrors ``SamplingResult`` fields)."""

    model_config = ConfigDict(extra="forbid")

    entity_type: str
    strategy: str
    seed: int | None = None
    criteria_json: dict[str, Any] = Field(default_factory=dict)
    population_size: int
    population_query_hash: str = ""
    member_ids: list[str] = Field(default_factory=list)
    created_by_run_id: str | None = None


class SampleCompareRequest(BaseModel):
    """Body of ``POST {prefix}/samples/compare``.

    ``metrics`` is accepted up front as a forward-compatible dimension for
    future metric-level comparison; it is echoed back verbatim today.
    """

    model_config = ConfigDict(extra="forbid")

    sample_ids: list[str]
    metrics: list[str] = Field(default_factory=list)


class PairwiseOverlap(BaseModel):
    """Overlap statistics for one pair of samples (key ``a|b`` with a<b)."""

    model_config = ConfigDict(extra="allow")

    intersection_size: int
    union_size: int
    jaccard: float


class SampleCompareResult(BaseModel):
    """Response of ``POST {prefix}/samples/compare``.

    ``counts`` is per-sample membership; ``intersection_size`` counts members
    shared by *all* compared samples; ``criteria_diffs`` lists, per sample, the
    criteria fields (strategy/seed/hash/population size/criteria JSON) that
    differ from the first sample in the request.
    """

    model_config = ConfigDict(extra="allow")

    sample_ids: list[str]
    counts: dict[str, int]
    union_size: int
    intersection_size: int
    pairwise: dict[str, PairwiseOverlap]
    criteria_diffs: dict[str, list[str]]
    metrics: list[str] = Field(default_factory=list)


class DeleteSampleResponse(BaseModel):
    """Response of ``DELETE {prefix}/samples/{sample_id}`` (404 if missing)."""

    model_config = ConfigDict(extra="allow")

    sample_id: str
    deleted: bool = True


class SampleScope(BaseModel):
    """Scope boundaries for sample reproducibility."""

    channel_ids: list[str] = Field(default_factory=list)
    video_ids: list[str] = Field(default_factory=list)
    author_ids: list[str] = Field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None


class SampleLabels(BaseModel):
    """Three-namespace labeling system for samples."""

    system: dict[str, Any] = Field(default_factory=dict)
    research: dict[str, Any] = Field(default_factory=dict)
    custom: dict[str, Any] = Field(default_factory=dict)