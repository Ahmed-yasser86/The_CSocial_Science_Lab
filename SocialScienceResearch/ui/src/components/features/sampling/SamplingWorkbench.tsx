"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import {
  FlaskConical,
  Loader2,
  Save,
  Zap,
  ChevronDown,
  Maximize2,
  CheckCircle2,
  XCircle,
  User,
  Tv,
  Filter,
  Shuffle,
  Calendar,
  TrendingUp,
  Crosshair,
  SlidersHorizontal,
  Dices,
  Tags,
  Bookmark,
  Target,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import type { AdvancedSamplingSpec, SamplingResult, Channel, SamplingSpec } from "@/services/api";
import type { CollectionRun } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { useChannels, useRuns, useCreateDataset } from "@/services/queries";
import {
  ScopeSelector,
  LivePreview,
  FilterPanel,
  SamplingMethodSelector,
  ResultActions,
  type WorkbenchState,
  type WorkbenchFilters,
  type WorkbenchLabels,
  type SamplingMethod,
  type TopMetric,
  INITIAL_STATE,
} from "./index";
import type { ScopeValue } from "./ScopeSelector";
import * as api from "@/services/api";

interface SamplingWorkbenchProps {
  entityType: "video" | "comment";
  channelIds?: string[];
  channels?: Channel[];
  populationSize?: number;
  mutate?: ReturnType<typeof useMutation<SamplingResult, Error, SamplingSpec>>;
}

interface PresetTemplate {
  id: string;
  label: string;
  description: string;
  icon: string;
  scopeType: "all" | "channel" | "author" | "custom";
  filters?: Partial<WorkbenchFilters>;
  samplingMethod: "full" | "random" | "stratified";
  randomSize?: string;
  randomPercent?: string;
  strataVariable?: string;
  samplesPerStratum?: string;
}

const PRESET_TEMPLATES: PresetTemplate[] = [
  {
    id: "by-author",
    label: "By Author(s)",
    description: "Sample comments from specific users",
    icon: "user",
    scopeType: "author",
    filters: {
      excludeVideoAuthor: false,
    },
    samplingMethod: "full",
  },
  {
    id: "by-channel",
    label: "By Channel",
    description: "All comments in selected channels",
    icon: "tv",
    scopeType: "channel",
    samplingMethod: "full",
  },
  {
    id: "by-video-criteria",
    label: "By Video Criteria",
    description: "Filter by video attributes (duration, views, date)",
    icon: "filter",
    scopeType: "custom",
    filters: {},
    samplingMethod: "full",
  },
  {
    id: "random-sample",
    label: "Random Sample",
    description: "Random selection from all data",
    icon: "shuffle",
    scopeType: "all",
    samplingMethod: "random",
    randomSize: "500",
    randomPercent: "",
  },
  {
    id: "stratified-temporal",
    label: "Stratified by Time",
    description: "Balanced across months/weekdays",
    icon: "calendar",
    scopeType: "all",
    samplingMethod: "stratified",
    strataVariable: "month",
    samplesPerStratum: "50",
  },
  {
    id: "high-engagement",
    label: "High Engagement",
    description: "Comments with many likes/replies",
    icon: "trending-up",
    scopeType: "all",
    filters: {
      minLikes: 10,
      minReplies: 5,
      commentType: "roots",
    },
    samplingMethod: "random",
    randomSize: "500",
    randomPercent: "",
  },
];

const PRESET_ICONS: Record<string, LucideIcon> = {
  user: User,
  tv: Tv,
  filter: Filter,
  shuffle: Shuffle,
  calendar: Calendar,
  "trending-up": TrendingUp,
};

const STEPS: { id: "scope" | "filters" | "method" | "save"; label: string; icon: LucideIcon }[] = [
  { id: "scope", label: "Scope", icon: Crosshair },
  { id: "filters", label: "Filters", icon: SlidersHorizontal },
  { id: "method", label: "Method", icon: Dices },
  { id: "save", label: "Labels & Save", icon: Tags },
];

