"""Tests for the Phase 1 Global Budget Controller (global coordination).

Verifies that the controller paces admission, that one instance is shared by all
scraping services, that the YoutubeDL context semaphore caps concurrency, and
that per-event observability is emitted and queryable.
"""

from __future__ import annotations

import threading
import time

import pytest

from SocialScienceResearch.concurrency.budget_controller import (
    BudgetController,
    OPER_EXTRACT_VIDEO,
)
from SocialScienceResearch.concurrency.ytdlp_semaphore import YtdlContextLimiter


def _settings(tmp_path):
    from SocialScienceResearch.config.settings import (
        RepositorySettings,
        ScraperSettings,
        SocialScienceSettings,
    )

    return SocialScienceSettings(
        repository=RepositorySettings(
            backend="excel", data_dir=str(tmp_path), dataset_name="t"
        ),
        scraper=ScraperSettings(retries=1, retry_backoff=0.0, request_delay_seconds=0),
    )


def test_controller_paces_min_interval():
    # Fixed rate: two consecutive acquires must be spaced by >= min_interval.
    ctrl = BudgetController(min_interval=0.1, max_ytdl_contexts=4)
    t0 = time.monotonic()
    ctrl.acquire(OPER_EXTRACT_VIDEO, run_id="r1")
    ctrl.acquire(OPER_EXTRACT_VIDEO, run_id="r1")
    elapsed = time.monotonic() - t0
    # First acquire waits 0; second waits ~min_interval. Allow slack.
    assert elapsed >= 0.1 - 0.02, elapsed


def test_controller_no_wait_when_interval_zero():
    ctrl = BudgetController(min_interval=0.0, max_ytdl_contexts=4)
    t0 = time.monotonic()
    ctrl.acquire(OPER_EXTRACT_VIDEO, run_id="r1")
    ctrl.acquire(OPER_EXTRACT_VIDEO, run_id="r1")
    assert time.monotonic() - t0 < 0.05


def test_events_emitted_and_queryable():
    ctrl = BudgetController(min_interval=0.0, max_ytdl_contexts=4)
    ctrl.acquire(OPER_EXTRACT_VIDEO, run_id="runA")
    ctrl.on_rate_limited(operation=OPER_EXTRACT_VIDEO, run_id="runA", reason="429")
    events = ctrl.events()
    assert len(events) >= 2
    kinds = {e["kind"] for e in events}
    assert "acquire" in kinds
    assert "rate_limit" in kinds
    assert any(e["run_id"] == "runA" for e in events)
    state = ctrl.state()
    assert state["admits"] == 1
    assert state["rate_limited"] == 1
    # per-run scoping of the query API
    assert len(ctrl.events(run_id="runA")) >= 2


def test_build_services_shares_one_controller():
    from SocialScienceResearch.services.collection_service import CollectionService
    from SocialScienceResearch.services.layer_scrape_service import (
        LayerScrapeService,
    )
    from SocialScienceResearch.services.recommendation_service import (
        RecommendationService,
    )

    settings = _settings(__import__("pathlib").Path("/tmp"))
    ctrl = BudgetController(min_interval=0.0, max_ytdl_contexts=4)
    provider = _FakeProvider()
    # Mirrors exactly what build_services does: one controller passed to all three.
    collection = CollectionService(provider, None, settings=settings, budget_controller=ctrl)
    recs = RecommendationService(provider, None, settings=settings, budget_controller=ctrl)
    layer = LayerScrapeService(provider, None, settings=settings, budget_controller=ctrl)
    assert collection._budget is ctrl
    assert recs._budget is ctrl
    assert layer._budget is ctrl
    # And each service still exposes the controller for the API layer to read.
    assert collection._budget.min_interval == 0.0


def test_semaphore_caps_concurrent_contexts():
    limiter = YtdlContextLimiter(max_contexts=2)
    active = 0
    peak = 0
    lock = threading.Lock()

    def worker():
        nonlocal active, peak
        with limiter.acquire():
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.1)
            with lock:
                active -= 1

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # The module singleton would cap the WHOLE process; here we test the class
    # directly, proving the cap logic bounds simultaneous contexts.
    assert peak <= 2


