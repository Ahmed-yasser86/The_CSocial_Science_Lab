"""Scraper configuration endpoints.

Lets the UI read and update runtime scraper settings (speed/concurrency)
without restarting the server.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


class ScraperConfigPayload(BaseModel):
    request_delay_seconds: float | None = Field(None, ge=0, le=30)
    enrichment_concurrency: int | None = Field(None, ge=1, le=20)
    socket_timeout: float | None = Field(None, ge=5, le=120)
    retries: int | None = Field(None, ge=0, le=10)
    retry_backoff: float | None = Field(None, ge=0, le=30)
    max_enrich_targets: int | None = Field(None, ge=0, le=2000)
    transcript_provider: str | None = Field(None, pattern="^(ytdlp|freetranscriptapi)$")


class PresetRequest(BaseModel):
    preset: str


@router.get(
    "/scraper/config",
    tags=["scraper"],
)
def get_scraper_config(request: Request) -> dict[str, Any]:
    """Return current runtime scraper settings."""
    config = request.app.state.runtime_scraper_config
    return config.to_dict()


@router.put(
    "/scraper/config",
    tags=["scraper"],
)
def update_scraper_config(request: Request, body: ScraperConfigPayload) -> dict[str, Any]:
    """Update runtime scraper settings (only provided fields are changed)."""
    config = request.app.state.runtime_scraper_config
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    config.update(**updates)
    return config.to_dict()


@router.post(
    "/scraper/config/preset",
    tags=["scraper"],
)
def apply_preset(request: Request, body: PresetRequest) -> dict[str, Any]:
    """Apply a named speed preset (fast / balanced / default / slow)."""
    from SocialScienceResearch.config.runtime_config import PRESETS

    preset = PRESETS.get(body.preset)
    if preset is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown preset '{body.preset}'. Available: {list(PRESETS.keys())}",
        )
    config = request.app.state.runtime_scraper_config
    config.update(
        request_delay_seconds=preset["request_delay_seconds"],
        enrichment_concurrency=preset["enrichment_concurrency"],
        socket_timeout=preset["socket_timeout"],
    )
    return {**config.to_dict(), "applied_preset": body.preset}