const STEP_IDS = ["scope", "filters", "method", "save"] as const;

export function SamplingWorkbench({ entityType, channelIds = [], channels = [] }: SamplingWorkbenchProps) {
  const [state, setState] = useState<WorkbenchState>({
    ...INITIAL_STATE,
    channelIds,
    entityType: entityType === "video" ? "video" : "comment",
  } as WorkbenchState);

  const channelsQuery = useChannels();
  const runsQuery = useRuns();
  const createDatasetMutation = useCreateDataset();
  const allChannels = channels.length > 0 ? channels : (channelsQuery.data ?? []);
  const runs = runsQuery.data ?? [];

  const [previewResult, setPreviewResult] = useState<SamplingResult | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [savedQueries, setSavedQueries] = useState<Array<{ id: string; name: string; state: WorkbenchState }>>([]);
  const [isExpanded, setIsExpanded] = useState(false);
  const [datasetNotice, setDatasetNotice] = useState<{ ok: boolean; message: string } | null>(null);

  const runPreview = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const spec = buildAdvancedSpec(state);
      const result = await api.sampleAdvanced(spec);
      setPreviewResult(result);
    } catch (error) {
      console.error("Preview failed:", error);
      setPreviewResult(null);
    } finally {
      setIsRefreshing(false);
    }
  }, [state]);

  const runSample = useCallback(async () => {
    try {
      const spec = buildAdvancedSpec(state);
      const result = await api.sampleAdvanced(spec);
      setPreviewResult(result);
      return result;
    } catch (error) {
      console.error("Sample failed:", error);
      throw error;
    }
  }, [state]);

  const handleScopeChange = (value: ScopeValue) => {
    setState((prev) => ({
      ...prev,
      scopeType: value.scopeType,
      channelIds: value.channelIds,
      authorIds: value.authorIds,
      runScope: value.runScope,
      runIds: value.runIds,
    }));
  };

  const handleFiltersChange = (filters: WorkbenchFilters) => {
    setState((prev) => ({ ...prev, filters }));
  };

  const handleSamplingMethodChange = (method: SamplingMethod) => {
    setState((prev) => ({ ...prev, samplingMethod: method }));
  };

  const handleRandomSizeChange = (size: string) => {
    setState((prev) => ({ ...prev, sampleSize: size }));
  };

  const handleRandomPercentChange = (percent: string) => {
    setState((prev) => ({ ...prev, samplePercent: percent }));
  };

  const handleSeedChange = (seed: string) => {
    setState((prev) => ({ ...prev, seed }));
  };

  const handleStrataVariableChange = (variable: string) => {
    setState((prev) => ({ ...prev, strataVariable: variable }));
  };

  const handleSamplesPerStratumChange = (count: string) => {
    setState((prev) => ({ ...prev, samplesPerStratum: count }));
  };

  const handleTopMetricChange = (metric: TopMetric) => {
    setState((prev) => ({ ...prev, topMetric: metric }));
  };

  const handleTopPercentChange = (percent: string) => {
    setState((prev) => ({ ...prev, topPercent: percent }));
  };

  const handleLabelsChange = (labels: WorkbenchLabels) => {
    setState((prev) => ({ ...prev, labels }));
  };

  const handleSaveOptionChange = (option: "individual" | "dataset") => {
    setState((prev) => ({ ...prev, saveOption: option }));
  };

  const handleDatasetNameChange = (name: string) => {
    setState((prev) => ({ ...prev, datasetName: name }));
  };

  const handleCreateDataset = async (name: string, sampleIds: string[]) => {
    if (sampleIds.length === 0) {
      setDatasetNotice({
        ok: false,
        message: "Run a sample first — there are no member IDs to add to a dataset.",
      });
      return;
    }
    try {
      const dataset = await createDatasetMutation.mutateAsync({
        name,
        entity_type: state.entityType,
        member_ids: sampleIds,
      });
      setDatasetNotice({
        ok: true,
        message: `Dataset "${dataset.name}" created with ${dataset.member_count} members.`,
      });
      setState((prev) => ({ ...prev, datasetName: "" }));
    } catch (error) {
      setDatasetNotice({
        ok: false,
        message: `Failed to create dataset: ${(error as Error).message}`,
      });
    }
  };

  const handleSaveQuery = () => {
    const name = prompt("Save query as:");
    if (name) {
      setSavedQueries([...savedQueries, { id: Date.now().toString(), name, state }]);
    }
  };

  const handleLoadQuery = (query: { id: string; name: string; state: WorkbenchState }) => {
    setState(query.state);
  };

  const applyPreset = (preset: typeof PRESET_TEMPLATES[0]) => {
    setState((prev) => ({
      ...prev,
      scopeType: preset.scopeType,
      runScope: preset.scopeType === "channel" ? prev.runScope : "all",
      runIds: preset.scopeType === "channel" ? prev.runIds : [],
      samplingMethod: preset.samplingMethod,
      sampleSize: preset.randomSize ?? prev.sampleSize,
      samplePercent: preset.randomPercent ?? prev.samplePercent,
      strataVariable: preset.strataVariable ?? prev.strataVariable,
      samplesPerStratum: preset.samplesPerStratum ?? prev.samplesPerStratum,
      filters: { ...prev.filters, ...preset.filters },
    }));
  };

  const processProps: SamplingProcessProps = {
    state,
    channels: allChannels,
    runs,
    savedQueries,
    previewResult,
    isRefreshing,
    onScopeChange: handleScopeChange,
    onFiltersChange: handleFiltersChange,
    onSamplingMethodChange: handleSamplingMethodChange,
    onRandomSizeChange: handleRandomSizeChange,
    onRandomPercentChange: handleRandomPercentChange,
    onSeedChange: handleSeedChange,
    onStrataVariableChange: handleStrataVariableChange,
    onSamplesPerStratumChange: handleSamplesPerStratumChange,
    onTopMetricChange: handleTopMetricChange,
    onTopPercentChange: handleTopPercentChange,
    onLabelsChange: handleLabelsChange,
    onSaveOptionChange: handleSaveOptionChange,
    onDatasetNameChange: handleDatasetNameChange,
    onCreateDataset: handleCreateDataset,
    onLoadQuery: handleLoadQuery,
    onApplyPreset: applyPreset,
    onRefreshPreview: runPreview,
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-muted/30">
      <header className="shrink-0 border-b bg-background/80 px-6 py-4 backdrop-blur-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="min-w-0">
            <h2
              onDoubleClick={() => setIsExpanded(true)}
              title="Double-click to expand the sampling workspace"
              className="flex cursor-zoom-in items-center gap-2.5 text-lg font-semibold tracking-tight"
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <FlaskConical className="size-4" aria-hidden />
              </span>
              Advanced Sampling Workbench
              <span
                className="flex size-6 shrink-0 items-center justify-center rounded-md border bg-background/60 text-muted-foreground"
                aria-hidden
              >
                <Maximize2 className="size-3.5" />
              </span>
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Build reproducible {entityType} samples in four steps — scope, filter, method, and save. Double-click the title for an expanded workspace.
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleSaveQuery}>
              <Save className="size-3.5" />
              Save Query
            </Button>
            <Button variant="outline" size="sm" onClick={runPreview}>
              <Zap className="size-3.5" />
              Refresh Preview
            </Button>
            <Button variant="default" size="sm" onClick={runSample} disabled={isRefreshing}>
              {isRefreshing ? (
                <>
                  <Loader2 className="size-3.5 animate-spin" />
                  Running…
                </>
              ) : (
                <>
                  <FlaskConical className="size-3.5" />
                  Run Sample
                </>
              )}
            </Button>
          </div>
        </div>
      </header>

      {datasetNotice && (
        <div
          role="status"
          className={cn(
            "flex items-center gap-2 border-b px-6 py-2 text-sm",
            datasetNotice.ok
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-red-200 bg-red-50 text-red-800"
          )}
        >
          {datasetNotice.ok ? (
            <CheckCircle2 className="size-4 shrink-0" aria-hidden />
          ) : (
            <XCircle className="size-4 shrink-0" aria-hidden />
          )}
          <span className="min-w-0 flex-1">{datasetNotice.message}</span>
        </div>
      )}

      <div className="min-h-0 flex-1">
        <SamplingProcess {...processProps} />
      </div>

      <Dialog open={isExpanded} onOpenChange={setIsExpanded}>
        <DialogContent className="flex h-[calc(100dvh-2rem)] max-h-[calc(100dvh-2rem)] w-full flex-col gap-0 overflow-hidden p-0 sm:max-w-7xl">
          <div className="shrink-0 border-b bg-background/80 px-6 py-4 pr-14 backdrop-blur-sm">
            <DialogHeader className="gap-1">
              <DialogTitle className="flex items-center gap-2.5 text-lg font-semibold tracking-tight">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <FlaskConical className="size-4" aria-hidden />
                </span>
                Advanced Sampling Workbench
              </DialogTitle>
              <DialogDescription>
                Expanded {entityType} sampling workspace — scope, filter, method, and save.
              </DialogDescription>
            </DialogHeader>
          </div>
          <div className="min-h-0 flex-1">
            <SamplingProcess {...processProps} scrollHint />
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

