"""Defensive "Up Next" extraction for YouTube watch pages.

yt-dlp does not expose watch-page recommendations as an extracted field, but
it can dump the raw watch-page INNERTUBE payload (``--write-pages``). YouTube
rotates both the *nesting* and the *renderer shapes* of that payload without
notice, so this module implements a smart parser that never fails on a shape
change:

* it first tries the known ``twoColumnWatchNextResults.secondaryResults`` key
  paths (including the ``onResponseReceivedEndpoints`` continuation shape),
* it unwraps ``itemSectionRenderer`` nesting when present,
* it understands both the legacy ``compactVideoRenderer`` /
  ``videoWithContextRenderer`` items and the newer ``lockupViewModel`` items,
* and if no known path yields anything it deep-scans the whole payload for
  recommendation renderers so a renamed/relocated section still parses.

Items are mapped to the provider contract dicts consumed by
``normalize_recommendations`` (``id``/``video_id`` plus optional ``channel_id``,
``channel_name`` and ``title``). Non-video entries (continuation tokens, ad
slots, shorts/reel shelves, radio mixes) are skipped so observed edges always
point at real videos.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

#: Renderer keys that carry a single recommended video.
_RENDERER_KEYS = (
    "compactVideoRenderer",
    "videoWithContextRenderer",
    "lockupViewModel",
)

#: Renderer keys for radio/mix playlists - deliberately NOT collected so edges
#: never point at auto-generated playlist ids.
_RADIO_KEYS = ("compactRadioRenderer", "compactAutoplayRenderer")

#: Known nesting paths that lead to the secondary (Up Next) result items.
_SECONDARY_PATHS = (
    ("contents", "twoColumnWatchNextResults", "secondaryResults", "secondaryResults", "results"),
    ("contents", "twoColumnWatchNextResults", "secondaryResults", "results"),
)


def _get_path(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    """Walk a dotted key path defensively; returns ``None`` on any miss."""
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _flatten_items(items: Any) -> list[dict[str, Any]]:
    """Unwrap recommendation renderers from a list of result items.

    Handles items that are renderers directly as well as items wrapped in an
    ``itemSectionRenderer`` (the current YouTube shape). Non-video entries are
    ignored.
    """
    flattened: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return flattened
    for item in items:
        if not isinstance(item, dict):
            continue
        section = item.get("itemSectionRenderer")
        if isinstance(section, dict):
            flattened.extend(_flatten_items(section.get("contents")))
            continue
        for key in _RENDERER_KEYS:
            if key in item and isinstance(item[key], dict):
                flattened.append(item[key])
                break
    return flattened


def _continuation_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect renderers from ``appendContinuationItemsAction`` responses."""
    items: list[dict[str, Any]] = []
    endpoints = _get_path(payload, ("onResponseReceivedEndpoints",))
    if not isinstance(endpoints, list):
        return items
    for endpoint in endpoints:
        if not isinstance(endpoint, dict):
            continue
        action = endpoint.get("appendContinuationItemsAction")
        if not isinstance(action, dict):
            continue
        items.extend(_flatten_items(action.get("continuationItems")))
    return items


def _deep_collect(node: Any, found: list[dict[str, Any]]) -> None:
    """Recursively gather every recommendation renderer anywhere in the tree."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _RENDERER_KEYS and isinstance(value, dict):
                found.append(value)
            elif key not in _RADIO_KEYS:
                _deep_collect(value, found)
    elif isinstance(node, list):
        for element in node:
            _deep_collect(element, found)


def _renderer_title(renderer: dict[str, Any]) -> str | None:
    """Read the title out of a compact/video renderer's title object."""
    title = renderer.get("title")
    if not isinstance(title, dict):
        return None
    simple = title.get("simpleText")
    if simple:
        return simple
    runs = title.get("runs")
    if isinstance(runs, list) and runs and isinstance(runs[0], dict):
        return runs[0].get("text")
    return None


def _renderer_channel_id(renderer: dict[str, Any]) -> str | None:
    """Read the channel id out of a compact/video renderer's byline."""
    for key in ("longBylineText", "shortBylineText", "ownerText"):
        byline = renderer.get(key)
        if not isinstance(byline, dict):
            continue
        runs = byline.get("runs")
        if not isinstance(runs, list) or not runs or not isinstance(runs[0], dict):
            continue
        nav = runs[0].get("navigationEndpoint")
        if isinstance(nav, dict):
            browse_id = nav.get("browseEndpoint", {}).get("browseId")
            if browse_id:
                return str(browse_id)
    return None


