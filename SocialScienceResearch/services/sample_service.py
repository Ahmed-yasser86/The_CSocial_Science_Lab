"""Persisted research sample service (B5).

Builds a :class:`SampleRepository` over the shared store and exposes the
immutable-sample lifecycle (ADR-0011) demanded by the API: save, list, get,
delete and comparison (overlap / union / Jaccard / criteria diff).

``repos`` is the repository container from ``app.state.services["repos"]`` (an
``ExcelRepositories`` exposing ``.store``); the samples repository re-uses that
single store so all sheets share one workbook. Bad input raises
``ValueError``, which the app's exception handler maps to HTTP 400.
"""

from __future__ import annotations

from SocialScienceResearch.domain.sample_models import (
    PairwiseOverlap,
    Sample,
    SampleCompareResult,
)
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.utils.idgen import new_id

_ALLOWED_ENTITY_TYPES = frozenset(
    {"video", "comment", "channel", "recommendation"}
)

#: Criteria fields compared across samples to report whether two samples were
#: drawn from the same population definition (changes since reference).
_COMPARED_CRITERIA_FIELDS = (
    "strategy",
    "seed",
    "population_query_hash",
    "population_size",
    "criteria_json",
)


class SampleService:
    """Lifecycle and comparison of immutable, persisted research samples."""

    def __init__(self, repos: Repositories) -> None:
        self._repo = repos.samples

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def save(self, sample: Sample) -> Sample:
        """Validate and persist a sample; returns the stored object.

        ``sample_id`` is generated from ``utils.idgen`` when absent and
        ``sample_size`` is always derived from the member list so the stored
        record is self-consistent.
        """
        if sample.entity_type not in _ALLOWED_ENTITY_TYPES:
            raise ValueError(
                f"Unsupported entity_type {sample.entity_type!r}; expected one of "
                f"{sorted(_ALLOWED_ENTITY_TYPES)}"
            )
        sample = sample.model_copy(
            update={
                "sample_id": sample.sample_id or new_id("sample"),
                "sample_size": len(sample.member_ids),
            }
        )
        return self._repo.save(sample)

    def list_samples(self) -> list[Sample]:
        """Return all persisted, non-deleted samples."""
        return self._repo.list()

    def get_sample(self, sample_id: str) -> Sample | None:
        """Return one sample (member ids reassembled), or ``None``."""
        return self._repo.get(sample_id)

    def delete_sample(self, sample_id: str) -> bool:
        """Tombstone a sample; ``False`` when it does not exist."""
        return self._repo.delete(sample_id)

    def list_members(self, sample_id: str) -> list[str]:
        """Full ordered member id list of a sample (chunks reassembled)."""
        return self._repo.list_members(sample_id)

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------
    def compare_samples(self, sample_ids: list[str]) -> SampleCompareResult:
        """Overlap / union / Jaccard / criteria diff across persisted samples."""
        if len(sample_ids) < 2:
            raise ValueError("compare_samples requires at least 2 sample_ids")
        samples = [self.get_sample(sample_id) for sample_id in sample_ids]
        missing = [
            sample_id
            for sample_id, sample in zip(sample_ids, samples)
            if sample is None
        ]
        if missing:
            raise ValueError(f"Samples not found: {sorted(missing)}")

        members = {s.sample_id: set(s.member_ids) for s in samples}

        counts = {sample_id: len(members[sample_id]) for sample_id in sample_ids}
        union = set().union(*(members[sample_id] for sample_id in sample_ids))
        common = set.intersection(*(members[sample_id] for sample_id in sample_ids))

        pairwise: dict[str, PairwiseOverlap] = {}
        for i in range(len(sample_ids)):
            for j in range(i + 1, len(sample_ids)):
                left, right = sample_ids[i], sample_ids[j]
                both = len(members[left] & members[right])
                either = len(members[left] | members[right])
                pairwise[f"{left}|{right}"] = PairwiseOverlap(
                    intersection_size=both,
                    union_size=either,
                    jaccard=(both / either) if either else 0.0,
                )

        criteria_diffs = {
            s.sample_id: self._criteria_diff(s, samples[0]) for s in samples
        }
        return SampleCompareResult(
            sample_ids=sample_ids,
            counts=counts,
            union_size=len(union),
            intersection_size=len(common),
            pairwise=pairwise,
            criteria_diffs=criteria_diffs,
        )

    @staticmethod
    def _criteria_diff(sample: Sample, reference: Sample) -> list[str]:
        """Names of criteria fields that differ vs the reference sample."""
        return [
            field
            for field in _COMPARED_CRITERIA_FIELDS
            if getattr(sample, field) != getattr(reference, field)
        ]