"use client";

import { useEffect } from "react";
import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import type {
  CollectionSpec,
  ExportRequest,
  ResearchEntity,
  ResearchQuery,
  RunType,
  SamplingSpec,
  VideoFilter,
} from "@/lib/types";
import * as api from "@/services/api";
import { API_BASE } from "@/services/api";
import type { Job } from "@/lib/types";
import {
  listDatasets,
  getDataset,
  createDataset,
  deleteDataset,
  updateDataset,
  combineDatasets,
  listProjects,
  getProject,
  createProject,
  updateProject,
  deleteProject,
  addDatasetToProject,
  removeDatasetFromProject,
  listProjectItems,
  getProjectItem,
  createProjectItem,
  updateProjectItem,
  deleteProjectItem,
  addSamplesToItem,
  removeSamplesFromItem,
  addDatasetsToItem,
  removeDatasetsFromItem,
} from "@/services/datasets";
import {
  getSessionContext,
  putSessionContext,
} from "@/services/session";

export const queryKeys = {
  runs: (runType?: RunType) => ["runs", runType ?? "all"] as const,
  run: (runId: string) => ["runs", runId] as const,
  runErrors: (runId: string) => ["runs", runId, "errors"] as const,
  runVideos: (runId: string) => ["runs", runId, "videos"] as const,
  runSubRuns: (runId: string) => ["runs", runId, "sub-runs"] as const,
  channelOverview: (channelId: string) => ["channels", channelId, "overview"] as const,
  channels: () => ["channels"] as const,
  channelVideos: (channelId: string, filter?: VideoFilter) =>
    ["channels", channelId, "videos", JSON.stringify(filter ?? {})] as const,
  channelVideoCount: (channelId: string) =>
    ["channels", channelId, "videos", "count"] as const,
  video: (videoId: string) => ["videos", videoId] as const,
  videoEngagement: (videoId: string) => ["videos", videoId, "engagement"] as const,
  commentPercentiles: (videoId: string) =>
    ["videos", videoId, "comments", "percentiles"] as const,
  commentStats: (videoId: string) =>
    ["videos", videoId, "comments", "stats"] as const,
  commentVelocity: (videoId: string, bucket: "day" | "hour") =>
    ["videos", videoId, "comments", "velocity", bucket] as const,
  videoComments: (videoId: string) => ["videos", videoId, "comments"] as const,
  videoRecommendations: (videoId: string) =>
    ["videos", videoId, "recommendations"] as const,
  networkSummary: (runId?: string, topN = 10) =>
    ["network", "summary", runId ?? "all", topN] as const,
  networkVideoContext: (videoId: string, runId?: string | string[]) =>
    ["network", "videos", videoId, runId ?? "all"] as const,
  jobs: () => ["jobs"] as const,
  job: (jobId: string) => ["jobs", jobId] as const,
  coverage: () => ["coverage"] as const,
  datasetSummary: () => ["dataset", "summary"] as const,
  systemFolders: () => ["system", "folders"] as const,
  researchVariables: (entity?: ResearchEntity) =>
    ["research", "variables", entity ?? "all"] as const,
  researchOperators: () => ["research", "operators"] as const,
  search: (q: string, entity?: string) =>
    ["search", q, entity ?? "all"] as const,
  datasets: () => ["datasets"] as const,
  dataset: (datasetId: string) => ["datasets", datasetId] as const,
  projects: () => ["projects"] as const,
  project: (projectId: string) => ["projects", projectId] as const,
  projectItems: (projectId: string) => ["project-items", projectId] as const,
  projectItem: (projectId: string, itemId: string) =>
    ["project-items", projectId, itemId] as const,
  sessionContext: () => ["session", "context"] as const,
};

export function useRuns(runType?: RunType) {
  return useQuery({
    queryKey: queryKeys.runs(runType),
    queryFn: () => api.getRuns(runType),
  });
}

export function useRun(runId: string) {
  return useQuery({
    queryKey: queryKeys.run(runId),
    queryFn: () => api.getRun(runId),
    enabled: !!runId,
  });
}

export function useRunErrors(runId: string) {
  return useQuery({
    queryKey: queryKeys.runErrors(runId),
    queryFn: () => api.getRunErrors(runId),
    enabled: !!runId,
  });
}

