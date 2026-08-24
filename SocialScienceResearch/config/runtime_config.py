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

    request_delay_seconds: float = 0.5
    enrichment_concurrency: int = 4
    socket_timeout: float = 30.0
    retries: int = 3
    retry_backoff: float = 2.0
    max_enrich_targets: int = 100

    def to_dict(self) -> dict:
        return {
            "request_delay_seconds": self.request_delay_seconds,
            "enrichment_concurrency": self.enrichment_concurrency,
            "socket_timeout": self.socket_timeout,
            "retries": self.retries,
            "retry_backoff": self.retry_backoff,
            "max_enrich_targets": self.max_enrich_targets,
        }

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if value is not None and hasattr(self, key):
                setattr(self, key, value)


PRESETS: dict[str, dict] = {
    "fast": {
        "label": "Fast",
        "description": "High concurrency, minimal delay. Best for small crawls.",
        "request_delay_seconds": 0.05,
        "enrichment_concurrency": 10,
        "socket_timeout": 20.0,
        "max_enrich_targets": 200,
    },
    "balanced": {
        "label": "Balanced",
        "description": "Moderate speed with reasonable safety.",
        "request_delay_seconds": 0.2,
        "enrichment_concurrency": 6,
        "socket_timeout": 25.0,
        "max_enrich_targets": 100,
    },
    "default": {
        "label": "Default",
        "description": "Safe defaults for most use cases.",
        "request_delay_seconds": 0.5,
        "enrichment_concurrency": 4,
        "socket_timeout": 30.0,
        "max_enrich_targets": 100,
    },
    "slow": {
        "label": "Slow",
        "description": "Conservative pacing. Avoids rate limits.",
        "request_delay_seconds": 1.0,
        "enrichment_concurrency": 2,
        "socket_timeout": 45.0,
        "max_enrich_targets": 50,
    },
}
