"""Persistent, user-configurable embedding rate-limit settings.

This is the backend half of "set embedding rate-limit params from the UI, per
module". The values are stored both as a JSON config (for reloads) and mirrored
into the project ``.env`` (so every module that reads its env var picks them up
on next start). At runtime the values are also pushed into ``os.environ`` so
already-running processes use them for new embedding calls.

UI field -> env var mapping per module:
    gpt_researcher.tpm      -> GPT_RESEARCHER_EMBED_TPM
    gpt_researcher.rpm      -> GPT_RESEARCHER_EMBED_RPM
    gpt_researcher.encoding -> GPT_RESEARCHER_EMBED_ENCODING
    content_homophily.tpm   -> CONTENT_HOMOPHILY_EMBED_MAX_TOKENS_PER_MINUTE
    ingestion.rpm           -> GEMINI_EMBED_RPM
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# parents: server -> backend -> gpt-researcher -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG_PATH = _REPO_ROOT / ".embedding_ratelimit.json"
_DEFAULT_ENV_PATH = _REPO_ROOT / ".env"

# module -> {ui_field: (ENV_VAR, default)}
_MODULE_FIELDS: dict[str, dict[str, tuple[str, Any]]] = {
    "gpt_researcher": {
        "tpm": ("GPT_RESEARCHER_EMBED_TPM", 0),
        "rpm": ("GPT_RESEARCHER_EMBED_RPM", 0),
        "encoding": ("GPT_RESEARCHER_EMBED_ENCODING", "cl100k_base"),
    },
    "content_homophily": {
        "tpm": ("CONTENT_HOMOPHILY_EMBED_MAX_TOKENS_PER_MINUTE", 0),
    },
    "ingestion": {
        "rpm": ("GEMINI_EMBED_RPM", 90),
    },
}


def _defaults() -> dict[str, dict[str, Any]]:
    return {
        module: {field: default for field, (_env, default) in fields.items()}
        for module, fields in _MODULE_FIELDS.items()
    }


def _coerce_int(value: Any, default: int) -> int:
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return default
    return ivalue if ivalue >= 0 else default


def _coerce_str(value: Any, default: str) -> str:
    if value is None:
        return default
    return str(value)


def _merge_env(config: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Overlay currently-set env vars onto a config dict (live view)."""
    for module, fields in _MODULE_FIELDS.items():
        for field, (env_var, default) in fields.items():
            env_val = os.environ.get(env_var)
            if env_val is not None:
                if isinstance(default, int):
                    config[module][field] = _coerce_int(env_val, default)
                else:
                    config[module][field] = _coerce_str(env_val, default)
    return config


def load_embedding_rate_limits(
    config_path: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Return the current embedding rate-limit config.

    Starts from defaults, overlays any persisted JSON config, then overlays the
    live ``os.environ`` values so the returned dict reflects reality.
    """
    config = _defaults()
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    if path.exists():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            for module, fields in stored.items():
                if module not in config:
                    continue
                for field, value in fields.items():
                    if field not in config[module]:
                        continue
                    default = config[module][field]
                    config[module][field] = (
                        _coerce_int(value, default)
                        if isinstance(default, int)
                        else _coerce_str(value, default)
                    )
        except (json.JSONDecodeError, OSError):
            pass
    return _merge_env(config)


def _write_dotenv(updates: dict[str, str], env_path: Path) -> None:
    """Write/update the given keys in a ``.env`` file, preserving other lines."""
    lines: list[str] = []
    if env_path.exists():
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []

    kept = [ln for ln in lines if not any(ln.startswith(f"{k}=") for k in updates)]
    for key, value in updates.items():
        kept.append(f"{key}={value}")
    env_path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def save_embedding_rate_limits(
    payload: dict[str, Any],
    config_path: Path | None = None,
    env_path: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Validate, persist and apply embedding rate-limit settings.

    Returns the merged config that was saved.
    """
    merged = _defaults()
    for module, fields in _MODULE_FIELDS.items():
        incoming = payload.get(module) or {}
        for field, (_env, default) in fields.items():
            if field in incoming:
                value = incoming[field]
                merged[module][field] = (
                    _coerce_int(value, default)
                    if isinstance(default, int)
                    else _coerce_str(value, default)
                )

    cpath = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    cpath.write_text(json.dumps(merged, indent=2), encoding="utf-8")

    # Mirror into .env and the live process environment.
    env_updates: dict[str, str] = {}
    for module, fields in _MODULE_FIELDS.items():
        for field, (env_var, default) in fields.items():
            value = merged[module][field]
            env_updates[env_var] = str(value)
            os.environ[env_var] = str(value)

    epath = Path(env_path) if env_path else _DEFAULT_ENV_PATH
    _write_dotenv(env_updates, epath)

    return merged
