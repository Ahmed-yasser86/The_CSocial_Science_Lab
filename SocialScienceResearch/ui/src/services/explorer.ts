"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request, toQuery } from "@/services/api";
import type {
  ExplorerEntity,
  ExplorerFilter,
  ExplorePage,
  ProvenanceRecord,
  RawRecord,
} from "@/lib/explorer-types";

export const explorerKeys = {
  records: (entity: ExplorerEntity, pageKey: string) =>
    ["explore", "records", entity, pageKey] as const,
  raw: (entity: string, id: string) =>
    ["explore", "raw", entity, id] as const,
  provenance: (entity: string, id: string) =>
    ["explore", "provenance", entity, id] as const,
};

export function buildExplorerPageKey(
  q: string,
  filters: ExplorerFilter[],
  sort: string | null,
  cursor: string | null | undefined,
): string {
  return JSON.stringify({ q, filters, sort, cursor: cursor ?? null });
}

export function getExploreRecords(
  entity: ExplorerEntity,
  q?: string,
  filters?: ExplorerFilter[],
  sort?: string | null,
  cursor?: string,
): Promise<ExplorePage> {
  return request(
    `/explore/records${toQuery({
      entity,
      q: q || undefined,
      filters: filters && filters.length > 0 ? JSON.stringify(filters) : undefined,
      sort: sort || undefined,
      cursor: cursor || undefined,
    })}`,
  );
}

export function getRawRecord(
  entity: string,
  entityId: string,
): Promise<RawRecord> {
  return request(`/explore/records/${entity}/${entityId}/raw`);
}

export function getProvenance(
  entity: string,
  entityId: string,
): Promise<ProvenanceRecord> {
  return request(`/explore/provenance/${entity}/${entityId}`);
}

export function useExploreRecords(
  entity: ExplorerEntity,
  q: string,
  filters: ExplorerFilter[],
  sort: string | null,
  cursor: string | null | undefined,
) {
  const pageKey = buildExplorerPageKey(q, filters, sort, cursor);
  return useQuery({
    queryKey: explorerKeys.records(entity, pageKey),
    queryFn: () => getExploreRecords(entity, q, filters, sort ?? undefined, cursor ?? undefined),
    placeholderData: (previous) => previous,
    staleTime: 30_000,
  });
}

export function useRawRecord(entity: string, entityId: string | null) {
  return useQuery({
    queryKey: explorerKeys.raw(entity, entityId ?? ""),
    queryFn: () => getRawRecord(entity, entityId as string),
    enabled: !!entityId,
  });
}

export function useProvenance(entity: string, entityId: string | null) {
  return useQuery({
    queryKey: explorerKeys.provenance(entity, entityId ?? ""),
    queryFn: () => getProvenance(entity, entityId as string),
    enabled: !!entityId,
  });
}

export function useInvalidateExplorer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (entity: ExplorerEntity) => {
      await queryClient.invalidateQueries({
        queryKey: ["explore", "records", entity],
      });
    },
  });
}
