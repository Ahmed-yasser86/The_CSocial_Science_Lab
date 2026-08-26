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

from SocialScienceResearch.domain.enums import TranscriptStatus
from SocialScienceResearch.domain.models import TranscriptRecord
from SocialScienceResearch.utils.idgen import new_id, utcnow
from SocialScienceResearch.utils.logger import get_logger

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
    """Chunk one transcript via the EXISTING Ingestion_Pipline splitter."""
    from langchain_core.documents import Document

    from Ingestion_Pipline.config.settings import ChunkingSettings
    from Ingestion_Pipline.ingestion.chunking import split_text

    settings = ChunkingSettings()
    docs = split_text(
        [Document(page_content=text, metadata={"source": source})],
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
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
            return cached
        try:
            if self._embedder is None:
                self._embedder = _default_embedder()
            chunks = _ingestion_chunker(text, source=f"youtube:{video_id}")
            if not chunks:
                self.embedding_failures += 1
                return None
            vectors = self._embedder.embed_documents(chunks)
            if not vectors:
                self.embedding_failures += 1
                return None
            pooled = np.mean(np.asarray(vectors, dtype=float), axis=0)
            self.embeddings_generated += 1
            self._write_cache(video_id, digest, pooled)
            return pooled
        except Exception as exc:  # noqa: BLE001 - a failed video never aborts the run
            logger.warning(
                "content-homophily embedding failed for %s: %s", video_id, exc
            )
            self.embedding_failures += 1
            return None

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
                 embedder=None, embedder_factory=None) -> None:
        from SocialScienceResearch.config.settings import SocialScienceSettings

        self._provider = provider
        self._repos = repos
        self._settings = settings or SocialScienceSettings()
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
        progress["videos_total"] = sum(
            min(len(v), params["max_videos_per_community"]) for v in groups.values()
        )

        # 2. Targeted transcript collection with replacement sampling.
        self._stage(record, "transcript_collection", "running")
        self._save(record)
        selected_texts: dict[str, str] = {}
        without_transcript = 0
        # Per-channel failure tracking: once a channel accumulates more than
        # 7 transcript failures we stop trying its remaining videos (the
        # channel is effectively untranscribable) rather than burning time.
        channel_failures: dict[str, int] = {}
        channel_skipped: set[str] = set()
        # Flatten the selection plan (bounded by max_videos_per_community).
        plan: list[tuple[str, str]] = []  # (community, video_id)
        for community in sorted(groups):
            limit = min(len(groups[community]),
                        params["max_videos_per_community"])
            usable = 0
            for video_id in groups[community]:
                if usable >= limit:
                    break
                plan.append((community, video_id))
        # Concurrent, cancel-aware fetching with bounded workers.
        # Cap at 5 simultaneous linguistic-analysis (transcript) requests so we
        # never overwhelm the upstream provider.
        workers = max(1, min(5, len(plan)))
        processed = 0
        progress["transcripts_in_hand"] = len(selected_texts)
        progress["transcripts_remaining"] = len(plan)
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
            futures = {ex.submit(_fetch_one, item): item for item in plan}
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
                    usable = len(selected_texts)
                    self._log(record, f"transcript loaded: {video_id}")
                else:
                    without_transcript += 1
                    self._log(record,
                              f"transcript unavailable for {video_id}; "
                              "replacement candidate attempted")
                progress["videos_processed"] = processed
                progress["transcripts_in_hand"] = len(selected_texts)
                progress["transcripts_remaining"] = len(plan) - processed
                self._touch_eta(record, processed, len(plan), started)
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

        # 3. Embedding preparation (reuse/generate; on-demand only).
        self._stage(record, "embedding_preparation", "running")
        self._save(record)
        adapter = VideoEmbeddingAdapter(
            self._repos, self._settings.repository.data_dir,
            embedder=self._embedder,
            model_name=getattr(self._embedder, "model_name", None)
            if self._embedder is not None else None,
        )
        vectors: dict[str, np.ndarray] = {}
        for index, video_id in enumerate(sorted(selected_texts)):
            if self._stop_requested(job_id_holder):
                raise OperationCancelled()
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
            self._touch_eta(record, index + 1, len(selected_texts), started)
            self._save(record)
            self._log(record, f"embedding ready: {video_id}")
        progress.pop("current_video", None)
        self._stage(record, "embedding_preparation", "done")
        if len(vectors) < 2:
            return self._insufficient(
                record, params,
                reason="fewer than two successful embeddings",
                videos_without_transcript=without_transcript)

        eligible_groups = {
            c: [v for v in members if v in vectors]
            for c, members in groups.items()
        }
        eligible_groups = {c: m for c, m in eligible_groups.items() if len(m) >= 2}
        embedded_n = len(vectors)
        within_available_total = sum(
            math.comb(len(m), 2) for m in eligible_groups.values()
        )
        between_available_total = (
            math.comb(embedded_n, 2) - within_available_total
        )
        if within_available_total < 1 and between_available_total < 1:
            return self._insufficient(record, params,
                                      reason="not enough embedded videos",
                                      videos_without_transcript=without_transcript)

        sampler = PairSamplingService(params["sampling_fraction"],
                                      params["max_pair_cap"])
        seed = params["random_seed"]

        # 4. Pair sampling (seeded; balanced within; stratified between).
        self._stage(record, "pair_sampling", "running")
        self._save(record)
        rng = random.Random(seed)
        within = sampler.sample_within(eligible_groups, rng)
        between = sampler.sample_between(eligible_groups, rng)
        self._log(record,
                  f"pairs sampled: within {within.sampled}/{within.available}, "
                  f"between {between.sampled}/{between.available}")
        self._stage(record, "pair_sampling", "done")

        # 5. Similarity calculation.
        self._stage(record, "similarity_calculation", "running")
        self._save(record)
        within_mean, within_n = SemanticSimilarityService.mean_similarity(
            vectors, within.pairs)
        between_mean, between_n = SemanticSimilarityService.mean_similarity(
            vectors, between.pairs)
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
        results: dict[str, Any] = {
            "status": "observed",
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
            "videos_with_transcript": total_analyzed,
            "videos_without_transcript": without_transcript,
            "transcript_coverage": coverage,
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
                      extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """Small-dataset handling (spec §8): honest, never fabricated zeros."""
        for name in STAGES:
            if record["progress"]["stages"].get(name) == "pending":
                record["progress"]["stages"][name] = "skipped"
        self._log(record, f"insufficient data: {reason}")
        results: dict[str, Any] = {
            "status": "insufficient_data",
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

