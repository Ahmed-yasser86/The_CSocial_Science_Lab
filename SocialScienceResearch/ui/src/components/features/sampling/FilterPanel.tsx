"use client";

import { useState, type ComponentType } from "react";
import {
  HelpCircle,
  Filter,
  User,
  Tv,
  Film,
  MessageSquareText,
  Network,
  CalendarRange,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Combobox } from "@/components/ui/combobox";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Accordion,
  AccordionItem,
  AccordionPanel,
  AccordionTrigger,
} from "@/components/ui/accordion";
import type { Channel } from "@/services/api";
import type { WorkbenchFilters } from "./LivePreview";

export interface FilterPanelProps {
  filters: WorkbenchFilters;
  onChange: (filters: WorkbenchFilters) => void;
  channels?: Channel[];
}

const DURATIONS = [
  { value: "any", label: "Any duration" },
  { value: "short", label: "Short (<60s)" },
  { value: "medium", label: "Medium (1-5min)" },
  { value: "long", label: "Long (5-20min)" },
  { value: "very_long", label: "Very long (>20min)" },
];

const COMMENT_TYPES = [
  { value: "all", label: "All comments" },
  { value: "roots", label: "Root comments only" },
  { value: "replies", label: "Replies only" },
];

const MATCH_MODES = [
  { value: "any", label: "Match any" },
  { value: "all", label: "Match all" },
];

const OVERLAP_MODES = [
  { value: "off", label: "Off" },
  { value: "video", label: "Across specific videos" },
  { value: "channel", label: "Across specific channels" },
];

const CATEGORY_OPTIONS = [
  "Entertainment",
  "News & Politics",
  "Education",
  "Science & Technology",
  "Music",
  "Gaming",
  "Sports",
  "Comedy",
  "Travel & Events",
  "Howto & Style",
  "People & Blogs",
  "Film & Animation",
  "Autos & Vehicles",
  "Pets & Animals",
  "Nonprofits & Activism",
];

function HelpTooltip({ content }: { content: string }) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span className="inline-flex cursor-help" aria-label="Help" tabIndex={0} />
        }
      >
        <HelpCircle className="size-3.5 shrink-0 text-muted-foreground cursor-help" />
      </TooltipTrigger>
      <TooltipContent side="right" className="max-w-64">
        <p>{content}</p>
      </TooltipContent>
    </Tooltip>
  );
}

function TagsInput({
  value,
  onChange,
  placeholder,
  helpText,
}: {
  value: string[];
  onChange: (val: string[]) => void;
  placeholder: string;
  helpText: string;
}) {
  const [input, setInput] = useState("");

  function addTag(tag: string) {
    const trimmed = tag.trim();
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
    }
    setInput("");
  }

  function removeTag(tag: string) {
    onChange(value.filter((t) => t !== tag));
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && input.trim()) {
              e.preventDefault();
              addTag(input);
            }
          }}
          placeholder={placeholder}
          className="flex-1"
        />
        <Button type="button" variant="outline" size="sm" onClick={() => addTag(input)}>
          Add
        </Button>
      </div>
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded-md border border-input bg-muted/50 px-2 py-0.5 text-xs"
            >
              <span className="truncate max-w-[200px]">{tag}</span>
              <button
                type="button"
                onClick={() => removeTag(tag)}
                className="shrink-0 text-muted-foreground hover:text-foreground"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <p className="text-xs text-muted-foreground">{helpText}</p>
    </div>
  );
}

function CategoriesSelect({
  value,
  onChange,
  helpText,
}: {
  value: string[];
  onChange: (val: string[]) => void;
  helpText: string;
}) {
  const [input, setInput] = useState("");
  const options = Array.from(new Set([...CATEGORY_OPTIONS, ...value]));

  function addCategory() {
    const trimmed = input.trim();
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
    }
    setInput("");
  }

  return (
    <div className="space-y-2">
      <Combobox
        items={options.map((option) => ({ value: option, label: option }))}
        value={value}
        onChange={(val) => onChange(Array.isArray(val) ? val : [val])}
        multiple
        placeholder="Select categories…"
        searchPlaceholder="Search categories…"
        emptyLabel="No categories found."
      />
      <div className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && input.trim()) {
              e.preventDefault();
              addCategory();
            }
          }}
          placeholder="Or type a custom category…"
          className="flex-1"
        />
        <Button type="button" variant="outline" size="sm" onClick={addCategory}>
          Add
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">{helpText}</p>
    </div>
  );
}

