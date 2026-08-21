"""Tests for the VariableRegistry and VariableMeta definitions.

Verifies catalogue completeness (counts per entity), allowed types/sources,
and the integrity rule that every ``availability`` entry parses as
``ModelName.field`` where the field genuinely exists on the corresponding
domain model class.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from SocialScienceResearch.domain import models as domain_models
from SocialScienceResearch.services.variable_registry import (
    VariableMeta,
    VariableRegistry,
)


def _by_name(entity: str) -> dict[str, VariableMeta]:
    return {meta.name: meta for meta in VariableRegistry.get_variables(entity)}


def test_catalogue_counts_per_entity() -> None:
    counts = {entity: len(VariableRegistry.get_variables(entity)) for entity in VariableRegistry.entities()}
    assert counts == {"channel": 11, "video": 21, "comment": 11, "recommendation": 7, "author": 8}


def test_total_catalogue_size() -> None:
    assert len(VariableRegistry.all_variables()) == 58


def test_get_variables_fingerprint_entries() -> None:
    video = _by_name("video")
    assert video["view_count"].data_type == "int"
    assert video["view_count"].entity == "video"
    assert video["duration"].unit == "seconds"
    assert video["transcript_length_chars"].source == "derived"
    assert video["transcript_length_chars"].availability == "Video.transcript_path"


def test_get_variable_lookup() -> None:
    assert VariableRegistry.get_variable("video", "duration").name == "duration"
    assert VariableRegistry.get_variable("comment", "comment_text").source == "observed"
    assert VariableRegistry.get_variable("video", "bogus") is None


def test_unknown_entity_raises_value_error() -> None:
    with pytest.raises(ValueError):
        VariableRegistry.get_variables("planet")
    with pytest.raises(ValueError):
        VariableRegistry.get_variable("planet", "title")


def test_allowed_types_and_sources() -> None:
    assert VariableRegistry.allowed_types() == {"int", "float", "bool", "str", "datetime", "list"}
    assert VariableRegistry.allowed_sources() == {"observed", "derived", "raw"}


def test_inventory_name_maps_to_model_field_name() -> None:
    video = _by_name("video")
    comment = _by_name("comment")
    assert video["duration"].name == "duration"  # inventory "duration_seconds"
    assert comment["comment_text"].name == "comment_text"  # inventory "text"
    assert video["transcript_lang"].name == "transcript_lang"  # inventory "transcript_language"
    assert video["upload_date"].name == "upload_date"
    assert video["view_count"].name == "view_count"


def test_variable_meta_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        VariableMeta(
            entity="video",
            name="x",
            data_type="int",
            source="observed",
            description="d",
            availability="Video.x",
            bogus=True,
        )


def test_variable_meta_requires_availability() -> None:
    with pytest.raises(ValidationError):
        VariableMeta(entity="video", name="x", data_type="int", source="observed", description="d")


def test_availability_resolves_to_real_domain_model_field() -> None:
    """Integrity rule: availability is 'ModelName.field' and the model has that field."""
    problems = []
    for entity in VariableRegistry.entities():
        for meta in VariableRegistry.get_variables(entity):
            model_name, _, field = meta.availability.partition(".")
            model_class = getattr(domain_models, model_name, None)
            if model_class is None:
                problems.append(f"{entity}.{meta.name} -> unknown model {model_name!r}")
            elif field not in getattr(model_class, "model_fields", {}):
                problems.append(f"{entity}.{meta.name} -> {meta.availability!r} field missing")
    assert problems == [], "variables whose availability points at a missing model field"


def test_all_availability_refer_to_non_private_fields() -> None:
    bad = [
        (meta.entity, meta.name)
        for meta in VariableRegistry.all_variables()
        if not meta.availability or meta.availability.startswith("_")
    ]
    assert bad == []