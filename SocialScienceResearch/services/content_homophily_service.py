"""Content Homophily analysis (Content Homophily spec, authoritative).

An independent, opt-in, on-demand CONTENT evidence layer for ANY supported
recommendation network:

    NETWORK  (conductance/modularity/WCR/...)     <- structural layer
    CONTENT  (within/between semantic similarity,
              permutation null, z + p)            <- THIS module
    AUDIENCE (commenter Jaccard)                  <- audience layer
    CHANNEL  (HHI/top share)                      <- channel layer

The layers are never merged into a composite score. This module answers:

    Are videos inside recommendation-network communities more semantically
    similar than videos across communities, and is that difference
    statistically supported?

Pipeline (spec §2): eligible videos -> community samples -> TARGETED
transcript collection -> reuse/generate embeddings -> seeded 10%/10k-cap pair
sampling -> cosine similarities -> community-label permutation null ->
z-score + corrected permutation p-value.

Reuses the existing Ingestion_Pipline abstractions (``split_text`` chunking +
``build_embeddings`` embedding model) - no second chunking/embedding system.
Transcript collection is targeted (sampled videos only) and happens ONLY
because the researcher explicitly requested this analysis; the default
collection pipeline never fetches transcripts.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

import numpy as np

from SocialScienceResearch.concurrency.budget_controller import (
    BudgetController,
    run_context,
)
from SocialScienceResearch.domain.enums import TranscriptStatus
from SocialScienceResearch.domain.models import TranscriptRecord
from SocialScienceResearch.utils.idgen import new_id, utcnow
from SocialScienceResearch.utils.logger import get_logger

from SocialScienceResearch.config.settings import (
    CONTENT_HOMOPHILY_EMBED_MAX_TOKENS_PER_MINUTE,
    CONTENT_HOMOPHILY_EMBED_MAX_RETRIES,
)

# Project-specific embedding TOKEN gate (SocialScienceResearch only). Request
# pacing is handled globally on the shared Gemini embedder (see
# Ingestion_Pipline.infra.embeddings) because the free-tier request quota is
# shared across the whole project; a per-caller limiter cannot prevent the
# shared 429. Ingestion keeps its own (separate, higher) TokenRateLimiter.
_css_embed_token_limiter = None
if CONTENT_HOMOPHILY_EMBED_MAX_TOKENS_PER_MINUTE and CONTENT_HOMOPHILY_EMBED_MAX_TOKENS_PER_MINUTE > 0:
    from Ingestion_Pipline.infra.rate_limiter import TokenRateLimiter

    _css_embed_token_limiter = TokenRateLimiter(
        max_tokens_per_minute=CONTENT_HOMOPHILY_EMBED_MAX_TOKENS_PER_MINUTE
    )

logger = get_logger(__name__)

#: Computational sampling policy defaults (spec §7). These bound COST; they do
#: NOT claim that 10% sampling is statistically representative.
DEFAULT_SAMPLING_FRACTION = 0.10
DEFAULT_MAX_PAIR_CAP = 10_000
#: Hard ceiling on sampled pairs per pair-selection operation (spec §7).
ABSOLUTE_MAX_PAIR_CAP = 10_000
#: Default permutation count for the community-label null model (spec §14).
DEFAULT_NUM_PERMUTATIONS = 1_000
#: Cap on analyzed videos per community (replacement-sampling limit, spec §3).
DEFAULT_MAX_VIDEOS_PER_COMMUNITY = 40
#: Hard cap on UNIQUE videos for transcript/embedding collection in ONE
#: Content Homophily analysis. Transcript fetching is the dominant, rate-limited
#: cost (YouTube 429s), so we bound it independently of the pair count: the
#: bounded-pair selection step never targets more than this many distinct videos
#: for collection. Default 200 (researcher-configurable per request).
DEFAULT_MAX_TRANSCRIPT_VIDEOS = 200
#: Absolute ceiling for the per-analysis transcript-video cap (defense).
ABSOLUTE_MAX_TRANSCRIPT_VIDEOS = 2000
#: Replacement-sampling bounds (spec §3): keep the target usable sample by
#: swapping unavailable videos for same-community peers. Bounded so we never
#: scrape an entire community hunting for replacements.
REPLACEMENT_TRIES_PER_VIDEO = 5
MAX_REPLACEMENT_SWEEPS = 4
REPLACEMENT_BUDGET_MIN = 20
#: Community detection reused from NetworkAnalyticsService (seeded louvain).
COMMUNITY_ALGORITHM = "louvain_communities(seed=42)"

#: Verbatim research disclaimers served with every result payload.
CONTENT_HOMOPHILY_DISCLAIMERS = [
    "Content homophily is evidence about observed content structure only. It "
    "is not proof of an echo chamber, causality, user beliefs, psychological "
    "effects, or polarization caused by YouTube.",
    "The sampling fraction and pair cap are computational configurations, "
    "not a claim that the sampled pairs are statistically representative.",
    "Statistical significance is not substantive importance; interpret the "
    "observed difference alongside transcript coverage and effect size.",
]

STAGES = [
    "dataset_preparation",
    "transcript_collection",
    "embedding_preparation",
    "pair_sampling",
    "similarity_calculation",
    "observed_difference",
    "null_model",
    "statistical_summary",
    "results",
]


# ---------------------------------------------------------------------------
# Pair sampling (spec §7-§11): deterministic, balanced, stratified, capped
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PairSample:
    """Outcome of one pair-selection operation."""

    pairs: list[tuple[str, str]] = field(default_factory=list)
    available: int = 0
    sampled: int = 0


class PairSamplingService:
    """Seeded, dynamic, balanced/stratified pair sampler.

    * target sample size = min(available_pairs * fraction, cap)
    * within-community draws are balanced across communities so one very
      large community cannot dominate the sample (spec §9)
    * between-community draws are stratified by community pair (spec §10)
    * identical inputs (communities/members/config/seed) yield identical pairs
    """

    def __init__(
        self,
        sampling_fraction: float = DEFAULT_SAMPLING_FRACTION,
        max_pair_cap: int = DEFAULT_MAX_PAIR_CAP,
    ) -> None:
        if not 0 < sampling_fraction <= 1:
            raise ValueError("sampling_fraction must be in (0, 1]")
        if not 1 <= max_pair_cap <= ABSOLUTE_MAX_PAIR_CAP:
            raise ValueError(
                f"max_pair_cap must be between 1 and {ABSOLUTE_MAX_PAIR_CAP}"
            )
        self.sampling_fraction = sampling_fraction
        self.max_pair_cap = max_pair_cap

    def _target(self, available: int) -> int:
        """Spec §7 fraction/cap policy; spec §8 keeps a minimum of ONE pair
        whenever any pair exists (a single available pair is sampled)."""
        target = min(int(available * self.sampling_fraction), self.max_pair_cap)
        if available >= 1:
            target = max(target, 1)
        return min(target, available)

    @staticmethod
    def _allocate_balanced(avails: list[int], total: int) -> list[int]:
        """Distribute ``total`` samples across strata as evenly as capacities
        allow (deterministic; spare capacity is redistributed)."""
        alloc = [0] * len(avails)
        remaining = total
        active = {i for i, a in enumerate(avails) if a > 0}
        while remaining > 0 and active:
            share = max(1, remaining // len(active))
            progressed = False
            for i in sorted(active):
                if remaining <= 0:
                    break
                take = min(share, avails[i] - alloc[i], remaining)
                if take > 0:
                    alloc[i] += take
                    remaining -= take
                    progressed = True
                if alloc[i] >= avails[i]:
                    active.discard(i)
            if not progressed:
                break
        return alloc

    @staticmethod
    def _draw(
        rng: random.Random,
        k: int,
        available: int,
        generator: Callable[[], Iterator[tuple[str, str]]],
    ) -> list[tuple[str, str]]:
        """Draw ``k`` distinct pairs without materializing huge spaces.

        Small spaces (relative to k, or bounded absolutely) are enumerated and
        sampled directly; large ones use rejection sampling - safe because k
        never exceeds the 10k cap.
        """
        if k <= 0 or available <= 0:
            return []
        stream = generator()
        if available <= max(4 * k, 50_000):
            pool = sorted(dict.fromkeys(stream))
            return rng.sample(pool, min(k, len(pool)))
        picked: set[tuple[str, str]] = set()
        attempts = 0
        limit = k * 50 + 100
        while len(picked) < k and attempts < limit:
            picked.add(next(stream))
            attempts += 1
        return sorted(picked)

    def sample_within(
        self, members_by_community: dict[Any, list[str]], rng: random.Random
    ) -> PairSample:
        """Balanced within-community sample (community(A)==community(B))."""
        comms = sorted(members_by_community, key=str)
        availabilities = [
            math.comb(len(sorted(set(members_by_community[c]))), 2) for c in comms
        ]
        available = sum(availabilities)
        alloc = self._allocate_balanced(availabilities, self._target(available))
        pairs: list[tuple[str, str]] = []

        def _pair_iter(members: list[str]) -> Iterator[tuple[str, str]]:
            n = len(members)
            for i in range(n):
                for j in range(i + 1, n):
                    yield (members[i], members[j])

        for comm, k in zip(comms, alloc):
            members = sorted(set(members_by_community[comm]))
            pairs.extend(self._draw(rng, k, math.comb(len(members), 2),
                                    lambda m=members: _pair_iter(m)))
        return PairSample(pairs=pairs, available=available, sampled=len(pairs))

    def sample_between(
        self, members_by_community: dict[Any, list[str]], rng: random.Random
    ) -> PairSample:
        """Between-community sample stratified by community pair."""
        comms = sorted(members_by_community, key=str)
        member_lists = {
            c: sorted(set(members_by_community[c])) for c in comms
        }
        strata: list[tuple[str, str]] = [
            (a, b) for idx, a in enumerate(comms) for b in comms[idx + 1:]
        ]
        availabilities = [
            len(member_lists[a]) * len(member_lists[b]) for a, b in strata
        ]
        available = sum(availabilities)
        alloc = self._allocate_balanced(availabilities, self._target(available))
        pairs: list[tuple[str, str]] = []

        def _cross_iter(a: list[str], b: list[str]) -> Iterator[tuple[str, str]]:
            for x in a:
                for y in b:
                    yield (x, y)

        for (a, b), k in zip(strata, alloc):
            la, lb = member_lists[a], member_lists[b]
            pairs.extend(self._draw(rng, k, len(la) * len(lb),
                                    lambda la=la, lb=lb: _cross_iter(la, lb)))
        return PairSample(pairs=pairs, available=available, sampled=len(pairs))


# ---------------------------------------------------------------------------
# Semantic similarity (cosine) over cached video-level vectors
# ---------------------------------------------------------------------------
class SemanticSimilarityService:
    """Cosine similarity over video-level semantic vectors."""

    @staticmethod
    def cosine(vec_a: np.ndarray, vec_b: np.ndarray) -> float | None:
        norm_a = float(np.linalg.norm(vec_a))
        norm_b = float(np.linalg.norm(vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return None
        value = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
        # Guard against floating drift just outside [-1, 1].
        return max(-1.0, min(1.0, value))

    @staticmethod
    def mean_similarity(
        matrix: dict[str, np.ndarray], pairs: list[tuple[str, str]]
    ) -> tuple[float | None, int]:
        """Mean cosine over ``pairs``; uncomputable pairs are skipped, never
        treated as zero. Returns ``(mean, computed_count)``."""
        values: list[float] = []
        for a, b in pairs:
            sim = SemanticSimilarityService.cosine(matrix[a], matrix[b])
            if sim is not None:
                values.append(sim)
        if not values:
            return None, 0
        return sum(values) / len(values), len(values)


# ---------------------------------------------------------------------------
# Null model (spec §14-§17): community-label permutation
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NullModelResult:
    null_differences: list[float]
    null_mean: float | None
    null_std: float | None
    z_score: float | None
    permutation_p_value: float | None
    num_permutations: int


class ContentHomophilyNullModelService:
    """Shuffles community labels and re-applies the SAME sampling policy.

    The observed analysis' computational constraints (fraction/cap/stratified/
    balanced draws) apply identically to every permutation (spec §15); each
    permutation is seeded deterministically from ``seed`` so the whole run is
    reproducible.
    """

    def run(
        self,
        vectors: dict[str, np.ndarray],
        labels: dict[str, Any],
        sampler: PairSamplingService,
        *,
        num_permutations: int = DEFAULT_NUM_PERMUTATIONS,
        seed: int = 42,
        max_videos_per_community: int = DEFAULT_MAX_VIDEOS_PER_COMMUNITY,
        observed_difference: float | None = None,
        progress: Callable[[int], None] | None = None,
        stop_requested: Callable[[], bool] | None = None,
    ) -> NullModelResult:
        video_ids = sorted(vectors)
        base_labels = [labels[v] for v in video_ids]
        differences: list[float] = []
        for index in range(num_permutations):
            if stop_requested is not None and stop_requested():
                break
            rng = random.Random(f"{seed}:{index}")
            permuted = list(base_labels)
            rng.shuffle(permuted)
            shuffled = dict(zip(video_ids, permuted))
            groups: dict[Any, list[str]] = {}
            for vid, label in shuffled.items():
                groups.setdefault(label, []).append(vid)
            # Same per-community cap as the observed pipeline (spec §3) so the
            # null re-applies the identical sampling constraints.
            if max_videos_per_community and max_videos_per_community > 0:
                groups = {
                    c: sorted(m)[:max_videos_per_community]
                    for c, m in groups.items()
                }
            within = sampler.sample_within(groups, rng)
            between = sampler.sample_between(groups, rng)
            diff = self._difference(vectors, within.pairs, between.pairs)
            if diff is not None:
                differences.append(diff)
            if progress is not None:
                progress(index + 1)

        num = len(differences)
        if num == 0:
            return NullModelResult([], None, None, None, None, num)
        mean = sum(differences) / num
        variance = sum((d - mean) ** 2 for d in differences) / num
        std = math.sqrt(variance)
        z_score: float | None = None
        if observed_difference is not None:
            if std == 0.0:
                # Degenerate null (all permutations identical): report the raw
                # percentile instead of silently returning inf/NaN.
                exceed = sum(1 for d in differences if d >= observed_difference)
                z_score = None if exceed else float("-inf")
                z_score = None
            else:
                z_score = (observed_difference - mean) / std
        p_value = None
        if observed_difference is not None:
            exceed = sum(1 for d in differences if d >= observed_difference)
            # Finite-sample corrected, directional (+1 correction, spec §17).
            p_value = (1 + exceed) / (1 + num_permutations)
        return NullModelResult(
            null_differences=differences,
            null_mean=mean,
            null_std=std,
            z_score=z_score,
            permutation_p_value=p_value,
            num_permutations=num,
        )

    @staticmethod
    def _difference(
        vectors: dict[str, np.ndarray],
        within_pairs: list[tuple[str, str]],
        between_pairs: list[tuple[str, str]],
    ) -> float | None:
        within, n_within = SemanticSimilarityService.mean_similarity(vectors, within_pairs)
        between, n_between = SemanticSimilarityService.mean_similarity(vectors, between_pairs)
        if n_within == 0 or n_between == 0 or within is None or between is None:
            return None
        return within - between


# ---------------------------------------------------------------------------
# Ingestion_Pipline reuse (chunking + embeddings) - NO duplicate pipeline
# ---------------------------------------------------------------------------
def _ingestion_chunker(text: str, *, source: str) -> list[str]:
    """Chunk one transcript via the EXISTING Ingestion_Pipline splitter.

    Uses a CSS-specific (large) chunk size so a long transcript stays under
    ~100 chunks and therefore fits in a single ``batchEmbedContents`` request,
    keeping the global Gemini request limiter accurate (see
    Ingestion_Pipline.infra.embeddings).
    """
    from langchain_core.documents import Document

    from Ingestion_Pipline.config.settings import ChunkingSettings
    from Ingestion_Pipline.ingestion.chunking import split_text

    from SocialScienceResearch.config.settings import (
        CONTENT_HOMOPHILY_EMBED_CHUNK_SIZE,
        CONTENT_HOMOPHILY_EMBED_CHUNK_OVERLAP,
    )

    settings = ChunkingSettings()
    docs = split_text(
        [Document(page_content=text, metadata={"source": source})],
        chunk_size=CONTENT_HOMOPHILY_EMBED_CHUNK_SIZE or settings.chunk_size,
        chunk_overlap=CONTENT_HOMOPHILY_EMBED_CHUNK_OVERLAP or settings.chunk_overlap,
        encoding_name=settings.encoding_name,
    )
    return [doc.page_content for doc in docs]


def _default_embedder():
    """The existing Ingestion_Pipline embedding model (Gemini via LangChain)."""
    from Ingestion_Pipline.config.settings import EmbeddingSettings
    from Ingestion_Pipline.infra.embeddings import build_embeddings

    return build_embeddings(EmbeddingSettings())


def default_embedding_model_name() -> str:
    try:
        from Ingestion_Pipline.config.settings import EmbeddingSettings

        return EmbeddingSettings().model
    except Exception:  # noqa: BLE001
        return "unknown"


# ---------------------------------------------------------------------------
# Video-level representation adapter (spec §4-§6)
# ---------------------------------------------------------------------------
class VideoEmbeddingAdapter:
    """transcript text -> existing chunking/embedding -> one pooled vector.

    Reuses Ingestion_Pipline ``split_text`` + its embedding model; adds only
    the minimal video-level aggregation (mean of chunk embeddings). Compatible
    cached vectors are reused (keyed by transcript content hash + model);
    counters distinguish reused/generated/failures (spec §5).
    """

    def __init__(
        self,
        repos,
        data_dir: str | Path,
        *,
        embedder=None,
        model_name: str | None = None,
    ) -> None:
        self._repos = repos
        self._embedder = embedder
        self.model_name = model_name or default_embedding_model_name()
        self.model_version = "1"
        self.embeddings_reused = 0
        self.embeddings_generated = 0
        self.embedding_failures = 0
        safe_model = "".join(c if c.isalnum() else "-" for c in self.model_name)
        self.cache_dir = Path(data_dir) / "embedding_cache" / safe_model

    def video_vector(self, video_id: str, text: str) -> np.ndarray | None:
        """Return the cached/new video-level vector, or ``None`` on failure."""
        digest = hashlib.sha256(
            f"{self.model_name}|{self.model_version}|{text}".encode("utf-8")
        ).hexdigest()
        cached = self._load_cache(video_id, digest)
        if cached is not None:
            self.embeddings_reused += 1
            logger.info("content-homophily embedding REUSED from cache: %s", video_id)
            return cached
        try:
            if self._embedder is None:
                self._embedder = _default_embedder()
            chunks = _ingestion_chunker(text, source=f"youtube:{video_id}")
            if not chunks:
                self.embedding_failures += 1
                logger.warning("content-homophily no chunks to embed: %s", video_id)
                return None
            n_tokens = (
                _css_embed_token_limiter.count_tokens_text(chunks)
                if _css_embed_token_limiter is not None else 0
            )
            logger.info(
                "content-homophily embedding START %s: %d chunk(s), %d token(s)",
                video_id, len(chunks), n_tokens,
            )
            # Request pacing is handled globally on the shared Gemini embedder
            # (Ingestion_Pipline.infra.embeddings) because the free-tier request
            # quota is project-wide; nothing to do here.
            # Token gate (CSS-only politeness budget; ingestion is unaffected).
            if _css_embed_token_limiter is not None:
                _css_embed_token_limiter.throttle(n_tokens)
            # Queue + retry on transient failures (e.g. Gemini 429) so a chunk is
            # never dropped: it is waited out and retried, not lost.
            vectors = None
            max_retries = CONTENT_HOMOPHILY_EMBED_MAX_RETRIES
            for attempt in range(max(1, max_retries + 1)):
                try:
                    vectors = self._embedder.embed_documents(chunks)
                    break
                except Exception as exc:  # noqa: BLE001 - queue, don't drop
                    if attempt >= max_retries:
                        raise
                    wait = self._embedding_retry_delay(exc, attempt)
                    logger.warning(
                        "content-homophily embedding queued (retry %d/%d) for "
                        "%s: %s; waiting %.1fs",
                        attempt + 1, max_retries, video_id, exc, wait,
                    )
                    time.sleep(wait)
            if not vectors:
                self.embedding_failures += 1
                logger.warning("content-homophily embedding produced no vectors: %s", video_id)
                return None
            pooled = np.mean(np.asarray(vectors, dtype=float), axis=0)
            self.embeddings_generated += 1
            self._write_cache(video_id, digest, pooled)
            logger.info(
                "content-homophily embedding GENERATED: %s (%d vector(s))",
                video_id, len(vectors),
            )
            return pooled
        except Exception as exc:  # noqa: BLE001 - a failed video never aborts the run
            logger.warning(
                "content-homophily embedding failed for %s: %s", video_id, exc
            )
            self.embedding_failures += 1
            return None

    @staticmethod
    def _embedding_retry_delay(exc: Exception, attempt: int) -> float:
        """How long to wait before re-queuing a failed embedding.

        Honours a server ``Retry-After`` / ``retryDelay`` when present (Gemini
        embeds surface ``retry in 55.0s`` or ``retryDelay: '55s'``), otherwise
        falls back to exponential backoff.
        """
        import re

        text = str(exc)
        match = re.search(r"retry in\s*([0-9]+(?:\.[0-9]+)?)\s*s", text)
        if not match:
            match = re.search(r"retryDelay['\"]?\s*:\s*['\"]?([0-9]+(?:\.[0-9]+)?)", text)
        if match:
            return float(match.group(1)) + 0.5
        return min(2.0 * (2 ** attempt), 60.0)

    def _cache_path(self, video_id: str) -> Path:
        return self.cache_dir / f"{video_id}.json"

    def _load_cache(self, video_id: str, digest: str) -> np.ndarray | None:
        path = self._cache_path(video_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
        if payload.get("digest") != digest:
            return None
        vector = payload.get("vector")
        if not isinstance(vector, list) or not vector:
            return None
        return np.asarray(vector, dtype=float)

    def _write_cache(self, video_id: str, digest: str, vector: np.ndarray) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache_path(video_id).write_text(
                json.dumps(
                    {
                        "video_id": video_id,
                        "model": self.model_name,
                        "model_version": self.model_version,
                        "digest": digest,
                        "vector": [float(x) for x in vector],
                    }
                ),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001 - cache write is best-effort
            logger.warning("embedding cache write failed for %s: %s", video_id, exc)


# ---------------------------------------------------------------------------
# Orchestrating service (on-demand job, targeted transcripts, results §19)
# ---------------------------------------------------------------------------
class ContentHomophilyService:
    """Runs the full Content Homophily pipeline as ONE opt-in async job."""

    def __init__(self, provider, repos, settings=None, *, jobs=None, analytics=None,
                 embedder=None, embedder_factory=None, budget_controller=None) -> None:
        from SocialScienceResearch.config.settings import SocialScienceSettings

        self._provider = provider
        self._repos = repos
        self._settings = settings or SocialScienceSettings()
        self._budget = budget_controller or BudgetController(
            min_interval=self._settings.scraper.request_delay_seconds,
            max_ytdl_contexts=self._settings.scraper.budget_max_ytdl_contexts,
        )
        self._jobs = jobs
        self._analytics = analytics or None
        self._embedder = embedder
        self._embedder_factory = embedder_factory
        self._base_dir = (
            Path(self._settings.repository.data_dir) / "content_homophily"
        )
        self._lock = threading.Lock()
        self._memory: dict[str, dict[str, Any]] = {}
        # Any analysis left in running/pending from a previous process is
        # orphaned (no worker survives a restart) -> reconcile to interrupted
        # so it never permanently disables the Run button in the UI.
        self._reconcile_orphans()

    # -- persistence ----------------------------------------------------
    def _reconcile_orphans(self) -> None:
        if not self._base_dir.exists():
            return
        for path in self._base_dir.glob("*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            if record.get("status") in ("running", "pending"):
                record["status"] = "interrupted"
                record.setdefault("error", "")
                record["error"] = (
                    "Reconciled on startup: previous run had no surviving "
                    "worker (backend was terminated). Not treated as data."
                )
                try:
                    self._save(record)
                except Exception:  # noqa: BLE001
                    continue

    def _path(self, analysis_id: str) -> Path:
        return self._base_dir / f"{analysis_id}.json"

    def _save(self, record: dict[str, Any]) -> None:
        record["updated_at"] = utcnow().isoformat()
        with self._lock:
            # In-process mirror first: GETs never depend on Windows file
            # replace semantics racing a concurrent reader.
            self._memory[record["analysis_id"]] = record
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
            self._path(record["analysis_id"]).write_text(
                json.dumps(record), encoding="utf-8"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed persisting content-homophily record: %s", exc)

    def get(self, analysis_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._memory.get(analysis_id)
        if record is not None:
            return record
        try:
            return json.loads(self._path(analysis_id).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None

    def list(self) -> list[dict[str, Any]]:
        records: dict[str, dict[str, Any]] = {}
        if self._base_dir.exists():
            for path in sorted(self._base_dir.glob("*.json")):
                try:
                    record = json.loads(path.read_text(encoding="utf-8"))
                    records[record.get("analysis_id") or path.stem] = record
                except Exception:  # noqa: BLE001
                    continue
        with self._lock:
            for analysis_id, record in self._memory.items():
                records[analysis_id] = record
        merged = sorted(records.values(),
                        key=lambda r: r.get("created_at") or "", reverse=True)
        return merged

    # -- progress bookkeeping --------------------------------------------
    def _stage(self, record: dict[str, Any], name: str, state: str) -> None:
        stages = record["progress"]["stages"]
        stages[name] = state
        record["progress"]["current_stage"] = name if state == "running" else \
            record["progress"].get("current_stage")

    def _log(self, record: dict[str, Any], message: str) -> None:
        log = record["progress"].setdefault("log", [])
        log.append({"ts": utcnow().isoformat(), "message": message})
        del log[:-200]
        logger.info("content-homophily %s: %s", record["analysis_id"], message)

    def _touch_eta(self, record: dict[str, Any], done: int, total: int,
                   started: float) -> None:
        progress = record["progress"]
        elapsed = round(time.monotonic() - started, 1)
        progress["elapsed_seconds"] = elapsed
        if done > 0 and total > done:
            progress["eta_seconds"] = round(elapsed / done * (total - done), 1)

    # -- public API -------------------------------------------------------
    def start(
        self,
        *,
        run_id: str | None = None,
        video_ids: list[str] | None = None,
        sampling_fraction: float = DEFAULT_SAMPLING_FRACTION,
        max_pair_cap: int = DEFAULT_MAX_PAIR_CAP,
        random_seed: int | None = None,
        num_permutations: int = DEFAULT_NUM_PERMUTATIONS,
        max_videos_per_community: int = DEFAULT_MAX_VIDEOS_PER_COMMUNITY,
        max_transcript_videos: int = DEFAULT_MAX_TRANSCRIPT_VIDEOS,
        include_edge_similarity: bool = False,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        # No explicit scope = WHOLE NETWORK: every video with an observed
        # recommendation edge is eligible (the researcher asked for the net,
        # not a slice). Communities come from detection over that graph.
        if run_id is None and not video_ids:
            all_edges = self._repos.recommendations.list_recommendation_edges()
            video_ids = sorted(
                {
                    vid
                    for edge in all_edges
                    for vid in (edge.source_video_id, edge.recommended_video_id)
                }
            )
            if not video_ids:
                raise ValueError(
                    "No scraped videos found yet — scrape a network first "
                    "or pass run_id/video_ids."
                )
        if not 0 < sampling_fraction <= 1:
            raise ValueError("sampling_fraction must be in (0, 1]")
        if not 1 <= max_pair_cap <= ABSOLUTE_MAX_PAIR_CAP:
            raise ValueError(f"max_pair_cap must be <= {ABSOLUTE_MAX_PAIR_CAP}")
        if not 0 <= num_permutations <= 10_000:
            raise ValueError("num_permutations must be between 0 and 10000")
        if not 1 <= max_transcript_videos <= ABSOLUTE_MAX_TRANSCRIPT_VIDEOS:
            raise ValueError(
                f"max_transcript_videos must be between 1 and "
                f"{ABSOLUTE_MAX_TRANSCRIPT_VIDEOS}"
            )
        if run_id and self._repos.runs.get_run(run_id) is None:
            raise ValueError(f"Run {run_id} not found")
        seed = int(random_seed) if random_seed is not None \
            else self._settings.sampling.default_seed
        now = utcnow().isoformat()
        job_id = new_id("job")
        record: dict[str, Any] = {
            "analysis_id": new_id("chh"),
            "job_id": job_id,
            "status": "pending",
            "params": {
                "run_id": run_id,
                "video_ids": list(video_ids or []),
                "sampling_fraction": sampling_fraction,
                "max_pair_cap": max_pair_cap,
                "random_seed": seed,
                "num_permutations": num_permutations,
                "max_videos_per_community": max_videos_per_community,
                "max_transcript_videos": max_transcript_videos,
                "include_edge_similarity": include_edge_similarity,
            },
            "progress": {
                "current_stage": None,
                "stages": {name: "pending" for name in STAGES},
                "log": [],
                "videos_total": 0,
                "videos_processed": 0,
                "embeddings_reused": 0,
                "embeddings_generated": 0,
                "embedding_failures": 0,
                "null_permutations_done": 0,
            },
            "created_at": now,
        }
        self._save(record)

        def _worker(reporter) -> dict[str, Any]:
            return self._run_analysis(record["analysis_id"], {"job_id": job_id})

        if self._jobs is not None:
            self._jobs.submit(_worker, kind="content_homophily", job_id=job_id,
                              tags=list(tags or []))
        else:
            record["status"] = "failed"
            record["error"] = "no job manager configured"
            self._save(record)
        return {
            "analysis_id": record["analysis_id"],
            "job_id": job_id,
            "status": record["status"],
        }

    def _stop_requested(self, job_id_holder: dict[str, str]) -> bool:
        job_id = job_id_holder.get("job_id")
        return bool(job_id and self._jobs is not None
                    and self._jobs.is_cancel_requested(job_id))

    # -- targeted transcript collection (spec §3) --------------------------
    def _read_artifact_text(self, video_id: str) -> str | None:
        record = self._repos.transcripts.get_transcript(video_id)
        if record is None or record.status != TranscriptStatus.AVAILABLE:
            return None
        reader = getattr(self._repos.transcripts, "read_artifact", None)
        if reader is not None:
            return reader(video_id)
        if record.path:
            path = Path(self._settings.repository.data_dir) / record.path
            try:
                return path.read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001
                return None
        return None

    def _ensure_transcript(self, video_id: str, analysis_id: str) -> str | None:
        """Existing artifact first; otherwise a TARGETED best-effort fetch.

        This fetch runs ONLY because the researcher explicitly requested this
        Content Homophily analysis - it is never triggered by default scrapes.
        """
        existing = self._read_artifact_text(video_id)
        if existing and existing.strip():
            return existing
        video = self._repos.videos.get_video(video_id)
        url = video.url if video is not None else None
        if url is None:
            url = f"https://www.youtube.com/watch?v={video_id}"
        lang = self._settings.scraper.transcript_lang
        try:
            with run_context(analysis_id):
                extract = self._provider.extract_transcript(url, lang=lang)
        except Exception as exc:  # noqa: BLE001 - explicit unsupported outcome
            self._save_transcript_record(analysis_id, video_id, lang,
                                         TranscriptStatus.UNSUPPORTED, str(exc))
            return None
        if extract.status == TranscriptStatus.AVAILABLE and extract.content:
            writer = getattr(self._repos.transcripts, "write_artifact", None)
            relative = None
            if writer is not None:
                abs_path = writer(video_id, extract.content)
                try:
                    relative = str(abs_path.relative_to(
                        self._settings.repository.data_dir).as_posix())
                except ValueError:
                    relative = str(abs_path)
                if video is not None:
                    video.transcript_path = relative
                    video.transcript_status = TranscriptStatus.AVAILABLE.value
                    video.transcript_lang = extract.lang or lang
                    self._repos.videos.upsert_video(video)
            self._save_transcript_record(analysis_id, video_id,
                                         extract.lang or lang,
                                         TranscriptStatus.AVAILABLE,
                                         message=None, path=relative)
            return extract.content
        self._save_transcript_record(analysis_id, video_id, lang,
                                     extract.status, extract.message)
        return None

    def _save_transcript_record(self, run_ref: str, video_id: str, lang: str | None,
                                status: TranscriptStatus, message: str | None,
                                *, path: str | None = None) -> None:
        try:
            self._repos.transcripts.save_transcript(
                TranscriptRecord(
                    transcript_id=new_id("tx"),
                    video_id=video_id,
                    collection_run_id=run_ref,
                    path=path,
                    lang=lang,
                    status=status,
                    message=message,
                    observed_at=utcnow(),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("transcript record save failed for %s: %s", video_id, exc)

    # -- transcript-video budget (spec §3, cost-first) ----------------------
    def _video_has_transcript(self, video_id: str) -> bool:
        """True if a transcript artifact already exists locally for the video.

        Used by the bounded video selection to PRIORITISE videos that already
        have transcripts, so we reuse local artifacts instead of scraping (the
        dominant, rate-limited cost). Checks the file directly rather than the
        latest record status, so a usable artifact is never missed.
        """
        reader = getattr(self._repos.transcripts, "read_artifact", None)
        if reader is None:
            return False
        try:
            text = reader(video_id)
        except Exception:  # noqa: BLE001
            return False
        return bool(text and text.strip())

    def _select_bounded_videos(
        self, capped_groups: dict[int, list[str]], max_transcript_videos: int
    ) -> tuple[dict[int, list[str]], list[str]]:
        """First-class <=max_transcript_videos video budget (spec §3, cost-first).

        Pick a balanced, community-representative set of UNIQUE videos BEFORE any
        pair sampling, prioritising videos that already have a transcript (reuse
        local artifacts, avoid 429s). Pairs are later sampled ONLY from this
        selected set, so the number of videos requiring transcript/embedding
        collection can never exceed the budget. Deterministic given the data
        (seed-independent); pair sampling remains seeded for reproducibility.
        """
        comms = sorted(capped_groups, key=str)
        avail = [len(capped_groups[c]) for c in comms]
        total = min(max_transcript_videos, sum(avail))
        if total <= 0:
            return {}, []
        alloc = PairSamplingService._allocate_balanced(avail, total)
        selected_groups: dict[int, list[str]] = {}
        selected: list[str] = []
        for c, k in zip(comms, alloc):
            if k <= 0:
                continue
            members = capped_groups[c]
            # Transcript-first priority, deterministic id tie-break.
            ordered = sorted(
                members,
                key=lambda v: (0 if self._video_has_transcript(v) else 1, v),
            )
            chosen = ordered[:k]
            if chosen:
                selected_groups[c] = chosen
                selected.extend(chosen)
        return selected_groups, selected

    # -- replacement sampling (spec §3) ------------------------------------
    @staticmethod
    def _replacement_candidates(
        members: list[str], missing: str, other: str,
        vectors: dict[str, Any], used_videos: set[str],
        known_missing: set[str],
    ) -> list[str]:
        """Deterministic same-community candidate ordering for ``missing``.

        Excludes the missing video itself, the pair's other video (no
        self-pairs), and any video already known to be unavailable (we never
        re-fetch a transcript that already failed). Prefers videos that are
        ALREADY embedded (guaranteed usable, zero extra scraping) and, among
        those, peers not already used by another selected pair (avoids reusing
        selected videos whenever practical). Unembedded peers are a bounded
        fallback that triggers a single targeted fetch.
        """
        base = [
            v for v in members
            if v != missing and v != other and v not in known_missing
        ]
        unused = [v for v in base if v not in used_videos]
        used = [v for v in base if v in used_videos]
        embedded = lambda vs: [v for v in vs if v in vectors]
        fresh = lambda vs: [v for v in vs if v not in vectors]
        return (
            embedded(unused) + embedded(used) +
            fresh(unused) + fresh(used)
        )

    def _run_replacement_sampling(
        self, record, analysis_id, capped_groups, labels,
        within_pairs, between_pairs, adapter, vectors, rng,
        known_missing: set[str],
    ) -> dict[str, Any]:
        """Fill the target usable sample by swapping unavailable videos.

        Pairs are sampled FIRST; we only ever collect transcripts/embeddings
        for (a) the originally sampled videos and (b) the minimal set of same-
        community replacements needed to reach the target usable sample. For
        each sampled pair whose video is unavailable, a replacement is drawn
        from the SAME community (preserving within/between semantics) and tried.
        A given missing video is substituted by the SAME peer everywhere (a
        consistent ``replacement_map``), so the comparison structure is stable
        and we never re-fetch a confirmed-missing video. Replacement is bounded
        (per-video tries + a global fetch budget) and reproducible (deterministic
        candidate ordering, no RNG consumption beyond the sampling ``rng``).
        Never treats a missing transcript as zero.
        """
        meta = {
            "pairs_original_within": len(within_pairs),
            "pairs_original_between": len(between_pairs),
            "replacement_attempts": 0,
            "replacement_successes": 0,
            "replacement_fetches": 0,
            "replacement_budget": max(
                REPLACEMENT_BUDGET_MIN,
                2 * (len(within_pairs) + len(between_pairs)),
            ),
            "budget_exhausted": False,
            "pairs_dropped": 0,
        }
        replacement_map: dict[str, str] = {}

        def _pick(missing, other) -> str | None:
            community = labels.get(missing)
            if community is None:
                return None
            members = capped_groups.get(community, [])
            used_videos = {
                v for p in (within_pairs + between_pairs) for v in p
            }
            selected_pairs = {
                frozenset(p) for p in (within_pairs + between_pairs)
            }
            order = self._replacement_candidates(
                members, missing, other, vectors, used_videos, known_missing)
            # Prefer a candidate that yields a non-duplicate pair.
            for cand in order:
                if frozenset({cand, other}) not in selected_pairs:
                    return cand
            # Fallback: accept an embedded duplicate rather than drop the pair.
            for cand in order:
                if cand in vectors:
                    return cand
            return None

        def _replace_one(lst, idx, missing, other) -> bool:
            if missing in replacement_map:
                cand = replacement_map[missing]
                if cand in vectors:
                    self._apply_replacement(lst, idx, missing, cand)
                    meta["replacement_successes"] += 1
                    return True
                # Mapped candidate lost (shouldn't happen); clear and redo.
                del replacement_map[missing]
            cand = _pick(missing, other)
            if cand is None:
                return False
            # A fresh candidate needs a single targeted fetch (bounded).
            if cand not in vectors:
                if meta["replacement_fetches"] >= meta["replacement_budget"]:
                    return False
                meta["replacement_fetches"] += 1
                meta["replacement_attempts"] += 1
                text = self._ensure_transcript(cand, analysis_id)
                if not text or not text.strip():
                    known_missing.add(cand)
                    return False
                vector = adapter.video_vector(cand, text)
                if vector is None:
                    known_missing.add(cand)
                    return False
                vectors[cand] = vector
            replacement_map[missing] = cand
            self._apply_replacement(lst, idx, missing, cand)
            meta["replacement_successes"] += 1
            self._log(record,
                      f"replaced {missing} (community {labels.get(missing)}) "
                      f"-> {cand}")
            return True

        for _ in range(MAX_REPLACEMENT_SWEEPS):
            progress = False
            for lst in (within_pairs, between_pairs):
                for idx in range(len(lst)):
                    a, b = lst[idx]
                    if a in vectors and b in vectors:
                        continue
                    targets = []
                    if a not in vectors:
                        targets.append((a, b))
                    if b not in vectors:
                        targets.append((b, a))
                    for missing, other in targets:
                        if _replace_one(lst, idx, missing, other):
                            progress = True
                            break
            if not progress:
                break

        for lst in (within_pairs, between_pairs):
            for a, b in lst:
                if a not in vectors or b not in vectors:
                    meta["pairs_dropped"] += 1
        meta["budget_exhausted"] = (
            meta["replacement_fetches"] >= meta["replacement_budget"])
        return meta

    @staticmethod
    def _apply_replacement(lst, idx, missing, cand) -> None:
        cur = lst[idx]
        if missing == cur[0]:
            lst[idx] = [cand, cur[1]]
        else:
            lst[idx] = [cur[0], cand]

    # -- the pipeline ------------------------------------------------------
    def _run_analysis(self, analysis_id: str, job_id_holder: dict[str, str]) -> dict[str, Any]:
        record = self.get(analysis_id)
        if record is None:
            raise KeyError(f"Content homophily analysis {analysis_id} not found")
        record["status"] = "running"
        record["started_at"] = utcnow().isoformat()
        started = time.monotonic()
        self._save(record)
        params = record["params"]
        try:
            results = self._pipeline(record, params, job_id_holder, started)
            record["results"] = results
            record["status"] = results.get("status", "observed")
            record["finished_at"] = utcnow().isoformat()
            for name, state in record["progress"]["stages"].items():
                if state == "running":
                    record["progress"]["stages"][name] = "done"
            self._stage(record, "results", "done")
            self._save(record)
        except OperationCancelled:
            record["status"] = "stopped"
            record["finished_at"] = utcnow().isoformat()
            self._save(record)
        except Exception as exc:  # noqa: BLE001 - surface failure on the record
            logger.exception("content homophily %s failed", analysis_id)
            record["status"] = "failed"
            record["error"] = str(exc)[:500]
            record["finished_at"] = utcnow().isoformat()
            self._save(record)
        return {"analysis_id": analysis_id, "status": record["status"],
                "job_id": record["job_id"]}

    def _pipeline(self, record, params, job_id_holder, started) -> dict[str, Any]:
        progress = record["progress"]

        # 1. Dataset preparation: communities come from the shared network
        # engine (louvain seed=42) over the requested scope - any supported
        # network slice, never echo-chamber-specific.
        self._stage(record, "dataset_preparation", "running")
        self._save(record)
        if self._analytics is None:
            from SocialScienceResearch.services.network_analytics_service import (
                NetworkAnalyticsService,
            )

            self._analytics = NetworkAnalyticsService(self._repos)
        run_id = params.get("run_id")
        video_scope = params.get("video_ids") or None
        graph_payload = self._analytics.graph(
            run_ids=[run_id] if run_id else None, video_ids=video_scope
        )
        nodes = [n for n in graph_payload.nodes if n.community_id is not None]
        labels: dict[str, int] = {
            n.video_id: n.community_id for n in nodes
        }
        groups: dict[int, list[str]] = {}
        for vid in sorted(labels):
            groups.setdefault(labels[vid], []).append(vid)
        self._log(record,
                  f"dataset prepared: {len(nodes)} community-labeled video(s), "
                  f"{len(groups)} communitie(s), "
                  f"{graph_payload.edge_count} edge(s)")
        self._stage(record, "dataset_preparation", "done")
        if len(nodes) < 2:
            return self._insufficient(record, params,
                                      reason="fewer than two eligible videos")
        # 2. Cap the per-community pool (replacement-sampling limit, spec §3).
        capped_groups: dict[int, list[str]] = {
            c: groups[c][: params["max_videos_per_community"]]
            for c in sorted(groups)
        }
        total_eligible = sum(len(v) for v in capped_groups.values())
        if total_eligible < 2:
            return self._insufficient(record, params,
                                      reason="fewer than two eligible videos")

        # 2b. FIRST-CLASS transcript-video budget: select a balanced,
        # community-representative set of <= max_transcript_videos UNIQUE videos
        # BEFORE any pair sampling, prioritising videos that already have a
        # transcript (reuse local artifacts, avoid rate-limited 429s). Pairs are
        # then sampled ONLY from this selected set, so transcript/embedding
        # collection can never exceed the budget (the dominant, costly step).
        seed = params["random_seed"]
        rng = random.Random(seed)
        max_transcript_videos = int(params.get(
            "max_transcript_videos", DEFAULT_MAX_TRANSCRIPT_VIDEOS))
        selected_groups, selected_videos = self._select_bounded_videos(
            capped_groups, max_transcript_videos)
        self._log(record,
                  f"transcript budget applied: selected {len(selected_videos)}/"
                  f"{max_transcript_videos} unique video(s) across "
                  f"{len(selected_groups)} communitie(s) before pair sampling "
                  f"(prioritising those with existing transcripts)")
        if len(selected_videos) < 2:
            return self._insufficient(record, params,
                                      reason="fewer than two selected videos "
                                             "within the transcript budget")

        # 2c. Sample target pairs ONLY from the selected videos (cost-first: the
        # expensive step is transcript acquisition, not pair cosines). The union
        # of pair videos is therefore a subset of the <=max_transcript_videos
        # selected set.
        sampler = PairSamplingService(params["sampling_fraction"],
                                      params["max_pair_cap"])
        within = sampler.sample_within(selected_groups, rng)
        between = sampler.sample_between(selected_groups, rng)
        self._log(record,
                  f"pairs sampled (pre-collection): within "
                  f"{within.sampled}/{within.available}, between "
                  f"{between.sampled}/{between.available}")
        self._stage(record, "pair_sampling", "done")

        # Union of videos required by the sampled pairs (each video once).
        needed: list[tuple[str, str]] = []  # (community, video_id)
        seen_videos: set[str] = set()
        for pairs in (within.pairs, between.pairs):
            for a, b in pairs:
                for vid in (a, b):
                    if vid not in seen_videos:
                        seen_videos.add(vid)
                        needed.append((labels.get(vid), vid))
        if not needed:
            return self._insufficient(record, params,
                                      reason="no videos in sampled pairs")
        progress["videos_total"] = len(needed)

        # 3. Targeted transcript collection (only the sampled-pair videos).
        self._stage(record, "transcript_collection", "running")
        self._save(record)
        selected_texts: dict[str, str] = {}
        without_transcript = 0
        # Per-channel failure tracking: once a channel accumulates more than
        # 7 transcript failures we stop trying its remaining videos (the
        # channel is effectively untranscribable) rather than burning time.
        channel_failures: dict[str, int] = {}
        channel_skipped: set[str] = set()
        # Concurrent, cancel-aware fetching with bounded workers.
        # Cap at 5 simultaneous linguistic-analysis (transcript) requests so we
        # never overwhelm the upstream provider.
        workers = max(1, min(5, len(needed)))
        processed = 0
        progress["transcripts_in_hand"] = 0
        progress["transcripts_remaining"] = len(needed)
        self._save(record)

        def _fetch_one(item: tuple[str, str]) -> tuple[str, str, str | None, bool]:
            community, video_id = item
            if self._stop_requested(job_id_holder):
                raise OperationCancelled()
            vid = self._repos.videos.get_video(video_id)
            channel_id = vid.channel_id if vid is not None else None
            if channel_id in channel_skipped:
                return (community, video_id, None, False)
            text = self._ensure_transcript(video_id, record["analysis_id"])
            return (community, video_id, text, text is None or not text.strip())

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_fetch_one, item): item for item in needed}
            for fut in as_completed(futures):
                if self._stop_requested(job_id_holder):
                    for f in futures:
                        f.cancel()
                    raise OperationCancelled()
                community, video_id, text, failed = fut.result()
                processed += 1
                vid = self._repos.videos.get_video(video_id)
                channel_id = vid.channel_id if vid is not None else None
                if channel_id:
                    if failed:
                        channel_failures[channel_id] = (
                            channel_failures.get(channel_id, 0) + 1)
                        if channel_failures[channel_id] > 7:
                            channel_skipped.add(channel_id)
                            self._log(record,
                                      f"channel {channel_id} excluded after "
                                      f"{channel_failures[channel_id]} transcript "
                                      "failures")
                    else:
                        channel_failures.pop(channel_id, None)
                if text and text.strip():
                    selected_texts[video_id] = text
                    self._log(record, f"transcript loaded: {video_id}")
                else:
                    without_transcript += 1
                    self._log(record,
                              f"transcript unavailable for {video_id}")
                progress["videos_processed"] = processed
                progress["transcripts_in_hand"] = len(selected_texts)
                progress["transcripts_remaining"] = len(needed) - processed
                self._touch_eta(record, processed, len(needed), started)
                self._save(record)
        self._stage(record, "transcript_collection", "done")
        self._log(record,
                  f"transcripts usable: {len(selected_texts)}, "
                  f"unavailable: {without_transcript}")
        if len(selected_texts) < 2:
            return self._insufficient(
                record, params,
                reason="fewer than two usable transcripts after targeted "
                       "collection (missing transcripts are never treated "
                       "as zero similarity)",
                videos_without_transcript=without_transcript)

        # 4. Embedding preparation (only the collected transcripts).
        self._stage(record, "embedding_preparation", "running")
        self._save(record)
        adapter = VideoEmbeddingAdapter(
            self._repos, self._settings.repository.data_dir,
            embedder=self._embedder,
            model_name=getattr(self._embedder, "model_name", None)
            if self._embedder is not None else None,
        )
        vectors: dict[str, np.ndarray] = {}
        embedded_list = sorted(selected_texts)
        for index, video_id in enumerate(embedded_list):
            if self._stop_requested(job_id_holder):
                raise OperationCancelled()
            # Show the video being processed immediately so the UI never looks
            # frozen on the previous video while a large transcript is throttled.
            progress.update({
                "videos_processed": index,
                "current_video": video_id,
                "embedding_model": adapter.model_name,
            })
            self._save(record)
            logger.info(
                "content-homophily embedding %d/%d: %s",
                index + 1, len(embedded_list), video_id,
            )
            vector = adapter.video_vector(video_id, selected_texts[video_id])
            if vector is not None:
                vectors[video_id] = vector
            progress.update({
                "videos_processed": index + 1,
                "current_video": video_id,
                "embeddings_reused": adapter.embeddings_reused,
                "embeddings_generated": adapter.embeddings_generated,
                "embedding_failures": adapter.embedding_failures,
                "embedding_model": adapter.model_name,
            })
            self._touch_eta(record, index + 1, len(embedded_list), started)
            self._save(record)
            self._log(record, f"embedding ready: {video_id}")
        progress.pop("current_video", None)
        self._stage(record, "embedding_preparation", "done")
        if len(vectors) < 2:
            return self._insufficient(
                record, params,
                reason="fewer than two successful embeddings",
                videos_without_transcript=without_transcript)

        # 4b. Same-community replacement sampling: instead of dropping a pair
        # when one of its videos has no transcript/embedding, swap that video
        # for a peer from the SAME community and try it. Bounded + reproducible.
        within_pairs = [list(p) for p in within.pairs]
        between_pairs = [list(p) for p in between.pairs]
        # Videos already known to be unavailable (failed the initial targeted
        # collection) must never be re-fetched as replacement candidates.
        known_missing = {vid for _, vid in needed if vid not in selected_texts}
        replacement_meta = self._run_replacement_sampling(
            record, record["analysis_id"], capped_groups, labels,
            within_pairs, between_pairs, adapter, vectors, rng, known_missing)
        within_usable = [(a, b) for a, b in within_pairs
                         if a in vectors and b in vectors]
        between_usable = [(a, b) for a, b in between_pairs
                          if a in vectors and b in vectors]

        # 4c. Persist the selected sample (the unique videos actually analysed)
        # plus each video's community-pair role, so it can be exported with
        # titles/channels/links on demand. Bounded by the transcript budget.
        sample_role_map: dict[str, dict[str, bool]] = {}
        for a, b in within_usable:
            for v in (a, b):
                sample_role_map.setdefault(
                    v, {"within": False, "between": False})["within"] = True
        for a, b in between_usable:
            for v in (a, b):
                sample_role_map.setdefault(
                    v, {"within": False, "between": False})["between"] = True
        sample_videos = sorted(sample_role_map)

        self._log(record,
                  f"pairs after replacement: within {len(within_usable)}/"
                  f"{within.sampled}, between {len(between_usable)}/"
                  f"{between.sampled} "
                  f"(replacements={replacement_meta['replacement_successes']}, "
                  f"dropped={replacement_meta['pairs_dropped']})")
        if not within_usable and not between_usable:
            return self._insufficient(
                record, params,
                reason="no usable sampled pairs after replacement sampling",
                videos_without_transcript=without_transcript,
                status="insufficient_sample",
                extra={
                    "pairs_available_within": within.available,
                    "pairs_sampled_within": within.sampled,
                    "pairs_available_between": between.available,
                    "pairs_sampled_between": between.sampled,
                    **replacement_meta,
                })

        # 5. Similarity calculation.
        self._stage(record, "similarity_calculation", "running")
        self._save(record)
        within_mean, within_n = SemanticSimilarityService.mean_similarity(
            vectors, within_usable)
        between_mean, between_n = SemanticSimilarityService.mean_similarity(
            vectors, between_usable)
        self._stage(record, "similarity_calculation", "done")

        # 6. Observed difference.
        self._stage(record, "observed_difference", "running")
        self._save(record)
        observed_difference = (
            within_mean - between_mean
            if within_mean is not None and between_mean is not None else None
        )
        self._stage(record, "observed_difference", "done")
        if observed_difference is None:
            return self._insufficient(
                record, params,
                reason="no computable similarity pairs",
                videos_without_transcript=without_transcript,
                extra={
                    "pairs_available_within": within.available,
                    "pairs_sampled_within": within.sampled,
                    "pairs_available_between": between.available,
                    "pairs_sampled_between": between.sampled,
                })

        # 7. Null model (same sampling constraints; label permutation).
        self._stage(record, "null_model", "running")
        self._save(record)
        null_service = ContentHomophilyNullModelService()

        def _perm_progress(done: int) -> None:
            progress["null_permutations_done"] = done
            self._touch_eta(record, done, params["num_permutations"], started)
            if done % 50 == 0:
                self._save(record)

        null_result = null_service.run(
            vectors, {v: labels[v] for v in vectors}, sampler,
            num_permutations=params["num_permutations"], seed=seed,
            max_videos_per_community=params["max_videos_per_community"],
            observed_difference=observed_difference,
            progress=_perm_progress,
            stop_requested=lambda: self._stop_requested(job_id_holder),
        )
        self._stage(record, "null_model", "done")

        # 8. Statistical summary (§19 output contract).
        self._stage(record, "statistical_summary", "running")
        self._save(record)
        total_analyzed = len(selected_texts)
        coverage = (len(selected_texts) / total_analyzed) if total_analyzed else 0.0
        z_score = null_result.z_score
        if z_score is not None and math.isinf(z_score):
            z_score = None  # never serialize inf/NaN (spec §16)
        # When replacement sampling could not recover the full target usable
        # sample we still compute the analysis but flag it honestly.
        status = ("insufficient_sample"
                  if replacement_meta["pairs_dropped"] > 0 else "observed")
        results: dict[str, Any] = {
            "status": status,
            "label": "CONTENT EVIDENCE",
            "within_mean_similarity": within_mean,
            "between_mean_similarity": between_mean,
            "observed_difference": observed_difference,
            "null_mean": null_result.null_mean,
            "null_std": null_result.null_std,
            "z_score": z_score,
            "permutation_p_value": null_result.permutation_p_value,
            "pairs_available_within": within.available,
            "pairs_sampled_within": within.sampled,
            "pairs_available_between": between.available,
            "pairs_sampled_between": between.sampled,
            "sampling_fraction": params["sampling_fraction"],
            "max_pair_cap": params["max_pair_cap"],
            "random_seed": seed,
            "num_permutations": params["num_permutations"],
            "null_permutations_completed": null_result.num_permutations,
            "videos_targeted_for_transcripts": len(needed),
            "videos_with_transcript": total_analyzed,
            "videos_without_transcript": without_transcript,
            "max_transcript_videos": params["max_transcript_videos"],
            "videos_analyzed": len(vectors),
            "sample_videos": sample_videos,
            "sample_roles": sample_role_map,
            "sample_pair_count": len(within_usable) + len(between_usable),
            "transcript_coverage": coverage,
            "pairs_usable_within": len(within_usable),
            "pairs_usable_between": len(between_usable),
            "pairs_original_within": replacement_meta["pairs_original_within"],
            "pairs_original_between": replacement_meta["pairs_original_between"],
            "replacement_attempts": replacement_meta["replacement_attempts"],
            "replacement_successes": replacement_meta["replacement_successes"],
            "replacement_fetches": replacement_meta["replacement_fetches"],
            "replacement_budget": replacement_meta["replacement_budget"],
            "replacement_budget_exhausted": replacement_meta["budget_exhausted"],
            "pairs_dropped_after_replacement": replacement_meta["pairs_dropped"],
            "embedding_model": adapter.model_name,
            "embedding_model_version": adapter.model_version,
            "embeddings_reused": adapter.embeddings_reused,
            "embeddings_generated": adapter.embeddings_generated,
            "embedding_failures": adapter.embedding_failures,
            "analysis_run_id": record["analysis_id"],
            "scope": {"run_id": run_id, "node_count": len(nodes),
                      "edge_count": graph_payload.edge_count},
            "community_algorithm": COMMUNITY_ALGORITHM,
            "chunking_configuration": self._chunking_configuration(),
            "disclaimers": list(CONTENT_HOMOPHILY_DISCLAIMERS),
        }
        if params.get("include_edge_similarity"):
            results["edge_similarity"] = self._edge_similarity(
                vectors, params, seed)
        self._log(record,
                  f"observed difference {observed_difference:+.4f}; "
                  f"z={z_score if z_score is not None else 'undefined'}")
        return results

    def _edge_similarity(self, vectors, params, seed) -> dict[str, Any]:
        """Optional recommendation-edge semantic similarity (spec §13).

        Kept completely SEPARATE from the community-level statistics above.
        """
        rows = self._analytics.edges(
            run_ids=[params["run_id"]] if params.get("run_id") else None,
            video_ids=params.get("video_ids") or None,
        )
        eligible = [
            r for r in rows
            if r.source_video_id in vectors and r.recommended_video_id in vectors
        ]
        target = min(int(len(eligible) * params["sampling_fraction"]),
                     params["max_pair_cap"])
        rng = random.Random(f"{seed}:edges")
        picked = rng.sample(eligible, min(target, len(eligible))) if eligible else []
        pairs = [(r.source_video_id, r.recommended_video_id) for r in picked]
        mean, computed = SemanticSimilarityService.mean_similarity(vectors, pairs)
        return {
            "mean_edge_semantic_similarity": mean,
            "edges_available": len(eligible),
            "edges_sampled": len(pairs),
            "note": "separate from community-level content homophily",
        }

    @staticmethod
    def _chunking_configuration() -> dict[str, Any]:
        try:
            from Ingestion_Pipline.config.settings import ChunkingSettings

            cs = ChunkingSettings()
            return {
                "chunk_size": cs.chunk_size,
                "chunk_overlap": cs.chunk_overlap,
                "encoding_name": cs.encoding_name,
                "implementation": "Ingestion_Pipline.ingestion.chunking.split_text",
            }
        except Exception:  # noqa: BLE001
            return {"implementation": "unavailable"}

    def _insufficient(self, record, params, *, reason: str,
                      videos_without_transcript: int = 0,
                      extra: dict[str, Any] | None = None,
                      status: str = "insufficient_data") -> dict[str, Any]:
        """Small-dataset handling (spec §8): honest, never fabricated zeros."""
        for name in STAGES:
            if record["progress"]["stages"].get(name) == "pending":
                record["progress"]["stages"][name] = "skipped"
        self._log(record, f"insufficient data: {reason}")
        results: dict[str, Any] = {
            "status": status,
            "label": "CONTENT EVIDENCE",
            "reason": reason,
            "within_mean_similarity": None,
            "between_mean_similarity": None,
            "observed_difference": None,
            "null_mean": None,
            "null_std": None,
            "z_score": None,
            "permutation_p_value": None,
            "pairs_available_within": 0,
            "pairs_sampled_within": 0,
            "pairs_available_between": 0,
            "pairs_sampled_between": 0,
            "sampling_fraction": params["sampling_fraction"],
            "max_pair_cap": params["max_pair_cap"],
            "random_seed": params["random_seed"],
            "num_permutations": params["num_permutations"],
            "videos_with_transcript": 0,
            "videos_without_transcript": videos_without_transcript,
            "videos_targeted_for_transcripts": 0,
            "max_transcript_videos": params.get(
                "max_transcript_videos", DEFAULT_MAX_TRANSCRIPT_VIDEOS),
            "transcript_coverage": 0.0,
            "embedding_model": default_embedding_model_name(),
            "embedding_model_version": "1",
            "analysis_run_id": record["analysis_id"],
            "community_algorithm": COMMUNITY_ALGORITHM,
            "disclaimers": list(CONTENT_HOMOPHILY_DISCLAIMERS),
        }
        if extra:
            results.update(extra)
        return results


class OperationCancelled(Exception):
    """Internal: cooperative cancellation honoured at unit boundaries."""