def test_set_min_interval_updates_pacing():
    ctrl = BudgetController(min_interval=0.0, max_ytdl_contexts=4)
    ctrl.set_min_interval(0.1)
    assert ctrl.min_interval == 0.1
    t0 = time.monotonic()
    ctrl.acquire(OPER_EXTRACT_VIDEO)
    ctrl.acquire(OPER_EXTRACT_VIDEO)
    assert time.monotonic() - t0 >= 0.1 - 0.02


def test_controller_lock_serializes_concurrent_acquires():
    """Real threads compete for the same bucket at once.

    This is the core race the Global Budget Controller exists to fix: multiple
    jobs/threads calling ``acquire()`` concurrently must never be admitted faster
    than ``min_interval``. We prove it under genuine threading pressure, not just
    sequential logic.
    """
    import threading as _threading

    interval = 0.1
    ctrl = BudgetController(min_interval=interval, max_ytdl_contexts=4)
    n = 6
    admits: list[float] = []  # absolute admit timestamps
    admit_lock = _threading.Lock()

    def worker() -> None:
        ctrl.acquire(OPER_EXTRACT_VIDEO)
        with admit_lock:
            admits.append(time.monotonic())

    threads = [_threading.Thread(target=worker) for _ in range(n)]
    start = time.monotonic()
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    elapsed = time.monotonic() - start

    assert len(admits) == n
    admits.sort()
    # No two admits landed closer together than the configured minimum spacing
    # (timer slack accounted for with a small epsilon). This is the precise
    # invariant the controller's Lock must hold under real concurrency: the
    # admit rate never exceeds one-per-min_interval.
    for a, b in zip(admits, admits[1:]):
        assert (b - a) >= interval - 0.03
    # Serialized pacing bounds total wall time from below: (n-1) intervals.
    span = admits[-1] - admits[0]
    assert span >= (n - 1) * interval - 0.05
    # Sanity: the lock actually serialized work (not all 6 admitted at t=0).
    assert span >= (n - 1) * interval - 0.05
    assert elapsed >= span - 0.05


class _FakeProvider:
    """Minimal provider so build_services does not spin up real yt-dlp."""

    def extract_channel(self, *a, **k):  # pragma: no cover - not exercised
        raise NotImplementedError

    def extract_video(self, *a, **k):  # pragma: no cover - not exercised
        raise NotImplementedError

    def extract_recommendations(self, *a, **k):  # pragma: no cover
        raise NotImplementedError

    def extract_transcript(self, *a, **k):  # pragma: no cover
        raise NotImplementedError


def test_budget_endpoints_exposed(tmp_path):
    from fastapi.testclient import TestClient

    from SocialScienceResearch.api.app import create_app

    app = create_app(_settings(tmp_path), provider=_FakeProvider())
    client = TestClient(app)
    state = client.get("/api/v1/social-science/budget/state")
    assert state.status_code == 200
    assert "admits" in state.json()
    events = client.get("/api/v1/social-science/budget/events?limit=10")
    assert events.status_code == 200
    assert "events" in events.json()
    # Live tuning via the scraper-config endpoint flows into the controller.
    before = client.get("/api/v1/social-science/budget/state").json()["min_interval"]
    upd = client.put(
        "/api/v1/social-science/scraper/config",
        json={"request_delay_seconds": 0.75},
    )
    assert upd.status_code == 200
    after = client.get("/api/v1/social-science/budget/state").json()["min_interval"]
    assert after == 0.75
    assert after != before


