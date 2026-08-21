"""Tests for the defensive "Up Next" parser (no live network)."""

from __future__ import annotations

import json

from SocialScienceResearch.acquisition.up_next import (
    extract_up_next_items,
    parse_watch_payloads,
    scan_page_dumps,
)


def _payload_with_nested_lockup(ids, titles=None):
    """Mirror the current watch-page shape: secondaryResults.results holds one
    itemSectionRenderer whose contents carry lockupViewModels."""
    contents = [
        {"lockupViewModel": {"contentId": vid}} for vid in ids
    ]
    if titles:
        for i, title in enumerate(titles):
            contents[i]["lockupViewModel"]["metadata"] = {
                "lockupMetadataViewModel": {"title": {"content": title}}
            }
    contents.append({"continuationItemRenderer": {"token": "next"}})
    return {
        "contents": {
            "twoColumnWatchNextResults": {
                "secondaryResults": {
                    "secondaryResults": {"results": [
                        {"itemSectionRenderer": {"contents": contents}}
                    ]}
                }
            }
        }
    }


def test_extract_up_next_lockup_nested_shape() -> None:
    payload = _payload_with_nested_lockup(
        ["up1", "up2"], titles=["First", "Second"]
    )
    entries = extract_up_next_items(payload)
    assert [e["id"] for e in entries] == ["up1", "up2"]
    assert entries[1]["title"] == "Second"
    assert "channel_id" not in entries[0]


def test_extract_up_next_compact_renderer_at_top_level() -> None:
    payload = {
        "contents": {
            "twoColumnWatchNextResults": {
                "secondaryResults": {
                    "secondaryResults": {
                        "results": [
                            {
                                "compactVideoRenderer": {
                                    "videoId": "c1",
                                    "title": {"runs": [{"text": "Compact one"}]},
                                    "longBylineText": {
                                        "runs": [
                                            {
                                                "navigationEndpoint": {
                                                    "browseEndpoint": {
                                                        "browseId": "UCchannel"
                                                    }
                                                }
                                            }
                                        ]
                                    },
                                }
                            },
                            {
                                "compactVideoRenderer": {
                                    "videoId": "c2",
                                    "title": {"simpleText": "Compact two"},
                                }
                            },
                        ]
                    }
                }
            }
        }
    }
    entries = extract_up_next_items(payload)
    assert [e["id"] for e in entries] == ["c1", "c2"]
    assert entries[0]["title"] == "Compact one"
    assert entries[0]["channel_id"] == "UCchannel"
    assert entries[1]["title"] == "Compact two"
    assert "channel_id" not in entries[1]


def test_extract_up_next_continuation_items() -> None:
    payload = {
        "onResponseReceivedEndpoints": [
            {
                "appendContinuationItemsAction": {
                    "continuationItems": [
                        {"compactVideoRenderer": {"videoId": "n1"}},
                        {"continuationItemRenderer": {"token": "more"}},
                    ]
                }
            }
        ]
    }
    entries = extract_up_next_items(payload)
    assert [e["id"] for e in entries] == ["n1"]


def test_extract_up_next_deep_scan_fallback() -> None:
    # Renderers relocated to an unexpected part of the tree are still found.
    payload = {
        "responseContext": {
            "serviceTrackingParams": [
                {"scans": [{"shelf": {"lockupViewModel": {"contentId": "deep1"}}}]}
            ]
        }
    }
    entries = extract_up_next_items(payload)
    assert [e["id"] for e in entries] == ["deep1"]


def test_extract_up_next_skips_non_video_entries() -> None:
    payload = {
        "contents": {
            "twoColumnWatchNextResults": {
                "secondaryResults": {
                    "results": [
                        {"adSlotRenderer": {"x": 1}},
                        {"compactRadioRenderer": {"playlistId": "RD1"}},
                        {"reelShelfRenderer": {"contents": []}},
                        {"lockupViewModel": {"contentId": "real"}},
                    ]
                }
            }
        }
    }
    entries = extract_up_next_items(payload)
    assert [e["id"] for e in entries] == ["real"]


def test_extract_up_next_dedupes_by_id() -> None:
    payload = {
        "contents": {
            "twoColumnWatchNextResults": {
                "secondaryResults": {
                    "results": [
                        {"lockupViewModel": {"contentId": "dup"}},
                        {"lockupViewModel": {"contentId": "dup"}},
                    ]
                }
            }
        }
    }
    entries = extract_up_next_items(payload)
    assert [e["id"] for e in entries] == ["dup"]


def test_extract_up_next_empty_payload_returns_empty() -> None:
    assert extract_up_next_items({"nope": True}) == []


def test_parse_watch_payloads_from_raw_json() -> None:
    payload = {"contents": {"twoColumnWatchNextResults": {"secondaryResults": {}}}}
    payloads = parse_watch_payloads(json.dumps(payload))
    assert len(payloads) == 1
    assert "twoColumnWatchNextResults" in payloads[0]["contents"]


def test_parse_watch_payloads_from_html_yt_initial_data() -> None:
    payload = {"contents": {"twoColumnWatchNextResults": {}}}
    html = f"<html><script>var ytInitialData = {json.dumps(payload)};</script></html>"
    payloads = parse_watch_payloads(html)
    assert len(payloads) == 1
    assert "twoColumnWatchNextResults" in payloads[0]["contents"]


def test_scan_page_dumps(tmp_path) -> None:
    payload = _payload_with_nested_lockup(["a1", "a2"])
    (tmp_path / "watch_1.dump").write_text(
        "<html><script>var ytInitialData = "
        + json.dumps(payload)
        + ";</script></html>",
        encoding="utf-8",
    )
    # A player dump without the watch-next payload must be ignored.
    (tmp_path / "player_2.dump").write_text(
        json.dumps({"streamingData": {"formats": []}}), encoding="utf-8"
    )
    entries = scan_page_dumps(tmp_path)
    assert [e["id"] for e in entries] == ["a1", "a2"]