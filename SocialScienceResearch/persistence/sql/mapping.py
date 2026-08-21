"""Shared SQL <-> domain-model mapping helpers.

``_params`` converts a domain model into a psycopg parameter dict (JSONB for
dict/list fields, enums to their string value, scalars passed through).

``_row`` rebuilds a domain model from an SQL row. JSONB columns arrive from
psycopg already decoded (dict/list) and datetimes/dates as native objects, so
the Excel ``decode_cell`` empty-string -> ``None`` collapsing is *not*
applied: a stored ``""`` stays ``""`` (matching what pydantic expects for
``str = ""`` defaults such as ``Sample.population_query_hash``).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from psycopg.types.json import Jsonb

from SocialScienceResearch.persistence.serialization import headers_for


def _params(model) -> dict[str, Any]:
    """Model -> SQL parameter dict (JSONB for dict/list fields, enums to value)."""
    params: dict[str, Any] = {}
    for name in headers_for(type(model)):
        value = getattr(model, name)
        if isinstance(value, Enum):
            params[name] = value.value
        elif isinstance(value, (dict, list, tuple)):
            params[name] = Jsonb(list(value) if isinstance(value, tuple) else value)
        else:
            params[name] = value
    return params


def _row(model_cls, db_row: dict[str, Any] | None):
    """Build a domain model from an SQL row.

    Columns that are NULL in the row are omitted so the model's
    ``default_factory`` (e.g. ``raw_json: dict = Field(default_factory=dict)``)
    is used instead of an explicit ``None`` -- this is what lets list queries
    project away the heavy ``raw_json`` TOAST column without breaking models
    that declare it as a required ``dict``.
    """
    if db_row is None:
        return None
    return model_cls(
        **{
            name: val
            for name in headers_for(model_cls)
            if (val := db_row.get(name)) is not None
        }
    )