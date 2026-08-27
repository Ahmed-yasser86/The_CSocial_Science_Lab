"""Mutable runtime scraper configuration.

Unlike the frozen ``ScraperSettings``, this can be updated via the API
without restarting the server.  The layer scrape service reads from this
object so researchers can tune speed vs. safety on the fly.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


# Proxy fields persisted to disk independently of the rest of the config so the
# user's credentials survive a server restart (and are never logged verbatim).
_PROXY_KEYS = (
    "proxy_enabled",
    "proxy_host",
    "proxy_port",
    "proxy_username",
    "proxy_password",
    "proxy_verify",
    "proxy_session",
    "youtube_cookies_mode",
    "youtube_cookies_browser",
    "youtube_cookies_path",
)
_proxy_path: str | None = None


def init_proxy_persistence(data_dir: str) -> None:
    """Point proxy persistence at ``<data_dir>/proxy_config.json``."""
    global _proxy_path
    _proxy_path = os.path.join(data_dir, "proxy_config.json")


def load_proxy_fields(config: "RuntimeScraperConfig") -> None:
    """Overlay any persisted proxy credentials onto ``config``."""
    if not _proxy_path or not os.path.exists(_proxy_path):
        return
    try:
        with open(_proxy_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return
    for key, value in data.items():
        if key in _PROXY_KEYS and hasattr(config, key):
            setattr(config, key, value)


def save_proxy_fields(config: "RuntimeScraperConfig") -> None:
    """Persist only the proxy fields to disk (best-effort)."""
    if not _proxy_path:
        return
    try:
        with open(_proxy_path, "w", encoding="utf-8") as fh:
            json.dump({k: getattr(config, k) for k in _PROXY_KEYS}, fh)
    except OSError:
        pass


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
    # --- Proxy (Decodo / rotating residential) ---
    proxy_enabled: bool = False
    proxy_host: str = ""
    proxy_port: int = 0
    proxy_username: str = ""
    proxy_password: str = ""
    proxy_verify: bool = True
    # Decodo sticky session id; appended to the username as `-session-<id>` so
    # the egress IP stays constant across requests (avoids YouTube IP hopping).
    proxy_session: str = ""
    # YouTube authentication cookies - required to clear the "Sign in to confirm
    # you're not a bot" challenge that even clean proxy IPs receive.
    #   "none"   -> no cookies
    #   "browser"-> read live cookies from a local browser (cookiesfrombrowser)
    #   "file"   -> load a Netscape cookies.txt from youtube_cookies_path
    youtube_cookies_mode: str = "none"
    youtube_cookies_browser: str = "chrome"
    youtube_cookies_path: str = ""

    def to_dict(self) -> dict:
        return {
            "request_delay_seconds": self.request_delay_seconds,
            "enrichment_concurrency": self.enrichment_concurrency,
            "socket_timeout": self.socket_timeout,
            "retries": self.retries,
            "retry_backoff": self.retry_backoff,
            "max_enrich_targets": self.max_enrich_targets,
            "transcript_provider": self.transcript_provider,
            "proxy_enabled": self.proxy_enabled,
            "proxy_host": self.proxy_host,
            "proxy_port": self.proxy_port,
            "proxy_username": self.proxy_username,
            "proxy_password": self.proxy_password,
            "proxy_verify": self.proxy_verify,
            "proxy_session": self.proxy_session,
            "youtube_cookies_mode": self.youtube_cookies_mode,
            "youtube_cookies_browser": self.youtube_cookies_browser,
            "youtube_cookies_path": self.youtube_cookies_path,
        }

    def proxy_url(self) -> str | None:
        """Build the ``http://user:pass@host:port`` URL yt-dlp/requests accept."""
        if not self.proxy_enabled or not self.proxy_host or not self.proxy_port:
            return None
        auth = ""
        if self.proxy_username:
            user = self.proxy_username
            if self.proxy_session:
                user = f"{user}-session-{self.proxy_session}"
            auth = f"{user}:{self.proxy_password}@"
        return f"http://{auth}{self.proxy_host}:{self.proxy_port}"

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if value is None and key != "proxy_password":
                continue
            if hasattr(self, key):
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
