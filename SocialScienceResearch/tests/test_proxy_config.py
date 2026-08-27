"""Proxy (Decodo / rotating residential) configuration tests.

Covers the URL builder, the adapter's live resolution, and the self-test
endpoint that reports the egress IP through the proxy. No network is hit
(the requests call is mocked).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from SocialScienceResearch.acquisition.yt_dlp_adapter import YtDlpAcquisitionProvider
from SocialScienceResearch.api import routers
from SocialScienceResearch.config.runtime_config import RuntimeScraperConfig


# --------------------------------------------------------------------------
# URL builder
# --------------------------------------------------------------------------
def test_proxy_url_builder():
    cfg = RuntimeScraperConfig(
        proxy_enabled=True,
        proxy_host="dc.decodo.com",
        proxy_port=10001,
        proxy_username="user",
        proxy_password="pass",
    )
    assert cfg.proxy_url() == "http://user:pass@dc.decodo.com:10001"


def test_proxy_url_disabled_is_none():
    assert RuntimeScraperConfig(proxy_enabled=False).proxy_url() is None


def test_proxy_url_missing_host_or_port_is_none():
    assert RuntimeScraperConfig(proxy_enabled=True, proxy_host="dc.decodo.com").proxy_url() is None
    assert RuntimeScraperConfig(proxy_enabled=True, proxy_port=10001).proxy_url() is None


def test_proxy_url_without_auth():
    cfg = RuntimeScraperConfig(proxy_enabled=True, proxy_host="dc.decodo.com", proxy_port=10001)
    assert cfg.proxy_url() == "http://dc.decodo.com:10001"


# --------------------------------------------------------------------------
# Adapter resolves the live proxy (runtime config wins over frozen settings)
# --------------------------------------------------------------------------
def test_adapter_resolves_runtime_proxy():
    cfg = RuntimeScraperConfig(proxy_enabled=True, proxy_host="dc.decodo.com", proxy_port=10001)
    provider = YtDlpAcquisitionProvider(runtime_config=cfg)
    assert provider._resolve_proxy() == "http://dc.decodo.com:10001"


def test_adapter_falls_back_to_settings_proxy():
    from SocialScienceResearch.config.settings import ScraperSettings

    provider = YtDlpAcquisitionProvider(settings=ScraperSettings(proxy="http://legacy:9"))
    assert provider._resolve_proxy() == "http://legacy:9"


# --------------------------------------------------------------------------
# Self-test endpoint reports the egress IP observed through the proxy
# --------------------------------------------------------------------------
def test_proxy_test_endpoint_returns_egress_ip():
    cfg = RuntimeScraperConfig(proxy_enabled=True, proxy_host="dc.decodo.com", proxy_port=10001)
    fake_request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(runtime_scraper_config=cfg))
    )

    class _Resp:
        status_code = 200
        headers = {"content-type": "application/json"}

        def json(self):
            return {"ip": "1.2.3.4", "provider": "IPinfo"}

    with mock.patch.object(routers.scraper_config.requests, "get", return_value=_Resp()):
        result = routers.scraper_config.test_proxy(fake_request)

    assert result["ok"] is True
    assert result["egress_ip"] == "1.2.3.4"
    assert result["youtube"]["ok"] is True
    assert result["egress_checks"][0]["ok"] is True


def test_proxy_test_endpoint_handles_failure():
    cfg = RuntimeScraperConfig(proxy_enabled=True, proxy_host="dc.decodo.com", proxy_port=10001)
    fake_request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(runtime_scraper_config=cfg))
    )

    def _boom(*a, **k):
        raise RuntimeError("connection refused")

    with mock.patch.object(routers.scraper_config.requests, "get", side_effect=_boom):
        result = routers.scraper_config.test_proxy(fake_request)

    assert result["ok"] is False
    assert "connection refused" in result["youtube"]["error"]
