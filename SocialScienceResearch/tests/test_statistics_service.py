"""Tests for the StatisticsService (ADR-0006 descriptive statistics).

Covers known distributions and edge cases: linear-interpolation percentiles,
quartiles, quantiles, Gini, dispersion (variance/stdev/iqr/mad), outlier
flagging (IQR and z), per-1000 rates, zero-base growth, top-k concentration
and the provenance metadata on every result.
"""

from __future__ import annotations

import math

import numpy as np


import pytest

from SocialScienceResearch.services.statistics_service import (
    StatisticsService,
    gini,
    growth,
    iqr,
    mad,
    mean,
    median,
    outliers,
    percentile,
    percentiles,
    quantiles,
    quartiles,
    rate,
    ratio,
    sum_values,
    stdev,
    top_k_concentration,
    variance,
)


# ----------------------------------------------------------------------
# Percentiles / quartiles / quantiles
# ----------------------------------------------------------------------
def test_percentile_linear_interpolation_on_uniform() -> None:
    values = list(range(101))  # 0..100
    assert StatisticsService.percentile(values, 50) == pytest.approx(50.0)
    assert StatisticsService.percentile(values, 25) == pytest.approx(25.0)
    assert StatisticsService.percentile(values, 75) == pytest.approx(75.0)
    assert percentile(values, 99) == pytest.approx(99.0)


def test_percentile_edges_and_empty() -> None:
    values = [10, 20, 30]
    assert percentile(values, 0) == pytest.approx(10.0)
    assert percentile(values, 100) == pytest.approx(30.0)
    assert percentile([], 50) is None


def test_percentile_ignores_none_and_preserves_linear_semantics() -> None:
    # None values never participate; p=50 of [0, None, 100] is 50.
    assert percentile([0, None, 100], 50) == pytest.approx(50.0)
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 75) == pytest.approx(7.75)


def test_percentiles_returns_mapping() -> None:
    result = percentiles(list(range(101)), [10, 90])
    assert result[10.0] == pytest.approx(10.0)
    assert result[90.0] == pytest.approx(90.0)


def test_quartiles_uniform_distribution() -> None:
    q = quartiles(list(range(101)))
    assert q.q1 == pytest.approx(25.0)
    assert q.q2 == pytest.approx(50.0)
    assert q.q3 == pytest.approx(75.0)
    assert q.method == "linear_interpolation"


def test_quartiles_documented_interpolation() -> None:
    # 10 values 1..10: P25 = 3.25, P50 = 5.5, P75 = 7.75.
    q = StatisticsService.quartiles(list(range(1, 11)))
    assert q.q1 == pytest.approx(3.25)
    assert q.q2 == pytest.approx(5.5)
    assert q.q3 == pytest.approx(7.75)


def test_quartiles_metadata_provenance() -> None:
    q = quartiles([1, None, 2, 3])
    assert q.n == 3
    assert q.population_size == 4


def test_quartiles_empty() -> None:
    q = quartiles([])
    assert q.q1 is None and q.q2 is None and q.q3 is None
    assert q.n == 0


def test_quantiles_equal_count_boundaries() -> None:
    q = quantiles(list(range(10)), 5)
    assert q.n_groups == 5
    assert len(q.boundaries) == 4
    assert q.boundaries == pytest.approx([1.8, 3.6, 5.4, 7.2])
    assert q.method == "equal_count"


def test_quantiles_invalid_n_raises() -> None:
    with pytest.raises(ValueError):
        quantiles([1, 2, 3], 0)


def test_quantiles_single_group() -> None:
    q = quantiles([1, 2, 3], 1)
    assert q.boundaries == []


# ----------------------------------------------------------------------
# Gini
# ----------------------------------------------------------------------
def test_gini_perfect_equality_is_zero() -> None:
    assert StatisticsService.gini([1, 1, 1]).value == pytest.approx(0.0)


def test_gini_two_value_gradient() -> None:
    assert StatisticsService.gini([0, 1]).value == pytest.approx(0.5)


def test_gini_handles_zero_total() -> None:
    assert StatisticsService.gini([0, 0, 0]).value == pytest.approx(0.0)


def test_gini_empty_is_undefined() -> None:
    assert gini([]).value is None


def test_gini_metadata() -> None:
    result = StatisticsService.gini([1, 2, 3])
    assert result.metric == "gini"
    assert result.n == 3
    assert result.method == "brown"


# ----------------------------------------------------------------------
# Central tendency / dispersion
# ----------------------------------------------------------------------
def test_mean_and_median() -> None:
    values = [2, 4, 4, 4, 5, 5, 7, 9]
    assert mean(values).value == pytest.approx(5.0)
    assert median(values).value == pytest.approx(4.5)