function NumberRange({
  min,
  max,
  onMinChange,
  onMaxChange,
  minPlaceholder = "Min",
  maxPlaceholder = "Max",
}: {
  min?: number;
  max?: number;
  onMinChange: (val: number | undefined) => void;
  onMaxChange: (val: number | undefined) => void;
  minPlaceholder?: string;
  maxPlaceholder?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <Input
        type="number"
        value={min ?? ""}
        onChange={(e) =>
          onMinChange(e.target.value ? Number(e.target.value) : undefined)
        }
        placeholder={minPlaceholder}
        className="w-28"
        min={0}
      />
      <span className="text-muted-foreground">–</span>
      <Input
        type="number"
        value={max ?? ""}
        onChange={(e) =>
          onMaxChange(e.target.value ? Number(e.target.value) : undefined)
        }
        placeholder={maxPlaceholder}
        className="w-28"
        min={0}
      />
    </div>
  );
}

function countActiveFilters(filters: WorkbenchFilters): number {
  let count = 0;
  if (filters.excludeAuthorIds.length) count++;
  if (filters.includeAuthorIds.length) count++;
  if (filters.excludeAuthorNames.length) count++;
  if (filters.includeAuthorNames.length) count++;
  if (filters.excludeVideoAuthor) count++;
  if (filters.videoType !== "any") count++;
  if (filters.durationMin != null || filters.durationMax != null) count++;
  if (filters.viewsMin != null || filters.viewsMax != null) count++;
  if (filters.uploadDateFrom || filters.uploadDateTo) count++;
  if (filters.categories.length) count++;
  if (filters.videoIds.length) count++;
  if (filters.tags.length) count++;
  if (filters.minLikes != null || filters.maxLikes != null) count++;
  if (filters.minReplies != null || filters.maxReplies != null) count++;
  if (filters.commentType !== "all") count++;
  if (filters.commentKeywords.length) count++;
  if (filters.matchMode !== "any") count++;
  if (filters.overlapMode !== "off") count++;
  if (filters.overlapMin !== 2) count++;
  if (filters.overlapVideoIds.length) count++;
  if (filters.overlapChannelIds.length) count++;
  if (filters.videoDateFrom || filters.videoDateTo) count++;
  return count;
}

function SectionTrigger({
  icon: Icon,
  title,
  help,
  description,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  help: string;
  description: string;
}) {
  return (
    <span className="flex flex-col items-start gap-1 text-left">
      <span className="flex items-center gap-2.5">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-muted/70 text-foreground">
          <Icon className="size-3.5" aria-hidden />
        </span>
        <span className="flex items-center gap-1.5">
          {title}
          <HelpTooltip content={help} />
        </span>
      </span>
      <span className="pl-[34px] text-xs font-normal text-muted-foreground">{description}</span>
    </span>
  );
}

