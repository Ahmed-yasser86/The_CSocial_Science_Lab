"use client";

import { useMemo } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  useCommenterNetworkCommunityInsights,
  useCommenterNetworkRoles,
  useNetworkCommunityInsights,
  useNetworkRoles,
} from "@/services/networkFull";
import type { CommenterNetworkParams } from "@/services/networkFull";
import type {
  CommunityInsight,
  CommenterCommunityInsight,
  NetworkRole,
} from "@/lib/network-full-types";

const ROLE_COLORS: Record<NetworkRole, string> = {
  core: "bg-primary/15 text-primary",
  broker: "bg-accent2/15 text-accent2",
  bridge: "bg-accent/15 text-accent",
  periphery: "bg-muted text-muted-foreground",
};

function RolesPanelContent({
  query,
  onSelectCommenter,
}: {
  query: ReturnType<typeof useNetworkRoles> | ReturnType<typeof useCommenterNetworkRoles>;
  onSelectCommenter?: (id: string) => void;
}) {
  const { data, isLoading, isError, error, refetch } = query as ReturnType<
    typeof useNetworkRoles
  >;
  if (isLoading) {
    return (
      <Card className="p-4">
        <p className="text-sm text-muted-foreground">Loading roles…</p>
      </Card>
    );
  }
  if (isError) {
    return (
      <Card className="p-4">
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load roles"}
        </p>
      </Card>
    );
  }
  if (!data?.nodes || Object.keys(data.nodes).length === 0) {
    return (
      <Card className="p-4">
        <p className="text-sm text-muted-foreground">
          No nodes available for role assignment.
        </p>
      </Card>
    );
  }
  const counts = { core: 0, broker: 0, bridge: 0, periphery: 0 } as Record<
    NetworkRole,
    number
  >;
  for (const n of Object.values(data.nodes)) counts[n.role] += 1;
  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium">Structural roles</h3>
        <div className="flex flex-wrap items-center gap-1.5">
          {(Object.keys(counts) as NetworkRole[]).map((r) => (
            <Badge key={r} className={ROLE_COLORS[r]}>
              {r}: {counts[r]}
            </Badge>
          ))}
        </div>
      </div>
      <p className="mb-2 text-xs text-muted-foreground">
        core = top eigenvector quartile · broker = top betweenness decile ·
        periphery = bottom degree quartile · bridge = otherwise. Seeds fixed
        (louvain 42) so assignments are deterministic.
      </p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {(Object.keys(counts) as NetworkRole[]).map((r) => (
          <div key={r} className="rounded-md border border-border p-2">
            <div className="mb-1 text-xs font-medium capitalize">{r}</div>
            <ol className="space-y-0.5 text-xs">
              {Object.entries(data.nodes)
                .filter(([, d]) => d.role === r)
                .slice(0, 5)
                 .map(([id, d]) => (
                  <li key={id} className="flex items-center justify-between gap-2">
                    <button
                      type="button"
                      disabled={!onSelectCommenter}
                      onClick={() => onSelectCommenter?.(id)}
                      className="truncate font-mono text-left hover:text-primary disabled:cursor-default disabled:hover:text-inherit"
                    >
                      {id}
                    </button>
                    <span className="text-muted-foreground">
                      c{d.community_id}
                    </span>
                  </li>
                ))}
            </ol>
          </div>
        ))}
      </div>
    </Card>
  );
}

