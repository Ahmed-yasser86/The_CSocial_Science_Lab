"""Tests for the ResearchQuery evaluator, operators and funnel semantics.

Covers binary operators, rank operators (top_pct/bottom_pct/quartile/quantile/
median_split/percentile_rank) computed against the whole population, nested
AND/OR/NOT trees, missing-value handling and the funnel (query preview) stage
cumulative semantics.
"""

from __future__ import annotations

import pytest

from SocialScienceResearch.domain.query import (
    Operator,
    QueryCondition,
    QueryGroup,
    build_variable_value,
    evaluate_query,
    preview_query,
)


def _video_rows():
    """Deterministic population: view_count 100..1000 step 100 (n=10)."""
    rows = []
    for i in range(10):
        rows.append(
            {
                "video_id": f"v{i}",
                "channel_id": "UCx",
                "view_count": 100 + i * 100,
                "duration": 100 + i * 100,
                "title": f"Video {i}",
                "tags": [f"tag{i}", "common"],
                "is_short": i % 3 == 0,
            }
        )
    return rows


def _cond(variable="view_count", op=Operator.GT, **kwargs):
    return QueryCondition(variable=variable, operator=op, **kwargs)


def _ids(rows):
    return [row["video_id"] for row in rows]


# ----------------------------------------------------------------------
# Binary operators
# ----------------------------------------------------------------------
def test_eq_gt_gte_lt_lte() -> None:
    rows = _video_rows()
    assert _ids(evaluate_query("video", QueryGroup(operator="AND", conditions=[_cond(op=Operator.EQ, value=200)]), rows)) == ["v1"]
    assert _ids(evaluate_query("video", QueryGroup(operator="AND", conditions=[_cond(op=Operator.GT, value=500)]), rows)) == [f"v{i}" for i in range(5, 10)]
    assert _ids(evaluate_query("video", QueryGroup(operator="AND", conditions=[_cond(op=Operator.GTE, value=600)]), rows)) == [f"v{i}" for i in range(5, 10)]
    assert _ids(evaluate_query("video", QueryGroup(operator="AND", conditions=[_cond(op=Operator.LT, value=400)]), rows)) == [f"v{i}" for i in range(0, 3)]
    assert _ids(evaluate_query("video", QueryGroup(operator="AND", conditions=[_cond(op=Operator.LTE, value=300)]), rows)) == [f"v{i}" for i in range(0, 3)]


def test_neq() -> None:
    rows = _video_rows()
    result = evaluate_query("video", QueryGroup(operator="AND", conditions=[_cond(op=Operator.NEQ, value=500)]), rows)
    assert len(result) == 9 and "v4" not in _ids(result)


def test_contains_on_list_and_string() -> None:
    rows = _video_rows()
    list_cond = QueryGroup(operator="AND", conditions=[QueryCondition(variable="tags", operator=Operator.CONTAINS, value="tag2")])
    assert _ids(evaluate_query("video", list_cond, rows)) == ["v2"]
    str_cond = QueryGroup(operator="AND", conditions=[QueryCondition(variable="title", operator=Operator.CONTAINS, value="video 3")])
    assert _ids(evaluate_query("video", str_cond, rows)) == ["v3"]


def test_not_contains() -> None:
    rows = _video_rows()
    cond = QueryGroup(operator="AND", conditions=[QueryCondition(variable="tags", operator=Operator.NOT_CONTAINS, value="common")])
    assert evaluate_query("video", cond, rows) == []


def test_in_and_not_in() -> None:
    rows = _video_rows()
    cond = QueryGroup(operator="AND", conditions=[QueryCondition(variable="view_count", operator=Operator.IN, values=[200, 300])])
    assert _ids(evaluate_query("video", cond, rows)) == ["v1", "v2"]
    cond = QueryGroup(operator="AND", conditions=[QueryCondition(variable="view_count", operator=Operator.NOT_IN, values=[100, 1000])])
    result = _ids(evaluate_query("video", cond, rows))
    assert result == [f"v{i}" for i in range(1, 9)]


