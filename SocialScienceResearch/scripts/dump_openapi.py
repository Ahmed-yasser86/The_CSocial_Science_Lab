"""Dump the FastAPI OpenAPI schema to a checked-in snapshot.

Run from the repository root:

    python -m SocialScienceResearch.scripts.dump_openapi

or directly:

    python SocialScienceResearch/scripts/dump_openapi.py
"""

from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "api" / "openapi.json"


def dump() -> None:
    import json
    import os
    import sys
    from unittest.mock import MagicMock, patch

    # Mock database modules so the app can start without PostgreSQL
    os.environ.setdefault("SOCIAL_DATABASE_URL", "postgresql://localhost:5432/dummy")
    
    # Patch psycopg_pool before importing the app
    sys.modules["psycopg_pool"] = MagicMock()
    sys.modules["psycopg_pool.pool"] = MagicMock()
    
    # Also patch psycopg
    sys.modules["psycopg"] = MagicMock()
    sys.modules["psycopg.rows"] = MagicMock()
    sys.modules["psycopg_pool._cmodule"] = MagicMock()

    from SocialScienceResearch.api.app import app

    OUTPUT.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"OpenAPI snapshot written to {OUTPUT}")


if __name__ == "__main__":
    dump()
