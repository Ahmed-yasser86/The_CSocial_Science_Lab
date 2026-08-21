"use client";

import { useQuery } from "@tanstack/react-query";
import { request, toQuery } from "@/services/api";
import type {
  CommenterOverlapResult,
  CommenterProfile,
  OverlapMetric,
} from "@/lib/commenter-overlap-types";

export interface CommenterOverlapParams {
  videoIds: string[];
  channelIds: string[];
  metric?: OverlapMetric;
  minEntities?: number;
  minShared?: number;
  topN?: number;
}

export const commenterKeys = {
  overlap: (params: CommenterOverlapParams) =>
    [
      "network",
      "commenters",
      "overlap",
      params.videoIds.join(","),
      params.channelIds.join(","),
      params.metric ?? "jaccard",
      params.minEntities ?? 2,
      params.minShared ?? 1,
      params.topN ?? 50,
    ] as const,
  profile: (authorKey: string, videoIds: string[], channelIds: string[]) =>
    [
      "network",
      "commenters",
      "profile",
      authorKey,
      videoIds.join(","),
      channelIds.join(","),
    ] as const,
};

export function getCommenterOverlap(
  params: CommenterOverlapParams,
): Promise<CommenterOverlapResult> {
  return request(
    `/network/commenters/overlap${toQuery({
      video_ids: params.videoIds.length ? params.videoIds.join(",") : undefined,
      channel_ids: params.channelIds.length
        ? params.channelIds.join(",")
        : undefined,
      metric: params.metric,
      min_entities: params.minEntities,
      min_shared: params.minShared,
      top_n: params.topN,
    })}`,
  );
}

export function getCommenterProfile(
  authorKey: string,
  videoIds: string[] = [],
  channelIds: string[] = [],
  limit = 200,
): Promise<CommenterProfile> {
  return request(
    `/network/commenters/${encodeURIComponent(authorKey)}/profile${toQuery({
      video_ids: videoIds.length ? videoIds.join(",") : undefined,
      channel_ids: channelIds.length ? channelIds.join(",") : undefined,
      limit,
    })}`,
  );
}

export function useCommenterOverlap(params: CommenterOverlapParams, options = {}) {
  return useQuery({
    queryKey: commenterKeys.overlap(params),
    queryFn: () => getCommenterOverlap(params),
    enabled:
      params.videoIds.length > 0 || params.channelIds.length > 0,
    ...options,
  });
}

export function useCommenterProfile(
  authorKey: string | null,
  videoIds: string[] = [],
  channelIds: string[] = [],
) {
  return useQuery({
    queryKey: commenterKeys.profile(authorKey ?? "", videoIds, channelIds),
    queryFn: () => getCommenterProfile(authorKey as string, videoIds, channelIds),
    enabled: !!authorKey,
  });
}
