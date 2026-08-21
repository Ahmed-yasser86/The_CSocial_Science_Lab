"""Query and sampling specification models.

These are *request specifications* that keep the service and analytics layers
decoupled from the acquisition library. Filters and sampling criteria are
explicit and serializable so that sampling is reproducible and transparent.

The module also owns the **ResearchQuery** tree (conditions/groups) and its
pure in-memory evaluator (``evaluate_query`` / ``preview_query``), which the
research-query endpoints and the future explorer share. Rank operators are
implemented on top of :mod:`SocialScienceResearch.services.statistics_service`.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from .enums import SamplingStrategy

_MODEL_CONFIG = ConfigDict(extra="forbid")


class VideoFilter(BaseModel):
    """Filter for selecting videos of a channel corpus.

    View-based filters apply to the *latest* observation of each video at the
    time the filter runs - never to fabricated historical values.
    """

    model_config = _MODEL_CONFIG

    date_from: date | None = None
    date_to: date | None = None
    video_type: str | None = None  # e.g. 'short', 'long', 'live'
    duration_min: int | None = None  # seconds
    duration_max: int | None = None  # seconds
    views_min: int | None = None
    views_max: int | None = None
    upload_hour: int | None = None  # 0-23, local-to-upload platform time is unavailable; use published hour
    upload_weekday: int | None = None  # 0=Monday .. 6=Sunday
    keywords: list[str] = Field(default_factory=list)  # matched in title/description
    tags: list[str] = Field(default_factory=list)
    category: str | None = None

    def model_dump(self) -> dict[str, Any]:  # type: ignore[override]
        return super().model_dump(exclude_none=True)


class SamplingSpec(BaseModel):
    """Reproducible sampling criteria.

    ``seed`` makes random/stratified samples reproducible; ``criteria_json``
    records the exact criteria used so the sampling is transparent.
    """

    model_config = _MODEL_CONFIG

    strategy: SamplingStrategy
    size: int | None = None  # absolute number of videos/comments
    percent: float | None = None  # e.g. 10.0 == top/bottom/latest 10%
    seed: int | None = None  # None -> module default seed
    strata: str | None = None  # 'year' | 'month' | 'weekday' for stratified
    sample_per_stratum: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    top_n: int | None = None  # for top/bottom list endpoints


class PeriodSpec(BaseModel):
    """A named time window used for period comparison research."""

    model_config = _MODEL_CONFIG

    name: str | None = None
    start: date
    end: date


class CommentFilter(BaseModel):
    """Filter for selecting comments (wired by ``QueryService.filter_comments``).

    Row-based criteria apply to the *latest* observation of each comment's
    like/reply/removal counts - never to fabricated historical values.
    """

    model_config = _MODEL_CONFIG

    date_from: datetime | None = None
    date_to: datetime | None = None
    min_likes: int | None = None
    max_likes: int | None = None
    min_replies: int | None = None
    max_replies: int | None = None
    only_roots: bool = False
    only_replies: bool = False
    author_id: str | None = None
    is_author: bool | None = None
    keywords: list[str] = Field(default_factory=list)  # matched in comment text


class AdvancedSamplingSpec(BaseModel):
    """Advanced sampling specification for cross-channel, multi-video, and user-based sampling.

    Supports complex researcher scenarios:
    - Sample/population of specific user comments across all videos and channels
    - Sample/population within specific channel(s)
    - Sample/population of specific users with their IDs
    - Sample/population of non-specified users across one channel but among specified videos
    - Video filters within same channel (date range, type, duration, views, etc.)
    - Multiple channels among specific period
    - Combination of channel IDs, video IDs, author IDs with sampling strategies
    """

    model_config = _MODEL_CONFIG

    # Sampling strategy (same as SamplingSpec)
    strategy: SamplingStrategy
    size: int | None = None
    percent: float | None = None
    seed: int | None = None
    strata: str | None = None
    sample_per_stratum: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    top_n: int | None = None

    # Scope filters
    channel_ids: list[str] = Field(default_factory=list)  # specific channels
    run_ids: list[str] = Field(default_factory=list)  # restrict to entities first discovered in these runs
    video_ids: list[str] = Field(default_factory=list)  # specific videos
    author_ids: list[str] = Field(default_factory=list)  # specific author IDs
    exclude_author_ids: list[str] = Field(default_factory=list)  # exclude specific authors
    author_names: list[str] = Field(default_factory=list)  # include comments whose author name contains any (case-insensitive)
    exclude_author_names: list[str] = Field(default_factory=list)  # drop comments whose author name contains any (case-insensitive)

    # Video-level filters (applied when channel_ids provided)
    video_type: str | None = None  # 'short', 'long', 'live'
    duration_min: int | None = None
    duration_max: int | None = None
    views_min: int | None = None
    views_max: int | None = None
    upload_hour: int | None = None
    upload_weekday: int | None = None
    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    category: str | None = None  # kept for backward compatibility
    categories: list[str] = Field(default_factory=list)  # video categories (any match)

    # Comment-level filters
    min_likes: int | None = None
    max_likes: int | None = None
    min_replies: int | None = None
    max_replies: int | None = None
    only_roots: bool = False
    only_replies: bool = False
    is_author: bool | None = None
    comment_keywords: list[str] = Field(default_factory=list)

    # Author-overlap filters (comments of authors active across videos/channels)
    overlap: Literal["off", "video", "channel"] | None = None  # 'video' = distinct videos, 'channel' = distinct channels
    overlap_min: int = 2  # minimum distinct videos/channels an author must appear in
    overlap_video_ids: list[str] = Field(default_factory=list)  # restrict overlap count to these specific videos
    overlap_channel_ids: list[str] = Field(default_factory=list)  # restrict overlap count to these specific channels

    # Sampling mode
    entity_type: Literal["video", "comment"] = "video"  # what to sample
    include_all_channels: bool = False  # if true, ignore channel_ids and sample across all


# ----------------------------------------------------------------------
# ResearchQuery: operators, condition tree, evaluator
# ----------------------------------------------------------------------
class Operator(str, Enum):
    """Binary and rank operators understood by the query evaluator."""

    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    IS_NULL = "is_null"
    NOT_NULL = "not_null"
    TOP_PCT = "top_pct"
    BOTTOM_PCT = "bottom_pct"
    PERCENTILE_RANK = "percentile_rank"
    QUARTILE = "quartile"
    QUANTILE = "quantile"
    MEDIAN_SPLIT = "median_split"

    def __str__(self) -> str:
        return self.value


OPERATOR_DESCRIPTIONS: dict[Operator, str] = {
    Operator.EQ: "Value equals the condition value.",
    Operator.NEQ: "Value does not equal the condition value.",
    Operator.GT: "Value is strictly greater than the condition value.",
    Operator.GTE: "Value is greater than or equal to the condition value.",
    Operator.LT: "Value is strictly less than the condition value.",
    Operator.LTE: "Value is less than or equal to the condition value.",
    Operator.CONTAINS: "String contains the value (case-insensitive); list contains the element.",
    Operator.NOT_CONTAINS: "String does not contain the value; list does not contain the element.",
    Operator.IN: "Value is one of ``values``.",
    Operator.NOT_IN: "Value is not one of ``values``.",
    Operator.BETWEEN: "Value is in the inclusive ``[values[0], values[1]]`` range.",
    Operator.IS_NULL: "Value is missing (None).",
    Operator.NOT_NULL: "Value is present.",
    Operator.TOP_PCT: "Value >= the p-th percentile of the population (top p%).",
    Operator.BOTTOM_PCT: "Value < the (100-p)-th percentile of the population (bottom p%).",
    Operator.PERCENTILE_RANK: "The record's percentile position (share of the population below it, 0-100) >= the condition value.",
    Operator.QUARTILE: "Value belongs to the given quartile group (1..4).",
    Operator.QUANTILE: "Value belongs to the given equal-count group (1..quantile_n) of the population.",
    Operator.MEDIAN_SPLIT: "Value >= the median of the population.",
}


class QueryCondition(BaseModel):
    """One leaf condition in a research query.

    Rank operators read the *entire population* handed to ``evaluate_query``:
    ``top_pct``/``bottom_pct`` use ``value`` as the percentile threshold;
    ``quartile`` uses the ``quartile`` field (1..4); ``quantile`` uses
    ``quantile_n`` (number of groups) plus ``value`` (the 1-indexed group);
    ``percentile_rank`` uses ``value`` as the minimum rank percentage.
    """

    model_config = _MODEL_CONFIG

    variable: str
    operator: Operator
    value: Any = None
    values: list[Any] | None = None  # ``in``/``not_in`` pools, ``between`` range
    quantile_n: int | None = None  # number of groups for ``quantile``
    quartile: int | None = None  # group (1..4) for ``quartile``


class QueryGroup(BaseModel):
    """A node in the research query tree.

    ``operator`` is ``"AND"``/``"OR"``/``"NOT"``. Members are conditions or
    nested groups; ``NOT`` negates the conjunction of its members.
    """

    model_config = _MODEL_CONFIG

    operator: Literal["AND", "OR", "NOT"]
    conditions: list[Union[QueryCondition, "QueryGroup"]] = Field(default_factory=list)


class ResearchQuery(BaseModel):
    """Top-level research query: an entity and its condition tree."""

    model_config = _MODEL_CONFIG

    entity: Literal["video", "comment", "channel", "recommendation", "author"]
    root: QueryGroup


class QueryContext(BaseModel):
    """Optional scope for a research query (which subset of the corpus)."""

    model_config = _MODEL_CONFIG

    channel_id: str | None = None
    video_id: str | None = None


class ResearchQueryRequest(BaseModel):
    """HTTP body for ``POST /research/query/preview`` and ``.../resolve``."""

    model_config = _MODEL_CONFIG

    entity: Literal["video", "comment", "channel", "recommendation", "author"]
    root: QueryGroup
    query_context: QueryContext | None = None


class QueryStage(BaseModel):
    """One funnel stage: cumulative = rows matching the prefix so far,
    matched = incremental drop caused by adding this condition."""

    model_config = _MODEL_CONFIG

    condition: str
    matched: int
    cumulative: int


class QueryPreview(BaseModel):
    """Result of ``preview_query``: total, ordered stages and population."""

    model_config = _MODEL_CONFIG

    total: int
    stages: list[QueryStage] = Field(default_factory=list)
    population_size: int
    n: int  # final resolved count (== total); mirrors ``resolve``'s total


class QueryResolve(BaseModel):
    """Count-only result (no rows) used by the sampling stage."""

    model_config = _MODEL_CONFIG

    total: int
    population_size: int


#: Rebuild needed because ``QueryGroup`` references itself via a forward ref.
QueryGroup.model_rebuild()


# ----------------------------------------------------------------------
# Evaluator
# ----------------------------------------------------------------------
def _iter_conditions(group: QueryGroup):
    for member in group.conditions:
        if isinstance(member, QueryCondition):
            yield member
        else:
            yield from _iter_conditions(member)


def _validate_conditions(entity: str, root: QueryGroup) -> None:
    from SocialScienceResearch.services.variable_registry import VariableRegistry

    for cond in _iter_conditions(root):
        if VariableRegistry.get_variable(entity, cond.variable) is None:
            raise ValueError(
                f"Unknown variable {cond.variable!r} for entity {entity!r}"
            )


def build_variable_value(entity: str, row: dict, variable: str) -> Any:
    """Extract ``variable`` from a row dict keyed by variable name.

    Rows are built by ``QueryService.resolve_latest_rows``; observed metric
    variables (view/like/comment counts, ...) are already resolved to their
    **latest observation** there, so this helper is a plain validated lookup.
    """
    from SocialScienceResearch.services.variable_registry import VariableRegistry

    if VariableRegistry.get_variable(entity, variable) is None:
        raise ValueError(f"Unknown variable {variable!r} for entity {entity!r}")
    return row.get(variable)


def _population_values(
    variable: str, population: list[dict], entity: str, cache: dict[str, list[Any]]
) -> list[Any]:
    if variable not in cache:
        cache[variable] = [
            build_variable_value(entity, row, variable)
            for row in population
            if build_variable_value(entity, row, variable) is not None
        ]
    return cache[variable]


def _in_group(value: Any, boundaries: list[float], group: int, n_groups: int) -> bool:
    group = int(group)
    if not 1 <= group <= n_groups:
        raise ValueError(f"group must be in 1..{n_groups}, got {group}")
    if n_groups == 1:
        return True
    if group == 1:
        return value < boundaries[0]
    if group == n_groups:
        return value >= boundaries[-1]
    return boundaries[group - 2] <= value < boundaries[group - 1]


def _eval_condition(
    cond: QueryCondition,
    row: dict,
    entity: str,
    population: list[dict],
    cache: dict[str, list[Any]],
) -> bool:
    from SocialScienceResearch.services.statistics_service import StatisticsService

    op = cond.operator
    value = build_variable_value(entity, row, cond.variable)

    if op in (Operator.IS_NULL, Operator.NOT_NULL):
        return value is None if op is Operator.IS_NULL else value is not None
    if value is None:
        return False  # missing values cannot be judged for value-based ops

    if op is Operator.EQ:
        return value == cond.value
    if op is Operator.NEQ:
        return value != cond.value
    if op is Operator.GT:
        return value > cond.value
    if op is Operator.GTE:
        return value >= cond.value
    if op is Operator.LT:
        return value < cond.value
    if op is Operator.LTE:
        return value <= cond.value
    if op is Operator.CONTAINS:
        if isinstance(value, list):
            return cond.value in value
        return str(cond.value).lower() in str(value).lower()
    if op is Operator.NOT_CONTAINS:
        if isinstance(value, list):
            return cond.value not in value
        return str(cond.value).lower() not in str(value).lower()
    if op in (Operator.IN, Operator.NOT_IN):
        pool = cond.values if cond.values is not None else cond.value
        if pool is None:
            raise ValueError(f"operator {op.value} requires values")
        found = value in pool
        return found if op is Operator.IN else not found
    if op is Operator.BETWEEN:
        if not cond.values or len(cond.values) < 2:
            raise ValueError("operator 'between' requires values=[low, high]")
        return cond.values[0] <= value <= cond.values[1]

    # --- Rank operators: computed against the full population ---
    vals = _population_values(cond.variable, population, entity, cache)
    if not vals:
        return False

    if op is Operator.TOP_PCT:
        if cond.value is None:
            raise ValueError("operator 'top_pct' requires a numeric value")
        threshold = StatisticsService.percentile(vals, cond.value)
        return threshold is not None and value >= threshold
    if op is Operator.BOTTOM_PCT:
        if cond.value is None:
            raise ValueError("operator 'bottom_pct' requires a numeric value")
        threshold = StatisticsService.percentile(vals, 100 - cond.value)
        return threshold is not None and value < threshold
    if op is Operator.MEDIAN_SPLIT:
        median = StatisticsService.median(vals).value
        return median is not None and value >= median
    if op is Operator.QUARTILE:
        if cond.quartile is None:
            raise ValueError("operator 'quartile' requires the quartile field (1..4)")
        q = StatisticsService.quartiles(vals)
        return _in_group(
            value, [b for b in (q.q1, q.q2, q.q3) if b is not None], cond.quartile, 4
        )
    if op is Operator.QUANTILE:
        if cond.quantile_n is None:
            raise ValueError("operator 'quantile' requires quantile_n (number of groups)")
        n_groups = int(cond.quantile_n)
        if n_groups < 1:
            raise ValueError("quantile_n must be >= 1")
        boundaries = StatisticsService.quantiles(vals, n_groups).boundaries
        return _in_group(value, boundaries, cond.value, n_groups)
    if op is Operator.PERCENTILE_RANK:
        below = sum(1 for x in vals if x < value)
        rank = below / len(vals) * 100.0
        return rank >= float(cond.value or 0)

    raise ValueError(f"unsupported operator {op.value}")


def _apply_group(
    group: QueryGroup,
    rows: list[dict],
    population: list[dict],
    entity: str,
    cache: dict[str, list[Any]],
) -> list[dict]:
    if group.operator == "AND":
        current = rows
        for member in group.conditions:
            current = _apply_member(member, current, population, entity, cache)
        return current
    if group.operator == "OR":
        matched: list[dict] = []
        seen: set[int] = set()
        for member in group.conditions:
            for row in _apply_member(member, rows, population, entity, cache):
                if id(row) not in seen:
                    seen.add(id(row))
                    matched.append(row)
        return matched
    if group.operator == "NOT":
        inner = _apply_and_members(group.conditions, rows, population, entity, cache)
        inner_ids = {id(row) for row in inner}
        return [row for row in rows if id(row) not in inner_ids]
    raise ValueError(f"unsupported group operator {group.operator}")


def _apply_and_members(
    members: list[Union[QueryCondition, QueryGroup]],
    rows: list[dict],
    population: list[dict],
    entity: str,
    cache: dict[str, list[Any]],
) -> list[dict]:
    current = rows
    for member in members:
        current = _apply_member(member, current, population, entity, cache)
    return current


def _apply_member(
    member: Union[QueryCondition, QueryGroup],
    rows: list[dict],
    population: list[dict],
    entity: str,
    cache: dict[str, list[Any]],
) -> list[dict]:
    if isinstance(member, QueryCondition):
        return [row for row in rows if _eval_condition(member, row, entity, population, cache)]
    return _apply_group(member, rows, population, entity, cache)


def evaluate_query(entity: str, root: QueryGroup, rows: list[dict]) -> list[dict]:
    """Evaluate ``root`` against ``rows`` (dicts keyed by variable name).

    Rank operators always compute against the *entire* population passed in
    (``rows``), not the shrinking prefix. Returns the matched rows.
    """
    _validate_conditions(entity, root)
    population = list(rows)
    cache: dict[str, list[Any]] = {}
    return _apply_group(root, population, population, entity, cache)


# ----------------------------------------------------------------------
# Funnel (query preview)
# ----------------------------------------------------------------------
def _member_label(member: Union[QueryCondition, QueryGroup]) -> str:
    if isinstance(member, QueryCondition):
        detail = (
            f" {member.values}"
            if member.values is not None
            else f" {member.value}"
        )
        return f"{member.variable} {member.operator.value}{detail}"
    return f"{member.operator} group"


def _staged_group(
    group: QueryGroup,
    prefix: list[dict],
    population: list[dict],
    entity: str,
    cache: dict[str, list[Any]],
    stages: list[QueryStage],
) -> list[dict]:
    if group.operator == "AND":
        current = prefix
        for member in group.conditions:
            if isinstance(member, QueryCondition):
                matched = [
                    row
                    for row in current
                    if _eval_condition(member, row, entity, population, cache)
                ]
            else:
                # Nested OR/NOT groups are evaluated once over the full
                # population, then intersected with the running prefix.
                group_rows = _apply_group(member, population, population, entity, cache)
                group_ids = {id(row) for row in group_rows}
                matched = [row for row in current if id(row) in group_ids]
            stages.append(
                QueryStage(
                    condition=_member_label(member),
                    matched=len(current) - len(matched),
                    cumulative=len(matched),
                )
            )
            current = matched
        return current
    # OR / NOT at this level (including a root group): one stage, group result.
    result = _apply_group(group, prefix, population, entity, cache)
    stages.append(
        QueryStage(
            condition=_member_label(group),
            matched=len(prefix) - len(result),
            cumulative=len(result),
        )
    )
    return result


def preview_query(entity: str, root: QueryGroup, rows: list[dict]) -> QueryPreview:
    """Evaluate ``root`` and report the ordered funnel stages.

    Stages flatten the tree depth-first. For AND sequences each leaf is a
    stage whose ``cumulative`` is the count matching conditions ``1..k`` AND-ed
    (prefix semantics) and whose ``matched`` is the incremental drop. OR/NOT
    groups (at any level) contribute exactly one stage carrying their group
    result.
    """
    _validate_conditions(entity, root)
    population = list(rows)
    cache: dict[str, list[Any]] = {}
    stages: list[QueryStage] = []
    final = _staged_group(root, population, population, entity, cache, stages)
    total = len(final)
    return QueryPreview(
        total=total, stages=stages, population_size=len(population), n=total
    )