function CommunityInsightsContent({
  query,
  onSelectCommenter,
}: {
  query:
    | ReturnType<typeof useNetworkCommunityInsights>
    | ReturnType<typeof useCommenterNetworkCommunityInsights>;
  onSelectCommenter?: (id: string) => void;
}) {
  const { data, isLoading, isError, error } = query as ReturnType<
    typeof useNetworkCommunityInsights
  >;
  if (isLoading) {
    return (
      <Card className="p-4">
        <p className="text-sm text-muted-foreground">Loading communities…</p>
      </Card>
    );
  }
  if (isError) {
    return (
      <Card className="p-4">
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load communities"}
        </p>
      </Card>
    );
  }
  if (!data?.communities || data.communities.length === 0) {
    return (
      <Card className="p-4">
        <p className="text-sm text-muted-foreground">
          No communities detected for this slice.
        </p>
      </Card>
    );
  }
  return (
    <div className="space-y-3">
      {data.communities.map((raw) => {
        const cRec = raw as CommunityInsight;
        const cCom = raw as unknown as CommenterCommunityInsight;
        const isRec = "dominant_channels" in raw;
        const dominantChannels = isRec ? cRec.dominant_channels : [];
        const dominantKinds = isRec ? {} : cCom.dominant_kinds;
        const topCoreRows = (isRec ? cRec.top_eigenvector : []).map((n) => ({
          id: n.id,
          label: n.label,
          score: n.value,
        }));
        const topBridgeRows = (isRec ? cRec.top_betweenness : cCom.top_bridges).map(
          (n) => ({
            id: n.id,
            label: n.label,
            score: "value" in n ? n.value : n.betweenness,
          }),
        );
        return (
          <Card key={cRec.community_id} className="p-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-medium">Community {cRec.community_id}</h4>
              <Badge variant="outline">{cRec.size} nodes</Badge>
            </div>
            {isRec && dominantChannels.length > 0 ? (
              <div className="mb-2 text-xs text-muted-foreground">
                <span className="font-medium">Dominant channels: </span>
                {dominantChannels
                  .map((d) => `${d.channel_id} (${d.count})`)
                  .join(", ")}
              </div>
            ) : null}
            {!isRec ? (
              <div className="mb-2 text-xs text-muted-foreground">
                <span className="font-medium">Node kinds: </span>
                {Object.entries(dominantKinds)
                  .map(([k, v]) => `${k} ${v}`)
                  .join(", ")}
              </div>
            ) : null}
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div>
                <div className="mb-1 text-xs font-medium">Top core (eigenvector)</div>
                <ol className="space-y-0.5 text-xs">
                  {topCoreRows
                    .slice(0, 5)
                    .map((n) => (
                      <li key={n.id} className="flex justify-between gap-2">
                        <button
                          type="button"
                          disabled={!onSelectCommenter}
                          onClick={() => onSelectCommenter?.(n.id)}
                          className="truncate font-mono text-left hover:text-primary disabled:cursor-default disabled:hover:text-inherit"
                        >
                          {n.label ?? n.id}
                        </button>
                        <span className="text-muted-foreground">
                          {n.score.toFixed(3)}
                        </span>
                      </li>
                    ))}
                </ol>
              </div>
              <div>
                <div className="mb-1 text-xs font-medium">Top bridges (betweenness)</div>
                <ol className="space-y-0.5 text-xs">
                  {topBridgeRows
                    .slice(0, 5)
                    .map((n) => (
                      <li key={n.id} className="flex justify-between gap-2">
                        <button
                          type="button"
                          disabled={!onSelectCommenter}
                          onClick={() => onSelectCommenter?.(n.id)}
                          className="truncate font-mono text-left hover:text-primary disabled:cursor-default disabled:hover:text-inherit"
                        >
                          {n.label ?? n.id}
                        </button>
                        <span className="text-muted-foreground">
                          {n.score.toFixed(3)}
                        </span>
                      </li>
                    ))}
                </ol>
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
}

export function NetworkRolesPanel({ runId }: { runId?: string | null }) {
  const query = useNetworkRoles({
    runId: runId ?? undefined,
    projection: "video",
  });
  return <RolesPanelContent query={query} />;
}

export function NetworkCommunityInsightsPanel({
  runId,
}: {
  runId?: string | null;
}) {
  const query = useNetworkCommunityInsights({
    runId: runId ?? undefined,
    projection: "video",
  });
  return <CommunityInsightsContent query={query} />;
}

export function CommenterRolesPanel({
  runId,
  projection,
  weight,
  onSelectCommenter,
  minShared,
  topN,
  maxCandidates,
}: CommenterNetworkParams & { onSelectCommenter?: (id: string) => void }) {
  const query = useCommenterNetworkRoles({
    runId,
    projection,
    weight,
    minShared,
    topN,
    maxCandidates,
  });
  return <RolesPanelContent query={query} onSelectCommenter={onSelectCommenter} />;
}

export function CommenterCommunityInsightsPanel({
  runId,
  projection,
  weight,
  onSelectCommenter,
  minShared,
  topN,
  maxCandidates,
}: CommenterNetworkParams & { onSelectCommenter?: (id: string) => void }) {
  const query = useCommenterNetworkCommunityInsights({
    runId,
    projection,
    weight,
    minShared,
    topN,
    maxCandidates,
  });
  return (
    <CommunityInsightsContent query={query} onSelectCommenter={onSelectCommenter} />
  );
}