interface SamplingProcessProps {
  state: WorkbenchState;
  channels: Channel[];
  runs: CollectionRun[];
  savedQueries: Array<{ id: string; name: string; state: WorkbenchState }>;
  previewResult: SamplingResult | null;
  isRefreshing: boolean;
  onScopeChange: (value: ScopeValue) => void;
  onFiltersChange: (filters: WorkbenchFilters) => void;
  onSamplingMethodChange: (method: SamplingMethod) => void;
  onRandomSizeChange: (size: string) => void;
  onRandomPercentChange: (percent: string) => void;
  onSeedChange: (seed: string) => void;
  onStrataVariableChange: (variable: string) => void;
  onSamplesPerStratumChange: (count: string) => void;
  onTopMetricChange: (metric: TopMetric) => void;
  onTopPercentChange: (percent: string) => void;
  onLabelsChange: (labels: WorkbenchLabels) => void;
  onSaveOptionChange: (option: "individual" | "dataset") => void;
  onDatasetNameChange: (name: string) => void;
  onCreateDataset: (name: string, sampleIds: string[]) => void;
  onLoadQuery: (query: { id: string; name: string; state: WorkbenchState }) => void;
  onApplyPreset: (preset: PresetTemplate) => void;
  onRefreshPreview: () => void;
  scrollHint?: boolean;
}

