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
    from types import ModuleType
    from unittest.mock import MagicMock

    # Mock database modules so the app can start without PostgreSQL
    os.environ.setdefault("SOCIAL_DATABASE_URL", "postgresql://localhost:5432/dummy")

    # Create a mock module that returns MagicMock for any attribute access
    class MockModule(MagicMock):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.__path__ = []
            self.__file__ = ""

        def __getattr__(self, name):
            if name.startswith("_"):
                return super().__getattribute__(name)
            return MagicMock()

    # Mock all psycopg and psycopg_pool modules
    for mod_name in [
        "psycopg",
        "psycopg.rows",
        "psycopg.types",
        "psycopg.types.json",
        "psycopg_pool",
        "psycopg_pool.pool",
        "psycopg_pool._cmodule",
    ]:
        sys.modules[mod_name] = MockModule()

    from SocialScienceResearch.api.app import app

    OUTPUT.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"OpenAPI snapshot written to {OUTPUT}")


if __name__ == "__main__":
    dump()
