"""Tests for domain enums and their controlled vocabulary."""

from __future__ import annotations

import pytest

from SocialScienceResearch.domain.enums import (
    CollectionStatus,
    DataAvailability,
    EntityType,
    ErrorType,
    PercentileBand,
    RecommendationStatus,
    RunType,
    SamplingStrategy,
)


def test_collection_status_values() -> None:
    assert [s.value for s in CollectionStatus] == [
        "pending",
        "running",
        "success",
        "partial",
        "failed",
    ]


def test_run_type_values() -> None:
    assert [s.value for s in RunType] == ["channel", "video", "recommendation"]


def test_entity_type_values() -> None:
    assert {s.value for s in EntityType} == {
        "channel",
        "video",
        "comment",
        "recommendation",
        "observation",
    }


def test_error_type_coverage() -> None:
    """Every error category a collector may classify."""
    assert {s.value for s in ErrorType} == {
        "network",
        "rate_limit",
        "invalid_url",
        "not_found",
        "unavailable",
        "comments",
        "library",
        "recommendation_unsupported",
        "transcript_unsupported",
        "validation",
        "unknown",
    }


def test_recommendation_status_distinguishes_unsupported() -> None:
    """Unsupported must never be conflated with observed."""
    assert RecommendationStatus.OBSERVED != RecommendationStatus.UNSUPPORTED
    assert RecommendationStatus.UNSUPPORTED != RecommendationStatus.FAILED


def test_sampling_strategies_covered() -> None:
    assert {s.value for s in SamplingStrategy} == {
        "top_views",
        "bottom_views",
        "top_likes",
        "bottom_likes",
        "top_engagement",
        "bottom_engagement",
        "top_comments",
        "top_replies",
        "top_comment_rate",
        "top_like_rate",
        "longest",
        "shortest",
        "random",
        "stratified",
        "latest",
        "earliest",
        "date_range",
    }


def test_data_availability_no_fabrication() -> None:
    assert {s.value for s in DataAvailability} == {"available", "missing", "unsupported"}


def test_percentile_bands() -> None:
    assert [s.value for s in PercentileBand] == ["75", "90", "95", "99"]


def test_str_enum_stringifies_to_value() -> None:
    assert str(CollectionStatus.SUCCESS) == "success"
    assert str(RunType.VIDEO) == "video"


@pytest.mark.parametrize("enum_cls", [CollectionStatus, RunType, ErrorType])
def test_enum_roundtrip_via_value(enum_cls: type) -> None:
    """Enum values must be reconstructable from their own value string."""
    for member in enum_cls:
        assert enum_cls(member.value) is member
