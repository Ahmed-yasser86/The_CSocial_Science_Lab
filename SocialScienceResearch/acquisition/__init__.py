"""Acquisition layer: provider interface, yt-dlp adapter, normalization."""

from __future__ import annotations

from .base import AcquisitionProvider, ChannelExtract, TranscriptExtract
from .errors import (
    AcquisitionError,
    CommentCollectionError,
    InvalidURLError,
    LibraryError,
    LiveEventSkipError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    RecommendationUnsupportedError,
    TranscriptUnsupportedError,
    ValidationError,
    VideoUnavailableError,
    build_error,
    classify_exception,
)
from .retry import retry_policy
from .yt_dlp_adapter import YtDlpAcquisitionProvider

__all__ = [
    "AcquisitionError",
    "AcquisitionProvider",
    "ChannelExtract",
    "CommentCollectionError",
    "InvalidURLError",
    "LibraryError",
    "LiveEventSkipError",
    "NetworkError",
    "NotFoundError",
    "RateLimitError",
    "RecommendationUnsupportedError",
    "TranscriptExtract",
    "TranscriptUnsupportedError",
    "ValidationError",
    "VideoUnavailableError",
    "YtDlpAcquisitionProvider",
    "build_error",
    "classify_exception",
    "retry_policy",
]
