"""Shared in-process log hub for streaming backend activity to the UI.

Extracted from agent_server so the research graph (intelligence_graph) can emit
structured state/step events without creating a circular import.
"""

import asyncio
from typing import Any, Dict, List


class LogHub:
    def __init__(self) -> None:
        self._runs: Dict[str, Dict[str, Any]] = {}
        # Global fan-out: a single stream of every event, used when the UI
        # does not (yet) know a specific run_id.
        self._global_events: List[Dict[str, Any]] = []
        self._global_subs: List["asyncio.Queue"] = []

    def subscribe(self, run_id: str) -> "asyncio.Queue":
        run = self._runs.setdefault(run_id, {"events": [], "subs": [], "done": False})
        q: "asyncio.Queue" = asyncio.Queue()
        for ev in run["events"]:
            q.put_nowait(ev)
        if run["done"]:
            q.put_nowait({"type": "done", "run_id": run_id})
        run["subs"].append(q)
        return q

    def subscribe_global(self) -> "asyncio.Queue":
        q: "asyncio.Queue" = asyncio.Queue()
        for ev in self._global_events:
            q.put_nowait(ev)
        self._global_subs.append(q)
        return q

    async def put(self, run_id: str, event: Dict[str, Any]) -> None:
        run = self._runs.setdefault(run_id, {"events": [], "subs": [], "done": False})
        run["events"].append(event)
        if len(run["events"]) > 2000:
            run["events"] = run["events"][-2000:]
        for q in list(run["subs"]):
            try:
                q.put_nowait(event)
            except Exception:
                pass
        # Global fan-out (capped replay buffer).
        self._global_events.append(event)
        if len(self._global_events) > 4000:
            self._global_events = self._global_events[-4000:]
        for q in list(self._global_subs):
            try:
                q.put_nowait(event)
            except Exception:
                pass

    async def done(self, run_id: str) -> None:
        run = self._runs.get(run_id)
        if not run or run["done"]:
            return
        run["done"] = True
        ev = {"type": "done", "run_id": run_id, "ts": _iso_now()}
        run["events"].append(ev)
        for q in list(run["subs"]):
            try:
                q.put_nowait(ev)
            except Exception:
                pass


def _iso_now() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


LOG_HUB = LogHub()