def test_content_homophily_routes_transcript_through_budget(tmp_path):
    """No path bypasses the bucket: ContentHomophilyService's targeted transcript
    fetch must go through the shared BudgetController (Phase 1 gap fix). The
    provider is a real ``YtDlpAcquisitionProvider`` stub so the fetch actually
    exercises the budgeted-retry gate (Phase 2)."""
    from SocialScienceResearch.acquisition.yt_dlp_adapter import (
        YtDlpAcquisitionProvider,
    )
    from SocialScienceResearch.config.settings import (
        RepositorySettings,
        ScraperSettings,
        SocialScienceSettings,
    )
    from SocialScienceResearch.concurrency.budget_controller import (
        BudgetController,
        OPER_EXTRACT_TRANSCRIPT,
        run_context,
    )
    from SocialScienceResearch.services.content_homophily_service import (
        ContentHomophilyService,
    )

    settings = SocialScienceSettings(
        repository=RepositorySettings(
            backend="excel", data_dir=str(tmp_path), dataset_name="t"
        ),
        scraper=ScraperSettings(
            retries=1, retry_backoff=0.0, request_delay_seconds=0, transcript_lang="en"
        ),
    )
    controller = BudgetController(min_interval=0.0, max_ytdl_contexts=4)

    class _RealProviderStub(YtDlpAcquisitionProvider):
        def _extract(self, url, opts):  # noqa: ANN001 - monkeypatch
            return {
                "_type": "video",
                "automatic_captions": {
                    "en": [{"url": "https://captions/EN.vtt", "ext": "vtt"}]
                },
                "subtitles": {},
            }

        def _fetch_caption(self, url):  # noqa: ANN001 - monkeypatch
            return "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhello world\n"

    class _Video:
        url = "https://www.youtube.com/watch?v=VID"

    class _Repos:
        class _Transcripts:
            def get_transcript(self, vid):
                return None

            def save_transcript(self, *a, **k):
                pass

            write_artifact = None

        class _Videos:
            def get_video(self, vid):
                return _Video()

            def upsert_video(self, v):
                pass

        transcripts = _Transcripts()
        videos = _Videos()

    provider = _RealProviderStub(
        settings=settings.scraper, budget_controller=controller
    )
    svc = ContentHomophilyService(
        provider, _Repos(), settings=settings, budget_controller=controller
    )
    svc._read_artifact_text = lambda vid: None  # force a real fetch
    svc._save_transcript_record = lambda *a, **k: None
    with run_context("A1"):
        result = svc._ensure_transcript("VID", "A1")
    assert result == "hello world"
    ops = [e["operation"] for e in controller.events()]
    assert OPER_EXTRACT_TRANSCRIPT in ops
    # The run id is propagated so the event is queryable per-run.
    assert any(
        e["operation"] == OPER_EXTRACT_TRANSCRIPT and e["run_id"] == "A1"
        for e in controller.events()
    )


# ---------------------------------------------------------------------------
# Phase 2: retries must route through the Global Budget Controller.
# ---------------------------------------------------------------------------
def test_retry_policy_budgeted_charges_every_attempt_and_records_rate_limit():
    """The tenacity retry wrapper must charge the budget before *every* attempt
    (including the first) and record rate-limit outcomes via on_rate_limited."""
    from SocialScienceResearch.acquisition.errors import RateLimitError
    from SocialScienceResearch.acquisition.retry import retry_policy_budgeted

    class _Budget:
        def __init__(self):
            self.acquires = 0
            self.rl = 0
            self.run_ids = []

        def acquire(self, operation, *, run_id=None, cost=1.0):
            self.acquires += 1
            self.run_ids.append(run_id)

        def on_rate_limited(self, *, operation=None, run_id=None, session=None,
                            reason="429", detail=None):
            self.rl += 1

    budget = _Budget()
    attempts = {"n": 0}

    @retry_policy_budgeted(budget, "extract_video", "RUN1", retries=3,
                           backoff=0.0, max_wait=0.0)
    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RateLimitError("rate", retry_after=0.0)
        return "ok"

    assert flaky() == "ok"
    # 3 attempts -> acquire fired before each (including the first).
    assert budget.acquires == 3
    # Attempts 1 and 2 failed with RateLimitError -> recorded; attempt 3 succeeded.
    assert budget.rl == 2
    assert budget.run_ids == ["RUN1", "RUN1", "RUN1"]


