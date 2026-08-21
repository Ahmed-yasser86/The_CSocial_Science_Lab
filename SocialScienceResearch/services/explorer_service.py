"""Explorer service: browse structured rows per entity with filters.

The explorer reuses ``QueryService.resolve_latest_rows`` (the single row
resolution shared with the research-query evaluator) instead of reimplementing
any row building. On top of that it layers, in order:

1. a case-insensitive text search over the entity's searchable fields;
2. simple ``{variable, operator, value}`` filters evaluated by the **same**
   evaluator as research queries (``domain.query.evaluate_query``): each simple
   filter is lifted into a :class:`QueryCondition` and AND-ed under one
   :class:`QueryGroup`, so ``eq``/``neq``/``contains``/``gt``/``lt``/``in``/
   ``is_null``/... semantics are identical by construction - never re-implemented
   in this module. Unknown variables raise ``ValueError`` (HTTP 400 upstream);
3. ordering by one variable (ascending by default, ``-`` prefix for descending)
   with ``None`` values sorted last - mirroring ``QueryService._sorted_rows``;
4. opaque cursor pagination over a stable key that always ends with the
   entity's primary id (``video_id``/``comment_id``/``channel_id``/``observation_id``),
   via :class:`services.pagination` ``page_sorted``.

Rows are returned keyed by *variable name*; recommendation rows are enriched
with their ``observation_id`` (their primary id, not a registered variable)
so pagination and the raw-record endpoint stay stable.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from SocialScienceResearch.config.settings import SocialScienceSettings
from SocialScienceResearch.domain.query import (
    Operator,
    QueryCondition,
    QueryGroup,
    evaluate_query,
)
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.pagination import page_sorted
from SocialScienceResearch.services.query_service import QueryService
from SocialScienceResearch.services.variable_registry import (
    VariableMeta,
    VariableRegistry,
)

#: Registered entities (must match the research-query contract).
_REGISTERED_ENTITIES = ("video", "comment", "channel", "recommendation", "author")

#: Primary id field per entity - the stable tail of every cursor key.
_ID_FIELD: dict[str, str] = {
    "video": "video_id",
    "comment": "comment_id",
    "channel": "channel_id",
    "recommendation": "observation_id",
    "author": "author_id",
}

#: Text fields matched (OR-ed, case-insensitive) by the ``q`` search.
_SEARCH_FIELDS: dict[str, tuple[str, ...]] = {
    "video": ("title", "description"),
    "channel": ("title", "description"),
    "comment": ("comment_text",),
    "recommendation": ("title",),
    "author": ("author_name", "author_id"),
}

#: Operators the explorer accepts; a strict subset of the query evaluator's.
_SUPPORTED_OPERATORS = frozenset(
    {
        "eq",
        "neq",
        "contains",
        "not_contains",
        "in",
        "not_in",
        "gt",
        "gte",
        "lt",
        "lte",
        "is_null",
        "not_null",
    }
)


class SortOption(BaseModel):
    """One sortable variable exposed to the explorer UI."""

    model_config = ConfigDict(extra="allow")

    variable: str
    data_type: str


class ExploreResult(BaseModel):
    """Paginated explorer page for one entity."""

    model_config = ConfigDict(extra="allow")

    entity: str
    columns: list[VariableMeta]
    items: list[dict[str, Any]] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False
    total: int | None = None
    sort_options: list[SortOption] = Field(default_factory=list)


class ExplorerService:
    """Read-side browsing over entity rows with filters and provenance hooks."""

    def __init__(
        self, repos: Repositories, settings: SocialScienceSettings | None = None
    ) -> None:
        self._repos = repos
        self._settings = settings or SocialScienceSettings()
        self._query = QueryService(repos, self._settings)

    # ------------------------------------------------------------------
    def explore(
        self,
        entity: str,
        q: str | None = None,
        filters: list[dict[str, Any]] | None = None,
        sort: str | None = None,
        cursor: str | None = None,
        page_size: int = 25,
    ) -> ExploreResult:
        """Return one cursor-paginated page of ``entity`` rows.

        ``filters`` is a list of ``{variable, operator, value}`` dicts (the
        operator vocabulary from :data:`_SUPPORTED_OPERATORS`); every variable
        is validated against the :class:`VariableRegistry` (unknown -> ValueError).
        """
        entity = entity.lower()
        # Column catalogue doubles as the entity/column validator.
        columns = VariableRegistry.get_variables(entity)
        filters = self._validated_filters(entity, filters or [])
        sort, descending = self._validated_sort(entity, columns, sort)

        rows = self._explore_rows(entity)
        if q:
            rows = self._search_rows(entity, rows, q)
        if filters:
            rows = evaluate_query(entity, self._group_from_filters(filters), rows)
        rows = self._dedupe_rows(entity, rows)
        rows = self._ordered_rows(entity, rows, sort, descending)
        rows = self._ranked_rows(entity, rows)

        page = page_sorted(
            rows,
            cursor=cursor,
            page_size=page_size,
            key_func=self._row_key,
            total=len(rows),
        )
        return ExploreResult(
            entity=entity,
            columns=columns,
            items=[self._visible_row(row) for row in page.items],
            next_cursor=page.next_cursor,
            has_more=page.has_more,
            total=page.total,
            sort_options=[
                SortOption(variable=meta.name, data_type=meta.data_type)
                for meta in columns
                if meta.data_type != "list"
            ],
        )

    # ------------------------------------------------------------------
    def _dedupe_rows(
        self, entity: str, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Drop duplicate rows sharing the same primary id.

        Historical Excel data may contain the same entity id in multiple rows
        (e.g. written before upserts or from manual edits). The explorer is a
        browsable *latest-state* view, so only the first occurrence per primary
        id is kept, keeping the UI's row keys unique.
        """
        id_field = _ID_FIELD[entity]
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for row in rows:
            key = str(row.get(id_field) or "")
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(row)
        return unique

    # ------------------------------------------------------------------
    def get_row_raw(self, entity: str, entity_id: str) -> dict[str, Any] | None:
        """Return ``{entity, entity_id, raw_json}`` for one persisted record.

        Returns ``None`` when the id is not present; raises ``ValueError`` for
        an unknown entity (HTTP 400 upstream).
        """
        entity = entity.lower()
        model = self._fetch(entity, entity_id)
        if model is None:
            return None
        return {
            "entity": entity,
            "entity_id": entity_id,
            "raw_json": model.raw_json,
        }

    # ------------------------------------------------------------------
    # Filtering (reuses the research-query evaluator)
    # ------------------------------------------------------------------
    def _validated_filters(
        self, entity: str, filters: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not isinstance(filters, list):
            raise ValueError("filters must be a list of {variable, operator, value}")
        validated: list[dict[str, Any]] = []
        for index, spec in enumerate(filters):
            if not isinstance(spec, dict) or "variable" not in spec or "operator" not in spec:
                raise ValueError(
                    f"filter #{index} must be an object with 'variable' and 'operator'"
                )
            variable = str(spec["variable"])
            operator = str(spec["operator"]).lower()
            if VariableRegistry.get_variable(entity, variable) is None:
                raise ValueError(f"Unknown variable {variable!r} for entity {entity!r}")
            if operator not in _SUPPORTED_OPERATORS:
                raise ValueError(
                    f"Unsupported operator {operator!r}; supported: "
                    f"{sorted(_SUPPORTED_OPERATORS)}"
                )
            if operator in ("in", "not_in") and not isinstance(spec.get("value"), list):
                raise ValueError(
                    f"operator {operator!r} requires a list value"
                )
            data_type = VariableRegistry.get_variable(entity, variable).data_type
            validated.append(
                {
                    "variable": variable,
                    "operator": operator,
                    "value": self._coerce_value(data_type, spec.get("value")),
                }
            )
        return validated

    @staticmethod
    def _group_from_filters(filters: list[dict[str, Any]]) -> QueryGroup:
        """Lift simple filters into an AND-ed QueryGroup for the evaluator."""
        conditions = [
            QueryCondition(
                variable=spec["variable"],
                operator=Operator(spec["operator"]),
                value=spec.get("value"),
            )
            for spec in filters
        ]
        return QueryGroup(operator="AND", conditions=conditions)

    @staticmethod
    def _coerce_value(data_type: str, value: Any) -> Any:
        """Coerce JSON-decoded filter values to the variable's data type.

        Strings are left untouched so ``contains``/``eq`` keep their literal
        semantics; numeric/boolean variables are coerced so ``gt``/``gte``/``eq``
        compare against the right Python type. Unparseable values pass through
        (the evaluator simply excludes rows whose value cannot be judged).
        """
        if value is None or isinstance(value, list):
            return value
        try:
            if data_type == "int":
                return int(value)
            if data_type == "float":
                return float(value)
            if data_type == "bool":
                if isinstance(value, bool):
                    return value
                return str(value).strip().lower() in {"1", "true", "yes", "on"}
        except (TypeError, ValueError):
            return value
        return value

    # ------------------------------------------------------------------
    # Text search
    # ------------------------------------------------------------------
    def _search_rows(
        self, entity: str, rows: list[dict[str, Any]], q: str
    ) -> list[dict[str, Any]]:
        needle = str(q).lower()
        fields = _SEARCH_FIELDS[entity]
        return [
            row
            for row in rows
            if any(needle in str(row.get(field) or "").lower() for field in fields)
        ]

    # ------------------------------------------------------------------
    # Ordering + cursor pagination
    # ------------------------------------------------------------------
    def _validated_sort(
        self, entity: str, columns: list[VariableMeta], sort: str | None
    ) -> tuple[str | None, bool]:
        if not sort:
            return None, False
        descending = sort.startswith("-")
        variable = sort[1:] if descending else sort
        if not variable:
            raise ValueError("sort must name a variable (prefix '-' for descending)")
        meta = VariableRegistry.get_variable(entity, variable)
        if meta is None:
            raise ValueError(f"Unknown variable {variable!r} for entity {entity!r}")
        if meta.data_type == "list":
            raise ValueError(
                f"variable {variable!r} is a list and cannot be used to sort"
            )
        return variable, descending

    def _ordered_rows(
        self,
        entity: str,
        rows: list[dict[str, Any]],
        sort: str | None,
        descending: bool,
    ) -> list[dict[str, Any]]:
        if sort is None:
            id_field = _ID_FIELD[entity]
            if entity == "recommendation":
                # Default order is the observed feed rank (same key as
                # QueryService._recommendation_rows): grouped by source, then
                # ascending "Up Next" rail position, unknown positions last.
                return sorted(
                    rows,
                    key=lambda row: (
                        str(row.get("source_video_id") or ""),
                        row.get("position") is None,
                        row.get("position") if row.get("position") is not None else 0,
                        str(row.get("recommended_video_id") or ""),
                    ),
                )
            return sorted(rows, key=lambda row: (str(row[id_field] or ""),))
        if descending:
            present = [row for row in rows if row.get(sort) is not None]
            missing = [row for row in rows if row.get(sort) is None]
            present.sort(key=lambda row: row[sort], reverse=True)
            return present + missing
        return sorted(
            rows, key=lambda row: (row.get(sort) is None, row.get(sort))
        )

    def _ranked_rows(
        self, entity: str, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Attach an order-preserving string rank + primary key per row.

        The list is already in the display order; assigning a zero-padded rank
        index yields a monotonic, lexicographically-sortable cursor key so
        ``page_sorted`` can binary-search it regardless of the underlying value
        types (ints, datetimes, strings). The cursor token always ends with the
        entity's primary id for stability.
        """
        id_field = _ID_FIELD[entity]
        ranked: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            copy = dict(row)
            copy["__rank"] = f"{index:015d}"
            copy["__pk"] = str(copy.get(id_field) or "")
            ranked.append(copy)
        return ranked

    @staticmethod
    def _row_key(row: dict[str, Any]) -> tuple[str, ...]:
        return (row["__rank"], row["__pk"])

    @staticmethod
    def _visible_row(row: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in row.items() if not key.startswith("__")}

    # ------------------------------------------------------------------
    # Projected row resolution (no raw_json TOAST payloads)
    # ------------------------------------------------------------------
    def _explore_rows(self, entity: str) -> list[dict[str, Any]]:
        """Resolve the latest-state rows for one entity as projected dicts.

        Delegates to the repository's ``explore_*_rows`` methods, which column
        project (excluding heavy ``raw_json`` blobs) so a full-corpus browse is
        fast. Recommendation rows already carry their ``observation_id`` primary
        key from the projection.
        """
        if entity == "video":
            return self._repos.videos.explore_video_rows()
        if entity == "comment":
            return self._repos.comments.explore_comment_rows()
        if entity == "channel":
            return self._repos.channels.explore_channel_rows()
        if entity == "recommendation":
            return self._repos.recommendations.explore_recommendation_rows()
        if entity == "author":
            return self._repos.authors.explore_author_rows()
        raise ValueError(
            f"Unknown entity {entity!r}; expected one of "
            "channel, video, comment, recommendation, author"
        )

    # ------------------------------------------------------------------
    # Entity fetch for the raw-record endpoint
    # ------------------------------------------------------------------
    def _fetch(self, entity: str, entity_id: str):
        if entity not in _REGISTERED_ENTITIES:
            raise ValueError(
                f"Unknown entity {entity!r}; expected one of "
                f"{sorted(_REGISTERED_ENTITIES)}"
            )
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