export function FilterPanel({ filters, onChange, channels = [] }: FilterPanelProps) {
  function updateFilter<K extends keyof WorkbenchFilters>(
    key: K,
    value: WorkbenchFilters[K]
  ) {
    onChange({ ...filters, [key]: value });
  }

  const activeCount = countActiveFilters(filters);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Filter className="size-4" aria-hidden />
            </span>
            <div>
              <CardTitle className="text-base font-semibold">Filter the Sample</CardTitle>
              <CardDescription>
                Each section narrows a different layer — authors, channels, videos,
                comments, overlap and time. Sections start collapsed to keep things calm.
              </CardDescription>
            </div>
          </div>
          <Badge variant={activeCount > 0 ? "secondary" : "outline"} className="mt-1">
            {activeCount > 0 ? `${activeCount} active` : "All optional"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="py-2">
        <Accordion defaultValue={[]} className="space-y-3">
          <AccordionItem value="author" className="overflow-hidden rounded-lg border border-border bg-muted/20 px-4 data-open:bg-muted/40">
            <AccordionTrigger className="py-3.5">
              <SectionTrigger
                icon={User}
                title="Author Filters"
                help="Filter comments by the author who wrote them"
                description="Choose which comment authors to include or exclude."
              />
            </AccordionTrigger>
            <AccordionPanel>
              <div className="space-y-6 pb-2">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="excludeVideoAuthor"
                    checked={filters.excludeVideoAuthor}
                    onCheckedChange={(checked) =>
                      updateFilter("excludeVideoAuthor", Boolean(checked))
                    }
                  />
                  <Label htmlFor="excludeVideoAuthor" className="text-sm font-normal cursor-pointer">
                    Exclude the video uploader&apos;s comments
                  </Label>
                  <HelpTooltip content="Drop comments made by the uploader of the video" />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Include Author Names</Label>
                    <HelpTooltip content="Keep comments whose author name contains any entered name (case-insensitive)" />
                  </div>
                  <TagsInput
                    value={filters.includeAuthorNames}
                    onChange={(val) => updateFilter("includeAuthorNames", val)}
                    placeholder="Enter author name and press Add"
                    helpText="Comment authors whose name matches are included"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Exclude Author Names</Label>
                    <HelpTooltip content="Drop comments whose author name contains any entered name (case-insensitive)" />
                  </div>
                  <TagsInput
                    value={filters.excludeAuthorNames}
                    onChange={(val) => updateFilter("excludeAuthorNames", val)}
                    placeholder="Enter author name to exclude and press Add"
                    helpText="Comment authors whose name matches are removed"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Exclude Author IDs</Label>
                    <HelpTooltip content="Comma-separated author IDs to exclude from sampling" />
                  </div>
                  <Input
                    value={filters.excludeAuthorIds.join(", ")}
                    onChange={(e) =>
                      updateFilter(
                        "excludeAuthorIds",
                        e.target.value
                          .split(",")
                          .map((id) => id.trim())
                          .filter(Boolean)
                      )
                    }
                    placeholder="Enter author IDs, separated by commas"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Include Author IDs</Label>
                    <HelpTooltip content="Comma-separated author IDs to include in sampling" />
                  </div>
                  <Input
                    value={filters.includeAuthorIds.join(", ")}
                    onChange={(e) =>
                      updateFilter(
                        "includeAuthorIds",
                        e.target.value
                          .split(",")
                          .map((id) => id.trim())
                          .filter(Boolean)
                      )
                    }
                    placeholder="Enter author IDs, separated by commas"
                  />
                </div>
              </div>
            </AccordionPanel>
          </AccordionItem>

          <AccordionItem value="channel" className="overflow-hidden rounded-lg border border-border bg-muted/20 px-4 data-open:bg-muted/40">
            <AccordionTrigger className="py-3.5">
              <SectionTrigger
                icon={Tv}
                title="Channel Filters"
                help="Filter by the channel the video belongs to"
                description="Restrict the sample to specific channels, on top of the scope."
              />
            </AccordionTrigger>
            <AccordionPanel>
              <div className="space-y-1.5 pb-2">
                <Label className="text-sm font-medium">Channels</Label>
                <Combobox
                  items={channels.map((c) => ({
                    value: c.channel_id,
                    label: c.title ? `${c.title} (${c.channel_id})` : c.channel_id,
                  }))}
                  value={filters.includeChannelIds}
                  onChange={(val) =>
                    updateFilter("includeChannelIds", Array.isArray(val) ? val : [val])
                  }
                  placeholder="Search and select channels…"
                  searchPlaceholder="Search channels…"
                  multiple
                  emptyLabel="No channels found."
                />
                <p className="text-xs text-muted-foreground">
                  Comments on videos in these channels are included.
                </p>
              </div>
            </AccordionPanel>
          </AccordionItem>

          <AccordionItem value="video" className="overflow-hidden rounded-lg border border-border bg-muted/20 px-4 data-open:bg-muted/40">
            <AccordionTrigger className="py-3.5">
              <SectionTrigger
                icon={Film}
                title="Video Filters"
                help="Filter videos by their metadata"
                description="Restrict which videos enter the population."
              />
            </AccordionTrigger>
            <AccordionPanel>
              <div className="space-y-6 pb-2">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Specific Videos</Label>
                    <HelpTooltip content="Only sample comments on these videos" />
                  </div>
                  <TagsInput
                    value={filters.videoIds}
                    onChange={(val) => updateFilter("videoIds", val)}
                    placeholder="Enter video ID and press Add"
                    helpText="Only comments on these specific videos are considered"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Categories</Label>
                    <HelpTooltip content="Videos must belong to at least one selected category" />
                  </div>
                  <CategoriesSelect
                    value={filters.categories}
                    onChange={(val) => updateFilter("categories", val)}
                    helpText="Videos in any selected category are included"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Duration</Label>
                    <HelpTooltip content="Filter videos by their length" />
                  </div>
                  <Select
                    value={filters.videoType ?? "any"}
                    onValueChange={(val) => updateFilter("videoType", val ?? "any")}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {DURATIONS.map((d) => (
                        <SelectItem key={d.value} value={d.value}>
                          {d.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Views Range</Label>
                    <HelpTooltip content="Filter videos by view count range" />
                  </div>
                  <NumberRange
                    min={filters.viewsMin}
                    max={filters.viewsMax}
                    onMinChange={(val) => updateFilter("viewsMin", val)}
                    onMaxChange={(val) => updateFilter("viewsMax", val)}
                    minPlaceholder="Min views"
                    maxPlaceholder="Max views"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Upload Date Range</Label>
                    <HelpTooltip content="Filter videos by upload date range" />
                  </div>
                  <div className="flex items-center gap-2">
                    <Input
                      type="date"
                      value={filters.uploadDateFrom ?? ""}
                      onChange={(e) =>
                        updateFilter(
                          "uploadDateFrom",
                          e.target.value || undefined
                        )
                      }
                      className="flex-1"
                    />
                    <span className="text-muted-foreground">–</span>
                    <Input
                      type="date"
                      value={filters.uploadDateTo ?? ""}
                      onChange={(e) =>
                        updateFilter("uploadDateTo", e.target.value || undefined)
                      }
                      className="flex-1"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Tags</Label>
                    <HelpTooltip content="Filter videos by tags (any match)" />
                  </div>
                  <TagsInput
                    value={filters.tags}
                    onChange={(val) => updateFilter("tags", val)}
                    placeholder="Enter tag and press Add"
                    helpText="Videos must have at least one of these tags"
                  />
                </div>
              </div>
            </AccordionPanel>
          </AccordionItem>

          <AccordionItem value="comment" className="overflow-hidden rounded-lg border border-border bg-muted/20 px-4 data-open:bg-muted/40">
            <AccordionTrigger className="py-3.5">
              <SectionTrigger
                icon={MessageSquareText}
                title="Comment Filters"
                help="Filter comments by their attributes"
                description="Filter the comments themselves by engagement, type or text."
              />
            </AccordionTrigger>
            <AccordionPanel>
              <div className="space-y-6 pb-2">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Likes Range</Label>
                    <HelpTooltip content="Filter comments by like count range" />
                  </div>
                  <NumberRange
                    min={filters.minLikes}
                    max={filters.maxLikes}
                    onMinChange={(val) => updateFilter("minLikes", val)}
                    onMaxChange={(val) => updateFilter("maxLikes", val)}
                    minPlaceholder="Min likes"
                    maxPlaceholder="Max likes"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Replies Range</Label>
                    <HelpTooltip content="Filter comments by reply count range" />
                  </div>
                  <NumberRange
                    min={filters.minReplies}
                    max={filters.maxReplies}
                    onMinChange={(val) => updateFilter("minReplies", val)}
                    onMaxChange={(val) => updateFilter("maxReplies", val)}
                    minPlaceholder="Min replies"
                    maxPlaceholder="Max replies"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Comment Type</Label>
                    <HelpTooltip content="Filter by comment type" />
                  </div>
                  <Select
                    value={filters.commentType}
                    onValueChange={(val) =>
                      updateFilter("commentType", val as "all" | "roots" | "replies")
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {COMMENT_TYPES.map((ct) => (
                        <SelectItem key={ct.value} value={ct.value}>
                          {ct.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Keywords</Label>
                    <HelpTooltip content="Filter comments containing these keywords" />
                  </div>
                  <TagsInput
                    value={filters.commentKeywords}
                    onChange={(val) => updateFilter("commentKeywords", val)}
                    placeholder="Enter keyword and press Add"
                    helpText="Comments must contain at least one keyword"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Keyword Match Mode</Label>
                    <HelpTooltip content="Whether comments must match any or all keywords" />
                  </div>
                  <Select
                    value={filters.matchMode}
                    onValueChange={(val) =>
                      updateFilter("matchMode", val as "any" | "all")
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {MATCH_MODES.map((mm) => (
                        <SelectItem key={mm.value} value={mm.value}>
                          {mm.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </AccordionPanel>
          </AccordionItem>

          <AccordionItem value="overlap" className="overflow-hidden rounded-lg border border-border bg-muted/20 px-4 data-open:bg-muted/40">
            <AccordionTrigger className="py-3.5">
              <SectionTrigger
                icon={Network}
                title="Author Overlap Filters"
                help="Keep only authors active across multiple specific videos or channels"
                description="Keep authors who appear across several specific videos or channels (pick the entities, or count across all)."
              />
            </AccordionTrigger>
            <AccordionPanel>
              <div className="space-y-6 pb-2">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Overlap Mode</Label>
                    <HelpTooltip content="Count distinct videos or distinct channels per author" />
                  </div>
                  <Select
                    value={filters.overlapMode}
                    onValueChange={(val) =>
                      updateFilter("overlapMode", val as "off" | "video" | "channel")
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {OVERLAP_MODES.map((mode) => (
                        <SelectItem key={mode.value} value={mode.value}>
                          {mode.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {filters.overlapMode === "video" && (
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <Label className="text-sm font-medium">Specific Videos</Label>
                      <HelpTooltip content="Overlap is counted only across these videos. Leave empty to count across every video in the population." />
                    </div>
                    <TagsInput
                      value={filters.overlapVideoIds}
                      onChange={(val) => updateFilter("overlapVideoIds", val)}
                      placeholder="Enter video ID and press Add"
                      helpText="Authors must be active across these specific videos to qualify."
                    />
                  </div>
                )}

                {filters.overlapMode === "channel" && (
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <Label className="text-sm font-medium">Specific Channels</Label>
                      <HelpTooltip content="Overlap is counted only across these channels. Leave empty to count across every channel in the population." />
                    </div>
                    <Combobox
                      items={channels.map((c) => ({
                        value: c.channel_id,
                        label: c.title ? `${c.title} (${c.channel_id})` : c.channel_id,
                      }))}
                      value={filters.overlapChannelIds}
                      onChange={(val) =>
                        updateFilter("overlapChannelIds", Array.isArray(val) ? val : [val])
                      }
                      placeholder="Search and select channels…"
                      searchPlaceholder="Search channels…"
                      multiple
                      emptyLabel="No channels found."
                    />
                    <p className="text-xs text-muted-foreground">
                      Authors must be active across these specific channels to qualify.
                    </p>
                  </div>
                )}

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Minimum Overlap Count</Label>
                    <HelpTooltip content="An author must appear in at least this many distinct videos/channels" />
                  </div>
                  <Input
                    type="number"
                    min={1}
                    value={filters.overlapMin}
                    onChange={(e) =>
                      updateFilter(
                        "overlapMin",
                        Math.max(1, Number(e.target.value) || 1)
                      )
                    }
                    placeholder="Minimum overlap count"
                  />
                  <p className="text-xs text-muted-foreground">
                    Authors active in fewer distinct {filters.overlapMode === "channel" ? "channels" : "videos"}
                    {filters.overlapMode === "video" && filters.overlapVideoIds.length > 0
                      ? " among the selected videos"
                      : filters.overlapMode === "channel" && filters.overlapChannelIds.length > 0
                        ? " among the selected channels"
                        : ""}{" "}
                    are removed.
                  </p>
                </div>
              </div>
            </AccordionPanel>
          </AccordionItem>

          <AccordionItem value="temporal" className="overflow-hidden rounded-lg border border-border bg-muted/20 px-4 data-open:bg-muted/40">
            <AccordionTrigger className="py-3.5">
              <SectionTrigger
                icon={CalendarRange}
                title="Temporal Filters"
                help="Filter by date ranges for videos and comments"
                description="Narrow the population by publish or comment dates."
              />
            </AccordionTrigger>
            <AccordionPanel>
              <div className="space-y-6 pb-2">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Video Published Date</Label>
                    <HelpTooltip content="Filter videos by their publish date" />
                  </div>
                  <div className="flex items-center gap-2">
                    <Input
                      type="date"
                      value={filters.videoDateFrom ?? ""}
                      onChange={(e) =>
                        updateFilter(
                          "videoDateFrom",
                          e.target.value || undefined
                        )
                      }
                      className="flex-1"
                    />
                    <span className="text-muted-foreground">–</span>
                    <Input
                      type="date"
                      value={filters.videoDateTo ?? ""}
                      onChange={(e) =>
                        updateFilter("videoDateTo", e.target.value || undefined)
                      }
                      className="flex-1"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium">Comment Date</Label>
                    <HelpTooltip content="Filter comments by their creation date" />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Use the global date filter in the data panel for comment dates.
                  </p>
                </div>
              </div>
            </AccordionPanel>
          </AccordionItem>
        </Accordion>
      </CardContent>
    </Card>
  );
}