export function useRunVideos(runId: string) {
  return useQuery({
    queryKey: queryKeys.runVideos(runId),
    queryFn: () => api.getRunVideos(runId),
    enabled: !!runId,
  });
}

export function useRunSubRuns(runId: string) {
  return useQuery({
    queryKey: queryKeys.runSubRuns(runId),
    queryFn: () => api.getRunSubRuns(runId),
    enabled: !!runId,
  });
}

export function useChannels() {
  return useQuery({
    queryKey: queryKeys.channels(),
    queryFn: async () => {
      const first = await api.getChannels();
      let all = first.items;
      let cursor = first.next_cursor;
      while (cursor) {
        const page = await api.getChannels(cursor);
        all = all.concat(page.items);
        cursor = page.next_cursor;
      }
      return all;
    },
  });
}

export function useUpdateRunName() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, name }: { runId: string; name: string }) =>
      api.updateRunName(runId, name),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.runs() });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.run(variables.runId),
      });
    },
  });
}

export function useChannelOverview(channelId: string) {
  return useQuery({
    queryKey: queryKeys.channelOverview(channelId),
    queryFn: () => api.getChannelOverview(channelId),
    enabled: !!channelId,
  });
}

export function useChannelVideos(channelId: string, filter?: VideoFilter) {
  return useQuery({
    queryKey: queryKeys.channelVideos(channelId, filter),
    queryFn: () => api.getChannelVideos(channelId, filter),
    enabled: !!channelId,
  });
}

export function useChannelVideoCount(channelId: string) {
  return useQuery({
    queryKey: queryKeys.channelVideoCount(channelId),
    queryFn: () => api.getChannelVideoCount(channelId),
    enabled: !!channelId,
  });
}

export function useVideo(videoId: string) {
  return useQuery({
    queryKey: queryKeys.video(videoId),
    queryFn: () => api.getVideo(videoId),
    enabled: !!videoId,
  });
}

export function useVideoEngagement(videoId: string) {
  return useQuery({
    queryKey: queryKeys.videoEngagement(videoId),
    queryFn: () => api.getVideoEngagement(videoId),
    enabled: !!videoId,
  });
}

export function useCommentPercentiles(videoId: string) {
  return useQuery({
    queryKey: queryKeys.commentPercentiles(videoId),
    queryFn: () => api.getCommentPercentiles(videoId),
    enabled: !!videoId,
  });
}

export function useCommentStats(videoId: string) {
  return useQuery({
    queryKey: queryKeys.commentStats(videoId),
    queryFn: () => api.getCommentStats(videoId),
    enabled: !!videoId,
  });
}

export function useCommentVelocity(videoId: string, bucket: "day" | "hour") {
  return useQuery({
    queryKey: queryKeys.commentVelocity(videoId, bucket),
    queryFn: () => api.getCommentVelocity(videoId, bucket),
    enabled: !!videoId,
  });
}

export function useCommentThreads(videoId: string) {
  return useQuery({
    queryKey: ["videos", videoId, "comments", "threads"] as const,
    queryFn: () => api.getCommentThreads(videoId),
    enabled: !!videoId,
  });
}

export function useVideoComments(videoId: string) {
  return useQuery({
    queryKey: queryKeys.videoComments(videoId),
    queryFn: () => api.getVideoComments(videoId),
    enabled: !!videoId,
  });
}

export function useVideoRecommendations(videoId: string) {
  return useQuery({
    queryKey: queryKeys.videoRecommendations(videoId),
    queryFn: () => api.getVideoRecommendations(videoId),
    enabled: !!videoId,
  });
}

export function useNetworkSummary(runId?: string, topN = 10) {
  return useQuery({
    queryKey: queryKeys.networkSummary(runId, topN),
    queryFn: () => api.getNetworkSummary(runId, topN),
  });
}

export function useNetworkVideoContext(
  videoId: string,
  runIds?: string[],
) {
  return useQuery({
    queryKey: queryKeys.networkVideoContext(videoId, runIds ?? "all"),
    queryFn: () => api.getVideoNetworkContext(videoId, runIds),
    enabled: !!videoId,
  });
}

export type CollectKind = "channel" | "video" | "recommendations";

