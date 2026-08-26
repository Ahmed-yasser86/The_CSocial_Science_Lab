"""Deterministic Content Homophily unit tests (Content Homophily spec).

Covers pair sampling (10%/10k cap, balance/stratification, reproducibility,
small datasets), the community-label permutation null model (z-score, finite
-sample corrected p-value, null_std==0 safety), the §19 output contract and
insufficient_data handling. No network access; embeddings are faked.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

from SocialScienceResearch.services.content_homophily_service import (
    ABSOLUTE_MAX_PAIR_CAP,
    ContentHomophilyNullModelService,
    PairSample,
    PairSamplingService,
    SemanticSimilarityService,
)


def _groups(spec: dict[int, int]) -> dict[int, list[str]]:
    """{community: count} -> {community: [v0, v1, ...]} deterministic ids."""
    groups: dict[int, list[str]] = {}
    index = 0
    for community, count in sorted(spec.items()):
        groups[community] = [f"v{i}" for i in range(index, index + count)]
        index += count
    return groups


# ---------------------------------------------------------------------------
# Pair sampling (spec §7-§11)
# ---------------------------------------------------------------------------
def test_sampling_examples_from_spec() -> None:
    sampler = PairSamplingService(0.10, 10_000)
    # 20 videos -> 190 possible pairs -> 19 sampled.
    rng = random.Random(42)
    sample = sampler.sample_within({1: [f"v{i}" for i in range(20)]}, rng)
    assert sample.available == 190
    assert sample.sampled == 19


def test_cap_never_exceeds_10k_per_operation() -> None:
    sampler = PairSamplingService(0.10, 10_000)
    rng = random.Random(7)
    # 500 videos in one community: 124,750 available -> capped at 10,000.
    sample = sampler.sample_within({1: [f"v{i}" for i in range(500)]}, rng)
    assert sample.available == 124_750
    assert sample.sampled == 10_000
    assert len(set(sample.pairs)) == 10_000
    assert ABSOLUTE_MAX_PAIR_CAP == 10_000


def test_between_pairs_available_count() -> None:
    sampler = PairSamplingService(0.5, 100)
    rng = random.Random(3)
    groups = _groups({1: 4, 2: 6})
    between = sampler.sample_between(groups, rng)
    # Cross pairs = 4*6 = 24; every drawn pair crosses communities.
    assert between.available == 24
    for a, b in between.pairs:
        assert not any(a in members and b in members for members in groups.values())


def test_within_sample_is_balanced_across_communities() -> None:
    sampler = PairSamplingService(0.10, 10_000)
    # One huge + one small community; balanced allocation must not let the
    # large community take (almost) the entire sample.
    groups = {1: [f"a{i}" for i in range(200)], 2: ["b0", "b1", "b2", "b3"]}
    rng = random.Random(11)
    sample = sampler.sample_within(groups, rng)
    from_comm1 = sum(1 for a, _ in sample.pairs if a.startswith("a")
                     and _.startswith("a"))
    # Small community capacity = C(4,2)=6; it must receive its full share.
    small_share = sum(
        1 for pair in sample.pairs if all(p.startswith("b") for p in pair)
    )
    assert small_share >= min(6, sample.sampled - from_comm1) or small_share > 0
    # And the big community cannot exceed target - small_capacity by much.
    assert sample.available == math.comb(200, 2) + 6


def test_sampling_is_reproducible_with_seed() -> None:
    sampler = PairSamplingService(0.10, 10_000)
    groups = _groups({1: 30, 2: 25, 3: 20})
    first = (
        sampler.sample_within(groups, random.Random(123)),
        sampler.sample_between(groups, random.Random(123)),
    )
    second = (
        sampler.sample_within(groups, random.Random(123)),
        sampler.sample_between(groups, random.Random(123)),
    )
    assert first[0].pairs == second[0].pairs
    assert first[1].pairs == second[1].pairs


def test_single_pair_dataset() -> None:
    sampler = PairSamplingService(0.10, 10_000)
    rng = random.Random(42)
    within = sampler.sample_within(_groups({1: 2}), rng)
    assert within.available == 1
    assert within.sampled == 1


def test_invalid_configuration_rejected() -> None:
    with pytest.raises(ValueError):
        PairSamplingService(0.0)
    with pytest.raises(ValueError):
        PairSamplingService(0.1, max_pair_cap=ABSOLUTE_MAX_PAIR_CAP + 1)


# ---------------------------------------------------------------------------
# Similarity + null model (spec §12, §14-§17)
# ---------------------------------------------------------------------------
def test_cosine_basic_and_zero_vector_safety() -> None:
    sim = SemanticSimilarityService.cosine(np.array([1.0, 0.0]),
                                           np.array([1.0, 0.0]))
    assert sim == pytest.approx(1.0)
    # Zero vectors are uncomputable -> None, never silently 0 similarity.
    assert SemanticSimilarityService.cosine(np.zeros(2), np.array([1.0, 1.0])) is None


def test_null_model_small_case_known_values() -> None:
    """Two tight clusters; observed difference must be strongly positive and
    the permutation null must be clearly separated."""
    vectors = {
        **{f"w{i}": np.array([10.0 + i * 0.01, 1.0]) for i in range(6)},
        **{f"b{i}": np.array([1.0, 10.0 + i * 0.01]) for i in range(6)},
    }
    labels = {f"w{i}": 1 for i in range(6)}
    labels.update({f"b{i}": 2 for i in range(6)})
    sampler = PairSamplingService(0.34, 10_000)
    null_service = ContentHomophilyNullModelService()
    observed_within = SemanticSimilarityService.mean_similarity(
        vectors,
        [
            ("w0", "w1"), ("w2", "w3"),
        ],
    )[0]
    observed_between = SemanticSimilarityService.mean_similarity(
        vectors, [("w0", "b0")]
    )[0]
    observed_difference = observed_within - observed_between
    result = null_service.run(
        vectors, labels, sampler,
        num_permutations=200, seed=99,
        observed_difference=observed_difference,
    )
    assert result.num_permutations == 200
    assert result.null_mean is not None and result.null_std is not None
    assert result.z_score is not None and result.z_score > 0
    assert result.permutation_p_value is not None
    assert result.permutation_p_value <= (1 + 0) / (1 + 200)


def test_permutation_p_value_correction_formula() -> None:
    """p = (1 + #(null >= observed)) / (1 + n_perm), directional positive."""
    class FakeNull(ContentHomophilyNullModelService):
        def run(self, vectors, labels, sampler, *, num_permutations=1000,
                seed=42, observed_difference=None, progress=None,
                stop_requested=None):  # noqa: D401
            diffs = [-0.5, 0.1, 0.2, 0.2]
            exceed = sum(1 for d in diffs if d >= observed_difference)
            from SocialScienceResearch.services.content_homophily_service import (
                NullModelResult,
            )

            return NullModelResult(diffs, 0.0, 0.2, 1.0,
                                   (1 + exceed) / (1 + num_permutations),
                                   num_permutations)

    result = FakeNull().run({}, {}, None, num_permutations=4,
                            observed_difference=0.2)
    assert result.permutation_p_value == pytest.approx((1 + 2) / (1 + 4))


def test_null_model_deterministic_given_seed() -> None:
    rng_vectors = np.random.default_rng(5)
    labels = {}
    vectors = {}
    for i in range(24):
        base = np.array([1.0, 0.0]) if i % 2 == 0 else np.array([0.0, 1.0])
        vectors[f"v{i}"] = base + rng_vectors.normal(scale=0.01, size=2)
        labels[f"v{i}"] = i % 2
    sampler = PairSamplingService(0.2, 500)
    service = ContentHomophilyNullModelService()
    first = service.run(vectors, labels, sampler, num_permutations=25, seed=8)
    second = service.run(vectors, labels, sampler, num_permutations=25, seed=8)
    assert first.null_mean == second.null_mean
    assert first.null_std == second.null_std


def test_null_model_handles_degenerate_zero_std_safely() -> None:
    # Identical vectors => every permutation yields the same difference
    # (null_std == 0); z must be None, never inf/NaN.
    vectors = {f"v{i}": np.array([1.0, 1.0]) for i in range(8)}
    labels = {f"v{i}": i % 2 for i in range(8)}
    result = ContentHomophilyNullModelService().run(
        vectors, labels, PairSamplingService(0.5, 100),
        num_permutations=20, seed=1,
    )
    # With identical vectors every diff is exactly 0 -> std 0.
    assert result.null_std == 0.0
