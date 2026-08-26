"""Mutable runtime scraper configuration.

Unlike the frozen ``ScraperSettings``, this can be updated via the API
without restarting the server.  The layer scrape service reads from this
object so researchers can tune speed vs. safety on the fly.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RuntimeScraperConfig:
    """Mutable scraper settings that the UI can update at runtime."""

    request_delay_seconds: float = 0.25
    enrichment_concurrency: int = 6
    socket_timeout: float = 30.0
    retries: int = 3
    retry_backoff: float = 2.0
    max_enrich_targets: int = 100
    transcript_provider: str = "ytdlp"

    def to_dict(self) -> dict:
        return {
            "request_delay_seconds": self.request_delay_seconds,
            "enrichment_concurrency": self.enrichment_concurrency,
            "socket_timeout": self.socket_timeout,
            "retries": self.retries,
            "retry_backoff": self.retry_backoff,
            "max_enrich_targets": self.max_enrich_targets,
            "transcript_provider": self.transcript_provider,
        }

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if value is not None and hasattr(self, key):
                setattr(self, key, value)


PRESETS: dict[str, dict] = {
    "fast": {
        "label": "Fast",
        "description": (
            "High concurrency (10 workers), minimal delay (0.05s). Best for "
            "small crawls; higher chance of YouTube rate-limiting on big ones."
        ),
        "request_delay_seconds": 0.05,
        "enrichment_concurrency": 10,
        "socket_timeout": 20.0,
        "max_enrich_targets": 200,
    },
    "balanced": {
        "label": "Balanced",
        "description": (
            "Moderate speed (6 workers, 0.2s delay). Good default that "
            "usually stays under YouTube's rate-limit radar."
        ),
        "request_delay_seconds": 0.2,
        "enrichment_concurrency": 6,
        "socket_timeout": 25.0,
        "max_enrich_targets": 100,
    },
    "careful": {
        "label": "Careful",
        "description": (
            "Conservative pacing (3 workers, 0.75s delay). Slowest but "
            "safest against rate limits; use for large overnight crawls."
        ),
        "request_delay_seconds": 0.75,
        "enrichment_concurrency": 3,
        "socket_timeout": 45.0,
        "max_enrich_targets": 50,
    },
}