def test_between_inclusive() -> None:
    rows = _video_rows()
    cond = QueryGroup(operator="AND", conditions=[QueryCondition(variable="view_count", operator=Operator.BETWEEN, values=[300, 600])])
    assert _ids(evaluate_query("video", cond, rows)) == [f"v{i}" for i in range(2, 6)]


def test_is_null_and_not_null() -> None:
    rows = _video_rows() + [{"video_id": "ghost", "channel_id": "UCx", "view_count": None, "title": None}]
    null_cond = QueryGroup(operator="AND", conditions=[QueryCondition(variable="view_count", operator=Operator.IS_NULL)])
    assert _ids(evaluate_query("video", null_cond, rows)) == ["ghost"]
    not_null = QueryGroup(operator="AND", conditions=[QueryCondition(variable="view_count", operator=Operator.NOT_NULL)])
    assert evaluate_query("video", not_null, rows) == _video_rows()


# ----------------------------------------------------------------------
# Rank operators against the full population
# ----------------------------------------------------------------------
def test_top_pct_uses_percentile_threshold() -> None:
    rows = _video_rows()
    # top_pct(80): value >= P80 == 820 -> the top 20%.
    cond = QueryGroup(operator="AND", conditions=[QueryCondition(variable="view_count", operator=Operator.TOP_PCT, value=80)])
    assert _ids(evaluate_query("video", cond, rows)) == ["v8", "v9"]


def test_bottom_pct_below_high_percentile() -> None:
    rows = _video_rows()
    # bottom_pct(80): value < P20 == 280 -> the bottom 20%.
    cond = QueryGroup(operator="AND", conditions=[QueryCondition(variable="view_count", operator=Operator.BOTTOM_PCT, value=80)])
    assert _ids(evaluate_query("video", cond, rows)) == ["v0", "v1"]


def test_median_split_is_value_ge_median() -> None:
    rows = _video_rows()
    cond = QueryGroup(operator="AND", conditions=[QueryCondition(variable="view_count", operator=Operator.MEDIAN_SPLIT)])
    assert _ids(evaluate_query("video", cond, rows)) == [f"v{i}" for i in range(5, 10)]


def test_quartile_group_membership() -> None:
    rows = _video_rows()
    q1 = QueryGroup(operator="AND", conditions=[QueryCondition(variable="view_count", operator=Operator.QUARTILE, quartile=1)])
    assert _ids(evaluate_query("video", q1, rows)) == ["v0", "v1", "v2"]
    q4 = QueryGroup(operator="AND", conditions=[QueryCondition(variable="view_count", operator=Operator.QUARTILE, quartile=4)])
    assert _ids(evaluate_query("video", q4, rows)) == ["v7", "v8", "v9"]


def test_quantile_equal_count_membership() -> None:
    rows = _video_rows()
    first = QueryGroup(operator="AND", conditions=[QueryCondition(variable="view_count", operator=Operator.QUANTILE, value=1, quantile_n=5)])
    assert _ids(evaluate_query("video", first, rows)) == ["v0", "v1"]
    last = QueryGroup(operator="AND", conditions=[QueryCondition(variable="view_count", operator=Operator.QUANTILE, value=5, quantile_n=5)])
    assert _ids(evaluate_query("video", last, rows)) == ["v8", "v9"]


def test_percentile_rank_position_in_population() -> None:
    rows = _video_rows()
    # rank(v) = (# values below v) / n * 100 -> the top two hold ranks 80, 90.
    cond = QueryGroup(operator="AND", conditions=[QueryCondition(variable="view_count", operator=Operator.PERCENTILE_RANK, value=80)])
    assert _ids(evaluate_query("video", cond, rows)) == ["v8", "v9"]


