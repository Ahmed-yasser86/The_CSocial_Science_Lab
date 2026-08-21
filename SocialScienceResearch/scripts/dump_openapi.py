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

    from SocialScienceResearch.api.app import app

    OUTPUT.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"OpenAPI snapshot written to {OUTPUT}")


if __name__ == "__main__":
    dump()