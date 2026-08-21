"""Provenance service: reconstruct the collection chain of one entity.

Every persisted entity carries ``first_observed_run_id`` (the run that first
discovered it) and every observation references the run that produced it. This
service reassembles that chain into a deterministic, bounded record:

* the first-observed run (and its provider / provider version / config /
  status / timestamps) - the provenance backbone;
* the full observation history count plus the most recent ``N`` observations
  (``observed_at`` + producing ``run_id``), newest first;
* all runs that produced the entity or one of its observations, deduplicated
  and ordered by ``started_at``;
* entity-specific provenance links: ``channel_id`` for videos, parent/root
  comment ids for comments.

Bounded and deterministic: the observation list is capped (default 50), run
summaries are sorted, and no mutable global state is consulted.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from SocialScienceResearch.persistence.base import Repositories

#: Registered entities (must match the research-query contract).
_REGISTERED_ENTITIES = ("video", "comment", "channel", "recommendation", "author")

#: Cap on the returned per-observation history list.
_OBSERVATION_LIMIT = 50


class EntityNotFoundError(Exception):
    """Raised when an entity id is absent from the corpus (HTTP 404 upstream)."""


class RunSummary(BaseModel):
    """Provenance-relevant fields of one collection run."""

    model_config = ConfigDict(extra="allow")

    run_id: str
    run_type: str | None = None
    provider: str | None = None
    provider_version: str | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)
    status: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ObservationPoint(BaseModel):
    """One observation in the entity's history (most recent first, bounded)."""

    model_config = ConfigDict(extra="allow")

    observed_at: datetime | None = None
    run_id: str | None = None


class ProvenanceRecord(BaseModel):
    """The provenance chain of a single entity."""

    model_config = ConfigDict(extra="allow")

    entity: str
    entity_id: str
    first_observed_run_id: str | None = None
    first_seen_at: datetime | None = None
    runs: list[RunSummary] = Field(default_factory=list)
    observation_count: int = 0
    observations: list[ObservationPoint] = Field(default_factory=list)
    provider: str | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)
    channel_id: str | None = None
    parent_comment_id: str | None = None
    root_comment_id: str | None = None


class ProvenanceService:
    """Build deterministic provenance chains for persisted entities."""

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    # ------------------------------------------------------------------
    def provenance(self, entity: str, entity_id: str) -> ProvenanceRecord:
        """Return the provenance chain of ``entity_id``.

        Raises :class:`EntityNotFoundError` for a missing id and ``ValueError``
        for an unknown entity (HTTP 400 upstream).
        """
        entity = entity.lower()
        if entity not in _REGISTERED_ENTITIES:
            raise ValueError(
                f"Unknown entity {entity!r}; expected one of "
                f"{sorted(_REGISTERED_ENTITIES)}"
            )
        model = self._fetch(entity, entity_id)
        if model is None:
            raise EntityNotFoundError(f"{entity} {entity_id!r} not found")

        first_run_id = getattr(model, "first_observed_run_id", None)
        if first_run_id is None and entity == "author":
            first_run_id = getattr(model, "first_seen_run_id", None)
        first_run = (
            self._repos.runs.get_run(first_run_id) if first_run_id else None
        )

        observations, observation_count = self._observation_history(entity, model)

        run_ids: list[str] = []
        if first_run_id:
            run_ids.append(first_run_id)
        run_ids.extend(obs.run_id for obs in observations if obs.run_id)
        runs = self._run_summaries(list(dict.fromkeys(run_ids)))

        return ProvenanceRecord(
            entity=entity,
            entity_id=entity_id,
            first_observed_run_id=first_run_id,
            first_seen_at=first_run.started_at if first_run else None,
            runs=runs,
            observation_count=observation_count,
            observations=observations,
            provider=first_run.provider if first_run else None,
            config_json=first_run.config_json if first_run else {},
            channel_id=getattr(model, "channel_id", None) if entity == "video" else None,
            parent_comment_id=(
                getattr(model, "parent_comment_id", None)
                if entity == "comment"
                else None
            ),
            root_comment_id=(
                getattr(model, "root_comment_id", None)
                if entity == "comment"
                else None
            ),
        )

    # ------------------------------------------------------------------
    def _observation_history(
        self, entity: str, model: Any
    ) -> tuple[list[ObservationPoint], int]:
        """Return the bounded, newest-first observation list and total count."""
        if entity == "author":
            # Author profiles are derived from comments (ADR-0010); their
            # "observations" are the producing comments' first-seen run only.
            if not getattr(model, "first_seen_run_id", None):
                return [], 0
            return [
                ObservationPoint(
                    observed_at=model.first_seen_at,
                    run_id=model.first_seen_run_id,
                )
            ], 1
        if entity == "channel":
            observations = self._repos.channels.list_channel_observations(
                model.channel_id
            )
        elif entity == "video":
            observations = self._repos.videos.list_video_observations(model.video_id)
        elif entity == "comment":
            observations = self._repos.comments.list_comment_observations(
                comment_id=model.comment_id
            )
        else:
            # A recommendation *is* one observed relationship: the edge itself.
            observations = [model]

        total = len(observations)
        points = [
            ObservationPoint(
                observed_at=observation.observed_at,
                run_id=getattr(observation, "collection_run_id", None),
            )
            for observation in observations[-_OBSERVATION_LIMIT:]
        ]
        return points[::-1], total

    def _run_summaries(self, run_ids: list[str]) -> list[RunSummary]:
        """Resolve run summaries, deduplicated and ordered by ``started_at``."""
        summaries: list[RunSummary] = []
        for run_id in run_ids:
            run = self._repos.runs.get_run(run_id)
            if run is None:
                continue
            summaries.append(
                RunSummary(
                    run_id=run_id,
                    run_type=run.run_type.value if run.run_type else None,
                    provider=run.provider,
                    provider_version=run.provider_version,
                    config_json=run.config_json,
                    status=run.status.value if run.status else None,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                )
            )
        return sorted(
            summaries,
            key=lambda summary: (
                summary.started_at is None,
                summary.started_at.isoformat() if summary.started_at else "",
            ),
        )

    # ------------------------------------------------------------------
    def _fetch(self, entity: str, entity_id: str) -> Any:
        if entity == "video":
            return self._repos.videos.get_video(entity_id)
        if entity == "channel":
            return self._repos.channels.get_channel(entity_id)
        if entity == "comment":
            return self._repos.comments.get_comment(entity_id)
        if entity == "author":
            return self._repos.authors.get_author(entity_id)
        for edge in self._repos.recommendations.list_recommendation_edges():
            if edge.observation_id == entity_id:
                return edge
        return None