def test_rank_ops_ignore_missing_values_and_never_match_them() -> None:
    rows = _video_rows() + [{"video_id": "ghost", "channel_id": "UCx", "view_count": None, "title": None}]
    cond = QueryGroup(operator="AND", conditions=[QueryCondition(variable="view_count", operator=Operator.TOP_PCT, value=80)])
    result = _ids(evaluate_query("video", cond, rows))
    assert result == ["v8", "v9"] and "ghost" not in result


# ----------------------------------------------------------------------
# Group trees: AND / OR / NOT, nested
# ----------------------------------------------------------------------
def test_and_combines_conditions() -> None:
    rows = _video_rows()
    tree = QueryGroup(
        operator="AND",
        conditions=[
            _cond(op=Operator.GT, value=500),
            QueryCondition(variable="tags", operator=Operator.CONTAINS, value="common"),
        ],
    )
    assert _ids(evaluate_query("video", tree, rows)) == [f"v{i}" for i in range(5, 10)]


def test_or_union_without_duplicates() -> None:
    rows = _video_rows()
    tree = QueryGroup(
        operator="OR",
        conditions=[
            _cond(op=Operator.LT, value=300),
            _cond(op=Operator.GT, value=800),
        ],
    )
    assert _ids(evaluate_query("video", tree, rows)) == ["v0", "v1", "v8", "v9"]


def test_not_negates_conjunction() -> None:
    rows = _video_rows()
    tree = QueryGroup(operator="NOT", conditions=[_cond(op=Operator.GT, value=800)])
    assert _ids(evaluate_query("video", tree, rows)) == [f"v{i}" for i in range(0, 8)]


def test_nested_group_inside_and() -> None:
    rows = _video_rows()
    tree = QueryGroup(
        operator="AND",
        conditions=[
            _cond(op=Operator.GT, value=500),
            QueryGroup(
                operator="OR",
                conditions=[
                    _cond(op=Operator.LT, value=400),
                    _cond(op=Operator.GT, value=800),
                ],
            ),
        ],
    )
    assert _ids(evaluate_query("video", tree, rows)) == ["v8", "v9"]


def test_deep_not_group_inside_and() -> None:
    rows = _video_rows()
    tree = QueryGroup(
        operator="AND",
        conditions=[
            _cond(op=Operator.GT, value=200),
            QueryGroup(operator="NOT", conditions=[_cond(op=Operator.GT, value=800)]),
        ],
    )
    assert _ids(evaluate_query("video", tree, rows)) == [f"v{i}" for i in range(2, 8)]


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------
def test_unknown_variable_raises() -> None:
    rows = _video_rows()
    tree = QueryGroup(operator="AND", conditions=[_cond(variable="nope", op=Operator.GT, value=5)])
    with pytest.raises(ValueError):
        evaluate_query("video", tree, rows)


def test_unknown_entity_in_build_variable_value_raises() -> None:
    with pytest.raises(ValueError):
        build_variable_value("planet", {}, "title")


# ----------------------------------------------------------------------
# Funnel (query preview) stage semantics
# ----------------------------------------------------------------------
def test_funnel_stages_cumulative_and_incremental_drop() -> None:
    rows = _video_rows()
    tree = QueryGroup(
        operator="AND",
        conditions=[
            _cond(op=Operator.GT, value=500),  # -> 5 rows
            _cond(op=Operator.LT, value=1000),  # -> 4 rows (600..900)
            _cond(op=Operator.GT, value=650),  # -> 3 rows (700..900)
        ],
    )
    preview = preview_query("video", tree, rows)
    assert preview.population_size == 10
    assert preview.total == 3
    assert preview.n == preview.total
    assert [stage.matched for stage in preview.stages] == [5, 1, 1]
    assert [stage.cumulative for stage in preview.stages] == [5, 4, 3]
    assert [stage.condition for stage in preview.stages] == [
        "view_count gt 500",
        "view_count lt 1000",
        "view_count gt 650",
    ]


