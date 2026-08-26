"use client";

import { useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  CircleAlert,
  History,
  Play,
  RefreshCw,
  Square,
} from "lucide-react";
import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { JobProgressCard } from "@/components/features/job-progress-card";
import { ContentHomophilySection } from "@/components/features/content-homophily/content-homophily-section";
import {
  canContinue,
  ECHO_DISCLAIMERS,
  shapeTimeline,
  statusLabel,
  VERDICT_CHIP_CLASSES,
  VERDICT_DESCRIPTIONS,
  VERDICT_LABELS,
  type CommunityStructure,
  type EchoAudience,
  type EchoDetection,
  type EchoLens,
  type EchoLensSeed,
  type EchoProjection,
  type EchoSignalStatus,
  type EchoStructure,
  type EchoTimelineRow,
  type EchoVerdict,
  type EchoChannelShare,
  type MetricEnvelope,
  type NullModelPayload,
} from "@/lib/echo-chamber";
import { formatPercent } from "@/lib/format";
import {
  continueEchoChamber,
  detectEchoChamber,
  echoChamberKeys,
  listEchoDetections,
  stopEchoChamber,
  useEchoAudience,
  useEchoDetection,
  useEchoLens,
  useEchoStructure,
} from "@/services/echoChamber";

const MAX_LAYERS_TOTAL = 10;

function SignalCell({
  label,
  value,
  status,
}: {
  label: string;
  value: number | null;
  status: EchoSignalStatus;
}) {
  if (status !== "available" || value === null) {
    return (
      <span
        className="text-xs text-muted-foreground"
        title={`${label}: not observed`}
      >
        not observed
      </span>
    );
  }
  return <span className="font-mono text-xs">{formatPercent(value)}</span>;
}

/**
 * §36 metadata envelope renderer: available values render numerically with
 * numerator/denominator evidence; unavailable metrics never render as 0.
 */
function EnvelopeValue({ env }: { env: MetricEnvelope }) {
  if (!env) return <span className="text-xs text-muted-foreground">—</span>;
  if (env.status !== "available" || env.value === null || env.value === undefined) {
    const reason =
      (env.detail?.reason as string | undefined) ?? "data unavailable";
    return (
      <span
        className="text-xs text-muted-foreground"
        title={`${env.metric}: ${reason}`}
      >
        unavailable
      </span>
    );
  }
  const ratioText =
    env.numerator != null && env.denominator != null
      ? ` (${env.numerator}/${env.denominator})`
      : "";
  const isShare = env.value >= 0 && env.value <= 1;
  return (
    <span className="font-mono text-xs" title={env.definition ?? env.metric}>
      {isShare ? formatPercent(env.value) : env.value}
      {ratioText}
    </span>
  );
}

