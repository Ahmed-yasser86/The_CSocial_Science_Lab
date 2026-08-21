"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  QueryGroup,
  ResearchEntity,
  ResearchQuery,
} from "@/lib/types";
import { QueryBuilder } from "@/components/features/query-builder";
import { FunnelPreview } from "@/components/features/funnel-preview";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  usePreviewResearchQuery,
  useResolveResearchQuery,
} from "@/services/queries";
import { useResearchContext } from "@/lib/context";
import { Button } from "@/components/ui/button";

const ENTITY_QUERY_PARAM = "entity";

function serializeRoot(root: QueryGroup): string {
  return JSON.stringify(root);
}

export function QueryWorkspace({
  initialEntity,
  initialRoot,
}: {
  initialEntity: ResearchEntity;
  initialRoot: QueryGroup | null;
}) {
  const router = useRouter();
  const { context } = useResearchContext();
  const [entity, setEntity] = useState<ResearchEntity>(initialEntity);
  const [root, setRoot] = useState<QueryGroup | null>(initialRoot);

  const updateUrl = useCallback(
    (nextEntity: ResearchEntity, nextRoot: QueryGroup) => {
      const params = new URLSearchParams();
      params.set(ENTITY_QUERY_PARAM, nextEntity);
      const serialized = serializeRoot(nextRoot);
      if (serialized !== '{"operator":"AND","conditions":[]}') {
        params.set("root", serialized);
      }
      const qs = params.toString();
      router.replace(qs ? `/query?${qs}` : "/query");
    },
    [router],
  );

  const handleChange = useCallback(
    (nextEntity: ResearchEntity, nextRoot: QueryGroup) => {
      setEntity(nextEntity);
      setRoot(nextRoot);
      updateUrl(nextEntity, nextRoot);
    },
    [updateUrl],
  );

  const previewMutation = usePreviewResearchQuery();
  const resolveMutation = useResolveResearchQuery();
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const query: ResearchQuery | null =
    entity && root
      ? {
          entity,
          root,
          query_context: {
            channel_id: context?.channelId ?? null,
            video_id: context?.videoId ?? null,
          },
        }
      : null;

  useEffect(() => {
    if (!root || root.conditions.length === 0) {
      previewMutation.reset();
      return;
    }
    if (previewTimer.current) clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(() => {
      if (query) previewMutation.mutate(query);
    }, 400);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Population</CardTitle>
        </CardHeader>
        <CardContent>
          <QueryBuilder
            initialRoot={root}
            initialEntity={entity}
            onChange={handleChange}
          />
        </CardContent>
      </Card>

      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!query || resolveMutation.isPending}
          onClick={() => resolveMutation.mutate(query!)}
        >
          Resolve count
        </Button>
        {resolveMutation.data ? (
          <p className="text-xs text-muted-foreground">
            {resolveMutation.data.total} matched of{" "}
            {resolveMutation.data.population_size}
          </p>
        ) : null}
      </div>

      <FunnelPreview
        result={previewMutation.isSuccess ? previewMutation.data : null}
        loading={previewMutation.isPending}
        error={
          previewMutation.isError
            ? (previewMutation.error as Error).message
            : null
        }
      />
    </div>
  );
}