export function useCollect() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ kind, url }: { kind: CollectKind; url: string }) => {
      if (kind === "channel") return api.collectChannel(url);
      if (kind === "video") return api.collectVideo(url);
      return api.collectRecommendations(url);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
      void queryClient.invalidateQueries({ queryKey: ["network", "summary"] });
      void queryClient.invalidateQueries({ queryKey: ["network", "graph"] });
      void queryClient.invalidateQueries({ queryKey: ["network", "full"] });
    },
  });
}

export function useSubmitCollect() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (spec: CollectionSpec) => api.submitCollect(spec),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
    },
  });
}

export function useJob(jobId: string | null) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: queryKeys.job(jobId ?? ""),
    queryFn: () => api.getJob(jobId as string),
    enabled: !!jobId,
    // SSE (EventSource) is the primary live channel, but if it drops we must
    // still recover: poll at 2s while the job is not terminal so the card can
    // never get stuck on "running".
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "running" ? 2000 : false;
    },
  });

  useEffect(() => {
    if (!jobId) return;
    const url = `${API_BASE}/jobs/${jobId}/stream`;
    const es = new EventSource(url);
    const onMessage = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as Job;
        queryClient.setQueryData(queryKeys.job(jobId), data);
        if (data.status === "succeeded" || data.status === "failed" || data.status === "cancelled") {
          es.close();
        }
      } catch {
        // ignore malformed payloads
      }
    };
    const onError = () => {
      es.close();
      void queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) });
    };
    es.addEventListener("message", onMessage);
    es.addEventListener("error", onError);
    return () => {
      es.removeEventListener("message", onMessage);
      es.removeEventListener("error", onError);
      es.close();
    };
  }, [jobId, queryClient]);

  return query;
}

export function useJobs() {
  return useQuery({
    queryKey: queryKeys.jobs(),
    queryFn: () => api.getJobs(),
    refetchInterval: 5000,
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => api.cancelJob(jobId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
    },
  });
}

export function useKillStuckJobs() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.killStuckJobs(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
    },
  });
}

export function useCoverage() {
  return useQuery({
    queryKey: queryKeys.coverage(),
    queryFn: () => api.getCoverage(),
    refetchInterval: 15000,
  });
}

export function useDatasetSummary() {
  return useQuery({
    queryKey: queryKeys.datasetSummary(),
    queryFn: () => api.getDatasetSummary(),
  });
}

export function useSystemFolders() {
  return useQuery({
    queryKey: queryKeys.systemFolders(),
    queryFn: () => api.getSystemFolders(),
  });
}

export function useSampleVideos(channelId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (spec: SamplingSpec) => api.sampleVideos(channelId, spec),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.channelVideos(channelId),
      });
    },
  });
}

export function useSampleComments(videoId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (spec: SamplingSpec) => api.sampleComments(videoId, spec),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.videoComments(videoId),
      });
    },
  });
}

export function useResearchVariables(entity?: ResearchEntity) {
  return useQuery({
    queryKey: queryKeys.researchVariables(entity),
    queryFn: () => api.getResearchVariables(entity),
  });
}

export function useResearchOperators() {
  return useQuery({
    queryKey: ["research", "operators"] as const,
    queryFn: () => api.getResearchOperators(),
  });
}

export function usePreviewResearchQuery() {
  return useMutation({
    mutationFn: (query: ResearchQuery) => api.previewResearchQuery(query),
  });
}

export function useResolveResearchQuery() {
  return useMutation({
    mutationFn: (query: ResearchQuery) => api.resolveResearchQuery(query),
  });
}

export function useExportData() {
  return useMutation({
    mutationFn: (request: ExportRequest) => api.exportData(request),
  });
}

export function useGlobalSearch(q: string, entity?: string) {
  return useQuery({
    queryKey: queryKeys.search(q, entity),
    queryFn: () => api.searchGlobal(q, entity),
    enabled: q.trim().length > 0,
    placeholderData: keepPreviousData,
  });
}

export function useDatasetList() {
  return useInfiniteQuery({
    queryKey: queryKeys.datasets(),
    queryFn: ({ pageParam }) => listDatasets(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? (lastPage.next_cursor ?? undefined) : undefined,
  });
}

export function useDataset(datasetId: string) {
  return useQuery({
    queryKey: queryKeys.dataset(datasetId),
    queryFn: () => getDataset(datasetId),
    enabled: !!datasetId,
  });
}

export function useCreateDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createDataset,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.datasets() });
    },
  });
}

