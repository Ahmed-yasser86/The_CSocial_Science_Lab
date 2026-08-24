"use client";

import {
  createContext,
  Suspense,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import { useSearchParams } from "next/navigation";
import { useVideo } from "@/services/queries";

export interface ResearchContext {
  projectName?: string;
  channelId?: string;
  videoId?: string;
  queryHash?: string;
  variables?: string[];
}

export const CONTEXT_PARAM_PROJECT = "project";
export const CONTEXT_PARAM_CHANNEL = "channel";
export const CONTEXT_PARAM_VIDEO = "video";
export const CONTEXT_PARAM_QUERY = "query";
export const CONTEXT_PARAM_VARIABLE = "var";

export const CONTEXT_PARAM_KEYS: string[] = [
  CONTEXT_PARAM_PROJECT,
  CONTEXT_PARAM_CHANNEL,
  CONTEXT_PARAM_VIDEO,
  CONTEXT_PARAM_QUERY,
  CONTEXT_PARAM_VARIABLE,
];

export function serializeContextParams(
  ctx: ResearchContext,
): URLSearchParams {
  const params = new URLSearchParams();
  if (ctx.projectName) params.set(CONTEXT_PARAM_PROJECT, ctx.projectName);
  if (ctx.channelId) params.set(CONTEXT_PARAM_CHANNEL, ctx.channelId);
  if (ctx.videoId) params.set(CONTEXT_PARAM_VIDEO, ctx.videoId);
  if (ctx.queryHash) params.set(CONTEXT_PARAM_QUERY, ctx.queryHash);
  for (const variable of ctx.variables ?? []) {
    if (variable) params.append(CONTEXT_PARAM_VARIABLE, variable);
  }
  return params;
}

export function parseContextParams(
  searchParams: URLSearchParams | string | null | undefined,
): ResearchContext {
  const params =
    typeof searchParams === "string"
      ? new URLSearchParams(searchParams)
      : searchParams;
  if (!params) return {};
  const ctx: ResearchContext = {};
  const project = params.get(CONTEXT_PARAM_PROJECT);
  if (project) ctx.projectName = project;
  const channel = params.get(CONTEXT_PARAM_CHANNEL);
  if (channel) ctx.channelId = channel;
  const video = params.get(CONTEXT_PARAM_VIDEO);
  if (video) ctx.videoId = video;
  const query = params.get(CONTEXT_PARAM_QUERY);
  if (query) ctx.queryHash = query;
  const variables = params.getAll(CONTEXT_PARAM_VARIABLE).filter(Boolean);
  if (variables.length > 0) ctx.variables = variables;
  return ctx;
}

export function withContext(href: string, ctx: ResearchContext): string {
  const [path, query] = href.split("?");
  const params = query ? new URLSearchParams(query) : new URLSearchParams();
  for (const [key, value] of serializeContextParams(ctx).entries()) {
    params.set(key, value);
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

export function stripContext(href: string): string {
  const [path, query] = href.split("?");
  if (!query) return path;
  const params = new URLSearchParams(query);
  for (const key of CONTEXT_PARAM_KEYS) params.delete(key);
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

export function useContextParams(): ResearchContext {
  return parseContextParams(useSearchParams());
}

export interface ResearchContextValue {
  context: ResearchContext;
  hasContext: boolean;
  projectName: string | null;
  channelId: string | null;
  channelLabel: string | null;
  videoId: string | null;
  videoLabel: string | null;
}

const ResearchContextValue = createContext<ResearchContextValue | null>(null);

export function ResearchContextProvider({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <Suspense fallback={<ResearchContextFallback>{children}</ResearchContextFallback>}>
      <ResearchContextBoundary>{children}</ResearchContextBoundary>
    </Suspense>
  );
}

export function useResearchContext(): ResearchContextValue {
  const value = useContext(ResearchContextValue);
  return (
    value ?? {
      context: {},
      hasContext: false,
      projectName: null,
      channelId: null,
      channelLabel: null,
      videoId: null,
      videoLabel: null,
    }
  );
}

function ResearchContextBoundary({ children }: { children: ReactNode }) {
  return <ResearchContextInner context={useContextParams()}>{children}</ResearchContextInner>;
}

function ResearchContextFallback({ children }: { children: ReactNode }) {
  return <ResearchContextInner context={{}}>{children}</ResearchContextInner>;
}

function ResearchContextInner({
  context,
  children,
}: {
  context: ResearchContext;
  children: ReactNode;
}) {
  const { data: video } = useVideo(context.videoId ?? "");

  const value = useMemo<ResearchContextValue>(() => {
    const channelId = context.channelId ?? null;
    const videoId = context.videoId ?? null;
    return {
      context,
      hasContext: Object.keys(context).length > 0,
      projectName: context.projectName ?? null,
      channelId,
      channelLabel: channelId,
      videoId,
      videoLabel: video?.title ?? videoId,
    };
  }, [context, video?.title]);

  return (
    <ResearchContextValue.Provider value={value}>
      {children}
    </ResearchContextValue.Provider>
  );
}
