"""Stress benchmark: time the heavy analytics endpoints against a seeded
scratch database served by a running uvicorn instance.

Starts nothing itself. Expected usage::

    # 1) seed (see scripts/stress_seed.py)
    # 2) serve the scratch DB:
    #    SOCIAL_DATABASE_URL=postgresql://... uvicorn SocialScienceResearch.api:create_app --factory --port 8021
    # 3) bench:
    python SocialScienceResearch\\scripts\\stress_bench.py \
        --base-url http://127.0.0.1:8000/api/v1/social-science \
        --manifest C:\\...\\stress_manifest.json

For each endpoint: 1 warmup call, then N timed calls; reports min/median/max
seconds, HTTP status and response payload bytes. Uses stdlib urllib only.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path


def _call(url: str, *, method: str = "GET", body: dict | None = None, timeout: float):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:  # non-2xx still counts, read body
        payload = exc.read()
        status = exc.code
    elapsed = time.perf_counter() - t0
    return elapsed, status, len(payload)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1/social-science")
    ap.add_argument("--manifest", help="stress_manifest.json written by stress_seed.py")
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=600.0)
    args = ap.parse_args(argv)

    manifest_path = Path(args.manifest or "C:/Users/DELL/AppData/Local/Temp/opencode/ssr_stress/stress_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runs: list[str] = manifest["runs"]
    channels: list[str] = manifest["channels"]

    base = args.base_url.rstrip("/")
    run1 = runs[0]
    temporal_runs = ",".join(runs[:3])
    overlap_channels = ",".join(channels[:2])

    advanced_body = {
        "strategy": "top_views",
        "top_n": 50,
        "entity_type": "video",
        "run_ids": [run1],
        "include_all_channels": True,
        "seed": 42,
    }

    endpoints: list[tuple[str, str, dict | None]] = [
        ("GET", f"/network/graph?run_id={run1}", None),
        ("GET", "/network/graph", None),
        ("GET", "/network/metrics", None),
        ("GET", f"/network/temporal?runs={temporal_runs}", None),
        ("GET", "/network/channels", None),
        ("GET", "/network/matrices", None),
        ("POST", "/sampling/advanced", advanced_body),
        (
            "GET",
            f"/network/commenters/overlap?channel_ids={overlap_channels}"
            "&metric=jaccard&min_entities=2&min_shared=1&top_n=50",
            None,
        ),
        ("GET", "/datasets", None),
    ]

    results = []
    for method, path, body in endpoints:
        url = base + path
        label = f"{method} {path.split('?')[0]}"
        suffix = path.split("?")[1] if "?" in path else ""
        print(f"\n>>> {label}  {'?' + suffix if suffix else ''}")
        statuses: set[int] = set()
        sizes: list[int] = []
        times: list[float] = []
        for i in range(args.warmup + args.repeats):
            try:
                dt, status, nbytes = _call(url, method=method, body=body, timeout=args.timeout)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                print(f"    call failed: {exc}")
                dt, status, nbytes = float("nan"), 0, 0
            kind = "warmup" if i < args.warmup else f"rep{i - args.warmup + 1}"
            print(f"    [{kind:>6}] {dt:8.3f}s  http={status}  bytes={nbytes}")
            if i >= args.warmup:
                times.append(dt)
                statuses.add(status)
                sizes.append(nbytes)
        if times:
            results.append(
                {
                    "label": label,
                    "query": suffix,
                    "status": sorted(statuses),
                    "min_s": min(times),
                    "median_s": statistics.median(times),
                    "max_s": max(times),
                    "bytes_median": int(statistics.median(sizes)),
                }
            )

    print("\n================ BENCHMARK SUMMARY ================")
    header = (
        f"{'endpoint':<38} {'status':<8} {'min s':>9} {'med s':>9} "
        f"{'max s':>9} {'bytes':>10}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        st = ",".join(str(s) for s in r["status"])
        print(
            f"{r['label']:<38} {st:<8} {r['min_s']:>9.3f} {r['median_s']:>9.3f} "
            f"{r['max_s']:>9.3f} {r['bytes_median']:>10,}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