def test_variance_stdev_sample_definition() -> None:
    values = [2, 4, 4, 4, 5, 5, 7, 9]
    variance_result = variance(values)
    assert variance_result.method == "sample_variance_n_minus_1"
    assert variance_result.value == pytest.approx(32.0 / 7.0)
    assert stdev(values).value == pytest.approx(math.sqrt(32.0 / 7.0))


def test_variance_undefined_for_single_value() -> None:
    assert variance([5]).value is None


def test_iqr_and_mad() -> None:
    assert StatisticsService.iqr([1, 2, 3, 4, 5]).value == pytest.approx(2.0)
    assert StatisticsService.mad([1, 2, 3, 4, 5]).value == pytest.approx(1.0)


def test_mad_empty() -> None:
    assert mad([]).value is None


# ----------------------------------------------------------------------
# Outliers (flag, never drop)
# ----------------------------------------------------------------------
def test_outliers_iqr_flags_isolated_extreme() -> None:
    result = StatisticsService.outliers([1, 2, 3, 4, 5, 100], method="iqr")
    assert 100.0 in result.outlier_values
    assert all(v not in result.outlier_values for v in (1, 2, 3, 4, 5))
    # k=1.5 default: boundaries = q1-1.5*iqr .. q3+1.5*iqr.
    assert set(result.boundaries) == {"low", "high"}
    assert result.boundaries["low"] < 1.0
    assert result.boundaries["high"] < 100.0


def test_outliers_iqr_no_outliers() -> None:
    result = outliers([1, 2, 3, 4, 5], method="iqr")
    assert result.outlier_values == []


def test_outliers_z_flags_beyond_threshold() -> None:
    cluster = [i / 10.0 for i in range(-20, 21)]
    values = cluster + [100.0]
    result = StatisticsService.outliers(values, method="z", threshold=3.0)
    assert 100.0 in result.outlier_values
    assert 2.0 not in result.outlier_values
    assert set(result.boundaries) == {"low", "high"}
    assert result.threshold == 3.0


def test_outliers_z_flat_sample_flags_nothing() -> None:
    result = outliers([5, 5, 5, 5], method="z")
    assert result.outlier_values == []


def test_outliers_invalid_method_raises() -> None:
    with pytest.raises(ValueError):
        outliers([1, 2, 3], method="bogus")


# ----------------------------------------------------------------------
# Rates / growth
# ----------------------------------------------------------------------
def test_rate_per_1000() -> None:
    assert StatisticsService.rate(50, 100_000).value == pytest.approx(0.5)
    assert StatisticsService.rate(5, 1000).value == pytest.approx(5.0)


def test_rate_zero_population_safe() -> None:
    result = StatisticsService.rate(5, 0)
    assert result.value == pytest.approx(0.0)
    assert result.population_size == 0


def test_growth_percent_change() -> None:
    assert StatisticsService.growth(120, 100).value == pytest.approx(20.0)
    assert StatisticsService.growth(100, 100).value == pytest.approx(0.0)


def test_growth_zero_base_handling() -> None:
    assert StatisticsService.growth(0, 0).value == pytest.approx(0.0)
    assert growth(5, 0).value is None  # undefined, no division by zero


# ----------------------------------------------------------------------
# Top-k concentration
# ----------------------------------------------------------------------
def test_top_k_concentration_uniform() -> None:
    # [10,20,30,40]: top 50% (largest two) hold 70% of the total.
    result = StatisticsService.top_k_concentration([10, 20, 30, 40], 50)
    assert result.value == pytest.approx(0.7)
    assert 0.0 <= result.value <= 1.0


def test_top_k_concentration_bounds() -> None:
    assert top_k_concentration([10, 20, 30, 40], 100).value == pytest.approx(1.0)
    assert top_k_concentration([10, 20, 30, 40], 0).value == pytest.approx(
        (40.0) / 100.0
    )


def test_top_k_concentration_empty() -> None:
    assert top_k_concentration([], 50).value is None


# ----------------------------------------------------------------------
# Migrated helpers keep identical behaviour
# ----------------------------------------------------------------------
def test_ratio_primitives() -> None:
    assert ratio(5, 2) == pytest.approx(2.5)
    assert ratio(None, 2) is None
    assert ratio(5, 0) is None
    assert ratio(5, None) is None


def test_sum_values_returns_none_on_missing() -> None:
    assert sum_values(1, 2, 3) == 6
    assert sum_values(1, None, 3) is None
    assert sum_values() == 0


def test_metadata_carried_on_results() -> None:
    result = StatisticsService.mean([1, None, 3])
    assert result.value == pytest.approx(2.0)
    assert result.n == 2
    assert result.population_size == 3
    assert result.method == "arithmetic_mean"


