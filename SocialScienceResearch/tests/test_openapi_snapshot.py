"""Contract gate: checked-in OpenAPI snapshot must match the live app.

Run:  python -m pytest SocialScienceResearch/tests/test_openapi_snapshot.py -q
Regenerate after intentional API changes:
    python SocialScienceResearch/scripts/dump_openapi.py
"""

import json
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parent.parent / "api" / "openapi.json"


def snapshot():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def live():
    from SocialScienceResearch.api.app import app

    return app.openapi()


def test_snapshot_matches_live_app():
    assert SNAPSHOT.exists(), "openapi.json missing; run scripts/dump_openapi.py"
    assert live() == snapshot()


def test_all_operations_declare_responses():
    doc = live()
    for path, item in doc["paths"].items():
        for method, op in item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            assert "responses" in op, f"{method.upper()} {path} missing responses"
            assert "200" in op["responses"], f"{method.upper()} {path} missing 200 response"


def test_research_endpoints_present():
    doc = live()
    paths = doc["paths"]
    for path in [
        "/api/v1/social-science/research/variables",
        "/api/v1/social-science/research/operators",
        "/api/v1/social-science/research/query/preview",
        "/api/v1/social-science/research/query/resolve",
    ]:
        assert path in paths, f"missing research endpoint {path}"


def test_paginated_envelope_present():
    doc = live()
    schemas = doc["components"]["schemas"]
    candidates = [
        name
        for name, schema in schemas.items()
        if isinstance(schema, dict)
        and all(k in schema.get("properties", {}) for k in ("items", "next_cursor", "has_more"))
    ]
    assert candidates, "no Paginated-like schema with items/next_cursor/has_more found"