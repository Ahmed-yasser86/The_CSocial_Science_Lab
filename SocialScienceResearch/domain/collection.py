"""Collection experiment specifications.

A ``CollectionSpec`` is a first-class research object: it records exactly what
a collection run was asked to do (targets, comment criteria, transcript
collection, enrichment depth, quotas) so that a run is reproducible and
auditable. Services validate specs and *never silently ignore a criterion*:
anything the acquisition layer cannot honour is recorded explicitly (e.g. a
``transcript_unsupported`` error) rather than dropped.

Unset fields fall back to the module defaults when the spec is resolved (see
:meth:`CollectionSpec.effective`), and the UI always renders the *resolved*
spec that a run actually executed so defaults never hide a methodological
decision.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from SocialScienceResearch.config.settings import SocialScienceSettings

from .enums import TargetKind
from .query import QueryGroup, _validate_conditions

_MIN_TARGETS = 1


class CollectionTarget(BaseModel):
    """One collection target (channel, video, or recommendation source)."""

    model_config = ConfigDict(extra="forbid")

    kind: TargetKind
    url: str

    @field_validator("url")
    @classmethod
    def _url_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("target url must not be empty")
        return value


class CollectionSpec(BaseModel):
    """A configurable, reproducible collection experiment.

    Every criterion may be left unset; unset values fall back to the module
    defaults (via :meth:`effective`) so the resolved configuration is always
    visible and auditable.
    """

    model_config = ConfigDict(extra="forbid")

    targets: list[CollectionTarget] = Field(min_length=_MIN_TARGETS)
    collect_comments: bool | None = None
    scrape_all_comments: bool | None = None
    max_comments_per_video: int | None = None
    comment_min_likes: int | None = None
    comment_date_from: datetime | None = None
    comment_date_to: datetime | None = None
    collect_transcripts: bool | None = None
    enrich_video_stats: bool | None = None
    max_videos_to_enrich: int | None = None
    max_videos_per_channel: int | None = None
    sampling_seed: int | None = None
    video_criteria: QueryGroup | None = None
    comment_criteria: QueryGroup | None = None
    include_live_videos: bool | None = None
    video_tabs: list[str] | None = None
    scrape_live_only: bool | None = None
    scrape_recommendations: bool | None = None

    @field_validator(
        "max_comments_per_video", "max_videos_to_enrich", "max_videos_per_channel"
    )
    @classmethod
    def _quota_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("quota values must be positive integers")
        return value

    @field_validator("comment_date_from", "comment_date_to")
    @classmethod
    def _tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            from SocialScienceResearch.utils.idgen import utcnow

            return value.replace(tzinfo=utcnow().tzinfo)
        return value

    @model_validator(mode="after")
    def _validate_criteria_entities(self) -> "CollectionSpec":
        """Video/comment criteria must reference variables of their entity."""
        if self.video_criteria is not None:
            _validate_conditions("video", self.video_criteria)
        if self.comment_criteria is not None:
            _validate_conditions("comment", self.comment_criteria)
        return self

    # ------------------------------------------------------------------
    # Reproducibility
    # ------------------------------------------------------------------
    @property
    def spec_hash(self) -> str:
        """Short content hash identifying this exact experiment definition."""
        canonical = json.dumps(self.snapshot(), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def snapshot(self) -> dict[str, Any]:
        """Serializable snapshot of the spec with unset fields omitted."""
        return json.loads(self.model_dump_json(exclude_none=True))

    def effective(self, settings: SocialScienceSettings) -> dict[str, Any]:
        """Resolve unset criteria against the module defaults.

        The result is the *actual* configuration a run executes, suitable for
        display and for persisting as the run's ``config_json``.
        """
        collection = settings.collection
        max_comments = self.max_comments_per_video
        if self.scrape_all_comments is True:
            max_comments = None
        return {
            "targets": [
                {"kind": t.kind.value, "url": t.url} for t in self.targets
            ],
            "collect_comments": (
                self.collect_comments
                if self.collect_comments is not None
                else collection.collect_comments
            ),
            "scrape_all_comments": self.scrape_all_comments,
            "max_comments_per_video": (
                max_comments or collection.max_comments_per_video
            ),
            "comment_min_likes": self.comment_min_likes,
            "comment_date_from": (
                self.comment_date_from.isoformat() if self.comment_date_from else None
            ),
            "comment_date_to": (
                self.comment_date_to.isoformat() if self.comment_date_to else None
            ),
            "collect_transcripts": (
                self.collect_transcripts
                if self.collect_transcripts is not None
                else bool(getattr(collection, "collect_transcripts", False))
            ),
            "enrich_video_stats": (
                self.enrich_video_stats
                if self.enrich_video_stats is not None
                else collection.enrich_video_stats
            ),
            "max_videos_to_enrich": (
                self.max_videos_to_enrich
                if self.max_videos_to_enrich is not None
                else collection.max_videos_to_enrich
            ),
            "max_videos_per_channel": (
                self.max_videos_per_channel or collection.max_videos_per_channel
            ),
            "sampling_seed": self.sampling_seed or settings.sampling.default_seed,
            "include_live_videos": (
                self.include_live_videos
                if self.include_live_videos is not None
                else collection.include_live_videos
            ),
            "scrape_live_only": (
                self.scrape_live_only
                if self.scrape_live_only is not None
                else getattr(collection, "scrape_live_only", False)
            ),
            "video_tabs": (
                self.video_tabs
                if self.video_tabs is not None
                else getattr(collection, "video_tabs", None)
            ),
            "scrape_recommendations": (
                self.scrape_recommendations
                if self.scrape_recommendations is not None
                else getattr(collection, "scrape_recommendations", False)
            ),
            "video_criteria": (
                self.video_criteria.model_dump(mode="json")
                if self.video_criteria is not None
                else None
            ),
            "comment_criteria": (
                self.comment_criteria.model_dump(mode="json")
                if self.comment_criteria is not None
                else None
            ),
            "spec_hash": self.spec_hash,
        }

    # ------------------------------------------------------------------
    # Convenience constructors (legacy single-target workflows)
    # ------------------------------------------------------------------
    @classmethod
    def for_channel(cls, url: str) -> "CollectionSpec":
        return cls(targets=[CollectionTarget(kind=TargetKind.CHANNEL, url=url)])

    @classmethod
    def for_video(cls, url: str) -> "CollectionSpec":
        return cls(targets=[CollectionTarget(kind=TargetKind.VIDEO, url=url)])

    @classmethod
    def for_recommendations(cls, url: str) -> "CollectionSpec":
        return cls(
            targets=[CollectionTarget(kind=TargetKind.RECOMMENDATION, url=url)]
        )