# ----------------------------------------------------------------------
# Shape / relationship statistics (skewness, kurtosis, correlation, histogram)
# ----------------------------------------------------------------------
def test_skewness_symmetric_is_zero() -> None:
    assert StatisticsService.skewness([1, 2, 3, 4, 5]).value == pytest.approx(0.0, abs=1e-9)


def test_skewness_right_tailed_positive() -> None:
    assert StatisticsService.skewness([1, 1, 1, 1, 100]).value > 0.5


def test_skewness_undefined_for_n_lt_3() -> None:
    assert StatisticsService.skewness([1, 2]).value is None
    assert StatisticsService.skewness([]).value is None


def test_kurtosis_heavy_tailed_exceeds_flat() -> None:
    # A single extreme outlier gives a heavy right tail (positive excess kurtosis);
    # a uniform sample is platykurtic (negative excess kurtosis).
    heavy = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]
    flat = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert StatisticsService.kurtosis(heavy).value > StatisticsService.kurtosis(flat).value


def test_kurtosis_undefined_for_n_lt_4() -> None:
    assert StatisticsService.kurtosis([1, 2, 3]).value is None


def test_pearson_perfect_positive_and_negative() -> None:
    assert StatisticsService.pearson([1, 2, 3, 4], [2, 4, 6, 8]).value == pytest.approx(1.0)
    assert StatisticsService.pearson([1, 2, 3, 4], [4, 3, 2, 1]).value == pytest.approx(-1.0)


def test_pearson_zero_variance_undefined() -> None:
    assert StatisticsService.pearson([1, 1, 1, 1], [1, 2, 3, 4]).value is None
    assert StatisticsService.pearson([1], [2]).value is None


def test_spearman_monotonic_is_one() -> None:
    # Perfectly monotonic (non-linear) -> Spearman rho == 1.
    assert StatisticsService.spearman([1, 2, 3, 4, 5], [1, 4, 9, 16, 25]).value == pytest.approx(1.0)


def test_spearman_matches_pearson_on_ranks() -> None:
    # Spearman rho must equal Pearson r computed over the integer ranks.
    xs = [10, 20, 30, 40]
    ys = [3, 1, 4, 2]
    # Ranks (1-based, ties averaged): xs -> [1,2,3,4]; ys -> [3,1,4,2].
    assert StatisticsService.spearman(xs, ys).value == pytest.approx(
        StatisticsService.pearson([1, 2, 3, 4], [3, 1, 4, 2]).value
    )


def test_spearman_against_linear_reference() -> None:
    # Spearman rho must equal Pearson r computed over the integer ranks.
    xs = [1, 2, 3, 4]
    ys = [4, 3, 2, 1]  # perfect inverse rank correlation -> -1
    assert StatisticsService.spearman(xs, ys).value == pytest.approx(-1.0)


def test_shape_statistics_match_scipy_benchmark() -> None:
    """Cross-check skewness/kurtosis/Pearson/Spearman against SciPy (verified)."""
    np.random.seed(0)
    x = (np.random.randn(200) * 10 + 50).tolist()
    y = (np.arange(200) * 2.0 + np.random.randn(200) * 5).tolist()
    from scipy import stats

    assert StatisticsService.skewness(x).value == pytest.approx(
        stats.skew(x, bias=False), rel=1e-9
    )
    assert StatisticsService.kurtosis(x).value == pytest.approx(
        stats.kurtosis(x, fisher=True, bias=False), rel=1e-9
    )
    assert StatisticsService.pearson(x, y).value == pytest.approx(
        stats.pearsonr(x, y).statistic, rel=1e-9
    )
    assert StatisticsService.spearman(x, y).value == pytest.approx(
        stats.spearmanr(x, y).statistic, rel=1e-9
    )


def test_histogram_counts_sum_to_n() -> None:
    result = StatisticsService.histogram([1, 2, 3, 4, 5], bins=5)
    assert sum(b.count for b in result.bins) == 5
    assert result.bin_count == 5


def test_histogram_excludes_nulls_but_counts_population() -> None:
    result = StatisticsService.histogram([1, None, 3, 4, 5])
    assert result.n == 4
    assert result.population_size == 5
    assert sum(b.count for b in result.bins) == 4


def test_histogram_single_value_one_bin() -> None:
    result = StatisticsService.histogram([7, 7, 7])
    assert len(result.bins) == 1
    assert result.bins[0].count == 3


def test_histogram_outliers_do_not_raise() -> None:
    result = StatisticsService.histogram([0, 0, 0, 0, 0, 100000])
    assert sum(b.count for b in result.bins) == 6


def test_histogram_empty_is_safe() -> None:
    result = StatisticsService.histogram([])
    assert result.bins == []
    assert result.population_size == 0