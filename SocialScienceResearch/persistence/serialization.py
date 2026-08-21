"""Serialization between pydantic domain models and Excel row dicts.

All Excel-specific value encoding is centralized here so that the rest of the
application deals with domain objects, never with cell formats.

Encoding rules
--------------
* ``None`` -> empty cell (``None``).
* ``datetime``/``date`` -> ISO-8601 string (preserves timezone offsets).
* enums -> their ``.value`` string.
* ``dict``/``list``/``tuple`` -> JSON string.
* everything else (int, float, bool, str) -> native cell value.

Decoding reverses the encoding; pydantic validates and coerces the result, so
ISO strings become datetimes/dates and JSON strings become lists/dicts.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


def headers_for(model_cls: type[BaseModel]) -> list[str]:
    """Return the ordered column names for a domain model."""
    return list(model_cls.model_fields.keys())


def encode_cell(value: Any) -> Any:
    """Convert a domain value into a safe Excel cell value."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


def decode_cell(raw: Any) -> Any:
    """Convert an Excel cell value back into a Python value.

    Complex structures (dicts/lists) are JSON-decoded; datetimes/dates are
    left as ISO strings for pydantic to parse; empty cells become ``None``.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return None
        if stripped[:1] in ("{", "["):
            try:
                return json.loads(stripped)
            except ValueError:
                pass
        return raw
    return raw


def model_to_row(model: BaseModel) -> dict[str, Any]:
    """Serialize a domain model into a row dict keyed by column name."""
    return {
        name: encode_cell(getattr(model, name)) for name in headers_for(type(model))
    }


def row_to_model(model_cls: type[BaseModel], row: dict[str, Any]) -> BaseModel:
    """Build a domain model from a row dict keyed by column name.

    ``None`` values for declared fields are passed through to pydantic, which
    validates required fields and accepts optional ``None`` defaults.
    """
    data = {}
    for name in headers_for(model_cls):
        value = decode_cell(row.get(name))
        if isinstance(value, str) and value[:1] in ("{", "["):
            annotation = model_cls.model_fields[name].annotation
            origin = getattr(annotation, "__origin__", annotation)
            if origin is dict:
                value = {}
            elif origin is list:
                value = []
        data[name] = value
    return model_cls(**data)