def _renderer_channel_name(renderer: dict[str, Any]) -> str | None:
    """Read the channel *name* out of a renderer's byline (run text)."""
    for key in ("longBylineText", "shortBylineText", "ownerText"):
        byline = renderer.get(key)
        if not isinstance(byline, dict):
            continue
        runs = byline.get("runs")
        if not isinstance(runs, list) or not runs or not isinstance(runs[0], dict):
            continue
        text = runs[0].get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return None


def _map_renderer(renderer: dict[str, Any]) -> dict[str, Any] | None:
    """Map a single renderer to the provider dict contract.

    ``lockupViewModel`` (newer shape) carries ``contentId`` and the title under
    ``metadata.lockupMetadataViewModel.title.content``; the compact/video
    renderers carry ``videoId`` plus ``title``/byline objects.
    """
    if "contentId" in renderer:
        video_id = renderer.get("contentId")
        if not video_id:
            return None
        metadata = renderer.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        lockup_metadata = metadata.get("lockupMetadataViewModel")
        if not isinstance(lockup_metadata, dict):
            lockup_metadata = {}
        title_obj = lockup_metadata.get("title")
        title = title_obj.get("content") if isinstance(title_obj, dict) else None
        entry: dict[str, Any] = {"id": str(video_id)}
        if title:
            entry["title"] = title
        return entry

    video_id = renderer.get("videoId")
    if not video_id:
        return None
    entry = {"id": str(video_id)}
    title = _renderer_title(renderer)
    if title:
        entry["title"] = title
    channel_id = _renderer_channel_id(renderer)
    if channel_id:
        entry["channel_id"] = channel_id
    channel_name = _renderer_channel_name(renderer)
    if channel_name:
        entry["channel_name"] = channel_name
    return entry


def extract_up_next_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract observed Up Next entries from an INNERTUBE watch payload.

    Never raises: a payload YouTube has reshaped still yields whatever
    recommendation renderers it contains, and an unparseable payload yields an
    empty list (the caller decides how to report absence).
    """
    renderers: list[dict[str, Any]] = []
    for path in _SECONDARY_PATHS:
        items = _get_path(payload, path)
        if items:
            renderers.extend(_flatten_items(items))
    renderers.extend(_continuation_items(payload))
    if not renderers:
        _deep_collect(payload, renderers)

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for renderer in renderers:
        if not isinstance(renderer, dict):
            continue
        entry = _map_renderer(renderer)
        if not entry:
            continue
        if entry["id"] in seen:
            continue
        seen.add(entry["id"])
        entries.append(entry)
    return entries


def _extract_yt_initial_data(text: str) -> dict[str, Any] | None:
    """Brace-balance the ``var ytInitialData = {...};`` block out of a page."""
    for match in re.finditer(r"ytInitialData", text):
        start = match.end()
        equals = text.find("=", start)
        if equals < 0:
            continue
        brace = text.find("{", equals)
        if brace < 0:
            continue
        depth = 0
        in_string = False
        escaped = False
        cursor = brace
        while cursor < len(text):
            char = text[cursor]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            else:
                if char == '"':
                    in_string = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            parsed = json.loads(text[brace : cursor + 1])
                        except (ValueError, TypeError):
                            break
                        if isinstance(parsed, dict):
                            return parsed
                        break
            cursor += 1
    return None


def parse_watch_payloads(text: str) -> list[dict[str, Any]]:
    """Return every INNERTUBE payload embedded in a dumped response.

    Handles both a raw JSON dump (e.g. a ``/next`` API response) and the watch
    page HTML with an embedded ``ytInitialData`` blob.
    """
    payloads: list[dict[str, Any]] = []
    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
        except (ValueError, TypeError):
            parsed = None
        if isinstance(parsed, dict):
            payloads.append(parsed)
    initial = _extract_yt_initial_data(text)
    if isinstance(initial, dict):
        payloads.append(initial)
    return payloads


def scan_page_dumps(directory: Path) -> list[dict[str, Any]]:
    """Scan a ``--write-pages`` dump directory for Up Next entries.

    Each saved response is inspected for the watch-next payload; the smart
    parser runs over every payload found. Ordering follows the saved files so
    the observed order is preserved across dumps.
    """
    entries: list[dict[str, Any]] = []
    for dump in sorted(Path(directory).glob("*.dump")):
        try:
            raw = dump.read_bytes()
        except OSError:
            continue
        if b"twoColumnWatchNextResults" not in raw:
            continue
        text = raw.decode("utf-8", errors="replace")
        for payload in parse_watch_payloads(text):
            entries.extend(extract_up_next_items(payload))
    return entries