"""Unit tests for the FreeTranscriptAPI transcript provider (HTTP mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import urllib.error
import urllib.request

from SocialScienceResearch.acquisition.errors import (
    NetworkError,
    RateLimitError,
    TranscriptUnsupportedError,
)
from SocialScienceResearch.acquisition.freetranscriptapi_provider import (
    FreeTranscriptApiProvider,
)
from SocialScienceResearch.domain.enums import TranscriptStatus


class _FakeResp:
    def __init__(self, status: int, body: str, headers: dict | None = None):
        self.status = status
        self._body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body.encode("utf-8")


def _fake_response(status: int, body: str, headers: dict | None = None):
    return _FakeResp(status, body, headers)


def _provider() -> FreeTranscriptApiProvider:
    return FreeTranscriptApiProvider(api_key="test-key", retries=1, backoff=0.01)


def test_200_returns_available_transcript() -> None:
    body = '{"language":"en","title":"T","transcript":[{"text":"hello","start":0.0,"duration":1.0}]}'
    with patch(
        "SocialScienceResearch.acquisition.freetranscriptapi_provider.urllib.request.urlopen",
        return_value=_fake_response(200, body),
    ):
        out = _provider().extract_transcript("dQw4w9WgXcQ")
    assert out.status == TranscriptStatus.AVAILABLE
    assert "hello" in out.content


def test_404_is_missing() -> None:
    with patch(
        "SocialScienceResearch.acquisition.freetranscriptapi_provider.urllib.request.urlopen",
        return_value=_fake_response(404, '{"error":{"code":"video_not_found"}}'),
    ):
        out = _provider().extract_transcript("bad")
    assert out.status == TranscriptStatus.MISSING


def test_429_raises_rate_limit_with_retry_after() -> None:
    err = urllib.error.HTTPError(
        "url", 429, "rate", {"Retry-After": "15"}, None
    )
    with patch(
        "SocialScienceResearch.acquisition.freetranscriptapi_provider.urllib.request.urlopen",
        side_effect=err,
    ):
        with pytest.raises(RateLimitError) as exc:
            _provider().extract_transcript("vid")
    assert exc.value.retry_after == 15.0


def test_500_raises_network_error() -> None:
    with patch(
        "SocialScienceResearch.acquisition.freetranscriptapi_provider.urllib.request.urlopen",
        return_value=_fake_response(500, "boom"),
    ):
        with pytest.raises(NetworkError):
            _provider().extract_transcript("vid")