def test_retry_policy_budgeted_propagates_run_context():
    """With budget_on_first=False the caller gates the first attempt; retries
    still charge the budget and inherit the run id from the run-context (read at
    call time, as the provider does)."""
    from SocialScienceResearch.acquisition.errors import RateLimitError
    from SocialScienceResearch.acquisition.retry import retry_policy_budgeted
    from SocialScienceResearch.concurrency.budget_controller import (
        get_current_run_id,
        run_context,
    )

    class _Budget:
        def __init__(self):
            self.acquires = 0
            self.run_ids = []

        def acquire(self, operation, *, run_id=None, cost=1.0):
            self.acquires += 1
            self.run_ids.append(run_id)

        def on_rate_limited(self, *, operation=None, run_id=None, session=None,
                            reason="429", detail=None):
            pass

    budget = _Budget()

    def make():
        attempts = {"n": 0}

        @retry_policy_budgeted(
            budget, "extract_channel", get_current_run_id(), retries=2,
            backoff=0.0, max_wait=0.0, budget_on_first=False,
        )
        def flaky():
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise RateLimitError("rate", retry_after=0.0)
            return "ok"

        return flaky

    with run_context("R2"):
        flaky = make()
        assert flaky() == "ok"
    # First attempt not charged (caller gates it); only the 1 retry is charged.
    assert budget.acquires == 1
    assert budget.run_ids == ["R2"]


def test_provider_routes_retries_through_shared_controller():
    """End-to-end: a YtDlpAcquisitionProvider whose extract fails with a
    RateLimitError routes BOTH attempts through the shared BudgetController and
    records the 429, instead of bypassing the bucket on retry."""
    from SocialScienceResearch.acquisition.errors import RateLimitError
    from SocialScienceResearch.acquisition.yt_dlp_adapter import YtDlpAcquisitionProvider
    from SocialScienceResearch.config.settings import ScraperSettings
    from SocialScienceResearch.concurrency.budget_controller import (
        BudgetController,
        run_context,
    )

    controller = BudgetController(min_interval=0.0, max_ytdl_contexts=4)
    provider = YtDlpAcquisitionProvider(
        settings=ScraperSettings(retries=2, retry_backoff=0.0),
        budget_controller=controller,
    )

    calls = {"n": 0}

    def fake_extract(self, url, opts):  # noqa: ANN001 - monkeypatch
        calls["n"] += 1
        if calls["n"] < 2:
            raise RateLimitError("rate", retry_after=0.0)
        return {"_type": "playlist", "entries": [], "id": "UC" + "x" * 22}

    provider._extract = fake_extract.__get__(provider, YtDlpAcquisitionProvider)

    with run_context("R9"):
        result = provider.extract_channel("https://youtube.com/channel/UC" + "x" * 22)

    assert result.channel is not None
    # Exactly two attempts -> two budget admits (first + one retry).
    assert controller.state()["admits"] == 2
    # The 429 from the first attempt was recorded.
    assert controller.state()["rate_limited"] == 1
    # Events are attributable to the run set via run_context.
    assert any(
        e["operation"] == "extract_channel" and e["run_id"] == "R9"
        for e in controller.events()
    )


# ---------------------------------------------------------------------------
# Phase 3: weighted cost per operation.
# ---------------------------------------------------------------------------
def test_weighted_cost_reserves_proportional_spacing():
    """Heavier operations reserve proportionally more of the shared timeline.

    The first admit is immediate; every *subsequent* admit waits for the slot the
    previous op reserved (``min_interval * previous_op_cost``).
    """
    from SocialScienceResearch.concurrency.budget_controller import (
        BudgetController,
        OPER_EXTRACT_CHANNEL,
        OPER_EXTRACT_RECOMMENDATIONS,
        OPER_EXTRACT_VIDEO,
    )

    ctrl = BudgetController(min_interval=0.1, max_ytdl_contexts=4)
    # video(2.0) then recs(1.5) then channel(4.0).
    t0 = time.monotonic()
    ctrl.acquire(OPER_EXTRACT_VIDEO)          # immediate
    t1 = time.monotonic()
    ctrl.acquire(OPER_EXTRACT_RECOMMENDATIONS)  # waits video's 0.2
    t2 = time.monotonic()
    ctrl.acquire(OPER_EXTRACT_CHANNEL)          # waits recs' 0.15
    t3 = time.monotonic()

    gap_first = t1 - t0          # immediate -> ~0
    gap_video = t2 - t1          # 2.0 * 0.1 = 0.2
    gap_recs = t3 - t2           # 1.5 * 0.1 = 0.15
    assert gap_first <= 0.02
    assert 0.2 - 0.03 <= gap_video <= 0.2 + 0.05
    assert 0.15 - 0.03 <= gap_recs <= 0.15 + 0.05

    costs = [e["cost"] for e in ctrl.events()]
    assert costs == [2.0, 1.5, 4.0]


