"use client";

import { useEffect, useRef } from "react";
import {
  useInfiniteQuery,
  useQuery,
  type UseQueryResult,
} from "@tanstack/react-query";
import { request, toQuery } from "@/services/api";
import { useToast } from "@/components/ui/toast";
import type {
  ChannelHistoryPoint,
  PaginatedHistory,
  ParticipationAnalytics,
  ReplyMetrics,
  RunDeltaReport,
  VelocityBucket,
  VelocityDecay,
  VideoHistoryPoint,
} from "@/lib/analytics-types";

export const analyticsKeys = {
  participation: (videoId: string) =>
    ["analytics", "videos", videoId, "comments", "participation"] as const,
  replies: (videoId: string) =>
    ["analytics", "videos", videoId, "comments", "replies"] as const,
  velocity: (videoId: string, bucket: VelocityBucket) =>
    ["analytics", "videos", videoId, "comments", "velocity", bucket] as const,
  videoHistory: (videoId: string) =>
    ["analytics", "videos", videoId, "history"] as const,
  channelHistory: (channelId: string) =>
    ["analytics", "channels", channelId, "history"] as const,
  runDelta: (from: string, to: string) =>
    ["analytics", "runs", "delta", from, to] as const,
};

// ---------------------------------------------------------------------------
// Request functions
// ---------------------------------------------------------------------------

export function getCommentParticipation(
  videoId: string,
): Promise<ParticipationAnalytics> {
  return request(`/videos/${videoId}/comments/analytics/participation`);
}

export function getCommentReplies(videoId: string): Promise<ReplyMetrics> {
  return request(`/videos/${videoId}/comments/analytics/replies`);
}

export function getCommentVelocity(
  videoId: string,
  bucket: VelocityBucket = "day",
): Promise<VelocityDecay> {
  return request(
    `/videos/${videoId}/comments/analytics/velocity${toQuery({ bucket })}`,
  );
}

export function getChannelHistory(
  channelId: string,
  cursor?: string,
): Promise<PaginatedHistory<ChannelHistoryPoint>> {
  return request(`/channels/${channelId}/history${toQuery({ cursor })}`);
}

export function getVideoHistory(
  videoId: string,
  cursor?: string,
): Promise<PaginatedHistory<VideoHistoryPoint>> {
  return request(`/videos/${videoId}/history${toQuery({ cursor })}`);
}

export function getRunDelta(
  from: string,
  to: string,
): Promise<RunDeltaReport> {
  return request(`/runs/delta${toQuery({ from_run: from, to_run: to })}`);
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useCommentParticipation(
  videoId: string,
): UseQueryResult<ParticipationAnalytics> {
  return useQuery({
    queryKey: analyticsKeys.participation(videoId),
    queryFn: () => getCommentParticipation(videoId),
    enabled: !!videoId,
  });
}

export function useCommentReplies(
  videoId: string,
): UseQueryResult<ReplyMetrics> {
  return useQuery({
    queryKey: analyticsKeys.replies(videoId),
    queryFn: () => getCommentReplies(videoId),
    enabled: !!videoId,
  });
}

export function useCommentVelocity(
  videoId: string,
  bucket: VelocityBucket = "day",
): UseQueryResult<VelocityDecay> {
  return useQuery({
    queryKey: analyticsKeys.velocity(videoId, bucket),
    queryFn: () => getCommentVelocity(videoId, bucket),
    enabled: !!videoId,
  });
}

export function useVideoHistory(videoId: string) {
  return useInfiniteQuery({
    queryKey: analyticsKeys.videoHistory(videoId),
    queryFn: ({ pageParam }) => getVideoHistory(videoId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? (lastPage.next_cursor ?? undefined) : undefined,
    enabled: !!videoId,
  });
}

export function useChannelHistory(channelId: string) {
  return useInfiniteQuery({
    queryKey: analyticsKeys.channelHistory(channelId),
    queryFn: ({ pageParam }) => getChannelHistory(channelId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? (lastPage.next_cursor ?? undefined) : undefined,
    enabled: !!channelId,
  });
}

export function useRunDelta(from: string, to: string) {
  return useQuery({
    queryKey: analyticsKeys.runDelta(from, to),
    queryFn: () => getRunDelta(from, to),
    enabled: !!from && !!to,
  });
}

/**
 * Shows a single destructive toast when a query transitions into an error
 * state (avoids spamming one toast per render).
 */
export function useAnalyticsErrorToast(
  isError: boolean,
  error: unknown,
  title = "Analytics could not be loaded",
) {
  const { toast } = useToast();
  const wasError = useRef(isError);
  useEffect(() => {
    if (isError && !wasError.current) {
      toast({
        title,
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive",
      });
    }
    wasError.current = isError;
  }, [isError, error, title, toast]);
}

/**
 * Extracts a display number from either the documented bare value or the
 * `{ value, n, population_size, method }` statistics envelope.
 */
export function statNumber(
  input: StatisticLike | number | null | undefined,
): number | null {
  if (input === null || input === undefined) return null;
  if (typeof input === "number") return input;
  if (typeof input.value === "number") return input.value;
  return null;
}

export interface StatisticLike {
  value?: number | null;
  metric?: string;
  n?: number;
  population_size?: number;
  method?: string;
}

export function statMeta(input: unknown): StatisticLike {
  if (input === null || input === undefined) return {};
  if (typeof input === "number") return {};
  if (typeof input === "object") return input as StatisticLike;
  return {};
}