export function useUpdateDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ datasetId, patch }: { datasetId: string; patch: Parameters<typeof updateDataset>[1] }) =>
      updateDataset(datasetId, patch),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.dataset(variables.datasetId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.datasets() });
    },
  });
}

export function useDeleteDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (datasetId: string) => deleteDataset(datasetId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.datasets() });
    },
  });
}

export function useCombineDatasets() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: combineDatasets,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.datasets() });
    },
  });
}

export function useActiveSessionQuery() {
  return useQuery({
    queryKey: queryKeys.sessionContext(),
    queryFn: getSessionContext,
    staleTime: Infinity,
    retry: false,
  });
}

export function useSaveSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: putSessionContext,
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.sessionContext(), data);
    },
  });
}

export function useProjectList() {
  return useInfiniteQuery({
    queryKey: queryKeys.projects(),
    queryFn: ({ pageParam }) => listProjects(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? (lastPage.next_cursor ?? undefined) : undefined,
  });
}

export function useProject(projectId: string) {
  return useQuery({
    queryKey: queryKeys.project(projectId),
    queryFn: () => getProject(projectId),
    enabled: !!projectId,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
    },
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, patch }: { projectId: string; patch: Parameters<typeof updateProject>[1] }) =>
      updateProject(projectId, patch),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(variables.projectId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) => deleteProject(projectId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
    },
  });
}

export function useAddDatasetToProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, datasetId }: { projectId: string; datasetId: string }) =>
      addDatasetToProject(projectId, datasetId),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(variables.projectId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
    },
  });
}

export function useRemoveDatasetFromProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, datasetId }: { projectId: string; datasetId: string }) =>
      removeDatasetFromProject(projectId, datasetId),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(variables.projectId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
    },
  });
}

export function useProjectItems(projectId: string) {
  return useQuery({
    queryKey: queryKeys.projectItems(projectId),
    queryFn: () => listProjectItems(projectId),
    enabled: !!projectId,
  });
}

export function useProjectItem(projectId: string, itemId: string) {
  return useQuery({
    queryKey: queryKeys.projectItem(projectId, itemId),
    queryFn: () => getProjectItem(projectId, itemId),
    enabled: !!projectId && !!itemId,
  });
}

export function useCreateProjectItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      body,
    }: {
      projectId: string;
      body: Parameters<typeof createProjectItem>[1];
    }) => createProjectItem(projectId, body),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.projectItems(variables.projectId),
      });
    },
  });
}

export function useUpdateProjectItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      itemId,
      patch,
    }: {
      projectId: string;
      itemId: string;
      patch: Parameters<typeof updateProjectItem>[2];
    }) => updateProjectItem(projectId, itemId, patch),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.projectItems(variables.projectId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.projectItem(variables.projectId, variables.itemId),
      });
    },
  });
}

export function useDeleteProjectItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, itemId }: { projectId: string; itemId: string }) =>
      deleteProjectItem(projectId, itemId),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.projectItems(variables.projectId),
      });
    },
  });
}

export function useAddSamplesToItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      itemId,
      sampleIds,
    }: {
      projectId: string;
      itemId: string;
      sampleIds: string[];
    }) => addSamplesToItem(projectId, itemId, sampleIds),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.projectItems(variables.projectId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.projectItem(variables.projectId, variables.itemId),
      });
    },
  });
}

export function useRemoveSamplesFromItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      itemId,
      sampleIds,
    }: {
      projectId: string;
      itemId: string;
      sampleIds: string[];
    }) => removeSamplesFromItem(projectId, itemId, sampleIds),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.projectItems(variables.projectId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.projectItem(variables.projectId, variables.itemId),
      });
    },
  });
}

export function useAddDatasetsToItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      itemId,
      datasetIds,
    }: {
      projectId: string;
      itemId: string;
      datasetIds: string[];
    }) => addDatasetsToItem(projectId, itemId, datasetIds),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.projectItems(variables.projectId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.projectItem(variables.projectId, variables.itemId),
      });
    },
  });
}

export function useRemoveDatasetsFromItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      itemId,
      datasetIds,
    }: {
      projectId: string;
      itemId: string;
      datasetIds: string[];
    }) => removeDatasetsFromItem(projectId, itemId, datasetIds),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.projectItems(variables.projectId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.projectItem(variables.projectId, variables.itemId),
      });
    },
  });
}