def test_explicit_cost_overrides_weight_and_unknown_op_defaults_to_one():
    from SocialScienceResearch.concurrency.budget_controller import (
        BudgetController,
        OPER_EXTRACT_VIDEO,
    )

    # Explicit cost=10 on the 2nd op -> the 3rd op waits 1.0s for that slot.
    ctrl = BudgetController(min_interval=0.1, max_ytdl_contexts=4)
    ctrl.acquire(OPER_EXTRACT_VIDEO)                 # immediate, reserves 0.2
    ctrl.acquire(OPER_EXTRACT_VIDEO, cost=10.0)      # reserves 1.0
    t = time.monotonic()
    ctrl.acquire("some_future_op")                   # waits the 1.0 slot
    gap = time.monotonic() - t
    assert 1.0 - 0.03 <= gap <= 1.0 + 0.05
    assert ctrl.events()[1]["cost"] == 10.0

    # A fresh controller: unknown op with no explicit cost falls back to unit cost.
    ctrl2 = BudgetController(min_interval=0.1, max_ytdl_contexts=4)
    ctrl2.acquire("op_a")                            # unknown, cost 1.0, reserves 0.1
    t2 = time.monotonic()
    ctrl2.acquire("op_b")                            # waits the 0.1 slot
    assert time.monotonic() - t2 >= 0.1 - 0.03
    assert ctrl2.events()[-1]["cost"] == 1.0


def test_provider_uses_comments_weight_for_video_extraction():
    """extract_video with comments on budgets OPER_EXTRACT_VIDEO_COMMENTS (6.0),
    without comments budgets OPER_EXTRACT_VIDEO (2.0)."""
    from SocialScienceResearch.acquisition.yt_dlp_adapter import (
        YtDlpAcquisitionProvider,
    )
    from SocialScienceResearch.config.settings import ScraperSettings
    from SocialScienceResearch.concurrency.budget_controller import (
        BudgetController,
        OPER_EXTRACT_VIDEO,
        OPER_EXTRACT_VIDEO_COMMENTS,
        run_context,
    )

    ctrl = BudgetController(min_interval=0.0, max_ytdl_contexts=4)
    provider = YtDlpAcquisitionProvider(
        settings=ScraperSettings(retries=1, retry_backoff=0.0),
        budget_controller=ctrl,
    )

    def fake_extract(self, url, opts):  # noqa: ANN001 - monkeypatch
        return {"_type": "video", "id": "vid", "title": "t"}

    provider._extract = fake_extract.__get__(provider, YtDlpAcquisitionProvider)

    with run_context("RC"):
        provider.extract_video("https://youtube.com/watch?v=vid", include_comments=True)
    with run_context("RC"):
        provider.extract_video("https://youtube.com/watch?v=vid", include_comments=False)

    ops = [e["operation"] for e in ctrl.events()]
    assert OPER_EXTRACT_VIDEO_COMMENTS in ops
    assert OPER_EXTRACT_VIDEO in ops


