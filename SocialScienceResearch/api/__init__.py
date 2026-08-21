"""HTTP API layer (FastAPI) for the SocialScienceResearch module."""

from __future__ import annotations

from .app import create_app

__all__ = ["create_app"]
