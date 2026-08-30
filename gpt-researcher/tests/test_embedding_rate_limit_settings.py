"""Tests for the embedding rate-limit settings persistence (backend config)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from server.embedding_rate_limit import (  # noqa: E402
    load_embedding_rate_limits,
    save_embedding_rate_limits,
)


def test_save_writes_env_and_json(tmp_path, monkeypatch):
    config = tmp_path / "ratelimit.json"
    env = tmp_path / ".env"

    saved = save_embedding_rate_limits(
        {
            "gpt_researcher": {"tpm": 500, "rpm": 10, "encoding": "cl100k_base"},
            "content_homophily": {"tpm": 900000},
            "ingestion": {"rpm": 45},
        },
        config_path=config,
        env_path=env,
    )

    # Merged config returned with all module fields.
    assert saved["gpt_researcher"]["tpm"] == 500
    assert saved["gpt_researcher"]["rpm"] == 10
    assert saved["content_homophily"]["tpm"] == 900000
    assert saved["ingestion"]["rpm"] == 45

    # .env mirrors the mapped env vars.
    env_text = env.read_text(encoding="utf-8")
    assert "GPT_RESEARCHER_EMBED_TPM=500" in env_text
    assert "GPT_RESEARCHER_EMBED_RPM=10" in env_text
    assert "GPT_RESEARCHER_EMBED_ENCODING=cl100k_base" in env_text
    assert "CONTENT_HOMOPHILY_EMBED_MAX_TOKENS_PER_MINUTE=900000" in env_text
    assert "GEMINI_EMBED_RPM=45" in env_text

    # Live process environment is updated too.
    assert os.environ.get("GPT_RESEARCHER_EMBED_TPM") == "500"


def test_save_preserves_unrelated_env_lines(tmp_path):
    config = tmp_path / "ratelimit.json"
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=secret\nGPT_RESEARCHER_EMBED_TPM=1\n", encoding="utf-8")

    save_embedding_rate_limits(
        {"gpt_researcher": {"tpm": 123}},
        config_path=config,
        env_path=env,
    )
    env_text = env.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=secret" in env_text  # unrelated line preserved
    assert "GPT_RESEARCHER_EMBED_TPM=123" in env_text


def test_load_overlays_persisted_config(tmp_path, monkeypatch):
    config = tmp_path / "ratelimit.json"
    env = tmp_path / ".env"

    save_embedding_rate_limits(
        {"gpt_researcher": {"tpm": 777}},
        config_path=config,
        env_path=env,
    )
    loaded = load_embedding_rate_limits(config_path=config)

    assert loaded["gpt_researcher"]["tpm"] == 777
    # Unset module fields fall back to their defaults.
    assert loaded["ingestion"]["rpm"] == 90


def test_load_reflects_live_env_override(tmp_path, monkeypatch):
    config = tmp_path / "ratelimit.json"
    config.write_text('{"gpt_researcher": {"tpm": 1}}', encoding="utf-8")
    monkeypatch.setenv("GPT_RESEARCHER_EMBED_TPM", "4242")

    loaded = load_embedding_rate_limits(config_path=config)
    assert loaded["gpt_researcher"]["tpm"] == 4242


def test_negative_values_clamped_to_default(tmp_path):
    config = tmp_path / "ratelimit.json"
    env = tmp_path / ".env"
    saved = save_embedding_rate_limits(
        {"gpt_researcher": {"tpm": -50}},
        config_path=config,
        env_path=env,
    )
    # Negative -> clamped to default (0)
    assert saved["gpt_researcher"]["tpm"] == 0