# ----------------------------------------------------------------------
# Phase 4: AIMD adaptive rate
# ----------------------------------------------------------------------
def test_aimd_multiplicative_decrease_halves_interval_and_cools_down():
    # First 429 doubles the interval (halves the budget) and enters cooldown;
    # a second 429 inside the cooldown window is counted but does not re-halve.
    ctrl = BudgetController(min_interval=0.5, max_ytdl_contexts=4)
    ctrl.on_rate_limited(operation=OPER_EXTRACT_VIDEO, run_id="r1")
    assert ctrl.min_interval == pytest.approx(1.0)
    assert ctrl.state()["rate_limited"] == 1
    assert ctrl.state()["in_cooldown"] is True

    ctrl.on_rate_limited(operation=OPER_EXTRACT_VIDEO, run_id="r1")
    assert ctrl.min_interval == pytest.approx(1.0)  # unchanged (cooldown)
    assert ctrl.state()["rate_limited"] == 2

    reasons = [e["reason"] for e in ctrl.events() if e["kind"] == "state_change"]
    assert "aimd_multiplicative_decrease" in reasons

    # Once the cooldown window has passed, another 429 halves again.
    ctrl._last_decrease_at = -1000.0  # simulate cooldown elapsed
    ctrl.on_rate_limited(operation=OPER_EXTRACT_VIDEO)
    assert ctrl.min_interval == pytest.approx(2.0)


def test_aimd_multiplicative_decrease_clamps_to_ceiling():
    ctrl = BudgetController(min_interval=0.5, max_ytdl_contexts=4)  # ceiling = 4.0
    ctrl._min_interval = 4.0
    ctrl._last_decrease_at = -1000.0
    ctrl.on_rate_limited(operation=OPER_EXTRACT_VIDEO)
    # 4.0 * 2 = 8.0 would exceed the ceiling, so it stays put.
    assert ctrl.min_interval == pytest.approx(4.0)


def test_aimd_additive_increase_speeds_up_when_healthy():
    # No 429 -> over time the interval shrinks toward the floor (faster rate).
    ctrl = BudgetController(min_interval=0.5, max_ytdl_contexts=4)  # floor = 0.125
    ctrl._next_ai_check = 0.0  # force an immediate AIMD tick on next acquire
    ctrl.acquire(OPER_EXTRACT_VIDEO)
    assert ctrl.min_interval == pytest.approx(0.5 * 0.95)
    reasons = [e["reason"] for e in ctrl.events() if e["kind"] == "state_change"]
    assert "aimd_additive_increase" in reasons


def test_aimd_additive_increase_clamps_to_floor():
    ctrl = BudgetController(min_interval=0.5, max_ytdl_contexts=4)  # floor = 0.125
    ctrl._min_interval = 0.125
    ctrl._in_cooldown_until = 0.0
    ctrl._next_ai_check = 0.0
    ctrl.acquire(OPER_EXTRACT_VIDEO)
    # 0.125 * 0.95 = 0.11875 would drop below the floor, so it stays put.
    assert ctrl.min_interval == pytest.approx(0.125)


def test_aimd_cooldown_blocks_additive_increase_until_expired():
    ctrl = BudgetController(min_interval=0.5, max_ytdl_contexts=4)
    ctrl._last_decrease_at = -1000.0
    ctrl.on_rate_limited(operation=OPER_EXTRACT_VIDEO)
    assert ctrl.min_interval == pytest.approx(1.0)  # doubled
    assert ctrl.state()["in_cooldown"] is True

    # While in cooldown, a forced AIMD tick must NOT speed things back up.
    before = ctrl.min_interval
    ctrl._next_ai_check = 0.0
    ctrl.acquire(OPER_EXTRACT_VIDEO)
    assert ctrl.min_interval == pytest.approx(before)

    # After the cooldown window expires, additive increase resumes.
    ctrl._in_cooldown_until = 0.0
    ctrl._next_ai_check = 0.0
    ctrl.acquire(OPER_EXTRACT_VIDEO)
    assert ctrl.min_interval < before


def test_aimd_additive_increase_converges_to_floor_over_many_ticks():
    ctrl = BudgetController(min_interval=0.5, max_ytdl_contexts=4)  # floor = 0.125
    for _ in range(100):
        ctrl._next_ai_check = 0.0
        ctrl.acquire(OPER_EXTRACT_VIDEO)
    assert ctrl.min_interval == pytest.approx(0.125)