function SamplingProcess({
  state,
  channels,
  runs,
  savedQueries,
  previewResult,
  isRefreshing,
  scrollHint = false,
  onScopeChange: handleScopeChange,
  onFiltersChange: handleFiltersChange,
  onSamplingMethodChange: handleSamplingMethodChange,
  onRandomSizeChange: handleRandomSizeChange,
  onRandomPercentChange: handleRandomPercentChange,
  onSeedChange: handleSeedChange,
  onStrataVariableChange: handleStrataVariableChange,
  onSamplesPerStratumChange: handleSamplesPerStratumChange,
  onTopMetricChange: handleTopMetricChange,
  onTopPercentChange: handleTopPercentChange,
  onLabelsChange: handleLabelsChange,
  onSaveOptionChange: handleSaveOptionChange,
  onDatasetNameChange: handleDatasetNameChange,
  onCreateDataset: handleCreateDataset,
  onLoadQuery: handleLoadQuery,
  onApplyPreset: applyPreset,
  onRefreshPreview: runPreview,
}: SamplingProcessProps) {
  const [activeStep, setActiveStep] = useState<(typeof STEP_IDS)[number]>("scope");
  const [canScrollDown, setCanScrollDown] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const computeActiveStep = useCallback(() => {
    const container = scrollRef.current;
    if (!container) return;
    const containerTop = container.getBoundingClientRect().top;
    const probe = containerTop + 200;
    let current: (typeof STEP_IDS)[number] = "scope";
    for (const id of STEP_IDS) {
      const el = container.querySelector(`#step-${id}`);
      if (el && el.getBoundingClientRect().top <= probe) {
        current = id;
      }
    }
    setActiveStep(current);
  }, []);

  const handleScroll = useCallback(() => {
    computeActiveStep();
    const container = scrollRef.current;
    if (container) {
      setCanScrollDown(container.scrollHeight - container.scrollTop - container.clientHeight > 24);
    }
  }, [computeActiveStep]);

  useEffect(() => {
    handleScroll();
  }, [handleScroll]);

  const scrollToStep = (id: (typeof STEP_IDS)[number]) => {
    scrollRef.current
      ?.querySelector(`#step-${id}`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div ref={scrollRef} onScroll={handleScroll} className="relative h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-6xl px-6 py-6">
<nav aria-label="Sampling steps" className="flex flex-wrap items-center gap-2">
                {STEPS.map((step, index) => {
                  const Icon = step.icon;
                  const active = activeStep === step.id;
                  return (
                    <button
                      key={step.id}
                      type="button"
                      onClick={() => scrollToStep(step.id)}
                      className={cn(
                        "flex items-center gap-2 rounded-full border py-1.5 pl-1.5 pr-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
                        active
                          ? "border-primary/40 bg-background text-foreground shadow-sm"
                          : "border-border bg-background/60 text-muted-foreground hover:border-input hover:text-foreground"
                      )}
                    >
                      <span
                        className={cn(
                          "flex size-6 items-center justify-center rounded-full",
                          active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                        )}
                      >
                        {index + 1}
                      </span>
                      <Icon className="size-4" aria-hidden />
                      {step.label}
                    </button>
                  );
                })}
              </nav>

              <div className="mt-8 grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
                <div className="min-w-0 space-y-10">
                  <section id="step-scope" className="scroll-mt-6 space-y-5">
                    <StepHeading
                      number={1}
                      title="Choose your scope"
                      description="Pick the universe of data this sample draws from, or start from a template."
                    />

                    <Card>
                      <CardHeader>
                        <div className="flex items-center gap-3">
                          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                            <Sparkles className="size-4" aria-hidden />
                          </span>
                          <div>
                            <CardTitle className="text-base font-semibold">Start from a template</CardTitle>
                            <CardDescription>
                              Quick recipes that pre-configure the scope, filters and method for you.
                            </CardDescription>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                          {PRESET_TEMPLATES.map((preset) => {
                            const Icon = PRESET_ICONS[preset.icon] ?? Sparkles;
                            return (
                              <Button
                                key={preset.id}
                                type="button"
                                variant="outline"
                                onClick={() => applyPreset(preset)}
                                className="h-auto flex-col items-start gap-2.5 rounded-xl p-3.5 text-left"
                              >
                                <span className="flex size-8 items-center justify-center rounded-lg bg-muted/60 text-foreground">
                                  <Icon className="size-4" aria-hidden />
                                </span>
                                <span className="flex flex-col items-start gap-1">
                                  <span className="text-sm font-semibold">{preset.label}</span>
                                  <span className="text-xs font-normal leading-snug text-muted-foreground">
                                    {preset.description}
                                  </span>
                                </span>
                              </Button>
                            );
                          })}
                        </div>
                      </CardContent>
                    </Card>

                    {savedQueries.length > 0 && (
                      <Card>
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
                            <Bookmark className="size-4" aria-hidden />
                            Saved Queries
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="flex flex-wrap gap-2">
                          {savedQueries.map((query) => (
                            <Button
                              key={query.id}
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => handleLoadQuery(query)}
                            >
                              <Bookmark className="size-3.5" aria-hidden />
                              {query.name}
                            </Button>
                          ))}
                        </CardContent>
                      </Card>
                    )}

                    <Card>
                      <CardHeader>
                        <div className="flex items-center gap-3">
                          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                            <Target className="size-4" aria-hidden />
                          </span>
                          <div>
                            <CardTitle className="text-base font-semibold">Define the scope</CardTitle>
                            <CardDescription>
                              Restrict the population to everything, specific channels, authors, or a custom mix.
                            </CardDescription>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <ScopeSelector
                          value={{
                            scopeType: state.scopeType,
                            channelIds: state.channelIds,
                            authorIds: state.authorIds,
                            runScope: state.runScope,
                            runIds: state.runIds,
                          }}
                          onChange={handleScopeChange}
                          channels={channels}
                          runs={runs}
                        />
                      </CardContent>
                    </Card>
                  </section>

                  <section id="step-filters" className="scroll-mt-6">
                    <StepHeading
                      number={2}
                      title="Narrow the population"
                      description="Apply optional filters across authors, channels, videos, comments, overlap and time."
                    />
                    <FilterPanel filters={state.filters} onChange={handleFiltersChange} channels={channels} />
                  </section>

                  <section id="step-method" className="scroll-mt-6">
                    <StepHeading
                      number={3}
                      title="Choose a sampling method"
                      description="Decide how records are drawn from the filtered population."
                    />
                    <SamplingMethodSelector
                      value={state.samplingMethod}
                      onChange={handleSamplingMethodChange}
                      randomSize={state.sampleSize}
                      onRandomSizeChange={handleRandomSizeChange}
                      randomPercent={state.samplePercent}
                      onRandomPercentChange={handleRandomPercentChange}
                      seed={state.seed}
                      onSeedChange={handleSeedChange}
                      strataVariable={state.strataVariable}
                      onStrataVariableChange={handleStrataVariableChange}
                      samplesPerStratum={state.samplesPerStratum}
                      onSamplesPerStratumChange={handleSamplesPerStratumChange}
                      topMetric={state.topMetric}
                      onTopMetricChange={handleTopMetricChange}
                      topPercent={state.topPercent}
                      onTopPercentChange={handleTopPercentChange}
                    />
                  </section>

                  <section id="step-save" className="scroll-mt-6">
                    <StepHeading
                      number={4}
                      title="Labels & save"
                      description="Document your sample with metadata and choose how it is stored."
                    />
                    <ResultActions
                      labels={state.labels}
                      onLabelsChange={handleLabelsChange}
                      saveOption={state.saveOption}
                      onSaveOptionChange={handleSaveOptionChange}
                      datasetName={state.datasetName}
                      onDatasetNameChange={handleDatasetNameChange}
                      existingDatasets={[]}
                      onCreateDataset={handleCreateDataset}
                      sampleIds={previewResult?.entity_ids ?? []}
                    />
                  </section>
                </div>

                <aside className="lg:sticky lg:top-6">
                  <LivePreview
                    state={state}
                    onRefresh={runPreview}
                    isRefreshing={isRefreshing}
                    previewResult={previewResult}
                  />
                </aside>
              </div>
      </div>
      {scrollHint && canScrollDown && (
        <button
          type="button"
          onClick={() =>
            scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
          }
          className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full border bg-background/90 px-3.5 py-2 text-xs font-medium text-muted-foreground shadow-lg backdrop-blur transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Scroll down
          <ChevronDown className="size-3.5 animate-bounce" aria-hidden />
        </button>
      )}
    </div>
  );
}

