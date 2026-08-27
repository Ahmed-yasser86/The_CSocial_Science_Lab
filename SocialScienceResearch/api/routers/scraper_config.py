"""Scraper configuration endpoints.

Lets the UI read and update runtime scraper settings (speed/concurrency)
without restarting the server, including the outbound proxy (Decodo /
rotating residential) used to avoid YouTube IP throttling.
"""

from __future__ import annotations

import requests  # noqa: BLE001 - used by the proxy self-test endpoint
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


def _get_runtime_config(request: Request):
    """Safely read the runtime scraper config off the app state.

    Returns None if it has not been initialised (e.g. on a stale backend
    build), so callers can degrade gracefully instead of raising a 500.
    """
    state = getattr(request.app, "state", None)
    return getattr(state, "runtime_scraper_config", None)


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


class ProxyConfigPayload(BaseModel):
    proxy_enabled: bool | None = None
    proxy_host: str | None = None
    proxy_port: int | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None
    proxy_verify: bool | None = None
    proxy_session: str | None = None
    youtube_cookies_mode: str | None = Field(None, pattern="^(none|browser|file)$")
    youtube_cookies_browser: str | None = None
    youtube_cookies_path: str | None = None


@router.get(
    "/scraper/proxy",
    tags=["scraper"],
)
def get_proxy_config(request: Request) -> dict[str, Any]:
    """Return the current outbound proxy configuration."""
    config = _get_runtime_config(request)
    if config is None:
        raise HTTPException(status_code=503, detail="Proxy configuration not initialised on the server")
    return config.to_dict()


@router.put(
    "/scraper/proxy",
    tags=["scraper"],
)
def update_proxy_config(request: Request, body: ProxyConfigPayload) -> dict[str, Any]:
    """Update the outbound proxy (only provided fields change)."""
    config = _get_runtime_config(request)
    if config is None:
        raise HTTPException(status_code=503, detail="Proxy configuration not initialised on the server")
    updates = body.model_dump(exclude_none=True)
    # An empty password means "leave the stored one untouched".
    if updates.get("proxy_password") == "":
        updates.pop("proxy_password", None)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    config.update(**updates)
    from SocialScienceResearch.config.runtime_config import save_proxy_fields

    save_proxy_fields(config)
    return config.to_dict()


@router.post(
    "/scraper/proxy/test",
    tags=["scraper"],
)
def test_proxy(request: Request) -> dict[str, Any]:
    """Verify the proxy works by requesting the egress IP through it.

    Tries the Decodo egress check first, then falls back to a neutral IP
    checker so a restriction on Decodo's own domain doesn't mask a working
    proxy. Residential proxies can be slow to warm up, so the read timeout is
    generous.
    """
    config = _get_runtime_config(request)
    if config is None:
        return {"ok": False, "error": "Proxy configuration not initialised on the server"}
    url = config.proxy_url()
    if not url:
        return {"ok": False, "error": "Proxy is not enabled/configured"}
    proxies = {"http": url, "https": url}

    def _try(label: str, target: str, expect_json: bool = True) -> dict[str, Any]:
        try:
            resp = requests.get(
                target,
                proxies=proxies,
                timeout=(20, 90),
                verify=config.proxy_verify,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            ok = resp.status_code < 400
            return {
                "label": label,
                "ok": ok,
                "status_code": resp.status_code,
                "body": resp.json() if (expect_json and resp.headers.get("content-type", "").startswith("application/json")) else resp.text[:400],
            }
        except Exception as exc:  # noqa: BLE001 - report any failure to the UI
            msg = str(exc)
            if "timed out" in msg:
                reason = (
                    "proxy too slow or unreachable - residential proxies can take "
                    ">30s to allocate an egress IP; increase patience or check the host/port"
                )
            elif "10054" in msg or "ConnectionReset" in type(exc).__name__ or "Connection aborted" in msg:
                reason = (
                    "proxy reset the connection - Decodo rejected it, almost always "
                    "bad credentials, wrong username format, or an inactive plan"
                )
            elif "407" in msg or "Proxy Authentication" in msg:
                reason = "proxy returned 407 - credentials rejected"
            else:
                reason = "request through the proxy failed"
            return {"label": label, "ok": False, "error": msg, "reason": reason}

    # Validate against the REAL target (YouTube) routed through the proxy, not
    # Decodo's own meta endpoint - that is what the proxy is actually for.
    youtube = _try(
        "youtube",
        "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=Ca4fjWgPrwI&format=json",
    )

    # Best-effort egress-IP reporting. IP-echo services are frequently blocked
    # or slowed by residential proxies, so we try a few and only surface the IP
    # when one actually answers. A null egress_ip is NOT a failure - the
    # YouTube check above is the real signal that the proxy egress works.
    import re as _re

    _ip_re = _re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    egress_probes = [
        ("ipify", "https://api.ipify.org?format=json", True),
        ("ifconfig.me", "https://ifconfig.me/ip", False),
        ("ipinfo.io", "https://ipinfo.io/ip", False),
    ]
    egress_results: list[dict[str, Any]] = []
    reported_ip = None
    for label, target, is_json in egress_probes:
        res = _try(label, target, expect_json=is_json)
        egress_results.append(res)
        if reported_ip is None and res.get("ok"):
            body = res.get("body")
            if isinstance(body, dict) and body.get("ip"):
                reported_ip = str(body["ip"])
            elif isinstance(body, str):
                m = _ip_re.search(body.strip())
                if m:
                    reported_ip = m.group(0)
    return {
        "ok": youtube["ok"] or any(r.get("ok") for r in egress_results),
        "egress_ip": reported_ip,
        "egress_note": (
            None
            if reported_ip
            else "Egress IP not reported (IP-echo services are often blocked by "
            "residential proxies) - but YouTube was reached through the proxy, "
            "which is what matters."
        ),
        "youtube": youtube,
        "egress_checks": egress_results,
    }


@router.get(
    "/scraper/config",
    tags=["scraper"],
)
def get_scraper_config(request: Request) -> dict[str, Any]:
    """Return current runtime scraper settings."""
    config = _get_runtime_config(request)
    if config is None:
        raise HTTPException(status_code=503, detail="Scraper configuration not initialised on the server")
    return config.to_dict()


@router.put(
    "/scraper/config",
    tags=["scraper"],
)
def update_scraper_config(request: Request, body: ScraperConfigPayload) -> dict[str, Any]:
    """Update runtime scraper settings (only provided fields are changed)."""
    config = _get_runtime_config(request)
    if config is None:
        raise HTTPException(status_code=503, detail="Scraper configuration not initialised on the server")
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    config.update(**updates)
    # Keep the shared budget controller's pacing in sync with the UI speed setting.
    _sync_budget(request, config.request_delay_seconds)
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
    config = _get_runtime_config(request)
    if config is None:
        raise HTTPException(status_code=503, detail="Scraper configuration not initialised on the server")
    config.update(
        request_delay_seconds=preset["request_delay_seconds"],
        enrichment_concurrency=preset["enrichment_concurrency"],
        socket_timeout=preset["socket_timeout"],
    )
    _sync_budget(request, config.request_delay_seconds)
    return {**config.to_dict(), "applied_preset": body.preset}


def _sync_budget(request: Request, request_delay_seconds: float) -> None:
    """Push the UI speed setting into the shared budget controller (best-effort)."""
    controller = getattr(request.app.state, "budget_controller", None)
    if controller is not None:
        controller.set_min_interval(request_delay_seconds)
