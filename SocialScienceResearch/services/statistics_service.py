"""Descriptive statistics service (ADR-0006: a single home for statistics).

Pure functions over lists of numbers - no I/O, no repositories, no estimation.
Every result returns a pydantic model that carries provenance metadata so the
research lineage is auditable:

* ``n`` - number of *usable* samples (``None`` values excluded);
* ``population_size`` - the length of the input list (including ``None``);
* ``method`` - the algorithm used to produce ``value``.

``None`` values never participate in the computation; they still count toward
``population_size`` so absence is visible, never silently dropped.

The module exposes both module-level functions (``percentile(...)``) and a
:class:`StatisticsService` facade class with ``staticmethod`` mirrors so callers
can ``from ...services.statistics_service import StatisticsService`` and use
``StatisticsService.percentile(...)`` interchangeably.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StatisticsResult(BaseModel):
    """Uniform envelope for a single descriptive-statistics value.

    ``value`` is ``None`` when the statistic is undefined for the input (empty
    sample, growth from a zero base, ...).
    """

    model_config = ConfigDict(extra="forbid")

    metric: str
    value: float | int | None = None
    n: int = 0
    population_size: int = 0
    method: str
    unit: str | None = None


class Quartiles(BaseModel):
    """25th/50th/75th percentiles (linear interpolation between ranks)."""

    model_config = ConfigDict(extra="forbid")

    q1: float | None = None
    q2: float | None = None
    q3: float | None = None
    n: int = 0
    population_size: int = 0
    method: str = "linear_interpolation"


class Quantiles(BaseModel):
    """Equal-count group partition of a sample.

    ``boundaries`` holds the ``n_groups - 1`` internal cutpoints: group 1 is
    ``value < boundaries[0]``, group ``g`` (1 < g < n) is
    ``boundaries[g-2] <= value < boundaries[g-1]`` and group ``n`` is
    ``value >= boundaries[-1]``.
    """

    model_config = ConfigDict(extra="forbid")

    n_groups: int
    boundaries: list[float] = []
    n: int = 0
    population_size: int = 0
    method: str = "equal_count"


class Outliers(BaseModel):
    """Flags (never drops) outlier values with their detection boundaries."""

    model_config = ConfigDict(extra="forbid")

    outlier_values: list[float] = []
    boundaries: dict[str, float] = {}
    n: int = 0
    population_size: int = 0
    method: str
    threshold: float | None = None


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _clean(values) -> list[float]:
    """Return the non-``None`` values as floats, preserving order."""
    return [float(v) for v in values if v is not None]


# ----------------------------------------------------------------------
# Individual statistics
# ----------------------------------------------------------------------
def percentile(values, p: float) -> float | None:
    """Linear-interpolated percentile of ``values``.

    Ranks follow ``h = (len - 1) * p / 100`` and interpolate between the
    bracketing ranks - identical to NumPy's default linear method and to the
    previous ``analytics_service._percentile`` semantics (p <= 0 yields the
    first value, p >= 100 the last, empty input yields ``None``).
    """
    vals = sorted(_clean(values))
    if not vals:
        return None
    p = max(0.0, min(100.0, float(p)))
    if p <= 0:
        return vals[0]
    if p >= 100:
        return vals[-1]
    rank = (len(vals) - 1) * p / 100.0
    low = int(rank)
    high = min(low + 1, len(vals) - 1)
    weight = rank - low
    return vals[low] * (1 - weight) + vals[high] * weight


def percentiles(values, ps: list[float]) -> dict[float, float | None]:
    """Multiple percentiles at once: ``{p: value}`` for each p in ``ps``."""
    return {float(p): percentile(values, float(p)) for p in ps}


def quartiles(values) -> Quartiles:
    """Return the first/second/third quartiles of ``values``.

    Interpolation: quartiles are the 25th/50th/75th percentiles using linear
    interpolation between closest ranks (the same rule as :func:`percentile`).
    """
    vals = _clean(values)
    return Quartiles(
        q1=percentile(vals, 25),
        q2=percentile(vals, 50),
        q3=percentile(vals, 75),
        n=len(vals),
        population_size=len(values),
        method="linear_interpolation",
    )


def quantiles(values, n: int) -> Quantiles:
    """Partition ``values`` into ``n`` equal-count groups.

    Returns the ``n - 1`` internal cutpoints (the ``100*k/n``-th percentiles).
    With fewer samples than groups some groups may be empty, documented in the
    returned :class:`Quantiles` (``n`` < ``population_size``).
    """
    n = int(n)
    if n < 1:
        raise ValueError(f"quantiles requires n >= 1, got {n}")
    vals = _clean(values)
    boundaries: list[float] = []
    if vals and n > 1:
        boundaries = [
            percentile(vals, 100.0 * k / n)  # type: ignore[list-item]
            for k in range(1, n)
        ]
    return Quantiles(
        n_groups=n,
        boundaries=boundaries,
        n=len(vals),
        population_size=len(values),
        method="equal_count",
    )


def gini(values) -> StatisticsResult:
    """Gini coefficient of ``values`` (sum/Brown's formula, handles zeros).

    ``gini([1, 1, 1]) == 0`` (perfect equality) and ``gini([0, 1]) == 0.5``.
    """
    vals = _clean(values)
    n = len(vals)
    if n == 0:
        return StatisticsResult(
            metric="gini", value=None, n=0, population_size=len(values), method="brown"
        )
    vals.sort()
    total = sum(vals)
    if total == 0:
        value = 0.0
    else:
        weighted = sum((i + 1) * v for i, v in enumerate(vals))
        value = (2.0 * weighted) / (n * total) - (n + 1.0) / n
    return StatisticsResult(
        metric="gini", value=value, n=n, population_size=len(values), method="brown"
    )


def mean(values) -> StatisticsResult:
    vals = _clean(values)
    value = sum(vals) / len(vals) if vals else None
    return StatisticsResult(
        metric="mean", value=value, n=len(vals), population_size=len(values), method="arithmetic_mean"
    )


def median(values) -> StatisticsResult:
    vals = _clean(values)
    value = percentile(vals, 50)
    return StatisticsResult(
        metric="median", value=value, n=len(vals), population_size=len(values), method="linear_50th_percentile"
    )


def variance(values) -> StatisticsResult:
    """Unbiased sample variance (``n - 1`` denominator); undefined for n < 2."""
    vals = _clean(values)
    n = len(vals)
    if n < 2:
        return StatisticsResult(
            metric="variance", value=None, n=n, population_size=len(values), method="sample_variance_n_minus_1"
        )
    m = sum(vals) / n
    value = sum((v - m) ** 2 for v in vals) / (n - 1)
    return StatisticsResult(
        metric="variance", value=value, n=n, population_size=len(values), method="sample_variance_n_minus_1"
    )


def stdev(values) -> StatisticsResult:
    result = variance(values)
    value = result.value ** 0.5 if result.value is not None else None
    return StatisticsResult(
        metric="stdev", value=value, n=result.n, population_size=result.population_size, method="sample_std_deviation"
    )


def iqr(values) -> StatisticsResult:
    q = quartiles(values)
    if q.q1 is None or q.q3 is None:
        return StatisticsResult(
            metric="iqr", value=None, n=q.n, population_size=q.population_size, method="q3_minus_q1"
        )
    return StatisticsResult(
        metric="iqr", value=q.q3 - q.q1, n=q.n, population_size=q.population_size, method="q3_minus_q1"
    )


def mad(values) -> StatisticsResult:
    """Median absolute deviation from the median (robust dispersion)."""
    vals = _clean(values)
    if not vals:
        return StatisticsResult(
            metric="mad", value=None, n=0, population_size=len(values), method="median_absolute_deviation"
        )
    centre = percentile(vals, 50)
    devs = [abs(v - centre) for v in vals]
    value = percentile(devs, 50)
    return StatisticsResult(
        metric="mad",
        value=value,
        n=len(vals),
        population_size=len(values),
        method="median_absolute_deviation",
    )


def outliers(
    values,
    method: str = "iqr",
    threshold: float = 3.0,
    k: float = 1.5,
) -> Outliers:
    """Flag (never drop) outlier values.

    ``method="iqr"`` flags values outside ``[q1 - k*iqr, q3 + k*iqr]``
    (``k=1.5`` by default). ``method="z"`` flags values whose absolute
    z-score (``|x - mean| / std``) exceeds ``threshold`` (3.0 by default).
    Flat (zero-variance) samples flag ``None`` values.
    """
    vals = _clean(values)
    n = len(vals)
    if not vals:
        return Outliers(
            outlier_values=[],
            boundaries={},
            n=0,
            population_size=len(values),
            method=method,
            threshold=threshold if method == "z" else None,
        )
    if method == "iqr":
        q = quartiles(vals)
        span = (q.q3 - q.q1) if (q.q1 is not None and q.q3 is not None) else None
        if span is None:
            low = high = None
        else:
            low = q.q1 - k * span
            high = q.q3 + k * span
        if low is None or high is None:
            flagged: list[float] = []
        else:
            flagged = [v for v in vals if v < low or v > high]
        return Outliers(
            outlier_values=flagged,
            boundaries={} if low is None else {"low": low, "high": high},
            n=n,
            population_size=len(values),
            method=method,
            threshold=None,
        )
    if method == "z":
        m = sum(vals) / n
        var = sum((v - m) ** 2 for v in vals) / n
        std = var ** 0.5
        if std == 0:
            return Outliers(
                outlier_values=[], boundaries={}, n=n, population_size=len(values),
                method=method, threshold=threshold,
            )
        flagged = [v for v in vals if abs(v - m) / std > threshold]
        return Outliers(
            outlier_values=flagged,
            boundaries={"low": m - threshold * std, "high": m + threshold * std},
            n=n,
            population_size=len(values),
            method=method,
            threshold=threshold,
        )
    raise ValueError(f"outliers method must be 'iqr' or 'z', got {method!r}")


def top_k_concentration(values, k_percent: float) -> StatisticsResult:
    """Share of the total held by the top ``k_percent``% of values.

    e.g. ``top_k_concentration([10, 20, 30, 40], 50) == 0.7`` (top 50% =
    the two largest values hold 70% of the total). Always in ``[0, 1]``.
    """
    vals = _clean(values)
    if not vals:
        return StatisticsResult(
            metric="top_k_concentration", value=None, n=0, population_size=len(values),
            method="top_k_share",
        )
    total = sum(vals)
    if total == 0:
        return StatisticsResult(
            metric="top_k_concentration", value=0.0, n=len(vals),
            population_size=len(values), method="top_k_share",
        )
    kp = max(0.0, min(100.0, float(k_percent)))
    count = max(1, min(len(vals), round(len(vals) * kp / 100.0)))
    top = sum(sorted(vals)[-count:])
    value = top / total
    return StatisticsResult(
        metric="top_k_concentration", value=value, n=len(vals),
        population_size=len(values), method="top_k_share",
    )


def ratio(numerator, denominator) -> float | None:
    """None-safe raw proportion ``numerator / denominator``.

    Returns ``None`` when the numerator is ``None`` or the denominator is
    ``None`` or zero - never raises. This is the primitive the legacy
    ``analytics_service._rate`` / ``sampling_service._ratio`` delegate to.
    """
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def rate(n, population) -> StatisticsResult:
    """Per-1000 rate ``n / population * 1000`` (decimal).

    Returns ``0.0`` when ``population`` is zero to avoid a division by zero.
    """
    pop = int(population or 0)
    count = int(n) if n is not None else 0
    if pop == 0:
        value: float | int | None = 0.0
    elif n is None:
        value = None
    else:
        value = float(n) / pop * 1000.0
    return StatisticsResult(
        metric="rate", value=value, n=count, population_size=pop, method="per_1000"
    )


def growth(current, previous) -> StatisticsResult:
    """Percent change ``(current - previous) / previous * 100``.

    Zero-base handling: ``previous == 0`` and ``current == 0`` is flat
    (``0.0``); ``previous == 0`` with a non-zero ``current`` is undefined
    (``value=None``) rather than ``inf``.
    """
    n = 2 if current is not None and previous is not None else 1
    if previous in (None, 0):
        if current in (None, 0):
            value: float | None = 0.0
        else:
            value = None
    elif current is None:
        value = None
    else:
        value = (float(current) - float(previous)) / float(previous) * 100.0
    return StatisticsResult(
        metric="growth", value=value, n=n, population_size=n, method="percent_change"
    )


def sum_values(*values) -> float | int | None:
    """Sum of ``values``; ``None`` if any input is ``None``.

    Mirrors the previous ``sampling_service._sum`` semantics exactly (an
    observation with a missing field is treated as missing, never as zero).
    """
    if any(v is None for v in values):
        return None
    return sum(values)  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# Shape / relationship statistics
# ----------------------------------------------------------------------
def _moments(values: list[float]) -> tuple[float, float, float, float, int]:
    """Return ``(n, mean, m2, m3, m4)`` central moments (population denominators)."""
    n = len(values)
    if n == 0:
        return 0, 0.0, 0.0, 0.0, 0.0
    mean = sum(values) / n
    m2 = sum((v - mean) ** 2 for v in values) / n
    m3 = sum((v - mean) ** 3 for v in values) / n
    m4 = sum((v - mean) ** 4 for v in values) / n
    return n, mean, m2, m3, m4


def skewness(values) -> StatisticsResult:
    """Adjusted Fisher-Pearson standardized moment coefficient ``G1``.

    Undefined (``value=None``) for fewer than 3 usable samples or when variance
    is zero (a flat sample has no skew to measure).
    """
    vals = _clean(values)
    n = len(vals)
    if n < 3:
        return StatisticsResult(
            metric="skewness", value=None, n=n, population_size=len(values),
            method="adjusted_fisher_pearson_g1",
        )
    _, mean, m2, m3, _ = _moments(vals)
    if m2 == 0:
        return StatisticsResult(
            metric="skewness", value=None, n=n, population_size=len(values),
            method="adjusted_fisher_pearson_g1",
        )
    g1 = m3 / (m2 ** 1.5)
    value = ((n * (n - 1)) ** 0.5 / (n - 2)) * g1
    return StatisticsResult(
        metric="skewness", value=value, n=n, population_size=len(values),
        method="adjusted_fisher_pearson_g1",
    )


def kurtosis(values) -> StatisticsResult:
    """Excess kurtosis (Fisher's ``G2``); normal distribution -> ~0.

    Undefined (``value=None``) for fewer than 4 usable samples or zero variance.
    """
    vals = _clean(values)
    n = len(vals)
    if n < 4:
        return StatisticsResult(
            metric="kurtosis", value=None, n=n, population_size=len(values),
            method="excess_kurtosis_g2",
        )
    _, mean, m2, _, m4 = _moments(vals)
    if m2 == 0:
        return StatisticsResult(
            metric="kurtosis", value=None, n=n, population_size=len(values),
            method="excess_kurtosis_g2",
        )
    g2 = m4 / (m2 ** 2) - 3.0
    value = ((n + 1) * g2 + 6.0) * (n - 1) / ((n - 2) * (n - 3))
    return StatisticsResult(
        metric="kurtosis", value=value, n=n, population_size=len(values),
        method="excess_kurtosis_g2",
    )


def _paired(values_x, values_y) -> tuple[list[float], list[float]]:
    """Keep only index-aligned pairs where both entries are non-``None``."""
    out_x: list[float] = []
    out_y: list[float] = []
    for x, y in zip(values_x, values_y):
        if x is None or y is None:
            continue
        out_x.append(float(x))
        out_y.append(float(y))
    return out_x, out_y


def _ranks(values: list[float]) -> list[float]:
    """Average (fractional) ranks for a list of values (ties share the mean rank)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # 1-based, average of the tied block
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def pearson(values_x, values_y) -> StatisticsResult:
    """Pearson product-moment correlation coefficient ``r``.

    Undefined (``value=None``) when there are fewer than 2 usable paired
    samples or either variable has zero variance.
    """
    xs, ys = _paired(values_x, values_y)
    n = len(xs)
    if n < 2:
        return StatisticsResult(
            metric="pearson", value=None, n=n, population_size=len(values_x),
            method="pearson_r",
        )
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0 or syy == 0:
        return StatisticsResult(
            metric="pearson", value=None, n=n, population_size=len(values_x),
            method="pearson_r",
        )
    return StatisticsResult(
        metric="pearson", value=sxy / ((sxx * syy) ** 0.5), n=n,
        population_size=len(values_x), method="pearson_r",
    )


def spearman(values_x, values_y) -> StatisticsResult:
    """Spearman rank correlation: Pearson's ``r`` computed on ranks."""
    xs, ys = _paired(values_x, values_y)
    if len(xs) < 2:
        return StatisticsResult(
            metric="spearman", value=None, n=len(xs), population_size=len(values_x),
            method="spearman_rho",
        )
    return StatisticsResult(
        metric="spearman", value=pearson(_ranks(xs), _ranks(ys)).value,
        n=len(xs), population_size=len(values_x), method="spearman_rho",
    )


class HistogramBin(BaseModel):
    """A single adaptive histogram bin (left-inclusive, right-exclusive)."""

    model_config = ConfigDict(extra="forbid")

    left: float
    right: float
    count: int


class HistogramResult(BaseModel):
    """Equal-width histogram resilient to outliers, multimodality and nulls.

    ``None`` values are excluded from the bins but counted in ``population_size``
    (absence is visible). With a single distinct value the bin spans that value
    (width 0) so the count is never lost; with no usable data the bin list is
    empty rather than raising.
    """

    model_config = ConfigDict(extra="forbid")

    metric: str = "histogram"
    bins: list[HistogramBin] = []
    n: int = 0
    population_size: int = 0
    method: str = "equal_width_adaptive"
    bin_count: int | None = None


def histogram(values, bins: int | None = None) -> HistogramResult:
    """Adaptive equal-width histogram.

    ``bins`` defaults to ``max(1, round(sqrt(n)))`` (Sturges-ish floor). Extreme
    outliers fall into the end bins (no exception); multimodal and single-valued
    inputs are handled; ``None``/empty inputs yield an empty bin list.
    """
    vals = _clean(values)
    n = len(vals)
    if n == 0:
        return HistogramResult(n=0, population_size=len(values))
    if bins is None:
        bins = max(1, round(n ** 0.5))
    lo = min(vals)
    hi = max(vals)
    if hi == lo:
        return HistogramResult(
            bins=[HistogramBin(left=lo, right=hi, count=n)],
            n=n, population_size=len(values), bin_count=1,
        )
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in vals:
        idx = int((v - lo) / width)
        if idx >= bins:  # v == hi lands in the last bin
            idx = bins - 1
        counts[idx] += 1
    bin_objs = [
        HistogramBin(left=lo + i * width, right=lo + (i + 1) * width, count=counts[i])
        for i in range(bins)
    ]
    return HistogramResult(
        bins=bin_objs, n=n, population_size=len(values), bin_count=bins
    )


# ----------------------------------------------------------------------
# Facade class (staticmethod mirrors of the module functions)
# ----------------------------------------------------------------------
class StatisticsService:
    """Stateless facade over the module-level descriptive-statistics functions."""

    percentile = staticmethod(percentile)
    percentiles = staticmethod(percentiles)
    quartiles = staticmethod(quartiles)
    quantiles = staticmethod(quantiles)
    gini = staticmethod(gini)
    mean = staticmethod(mean)
    median = staticmethod(median)
    variance = staticmethod(variance)
    stdev = staticmethod(stdev)
    iqr = staticmethod(iqr)
    mad = staticmethod(mad)
    outliers = staticmethod(outliers)
    top_k_concentration = staticmethod(top_k_concentration)
    ratio = staticmethod(ratio)
    rate = staticmethod(rate)
    growth = staticmethod(growth)
    sum_values = staticmethod(sum_values)
    skewness = staticmethod(skewness)
    kurtosis = staticmethod(kurtosis)
    pearson = staticmethod(pearson)
    spearman = staticmethod(spearman)
    histogram = staticmethod(histogram)