function StepHeading({
  number,
  title,
  description,
}: {
  number: number;
  title: string;
  description: string;
}) {
  return (
    <div className="mb-5 flex items-start gap-3">
      <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
        {number}
      </span>
      <div>
        <h3 className="text-base font-semibold tracking-tight">{title}</h3>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

function metricStrategy(state: WorkbenchState): string {
  if (state.entityType === "comment") {
    return state.topMetric === "replies" ? "top_replies" : "top_likes";
  }
  switch (state.topMetric) {
    case "likes":
      return "top_likes";
    case "views":
      return "top_views";
    default:
      return "top_comments";
  }
}

function buildAdvancedSpec(state: WorkbenchState): AdvancedSamplingSpec {
  const isTopMetric = state.samplingMethod === "topMetric";
  const isRandom = state.samplingMethod === "random";
  const spec: AdvancedSamplingSpec = {
    strategy: state.samplingMethod === "full" ? "random" : isTopMetric ? metricStrategy(state) : state.samplingMethod,
    entity_type: state.entityType,
    size: isRandom && state.sampleSize ? Math.max(0, Math.floor(Number(state.sampleSize))) : undefined,
    percent: isTopMetric && state.topPercent ? Number(state.topPercent) : isRandom && state.samplePercent ? Number(state.samplePercent) : undefined,
    seed: state.seed ? Number(state.seed) : undefined,
    date_from: state.filters.uploadDateFrom,
    date_to: state.filters.uploadDateTo,
    strata: state.samplingMethod === "stratified" ? (state.strataVariable as "year" | "month" | "weekday") : undefined,
    sample_per_stratum: state.samplingMethod === "stratified" && state.samplesPerStratum ? Math.max(1, Math.floor(Number(state.samplesPerStratum))) : undefined,
    channel_ids: Array.from(new Set([...state.channelIds, ...state.filters.includeChannelIds])),
    run_ids: state.runScope === "specific" && state.runIds.length > 0 ? state.runIds : undefined,
    author_ids: state.authorIds.length > 0 ? state.authorIds : undefined,
    exclude_author_ids: state.filters.excludeAuthorIds.length > 0 ? state.filters.excludeAuthorIds : undefined,
    author_names: state.filters.includeAuthorNames.length > 0 ? state.filters.includeAuthorNames : undefined,
    exclude_author_names: state.filters.excludeAuthorNames.length > 0 ? state.filters.excludeAuthorNames : undefined,
    video_ids: state.filters.videoIds.length > 0 ? state.filters.videoIds : undefined,
    video_type: state.filters.videoType !== "any" ? state.filters.videoType : undefined,
    duration_min: state.filters.durationMin,
    duration_max: state.filters.durationMax,
    views_min: state.filters.viewsMin,
    views_max: state.filters.viewsMax,
    keywords: state.filters.tags.length > 0 ? state.filters.tags : undefined,
    tags: state.filters.tags.length > 0 ? state.filters.tags : undefined,
    categories: state.filters.categories.length > 0 ? state.filters.categories : undefined,
    min_likes: state.filters.minLikes,
    max_likes: state.filters.maxLikes,
    min_replies: state.filters.minReplies,
    max_replies: state.filters.maxReplies,
    only_roots: state.filters.commentType === "roots",
    only_replies: state.filters.commentType === "replies",
    comment_keywords: state.filters.commentKeywords.length > 0 ? state.filters.commentKeywords : undefined,
    overlap: state.filters.overlapMode !== "off" ? state.filters.overlapMode : undefined,
    overlap_min: state.filters.overlapMin,
    overlap_video_ids:
      state.filters.overlapMode === "video" && state.filters.overlapVideoIds.length > 0
        ? state.filters.overlapVideoIds
        : undefined,
    overlap_channel_ids:
      state.filters.overlapMode === "channel" && state.filters.overlapChannelIds.length > 0
        ? state.filters.overlapChannelIds
        : undefined,
    include_all_channels: state.scopeType === "all",
  };

  return spec;
}