function SectionCard({
  title,
  description,
  children,
  testId,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  testId?: string;
}) {
  return (
    <Card data-testid={testId}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
        {description ? (
          <CardDescription>{description}</CardDescription>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  );
}

function VerdictBanner({ detection }: { detection: EchoDetection }) {
  const score = detection.score;
  const verdict: EchoVerdict =
    score?.verdict ?? (canContinue(detection) ? "inconclusive" : "inconclusive");
  const naturalStop =
    detection.status === "exhausted" || detection.status === "unsupported_stop";
  return (
    <SectionCard title="Custom Research Index" testId="echo-verdict"
      description="Researcher-defined composite of selected structural signals — not a probability, not causation."
    >
      <div className="flex flex-wrap items-center gap-3">
        <span
          data-testid="echo-verdict-chip"
          className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${VERDICT_CHIP_CLASSES[verdict]}`}
        >
          {VERDICT_LABELS[verdict]}
        </span>
        {score?.value != null ? (
          <span className="font-mono text-sm text-muted-foreground">
            Custom Lens Score: {score.value.toFixed(3)}
          </span>
        ) : null}
      </div>
      {naturalStop ? (
        <p className="flex items-start gap-2 text-xs text-muted-foreground">
          <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {detection.status === "exhausted"
            ? "The frontier was exhausted: every reachable video's recommendations have been observed. This natural stop is distinct from a verdict."
            : "A crawled layer observed zero recommendation edges, so the crawl stopped honestly instead of inventing content."}
        </p>
      ) : null}
      <div className="overflow-hidden rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Component</TableHead>
              <TableHead>Lens</TableHead>
              <TableHead>Raw value</TableHead>
              <TableHead>Normalized</TableHead>
              <TableHead>Weight</TableHead>
              <TableHead>Contribution</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(score?.components ?? []).map((component) => (
              <TableRow key={component.key}>
                <TableCell className="text-sm">{component.label}</TableCell>
                <TableCell>
                  <Badge variant="outline">{component.lens ?? "—"}</Badge>
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {component.status === "available" &&
                  component.value_raw != null
                    ? component.value_raw.toFixed(4)
                    : "—"}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {component.status === "available" &&
                  component.value_normalized != null
                    ? component.value_normalized.toFixed(4)
                    : "—"}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {component.weight != null
                    ? `${(component.weight * 100).toFixed(0)}%`
                    : "—"}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {component.status === "available"
                    ? (component.weighted_contribution ?? 0).toFixed(4)
                    : "—"}
                </TableCell>
                <TableCell>
                  <Badge
                    variant={
                      component.status === "available" ? "default" : "outline"
                    }
                  >
                    {component.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground">
        All values are observed structural properties of the crawled
        recommendation graph around the seed. Nothing here claims anything
        about viewer beliefs or causation.
      </p>
    </SectionCard>
  );
}

function TimelineTable({ rows }: { rows: EchoTimelineRow[] }) {
  return (
    <div
      className="overflow-x-auto rounded-md border"
      data-testid="echo-timeline"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Layer</TableHead>
            <TableHead>Nodes</TableHead>
            <TableHead>Edges</TableHead>
            <TableHead>Frontier collapse</TableHead>
            <TableHead>Top-channel share</TableHead>
            <TableHead>Community share</TableHead>
            <TableHead>Commenter overlap</TableHead>
            <TableHead>Network nodes</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.layerRunId} data-testid="echo-timeline-row">
              <TableCell className="font-medium">{row.layerIndex}</TableCell>
              <TableCell className="font-mono text-xs">
                {row.nodesDiscovered}
              </TableCell>
              <TableCell className="font-mono text-xs">
                {row.edgesObserved}
              </TableCell>
              <TableCell>
                <SignalCell
                  label="Frontier collapse"
                  value={row.collapsePercent}
                  status={row.statuses.s1}
                />
              </TableCell>
              <TableCell>
                <SignalCell
                  label="Top-channel share"
                  value={row.topChannelShare}
                  status={row.statuses.s3}
                />
              </TableCell>
              <TableCell>
                <SignalCell
                  label="Community share"
                  value={row.communityShare}
                  status={row.statuses.s2}
                />
              </TableCell>
              <TableCell>
                <SignalCell
                  label="Commenter overlap"
                  value={row.commenterOverlap}
                  status={row.statuses.s5}
                />
              </TableCell>
              <TableCell className="font-mono text-xs text-muted-foreground">
                {row.nodesTotal ?? "—"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function SeedCard({ seed }: { seed: EchoLensSeed | null }) {
  if (!seed) return null;
  return (
    <Card className="p-4" data-testid="echo-seed-card">
      <div className="flex items-center gap-3">
        {seed.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={seed.thumbnail_url}
            alt=""
            className="h-12 w-20 shrink-0 rounded object-cover"
          />
        ) : null}
        <div className="min-w-0 text-sm">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Analysis started from
          </p>
          <Link
            href={`/videos/${seed.video_id}`}
            className="font-medium underline underline-offset-2"
            data-testid="echo-seed-link"
          >
            {seed.title ?? seed.video_id}
          </Link>
          <p className="truncate text-xs text-muted-foreground">
            {seed.channel_name ?? seed.channel_id ?? "—"}
          </p>
        </div>
      </div>
    </Card>
  );
}

const LENS_SIGNAL_LABELS: Record<string, string> = {
  s1: "Frontier Collapse",
  s2:
    "Seed Concentration (video) / Seed-Channel Reinforcement Share (channel)",
  s3: "Top Channel Share",
  s4: "Cross-Layer Repetition",
  s5: "Commenter overlap",
};

const LENS_SIGNAL_WEIGHTS: Record<string, string> = {
  s1: "35%",
  s2: "30%",
  s3: "20%",
  s4: "15%",
  s5: "indicative",
};

function S3SharesTable({ shares }: { shares: EchoChannelShare[] }) {
  const max = shares.reduce((m, s) => Math.max(m, s.share), 0);
  return (
    <div className="overflow-x-auto rounded-md border" data-testid="s3-shares-table">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Channel</TableHead>
            <TableHead>Weighted in-degree</TableHead>
            <TableHead className="w-56">Share of attributed edges</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {shares.map((c) => (
            <TableRow key={c.channel_id}>
              <TableCell className="max-w-72 truncate text-sm">
                <a
                  className="hover:underline"
                  href={`/channels/${c.channel_id}`}
                  onClick={(e) => {
                    e.preventDefault();
                    window.location.assign(`/channels/${c.channel_id}`);
                  }}
                >
                  {c.channel_name ?? c.channel_id}
                </a>
              </TableCell>
              <TableCell className="font-mono text-xs">{c.weight}</TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <div className="h-2 w-28 shrink-0 overflow-hidden rounded bg-muted">
                    <div
                      className="h-full rounded bg-primary"
                      style={{
                        width: `${max > 0 ? (c.share / max) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <span className="font-mono text-xs">
                    {formatPercent(c.share)}
                  </span>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// §37 VIDEO LENS sections
// ---------------------------------------------------------------------------

const NETWORK_STAT_LABELS: Record<string, string> = {
  node_count: "Nodes (videos)",
  edge_count: "Edges (unique recommendations)",
  density: "Density",
  reciprocity: "Reciprocity",
  degree_statistics: "Degree statistics (in/out)",
  avg_clustering: "Avg clustering (G.to_undirected())",
  global_clustering: "Global clustering",
  weakly_connected_components: "Weakly connected components",
  largest_component_size: "Largest component",
  largest_component_share: "Largest component share",
};

function NetworkStatsSection({ envelopes }: { envelopes: MetricEnvelope[] }) {
  return (
    <SectionCard
      title="Network Statistics"
      description="Descriptive properties of the observed Video → Video recommendation graph (Category A). Not echo-chamber evidence on their own."
      testId="echo-video-network-stats"
    >
      <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {envelopes.map((env) => (
          <div key={env.metric} className="flex items-baseline justify-between gap-2 border-b pb-1 last:border-b-0">
            <span className="text-sm text-muted-foreground">
              {NETWORK_STAT_LABELS[env.metric] ?? env.metric}
            </span>
            <EnvelopeValue env={env} />
          </div>
        ))}
      </div>
      {envelopes.find((e) => e.metric === "degree_statistics")?.detail ? (
        <p className="text-xs text-muted-foreground">
          Degree P25/P75/P90/P95/P99 percentiles are included in the API
          payload for both in-degree and out-degree.
        </p>
      ) : null}
    </SectionCard>
  );
}

function CommunityStructureSection({
  cs,
}: {
  cs: CommunityStructure | undefined;
}) {
  if (!cs) return null;
  return (
    <SectionCard
      title="Community Structure"
      description="Louvain communities on G.to_undirected() (structural regions of observed recommendations — not groups of users or beliefs)."
      testId="echo-video-community"
    >
      <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
        <div className="flex items-baseline justify-between border-b pb-1">
          <span className="text-sm text-muted-foreground">Community count</span>
          <EnvelopeValue env={cs.community_count} />
        </div>
        <div className="flex items-baseline justify-between border-b pb-1">
          <span className="text-sm text-muted-foreground">Modularity</span>
          <EnvelopeValue env={cs.modularity} />
        </div>
        <div className="flex items-baseline justify-between border-b pb-1">
          <span className="text-sm text-muted-foreground">
            Largest community
          </span>
          <EnvelopeValue env={cs.largest_community_size} />
        </div>
      </div>
      {cs.seed_community?.contains_seed ? (
        <div className="rounded-md border p-2 text-xs" data-testid="echo-seed-community">
          <p className="font-medium">Seed community</p>
          <p className="text-muted-foreground">
            Size {cs.seed_community.size} · share{" "}
            {cs.seed_community.share != null
              ? formatPercent(cs.seed_community.share)
              : "unavailable"}
          </p>
          {cs.seed_community.conductance ? (
            <p className="text-muted-foreground">
              Conductance: <EnvelopeValue env={cs.seed_community.conductance} />{" "}
              · Internal/External:{" "}
              <EnvelopeValue env={cs.seed_community.internal_external_edge_ratio!} />
            </p>
          ) : null}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          Seed community unavailable
          {cs.seed_community?.reason ? `: ${cs.seed_community.reason}` : ""}
        </p>
      )}
      {cs.communities.length > 0 ? (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Community</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Conductance (lower = more separated)</TableHead>
                <TableHead>Internal / external edge ratio</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cs.communities.slice(0, 10).map((comm, idx) => (
                <TableRow key={idx}>
                  <TableCell className="text-xs">
                    #{idx + 1}
                    {comm.is_seed_community ? " (seed)" : ""}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {comm.size}
                  </TableCell>
                  <TableCell>
                    <EnvelopeValue env={comm.conductance} />
                  </TableCell>
                  <TableCell>
                    <EnvelopeValue env={comm.internal_external_edge_ratio} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
    </SectionCard>
  );
}

function NullModelTable({ nm }: { nm: NullModelPayload }) {
  if (nm.status !== "available") {
    return (
      <p className="text-xs text-muted-foreground" data-testid="echo-null-model">
        Null model unavailable
        {nm.detail?.reason ? `: ${nm.detail.reason}` : ""} · n_randomizations{" "}
        {nm.n_randomizations} · seed {nm.seed} · preserves:{" "}
        {(nm.preserves ?? []).join(", ") || "—"}
      </p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-md border" data-testid="echo-null-model">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Observed WCR</TableHead>
            <TableHead>Null mean</TableHead>
            <TableHead>Null SD</TableHead>
            <TableHead>Z-score</TableHead>
            <TableHead>Empirical percentile</TableHead>
            <TableHead>N randomizations</TableHead>
            <TableHead>Seed</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell className="font-mono text-xs">
              {nm.observed?.value != null ? nm.observed.value.toFixed(4) : "—"}
            </TableCell>
            <TableCell className="font-mono text-xs">
              {nm.null_mean?.toFixed(4) ?? "—"}
            </TableCell>
            <TableCell className="font-mono text-xs">
              {nm.null_sd?.toFixed(4) ?? "—"}
            </TableCell>
            <TableCell className="font-mono text-xs">
              {nm.z_score?.toFixed(3) ?? "undefined (zero null SD)"}
            </TableCell>
            <TableCell className="font-mono text-xs">
              {nm.empirical_percentile != null
                ? formatPercent(nm.empirical_percentile)
                : "—"}
            </TableCell>
            <TableCell className="font-mono text-xs">
              {nm.n_randomizations}
            </TableCell>
            <TableCell className="font-mono text-xs">{nm.seed}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <p className="p-2 text-xs text-muted-foreground">
        Null model: degree-preserving double-edge swaps on
        G.to_undirected() — preserves node count, edge count and the degree
        sequence; edge directions are not preserved. Communities re-detected
        per randomization with the same seeded algorithm.
      </p>
    </div>
  );
}

function ReinforcementSection({
  reinforcement,
}: {
  reinforcement: EchoStructure["video_lens"]["reinforcement"] | undefined;
}) {
  if (!reinforcement) return null;
  const persistence = reinforcement.community_persistence ?? [];
  return (
    <SectionCard
      title="Recommendation Reinforcement"
      description="Structural insularity evidence: within-community recommendation rate vs a seeded degree-preserving null model, plus community persistence across crawl layers."
      testId="echo-video-reinforcement"
    >
      <div className="flex items-baseline justify-between border-b pb-1">
        <span className="text-sm text-muted-foreground">
          Within-community recommendation rate (WCR)
        </span>
        <EnvelopeValue env={reinforcement.within_community_recommendation_rate} />
      </div>
      <NullModelTable nm={reinforcement.null_model} />
      {persistence.length > 0 ? (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Layer</TableHead>
                <TableHead>Nodes</TableHead>
                <TableHead>Edges</TableHead>
                <TableHead>Seed-comm. share</TableHead>
                <TableHead>Dominant-comm. share</TableHead>
                <TableHead>WCR</TableHead>
                <TableHead>Persistence (Jaccard vs prev.)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {persistence.map((row) => (
                <TableRow key={row.layer_index}>
                  <TableCell className="font-mono text-xs">
                    {row.layer_index}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {row.node_count}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {row.edge_count}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {row.seed_community_share != null
                      ? formatPercent(row.seed_community_share)
                      : "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {row.dominant_community_share != null
                      ? formatPercent(row.dominant_community_share)
                      : "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {row.within_community_recommendation_rate != null
                      ? formatPercent(row.within_community_recommendation_rate)
                      : "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {row.persistence_jaccard_vs_previous != null
                      ? row.persistence_jaccard_vs_previous.toFixed(4)
                      : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
    </SectionCard>
  );
}

const CENTRALITY_LABELS: Record<string, string> = {
  pagerank: "PageRank (top)",
  hits_hubs: "HITS hubs (top)",
  hits_authorities: "HITS authorities (top)",
};

function CentralitySection({
  centrality,
}: {
  centrality: EchoStructure["video_lens"]["centrality"] | undefined;
}) {
  if (!centrality) return null;
  return (
    <SectionCard
      title="Centrality"
      description="Structural prominence in the directed recommendation graph — NOT ideological influence or viewer importance."
      testId="echo-video-centrality"
    >
      <div className="space-y-3">
        {(["pagerank", "hits_hubs", "hits_authorities"] as const).map(
              (key) => {
                const env = centrality[key];
                const top = (env?.detail?.top ?? []) as {
                  id: string;
                  score: number;
                  title?: string | null;
                }[];
                return (
                  <div key={key}>
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-sm font-medium">
                        {CENTRALITY_LABELS[key]}
                      </span>
                    </div>
                    {env && top.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {top.slice(0, 5).map((item) => (
                          <Link
                            key={item.id}
                            href={`/videos/${item.id}`}
                            className="rounded bg-muted px-2 py-0.5 font-mono text-xs hover:underline"
                            title={item.title ?? item.id}
                          >
                            {(item.title ?? item.id).slice(0, 24)}
                            {" "}
                            ({item.score.toFixed(4)})
                          </Link>
                        ))}
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        unavailable
                      </span>
                    )}
                  </div>
                );
              },
            )}
      </div>
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// §37 CHANNEL LENS sections
// ---------------------------------------------------------------------------

function ChannelNetworkSection({
  channelLens,
}: {
  channelLens: EchoStructure["channel_lens"] | undefined;
}) {
  if (!channelLens) return null;
  return (
    <SectionCard
      title="Channel Network"
      description="Channel → Channel projection of the video graph. Repeated video edges between the same channels collapse to one unique channel edge; edges with unresolvable endpoint channels are dropped and counted."
      testId="echo-channel-network"
    >
      <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {channelLens.network.map((env) => (
          <div key={env.metric} className="flex items-baseline justify-between gap-2 border-b pb-1 last:border-b-0">
            <span className="text-sm text-muted-foreground">
              {NETWORK_STAT_LABELS[env.metric] ?? env.metric.replace(/_/g, " ")}
            </span>
            <EnvelopeValue env={env} />
          </div>
        ))}
        <div className="flex items-baseline justify-between border-b pb-1">
          <span className="text-sm text-muted-foreground">
            Unattributed edges (dropped)
          </span>
          <EnvelopeValue env={channelLens.unattributed_edges} />
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        {channelLens.projection_rule}
      </p>
    </SectionCard>
  );
}

function ConcentrationSection({
  concentration,
  shares,
  s3Open,
  setS3Open,
}: {
  concentration: EchoStructure["channel_lens"]["concentration"] | undefined;
  shares: EchoChannelShare[];
  s3Open: boolean;
  setS3Open: (fn: (open: boolean) => boolean) => void;
}) {
  if (!concentration) return null;
  return (
    <SectionCard
      title="Channel Concentration"
      description="Concentration at channel level (Category D). Concentration is not automatically content homophily or an echo chamber."
      testId="echo-channel-concentration"
    >
      <div className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
        <div className="flex items-baseline justify-between border-b pb-1">
          <span className="text-sm text-muted-foreground">
            Top channel share
          </span>
          <EnvelopeValue env={concentration.top_channel_share} />
        </div>
        <div className="flex items-baseline justify-between border-b pb-1">
          <span className="text-sm text-muted-foreground">HHI</span>
          <EnvelopeValue env={concentration.hhi} />
        </div>
        <div className="flex items-baseline justify-between border-b pb-1">
          <span className="text-sm text-muted-foreground">Unique channels</span>
          <EnvelopeValue env={concentration.unique_channel_count} />
        </div>
      </div>
      {shares.length > 0 ? (
        <>
          <button
            type="button"
            onClick={() => setS3Open((open) => !open)}
            className="inline-flex items-center gap-1 text-left text-sm underline-offset-2 hover:underline"
            data-testid="s3-shares-toggle"
            aria-expanded={s3Open}
          >
            {s3Open ? (
              <ChevronDown className="size-3.5" aria-hidden />
            ) : (
              <ChevronRight className="size-3.5" aria-hidden />
            )}
            All channel shares ({shares.length})
          </button>
          {s3Open ? <S3SharesTable shares={shares} /> : null}
        </>
      ) : null}
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// Custom signals + audience + disclaimers
// ---------------------------------------------------------------------------

function CustomSignalsSection({
  lens,
  projection,
}: {
  lens: EchoLens | undefined;
  projection: EchoProjection;
}) {
  const keys =
    projection === "video" ? ["s1", "s2", "s4", "s5"] : ["s1", "s2", "s4"];
  return (
    <SectionCard
      title="Custom Research Signals"
      description="Project-specific signals defined by this project's researcher — NOT standard, universally accepted echo-chamber metrics; not causal; not probabilities."
      testId={`echo-custom-signals-${projection}`}
    >
      <div className="overflow-hidden rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Signal</TableHead>
              <TableHead>Nominal weight</TableHead>
              <TableHead>Lens</TableHead>
              <TableHead>Value</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {keys.map((key) => {
              const signal = lens?.signals?.[
                key as keyof NonNullable<EchoLens["signals"]>
              ];
              return (
                <TableRow key={key}>
                  <TableCell className="text-sm">
                    {LENS_SIGNAL_LABELS[key] ?? key}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {LENS_SIGNAL_WEIGHTS[key]}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {key === "s3" || (projection === "channel" && key !== "s5")
                        ? "channel"
                        : key === "s5"
                          ? "audience"
                          : "video"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <SignalCell
                      label={key}
                      value={signal?.value ?? null}
                      status={(signal?.status ?? "unavailable") as EchoSignalStatus}
                    />
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        signal?.status === "available" ? "default" : "outline"
                      }
                    >
                      {signal?.status ?? "unavailable"}
                    </Badge>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </SectionCard>
  );
}

function AudienceSection({ audience }: { audience: EchoAudience | undefined }) {
  const block = audience?.commenter_overlap;
  return (
    <SectionCard
      title="Commenter Overlap"
      description="Separate analytical layer built from comment authors — never merged into the recommendation graph. Overlap does not establish shared beliefs."
      testId="echo-audience-overlap"
    >
      {!block || block.status !== "available" ? (
        <p className="text-sm text-muted-foreground" data-testid="audience-status">
          Unavailable
          {block?.reason ? `: ${block.reason}` : block ? `: ${block.status}` : ""}
        </p>
      ) : (
        <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
          <div className="flex items-baseline justify-between border-b pb-1">
            <span className="text-sm text-muted-foreground">
              Mean Jaccard overlap (all pairs)
            </span>
            <EnvelopeValue env={block.jaccard_mean} />
          </div>
          <div className="flex items-baseline justify-between border-b pb-1">
            <span className="text-sm text-muted-foreground">
              Within-community overlap
            </span>
            <EnvelopeValue env={block.within_community_jaccard_mean} />
          </div>
          <div className="flex items-baseline justify-between border-b pb-1">
            <span className="text-sm text-muted-foreground">
              Between-community overlap
            </span>
            <EnvelopeValue env={block.between_community_jaccard_mean} />
          </div>
          <div className="flex items-baseline justify-between border-b pb-1">
            <span className="text-sm text-muted-foreground">
              Videos with commenters
            </span>
            <EnvelopeValue env={block.videos_with_commenters} />
          </div>
        </div>
      )}
    </SectionCard>
  );
}

export function DisclaimersCard({ disclaimers }: { disclaimers?: string[] }) {
  const items = disclaimers?.length ? disclaimers : ECHO_DISCLAIMERS;
  return (
    <Card data-testid="echo-disclaimers">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Research Disclaimer</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
          {items.map((line, idx) => (
            <li key={idx}>{line}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function StructureSections({
  detectionId,
  projection,
}: {
  detectionId: string;
  projection: "video" | "channel";
}) {
  const structureQuery = useEchoStructure(detectionId);
  const [s3Open, setS3Open] = useState(false);
  let body: React.ReactNode;
  if (structureQuery.isLoading) {
    body = (
      <Card className="p-6 text-center text-sm text-muted-foreground">
        Computing {projection}-lens structure from stored crawl edges…
      </Card>
    );
  } else if (structureQuery.isError || !structureQuery.data) {
    body = (
      <Card className="p-6 text-sm text-muted-foreground">
        Structural analysis is not available for this detection.
      </Card>
    );
  } else {
    const structure: EchoStructure = structureQuery.data;
    body =
      projection === "video" ? (
        <div className="space-y-4">
          <NetworkStatsSection
            envelopes={structure.video_lens.network_statistics}
          />
          <CommunityStructureSection
            cs={structure.video_lens.community_structure}
          />
          <ReinforcementSection
            reinforcement={structure.video_lens.reinforcement}
          />
          <CentralitySection centrality={structure.video_lens.centrality} />
        </div>
      ) : (
        <div className="space-y-4">
          <ChannelNetworkSection channelLens={structure.channel_lens} />
          <ConcentrationSection
            concentration={structure.channel_lens.concentration}
            shares={structure.channel_lens.concentration.shares.map((s) => ({
              ...s,
              channel_name: null,
            }))}
            s3Open={s3Open}
            setS3Open={setS3Open}
          />
        </div>
      );
  }
  return (
    <div className="space-y-4" data-testid={`echo-lens-${projection}`}>
      {body}
      {projection === "video" ? (
        <VideoCustomSignalsWrapper detectionId={detectionId} />
      ) : (
        <ChannelCustomSignalsWrapper detectionId={detectionId} />
      )}
    </div>
  );
}

/** Custom signals read from the on-demand lens endpoint (existing math). */
function VideoCustomSignalsWrapper({ detectionId }: { detectionId: string }) {
  const lensQuery = useEchoLens(detectionId, "video");
  return (
    <CustomSignalsSection lens={lensQuery.data} projection="video" />
  );
}

function ChannelCustomSignalsWrapper({ detectionId }: { detectionId: string }) {
  const lensQuery = useEchoLens(detectionId, "channel");
  return (
    <CustomSignalsSection lens={lensQuery.data} projection="channel" />
  );
}

function TopVideosTable({ videos }: { videos: EchoLens["top_videos"] }) {
  if (videos.length === 0) return null;
  return (
    <div className="overflow-x-auto rounded-md border" data-testid="echo-top-videos">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Top videos (in-degree)</TableHead>
            <TableHead>Channel</TableHead>
            <TableHead>In</TableHead>
            <TableHead>Out</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {videos.map((v) => (
            <TableRow key={v.video_id}>
              <TableCell className="max-w-72 truncate">
                <Link
                  href={`/videos/${v.video_id}`}
                  className="underline-offset-2 hover:underline"
                  title={v.title ?? v.video_id}
                >
                  {v.title ?? v.video_id}
                </Link>
              </TableCell>
              <TableCell className="max-w-40 truncate text-xs text-muted-foreground">
                {v.channel_name ?? v.channel_id ?? "—"}
              </TableCell>
              <TableCell className="font-mono text-xs">{v.in_degree}</TableCell>
              <TableCell className="font-mono text-xs">{v.out_degree}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function TopChannelsTable({
  channels,
}: {
  channels: EchoLens["top_channels"];
}) {
  if (channels.length === 0) return null;
  return (
    <div className="overflow-x-auto rounded-md border" data-testid="echo-top-channels">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Top channels (weighted in-degree)</TableHead>
            <TableHead>Weighted in-degree</TableHead>
            <TableHead>Share of edges</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {channels.map((c) => (
            <TableRow key={c.channel_id}>
              <TableCell className="max-w-72 truncate">
                <a
                  className="hover:underline"
                  href={`/channels/${c.channel_id}`}
                  onClick={(e) => {
                    e.preventDefault();
                    window.location.assign(`/channels/${c.channel_id}`);
                  }}
                >
                  {c.channel_name ?? c.channel_id}
                </a>
              </TableCell>
              <TableCell className="font-mono text-xs">
                {c.weighted_in_degree}
              </TableCell>
              <TableCell className="font-mono text-xs">
                {c.share != null ? formatPercent(c.share) : "—"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function TopTablesSection({
  detectionId,
  projection,
}: {
  detectionId: string;
  projection: EchoProjection;
}) {
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const lensVideo = useEchoLens(detectionId, "video");
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const lensChannel = useEchoLens(detectionId, "channel");
  if (projection === "video") {
    return <TopVideosTable videos={lensVideo.data?.top_videos ?? []} />;
  }
  return <TopChannelsTable channels={lensChannel.data?.top_channels ?? []} />;
}

function downloadBlob(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function toCsv(rows: Record<string, unknown>[]): string {
  if (rows.length === 0) return "";
  const headers = Array.from(
    rows.reduce<Set<string>>((acc, r) => {
      Object.keys(r).forEach((k) => acc.add(k));
      return acc;
    }, new Set()),
  );
  const esc = (v: unknown) =>
    `"${String(v ?? "").replace(/"/g, '""')}"`;
  const lines = [headers.join(",")];
  for (const r of rows) {
    lines.push(headers.map((h) => esc((r as any)[h])).join(","));
  }
  return lines.join("\n");
}

function EchoExportMenu({ detection }: { detection: any }) {
  const base = detection?.detection_id ?? "echo";
  const exportJson = () =>
    downloadBlob(`${base}.json`, JSON.stringify(detection, null, 2), "application/json");
  const exportTimeline = () => {
    const rows = (detection?.layers ?? []).map((l: any) => ({
      layer_index: l.layer_index,
      status: l.status,
      s1_frontier_collapse: l.signals?.s1?.value,
      s2_seed_reinforcement: l.signals?.s2?.value,
      s3_top_channel_share: l.signals?.s3?.value,
      s4_cross_layer_repetition: l.signals?.s4?.value,
      new_edges: l.new_edges,
    }));
    downloadBlob(`${base}_timeline.csv`, toCsv(rows), "text/csv");
  };
  const exportChannels = () => {
    const rows = (detection?.top_channels ?? []).map((c: any) => ({
      channel_id: c.channel_id,
      channel_name: c.channel_name,
      weighted_in_degree: c.weighted_in_degree,
      share: c.share,
    }));
    downloadBlob(`${base}_channels.csv`, toCsv(rows), "text/csv");
  };
  const exportVideos = () => {
    const rows = (detection?.top_videos ?? []).map((v: any) => ({
      video_id: v.video_id,
      title: v.title,
      in_degree: v.in_degree,
      out_degree: v.out_degree,
    }));
    downloadBlob(`${base}_videos.csv`, toCsv(rows), "text/csv");
  };
  return (
    <details className="relative inline-block" data-testid="echo-export">
      <summary className="cursor-pointer select-none rounded-md border px-3 py-1.5 text-sm">
        Export
      </summary>
      <div className="absolute right-0 z-10 mt-1 w-48 space-y-1 rounded-md border bg-background p-2 shadow">
        <button className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-muted" onClick={exportJson}>
          JSON (full record)
        </button>
        <button className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-muted" onClick={exportTimeline}>
          CSV (timeline)
        </button>
        <button className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-muted" onClick={exportChannels}>
          CSV (channels)
        </button>
        <button className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-muted" onClick={exportVideos}>
          CSV (videos)
        </button>
      </div>
    </details>
  );
}

export function EchoChamberView() {
  const [videoUrl, setVideoUrl] = useState("");
  const [maxLayers, setMaxLayers] = useState(5);
  const [collectComments, setCollectComments] = useState(false);
  const [projection, setProjection] = useState<"video" | "channel">("video");
  const [extraLayers, setExtraLayers] = useState(2);
  const [detectionId, setDetectionId] = useState<string | null>(null);

  // Detection history: persisted rows for this workspace, newest first.
  // Without this a finished analysis was unreachable after a reload (the
  // selected id only lived in component state).
  const historyQuery = useQuery({
    queryKey: echoChamberKeys.list,
    queryFn: () => listEchoDetections(),
  });
  const history = historyQuery.data?.items ?? [];

  // Auto-select the most recent detection once, so returning researchers see
  // their latest analysis instead of an empty state.
  const autoSelectedRef = useRef(false);
  useEffect(() => {
    if (autoSelectedRef.current || detectionId) return;
    const latest = history[0];
    if (latest && historyQuery.isSuccess) {
      setDetectionId(latest.detection_id);
      autoSelectedRef.current = true;
    }
  }, [history, historyQuery.isSuccess, detectionId]);

  const detectionQuery = useEchoDetection(detectionId);
  const detection = detectionQuery.data;

  // Lenses: both projections are fetched once per (detection, projection) and
  // cached by the query client; sections and the seed card read cached data.
  const lensVideo = useEchoLens(detectionId, "video");
  const lensChannel = useEchoLens(detectionId, "channel");

  // Audience lens: fetched once per detection and cached.
  const audienceQuery = useEchoAudience(detectionId);

  const detect = useMutation({
    mutationFn: () =>
      detectEchoChamber({
        video_url: videoUrl.trim() || undefined,
        max_layers: maxLayers,
        collect_comments: collectComments,
        projection,
      }),
    onSuccess: (payload) => setDetectionId(payload.detection_id),
  });

  const cont = useMutation({
    mutationFn: () =>
      continueEchoChamber(detectionId as string, extraLayers),
    onSuccess: () => detectionQuery.refetch(),
  });

  const stop = useMutation({
    mutationFn: () => stopEchoChamber(detectionId as string),
    onSuccess: () => detectionQuery.refetch(),
  });

  const running =
    !!detection && (detection.status === "pending" || detection.status === "running");
  const rows = detection ? shapeTimeline(detection.layers) : [];

  return (
    <div className="space-y-6" data-testid="echo-chamber-view">
      <Card>
        <CardHeader>
          <CardTitle>Detect an echo chamber</CardTitle>
          <CardDescription>
            Paste a video link. The detector crawls up to N recommendation
            layers around it as one background job and reports observed
            per-layer signals — never estimates.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-[1fr_auto_auto] md:items-end">
            <div className="space-y-1.5">
              <Label htmlFor="echo-video-url">Video URL or ID</Label>
              <Input
                id="echo-video-url"
                placeholder="https://www.youtube.com/watch?v=…"
                value={videoUrl}
                onChange={(event) => setVideoUrl(event.target.value)}
                disabled={running}
                data-testid="echo-video-url"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="echo-max-layers">Max layers</Label>
              <Input
                id="echo-max-layers"
                type="number"
                min={1}
                max={MAX_LAYERS_TOTAL}
                value={maxLayers}
                onChange={(event) =>
                  setMaxLayers(
                    Math.max(
                      1,
                      Math.min(MAX_LAYERS_TOTAL, Number(event.target.value) || 1),
                    ),
                  )
                }
                disabled={running}
                className="w-28"
                data-testid="echo-max-layers"
              />
            </div>
            <Button
              onClick={() => detect.mutate()}
              disabled={running || videoUrl.trim().length === 0 || detect.isPending}
              data-testid="echo-detect-button"
            >
              <Play className="size-4" aria-hidden />
              {detect.isPending ? "Starting…" : "Detect"}
            </Button>
          </div>
          <div className="flex items-center gap-3">
            <div className="space-y-1.5" data-testid="echo-projection">
              <Label htmlFor="echo-projection-sel">Measure over</Label>
              <select
                id="echo-projection-sel"
                value={projection}
                onChange={(e) =>
                  setProjection(e.target.value as "video" | "channel")
                }
                disabled={running}
                className="h-9 rounded-md border bg-background px-2 text-sm"
              >
                <option value="video">Videos (recommendation graph)</option>
                <option value="channel">Channels (channel graph)</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
            <Checkbox
              id="echo-collect-comments"
              checked={collectComments}
              onCheckedChange={(checked) =>
                setCollectComments(checked === true)
              }
              disabled={running}
              data-testid="echo-collect-comments"
            />
            <Label htmlFor="echo-collect-comments" className="text-sm font-normal">
              Collect comments during the crawl (enables the commenter-overlap
              signal)
            </Label>
          </div>
          </div>
          {detect.isError ? (
            <p className="text-sm text-destructive">{String(detect.error)}</p>
          ) : null}
        </CardContent>
      </Card>

      {history.length > 0 && (
        <Card className="p-4" data-testid="echo-history">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-sm font-medium">
              <History className="size-4" aria-hidden /> Recent detections
            </span>
            {history.slice(0, 8).map((item) => (
              <button
                key={item.detection_id}
                type="button"
                onClick={() => setDetectionId(item.detection_id)}
                className={`rounded-full border px-3 py-1 text-xs transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  item.detection_id === detectionId
                    ? "border-primary bg-primary/10 text-foreground"
                    : "text-muted-foreground hover:bg-muted"
                }`}
                title={`${item.status} · ${item.created_at}`}
              >
                {item.detection_id.slice(4, 18)}… · {statusLabel(item.status)}
              </button>
            ))}
          </div>
        </Card>
      )}

      {!detection ? (
        <Card className="p-8 text-center text-sm text-muted-foreground" data-testid="echo-empty">
          No detection yet. Paste a video link above and press Detect to start
          a layered crawl.
        </Card>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Badge variant="secondary" data-testid="echo-status">
              {statusLabel(detection.status)}
            </Badge>
            <span className="font-mono text-xs text-muted-foreground">
              {detection.detection_id}
            </span>
            {running ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => stop.mutate()}
                disabled={stop.isPending}
                data-testid="echo-stop"
              >
                <Square className="size-3.5" aria-hidden />
                Stop
              </Button>
            ) : null}
            {canContinue(detection) ? (
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min={1}
                  max={MAX_LAYERS_TOTAL}
                  value={extraLayers}
                  onChange={(event) =>
                    setExtraLayers(
                      Math.max(
                        1,
                        Math.min(
                          MAX_LAYERS_TOTAL,
                          Number(event.target.value) || 1,
                        ),
                      ),
                    )
                  }
                  className="w-24"
                  aria-label="Extra layers"
                  data-testid="echo-extra-layers"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => cont.mutate()}
                  disabled={cont.isPending}
                  data-testid="echo-continue"
                >
                  <RefreshCw className="size-3.5" aria-hidden />
                  Continue crawling
                </Button>
              </div>
            ) : null}
          </div>

          {detection.error ? (
            <p className="text-sm text-muted-foreground" data-testid="echo-error">
              {detection.error}
            </p>
          ) : null}

          {detection.job_id ? (
            <JobProgressCard jobId={detection.job_id} title="Echo crawl" />
          ) : null}

          <SeedCard
            seed={lensVideo.data?.seed ?? lensChannel.data?.seed ?? null}
          />

          <div className="flex justify-end">
            <EchoExportMenu detection={detection} />
          </div>

          <Tabs defaultValue="video">
            <TabsList>
              <TabsTrigger value="video">Videos</TabsTrigger>
              <TabsTrigger value="channel">Channels</TabsTrigger>
              <TabsTrigger value="audience">Audience</TabsTrigger>
              <TabsTrigger value="content" data-testid="echo-tab-content">
                Content
              </TabsTrigger>
            </TabsList>
            <TabsContent value="video" className="mt-4 space-y-4">
              <StructureSections detectionId={detection.detection_id} projection="video" />
              <TopTablesSection
                detectionId={detection.detection_id}
                projection="video"
              />
            </TabsContent>
            <TabsContent value="channel" className="mt-4 space-y-4">
              <StructureSections detectionId={detection.detection_id} projection="channel" />
              <TopTablesSection
                detectionId={detection.detection_id}
                projection="channel"
              />
            </TabsContent>
            <TabsContent value="audience" className="mt-4 space-y-4">
              <AudienceSection audience={audienceQuery.data} />
            </TabsContent>
            <TabsContent value="content" className="mt-4 space-y-4">
              <p className="text-xs text-muted-foreground">
                Content Homophily is an independent, opt-in CONTENT evidence
                layer (usable from any supported network). It is kept separate
                from the structural signals above and never merged into a
                composite score.
              </p>
              <ContentHomophilySection />
            </TabsContent>
          </Tabs>

          {rows.length > 0 ? (
            <TimelineTable rows={rows} />
          ) : (
            <Card className="p-6 text-center text-sm text-muted-foreground" data-testid="echo-empty-running">
              The seed layer is being prepared. Timeline rows appear as each
              layer completes.
            </Card>
          )}

          {detection.score ? <VerdictBanner detection={detection} /> : null}

          <DisclaimersCard />
        </div>
      )}
    </div>
  );
}
