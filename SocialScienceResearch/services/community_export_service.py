"""Export communities (Content Homophily spec §24, researcher-export).

Builds a downloadable ZIP for a network scope (a run, a set of videos, or the
whole persisted recommendation network) containing:

* ``community_{id}_nodes.csv``  - node list for each detected community;
* ``community_{id}_edges.csv``  - recommendation edge list *inside* each
  community (both endpoints in the same community);
* ``all_communities_edges.csv``  - the full edge list across all communities;
* ``content_analysis_per_community.csv`` - a community x community mean semantic
  similarity matrix (every ordered pair, including within-community);
* ``content_analysis_detailed.json`` - the same data in a human-readable,
  per-community form: for each community its within-similarity and a ranked list
  of "similarity to community Y = z" for every other community, plus (when an
  analysis id is supplied) the aggregate CONTENT EVIDENCE results for reference;
* ``README.txt`` - manifest describing every file.

This is DETAILED per-community content evidence, not the aggregate
within/between summary. Semantic similarity reuses cached embeddings on disk
(no new Gemini calls), so it reflects every video that has ever been embedded
for this project. Videos without a cached embedding are excluded from a pair
and noted as ``n_videos_with_embeddings`` so the export is always honest.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from SocialScienceResearch.utils.logger import get_logger

logger = get_logger(__name__)


def _cosine(a: np.ndarray, b: np.ndarray) -> float | None:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return None
    return float(a.dot(b) / (na * nb))


class CommunityExportService:
    def __init__(self, repos, settings, embedder=None):
        self._repos = repos
        self._settings = settings
        self._embedder = embedder

    # -- graph + cached embeddings ----------------------------------------
    def _graph(self, run_id: str | None, video_ids: list[str] | None):
        from SocialScienceResearch.services.network_analytics_service import (
            NetworkAnalyticsService,
        )

        analytics = NetworkAnalyticsService(self._repos)
        return analytics.graph(
            run_ids=[run_id] if run_id else None,
            video_ids=video_ids or None,
        )

    def _cached_vectors(self, video_ids: set[str]) -> dict[str, np.ndarray]:
        """Load every cached embedding we have on disk for these videos.

        Scans all model sub-directories under ``embedding_cache`` so a vector is
        recovered regardless of which model produced it. No network calls.
        """
        data_dir = getattr(self._settings.repository, "data_dir", None)
        if not data_dir:
            return {}
        cache_root = Path(data_dir) / "embedding_cache"
        if not cache_root.exists():
            return {}
        vectors: dict[str, np.ndarray] = {}
        for vid in video_ids:
            for sub in cache_root.iterdir():
                if not sub.is_dir():
                    continue
                path = sub / f"{vid}.json"
                if not path.exists():
                    continue
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    vec = payload.get("vector")
                    if isinstance(vec, list) and vec:
                        vectors[vid] = np.asarray(vec, dtype=float)
                        break
                except Exception:  # noqa: BLE001 - skip unreadable cache entries
                    continue
        return vectors

    # -- similarity -------------------------------------------------------
    @staticmethod
    def _pair_similarity(
        items_x: list[tuple[str, np.ndarray]],
        items_y: list[tuple[str, np.ndarray]],
    ) -> tuple[float | None, int]:
        if not items_x or not items_y:
            return None, 0
        sims: list[float] = []
        for vid_a, vec_a in items_x:
            for vid_b, vec_b in items_y:
                if vid_a == vid_b:
                    continue
                s = _cosine(vec_a, vec_b)
                if s is not None:
                    sims.append(s)
        if not sims:
            return None, 0
        return float(np.mean(sims)), len(sims)

    # -- builders ---------------------------------------------------------
    def _node_rows(self, nodes):
        return [
            {
                "video_id": n.video_id,
                "title": n.title or "",
                "channel_id": n.channel_id or "",
                "channel_name": n.channel_name or "",
                "community_id": n.community_id,
                "kind": n.kind,
                "in_degree": n.in_degree,
                "out_degree": n.out_degree,
                "views": n.views if n.views is not None else "",
                "likes": n.likes if n.likes is not None else "",
                "duration": n.duration if n.duration is not None else "",
                "recommendations_scraped": n.recommendations_scraped,
            }
            for n in nodes
        ]

    @staticmethod
    def _csv(fieldnames, rows: list[dict]) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        return buf.getvalue()

    def export_zip(
        self,
        run_id: str | None = None,
        video_ids: list[str] | None = None,
        analysis_id: str | None = None,
    ) -> bytes:
        graph = self._graph(run_id, video_ids)
        nodes = [n for n in graph.nodes if n.community_id is not None]
        if not nodes:
            raise ValueError(
                "No community-labeled videos in this scope; nothing to export."
            )
        labels: dict[str, int] = {n.video_id: n.community_id for n in nodes}
        groups: dict[int, list] = {}
        for n in nodes:
            groups.setdefault(n.community_id, []).append(n)

        # Per-community semantic vectors (cached only).
        vectors = self._cached_vectors(set(labels))
        community_vectors: dict[int, list[tuple[str, np.ndarray]]] = {}
        for cid, members in groups.items():
            community_vectors[cid] = [
                (n.video_id, vectors[n.video_id])
                for n in members
                if n.video_id in vectors
            ]

        community_ids = sorted(groups)
        label_of = labels  # video -> community

        # Global + per-community edge rows.
        global_edge_rows: list[dict] = []
        per_community_edge_rows: dict[int, list[dict]] = {c: [] for c in community_ids}
        edge_fieldnames = [
            "source", "target", "weight", "relationship_type",
            "source_title", "target_title",
            "source_community", "target_community",
        ]
        for e in graph.edges:
            sc = label_of.get(e.source)
            tc = label_of.get(e.target)
            row = {
                "source": e.source,
                "target": e.target,
                "weight": e.weight,
                "relationship_type": e.relationship_type,
                "source_title": getattr(e, "title", None) or "",
                "target_title": "",
                "source_community": sc if sc is not None else "",
                "target_community": tc if tc is not None else "",
            }
            global_edge_rows.append(row)
            if sc is not None and sc == tc:
                per_community_edge_rows.setdefault(sc, []).append(row)

        # Community x community similarity matrix.
        matrix: dict[tuple[int, int], dict[str, Any]] = {}
        for i, cx in enumerate(community_ids):
            for cy in community_ids[i:]:
                mean, n = self._pair_similarity(
                    community_vectors.get(cx, []),
                    community_vectors.get(cy, []),
                )
                matrix[(cx, cy)] = {
                    "community_x": cx,
                    "community_y": cy,
                    "is_within": cx == cy,
                    "mean_similarity": mean,
                    "n_pairs": n,
                    "videos_with_embeddings_x": len(community_vectors.get(cx, [])),
                    "videos_with_embeddings_y": len(community_vectors.get(cy, [])),
                }

        # Per-community detailed (ranked) view.
        detailed = {
            "scope": {
                "run_id": run_id,
                "video_count": len(nodes),
                "community_count": len(community_ids),
                "edge_count": graph.edge_count,
                "videos_with_cached_embeddings": len(vectors),
                "embedding_model": (
                    getattr(self._embedder, "model_name", None)
                    or "gemini-embedding-2-preview"
                ),
            },
            "communities": [],
        }
        for cx in community_ids:
            within = matrix.get((cx, cx), {}).get("mean_similarity")
            others = []
            for cy in community_ids:
                if cy == cx:
                    continue
                key = (cx, cy) if cx <= cy else (cy, cx)
                entry = matrix.get(key)
                if entry is None:
                    continue
                others.append({
                    "community": cy,
                    "similarity": entry["mean_similarity"],
                    "n_pairs": entry["n_pairs"],
                })
            others.sort(
                key=lambda o: (o["similarity"] is not None, o["similarity"] or -2),
                reverse=True,
            )
            members = [n.video_id for n in groups[cx]]
            detailed["communities"].append({
                "community_id": cx,
                "n_videos": len(members),
                "n_videos_with_embeddings": len(community_vectors.get(cx, [])),
                "within_community_similarity": within,
                "similarity_to_other_communities": others,
                "top_similar_community": (
                    others[0]["community"]
                    if others and others[0]["similarity"] is not None
                    else None
                ),
            })

        # Aggregate analysis results (reference only, not the headline).
        aggregate = None
        if analysis_id is not None:
            try:
                from SocialScienceResearch.services.content_homophily_service import (
                    ContentHomophilyService,
                )

                svc = ContentHomophilyService(
                    self._repos, self._settings, embedder=self._embedder
                )
                rec = svc.get(analysis_id)
                if rec is not None:
                    aggregate = rec.get("results")
            except Exception as exc:  # noqa: BLE001
                logger.warning("export: could not attach analysis %s: %s", analysis_id, exc)

        # Assemble CSVs / JSON.
        node_fieldnames = [
            "video_id", "title", "channel_id", "channel_name", "community_id",
            "kind", "in_degree", "out_degree", "views", "likes", "duration",
            "recommendations_scraped",
        ]
        files: dict[str, bytes] = {}
        for cid in community_ids:
            members = groups[cid]
            files[f"community_{cid}_nodes.csv"] = self._csv(
                node_fieldnames, self._node_rows(members)
            ).encode("utf-8")
            files[f"community_{cid}_edges.csv"] = self._csv(
                edge_fieldnames, per_community_edge_rows.get(cid, [])
            ).encode("utf-8")

        files["all_communities_edges.csv"] = self._csv(
            edge_fieldnames, global_edge_rows
        ).encode("utf-8")

        matrix_rows = [matrix[k] for k in sorted(matrix)]
        files["content_analysis_per_community.csv"] = self._csv(
            [
                "community_x", "community_y", "is_within", "mean_similarity",
                "n_pairs", "videos_with_embeddings_x", "videos_with_embeddings_y",
            ],
            matrix_rows,
        ).encode("utf-8")

        detailed_payload: dict[str, Any] = {
            "generated_at": _now_iso(),
            "disclaimer": (
                "Content evidence about observed content structure only. Not proof "
                "of an echo chamber, causality, user beliefs, psychological effects, "
                "or polarization caused by YouTube. Similarities reuse cached "
                "embeddings; videos without a cached embedding are excluded per pair."
            ),
            "per_community_content_analysis": detailed["communities"],
            "community_similarity_matrix": matrix_rows,
            "scope": detailed["scope"],
        }
        if aggregate is not None:
            detailed_payload["aggregate_analysis_reference"] = aggregate
        files["content_analysis_detailed.json"] = json.dumps(
            detailed_payload, indent=2, ensure_ascii=False
        ).encode("utf-8")

        files["README.txt"] = _readme().encode("utf-8")

        # Zip it up.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in files.items():
                zf.writestr(f"communities_export/{name}", data)
        return buf.getvalue()


def _now_iso() -> str:
    from SocialScienceResearch.utils.idgen import utcnow
    return utcnow().isoformat()


def _readme() -> str:
    return (
        "Communities export (Content Homophily)\n"
        "=======================================\n\n"
        "Per-community network + DETAILED per-community-pair content evidence.\n\n"
        "Files\n"
        "-----\n"
        "community_{id}_nodes.csv        Node list for community {id} (videos with\n"
        "                                title, channel, degree, views, community id).\n"
        "community_{id}_edges.csv        Recommendation edges whose BOTH endpoints are\n"
        "                                inside community {id}.\n"
        "all_communities_edges.csv       Full edge list across every community, with\n"
        "                                source/target community ids.\n"
        "content_analysis_per_community.csv\n"
        "                                Community x community mean cosine similarity\n"
        "                                matrix (every ordered pair, including within).\n"
        "content_analysis_detailed.json  Human-readable per-community content evidence:\n"
        "                                for each community, its within-community\n"
        "                                similarity and a ranked list of\n"
        "                                'similarity to community Y = z' for every other\n"
        "                                community. Includes the aggregate CONTENT\n"
        "                                EVIDENCE results as reference when an analysis\n"
        "                                id was supplied.\n\n"
        "Notes\n"
        "-----\n"
        "- Semantic similarity reuses cached embeddings on disk; no new model calls.\n"
        "- A pair is only computed for videos that have a cached embedding; such\n"
        "  videos are counted in 'videos_with_embeddings_*' so absences are visible.\n"
        "- This is observed-content-structure evidence only. It is not a claim about\n"
        "  echo chambers, causality, user beliefs, or polarization.\n"
    )
