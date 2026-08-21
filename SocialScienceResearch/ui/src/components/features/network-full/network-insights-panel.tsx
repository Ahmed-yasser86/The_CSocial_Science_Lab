"use client";

import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { formatNumber } from "@/lib/format";
import type { NetworkMetrics } from "@/lib/network-full-types";
import type { NetworkGraphPayload } from "@/lib/network-full-types";

export interface NetworkInsightsPanelProps {
  metrics?: NetworkMetrics;
  graph?: NetworkGraphPayload;
  loading?: boolean;
}

export function NetworkInsightsPanel({ metrics, graph, loading }: NetworkInsightsPanelProps) {
  const insights = useMemo(() => buildInsights(metrics, graph), [metrics, graph]);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Analyzing the network…</p>;
  }

  if (insights.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No insights yet — load a network slice first.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {insights.map((insight, i) => (
        <div key={i} className="flex items-start gap-2.5 rounded-md border p-3">
          <Badge variant={insight.severity === "warning" ? "secondary" : "outline"}>
            {insight.tag}
          </Badge>
          <p className="text-sm">{insight.text}</p>
        </div>
      ))}
    </div>
  );
}

interface Insight {
  tag: string;
  severity: "info" | "warning";
  text: string;
}

function buildInsights(
  metrics?: NetworkMetrics,
  graph?: NetworkGraphPayload,
): Insight[] {
  const out: Insight[] = [];
  if (!metrics || metrics.node_count === 0) return out;

  const nodes = graph?.nodes ?? [];

  out.push({
    tag: "Density",
    severity: "info",
    text: `Network is ${metrics.is_directed ? "directed" : "undirected"} with ${formatNumber(metrics.edge_count)} edges across ${formatNumber(metrics.node_count)} nodes. Density is ${(metrics.density * 100).toFixed(2)}%${
      metrics.density < 0.05
        ? " — a sparse, hub-driven structure (typical of recommendation networks)."
        : " — a relatively dense structure."
    }`,
  });

  if (metrics.largest_component_share !== null && metrics.largest_component_share !== undefined) {
    const share = metrics.largest_component_share * 100;
    out.push({
      tag: "Connectivity",
      severity: share < 70 ? "warning" : "info",
      text: `The largest weakly-connected component holds ${share.toFixed(1)}% of the network (${formatNumber(metrics.largest_component_size)} of ${formatNumber(metrics.node_count)} nodes)${
        metrics.weakly_connected_components > 1
          ? `, across ${metrics.weakly_connected_components} total components.`
          : "."
      }`,
    });
  }

  if (metrics.reciprocity !== null && metrics.reciprocity !== undefined) {
    const r = metrics.reciprocity;
    out.push({
      tag: "Reciprocity",
      severity: "info",
      text: `Reciprocity is ${(r * 100).toFixed(1)}% — ${
        r < 0.05
          ? "recommendations rarely run both ways between a pair (one-directional influence)."
          : "a notable share of pairs recommend each other (mutual reinforcement)."
      }`,
    });
  }

  if (metrics.community_count > 1) {
    out.push({
      tag: "Communities",
      severity: "info",
      text: `Detected ${metrics.community_count} communities (modularity ${(metrics.modularity ?? 0).toFixed(2)})${
        (metrics.modularity ?? 0) > 0.3 ? " — strong community structure." : " — weak division."
      }`,
    });
  }

  if (metrics.top_hubs.length > 0) {
    const hub = metrics.top_hubs[0];
    out.push({
      tag: "Top hub",
      severity: "info",
      text: `Most connected source: ${hub.video_id} with ${formatNumber(hub.outgoing ?? 0)} outgoing recommendations.`,
    });
  }

  if (metrics.most_recommended.length > 0) {
    const target = metrics.most_recommended[0];
    out.push({
      tag: "Top authority",
      severity: "info",
      text: `Most recommended video: ${target.video_id} (recommended ${formatNumber(target.times_recommended ?? 0)} times) — a key information source others point to.`,
    });
  }

  if (nodes.length > 0) {
    const scraped = nodes.filter((n) => n.recommendations_scraped).length;
    const unscraped = nodes.length - scraped;
    out.push({
      tag: "Scrape coverage",
      severity: unscraped > 0 && unscraped > scraped ? "warning" : "info",
      text: `${formatNumber(scraped)} of ${formatNumber(nodes.length)} visible nodes have had their recommendations scraped (${
        nodes.length ? Math.round((scraped / nodes.length) * 100) : 0
      }%); ${formatNumber(unscraped)} remain candidates for the next expansion.`,
    });
  }

  const isolated = nodes.filter((n) => n.in_degree === 0 && n.out_degree === 0).length;
  if (isolated > 0) {
    out.push({
      tag: "Isolated nodes",
      severity: "warning",
      text: `${formatNumber(isolated)} node${isolated === 1 ? " is" : "s are"} currently isolated — present in the corpus but not yet connected by recommendation edges. Filter to "Isolated only" to list and scrape them.`,
    });
  }

  return out;
}