def test_funnel_or_root_single_stage() -> None:
    rows = _video_rows()
    tree = QueryGroup(
        operator="OR",
        conditions=[
            _cond(op=Operator.LT, value=300),
            _cond(op=Operator.GT, value=800),
        ],
    )
    preview = preview_query("video", tree, rows)
    assert preview.total == 4
    assert len(preview.stages) == 1
    stage = preview.stages[0]
    assert stage.cumulative == 4 and stage.matched == 6  # drop = 10 - 4


def test_funnel_nested_group_reported_once() -> None:
    rows = _video_rows()
    tree = QueryGroup(
        operator="AND",
        conditions=[
            _cond(op=Operator.GT, value=500),  # 5 rows (v5..v9)
            QueryGroup(
                operator="OR",
                conditions=[
                    _cond(op=Operator.LT, value=400),  # v0..v2 over full pop
                    _cond(op=Operator.GT, value=800),  # v8..v9 -> group = {v0,v1,v2,v8,v9}
                ],
            ),
        ],
    )
    preview = preview_query("video", tree, rows)
    assert preview.total == 2
    assert len(preview.stages) == 2
    assert preview.stages[0].cumulative == 5
    assert preview.stages[1].cumulative == 2
    assert preview.stages[1].matched == 3


# ----------------------------------------------------------------------
# Author entity
# ----------------------------------------------------------------------
def _author_rows():
    """Deterministic author population mirroring ``_author_rows`` emission."""
    return [
        {
            "author_id": "a1",
            "author_name": "Alice",
            "comment_count": 12,
            "video_ids": ["v1", "v2"],
            "first_seen_at": "2026-01-01T00:00:00+00:00",
            "last_seen_at": "2026-02-01T00:00:00+00:00",
            "is_author": True,
            "first_seen_run_id": "run_1",
        },
        {
            "author_id": "a2",
            "author_name": "Bob",
            "comment_count": 3,
            "video_ids": ["v1"],
            "first_seen_at": "2026-01-05T00:00:00+00:00",
            "last_seen_at": "2026-01-05T00:00:00+00:00",
            "is_author": False,
            "first_seen_run_id": "run_1",
        },
        {
            "author_id": "a3",
            "author_name": "Carol",
            "comment_count": 0,
            "video_ids": [],
            "first_seen_at": None,
            "last_seen_at": None,
            "is_author": None,
            "first_seen_run_id": None,
        },
    ]


def _author_ids(rows):
    return [row["author_id"] for row in rows]


def test_author_comment_count_and_is_author() -> None:
    rows = _author_rows()
    heavy = evaluate_query(
        "author",
        QueryGroup(operator="AND", conditions=[_cond(variable="comment_count", op=Operator.GTE, value=10)]),
        rows,
    )
    assert _author_ids(heavy) == ["a1"]

    uploaders = evaluate_query(
        "author",
        QueryGroup(operator="AND", conditions=[_cond(variable="is_author", op=Operator.EQ, value=True)]),
        rows,
    )
    assert _author_ids(uploaders) == ["a1"]


def test_author_video_ids_list_membership() -> None:
    rows = _author_rows()
    on_v2 = evaluate_query(
        "author",
        QueryGroup(operator="AND", conditions=[_cond(variable="video_ids", op=Operator.CONTAINS, value="v2")]),
        rows,
    )
    assert _author_ids(on_v2) == ["a1"]

    not_on_v2 = evaluate_query(
        "author",
        QueryGroup(operator="AND", conditions=[_cond(variable="video_ids", op=Operator.NOT_CONTAINS, value="v2")]),
        rows,
    )
    assert _author_ids(not_on_v2) == ["a2", "a3"]


def test_author_missing_values_do_not_match() -> None:
    rows = _author_rows()
    has_seen = evaluate_query(
        "author",
        QueryGroup(operator="AND", conditions=[_cond(variable="first_seen_at", op=Operator.IS_NULL)]),
        rows,
    )
    assert _author_ids(has_seen) == ["a3"]


def test_author_unknown_variable_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown variable"):
        evaluate_query(
            "author",
            QueryGroup(operator="AND", conditions=[_cond(variable="nope", op=Operator.EQ, value=1)]),
            _author_rows(),
        )