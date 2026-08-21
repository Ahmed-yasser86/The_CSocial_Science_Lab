"use client";

import { useQuery } from "@tanstack/react-query";
import * as api from "@/services/api";

export function useVideoPreview(videoId: string) {
  return useQuery({
    queryKey: ["videoPreview", videoId] as const,
    queryFn: () => api.getVideo(videoId),
    enabled: !!videoId,
  });
}

export function useVideoEngagementPreview(videoId: string) {
  return useQuery({
    queryKey: ["videoEngagementPreview", videoId] as const,
    queryFn: () => api.getVideoEngagement(videoId),
    enabled: !!videoId,
  });
}