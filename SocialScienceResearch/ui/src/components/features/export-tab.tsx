"use client";

import { useState, useEffect } from "react";
import { Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  SelectGroup,
  SelectLabel,
} from "@/components/ui/select";
import { Combobox, ComboboxOption } from "@/components/ui/combobox";
import { useToast } from "@/components/ui/toast";
import { useExportData } from "@/services/queries";
import { exportData } from "@/services/api";
import { formatNumber } from "@/lib/format";
import type { ExportRequest } from "@/lib/types";

const ENTITY_TYPES = [
  { value: "video", label: "Video" },
  { value: "comment", label: "Comment" },
  { value: "channel", label: "Channel" },
  { value: "run", label: "Run" },
  { value: "sample", label: "Sample" },
  { value: "dataset", label: "Dataset" },
] as const;

const ENTITY_TYPE_COLUMNS: Record<string, { value: string; label: string }[]> = {
  video: [
    { value: "video_id", label: "Video ID" },
    { value: "title", label: "Title" },
    { value: "channel_id", label: "Channel ID" },
    { value: "duration", label: "Duration (s)" },
    { value: "upload_date", label: "Upload Date" },
    { value: "tags", label: "Tags" },
    { value: "categories", label: "Categories" },
    { value: "view_count", label: "View Count" },
    { value: "like_count", label: "Like Count" },
    { value: "comment_count", label: "Comment Count" },
    { value: "is_short", label: "Is Short" },
    { value: "live_status", label: "Live Status" },
    { value: "transcript_status", label: "Transcript Status" },
  ],
  comment: [
    { value: "comment_id", label: "Comment ID" },
    { value: "video_id", label: "Video ID" },
    { value: "author_name", label: "Author Name" },
    { value: "author_id", label: "Author ID" },
    { value: "comment_text", label: "Comment Text" },
    { value: "published_at", label: "Published At" },
    { value: "like_count", label: "Like Count" },
    { value: "reply_count", label: "Reply Count" },
    { value: "is_reply", label: "Is Reply" },
    { value: "parent_comment_id", label: "Parent Comment ID" },
    { value: "is_removed", label: "Is Removed" },
  ],
  channel: [
    { value: "channel_id", label: "Channel ID" },
    { value: "title", label: "Title" },
    { value: "subscriber_count", label: "Subscriber Count" },
    { value: "video_count", label: "Video Count" },
    { value: "view_count", label: "View Count" },
    { value: "description", label: "Description" },
  ],
  run: [
    { value: "run_id", label: "Run ID" },
    { value: "run_type", label: "Run Type" },
    { value: "target_url", label: "Target URL" },
    { value: "status", label: "Status" },
    { value: "started_at", label: "Started At" },
    { value: "finished_at", label: "Finished At" },
    { value: "entities_discovered", label: "Entities Discovered" },
    { value: "entities_succeeded", label: "Entities Succeeded" },
    { value: "entities_failed", label: "Entities Failed" },
    { value: "comments_collected", label: "Comments Collected" },
  ],
  sample: [
    { value: "sample_id", label: "Sample ID" },
    { value: "strategy", label: "Strategy" },
    { value: "entity_type", label: "Entity Type" },
    { value: "population_size", label: "Population Size" },
    { value: "sample_size", label: "Sample Size" },
    { value: "seed", label: "Seed" },
    { value: "created_at", label: "Created At" },
  ],
  dataset: [
    { value: "dataset_id", label: "Dataset ID" },
    { value: "name", label: "Name" },
    { value: "entity_type", label: "Entity Type" },
    { value: "row_count", label: "Row Count" },
    { value: "columns", label: "Columns" },
    { value: "created_at", label: "Created At" },
    { value: "file_size", label: "File Size" },
  ],
};

function getAvailableColumns(entityType: string): { value: string; label: string }[] {
  return ENTITY_TYPE_COLUMNS[entityType] ?? [];
}

export function ProjectExportButton({
  projectId,
  className,
}: {
  projectId: string;
  className?: string;
}) {
  const { toast } = useToast();
  const [isExporting, setIsExporting] = useState(false);

  async function handleExport() {
    setIsExporting(true);
    try {
      const blob = await exportData({ project_id: projectId });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `project_${projectId}_export.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast({
        title: "Export started",
        description: "Your project's collected data is downloading as Excel.",
      });
    } catch (error) {
      toast({
        title: "Export failed",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive",
      });
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className={className}
      onClick={handleExport}
      disabled={isExporting}
    >
      {isExporting ? (
        <>
          <Loader2 className="size-4 animate-spin" aria-hidden />
          Exporting…
        </>
      ) : (
        <>
          <Download className="size-4" aria-hidden />
          Export project to Excel
        </>
      )}
    </Button>
  );
}

export function ExportTab() {
  const { toast } = useToast();
  const exportMutation = useExportData();

  const [entityType, setEntityType] = useState<typeof ENTITY_TYPES[number]["value"]>("video");
  const [entityIds, setEntityIds] = useState<string[]>([]);
  const [selectedColumns, setSelectedColumns] = useState<string[]>(() =>
    getAvailableColumns("video").map((c) => c.value),
  );
  const [filename, setFilename] = useState("");
  const [isLoadingIds, setIsLoadingIds] = useState(true);
  const [availableIds, setAvailableIds] = useState<ComboboxOption[]>([]);

  const columns = getAvailableColumns(entityType);

  useEffect(() => {
    let active = true;
    fetch(`/api/v1/social-science/entities/${entityType}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!active) return;
        const items = (data?.items ?? []) as { id: string; title?: string }[];
        setAvailableIds(
          items.map((item) => ({ value: item.id, label: item.title ?? item.id })),
        );
      })
      .catch(() => {
        if (active) setAvailableIds([]);
      })
      .finally(() => {
        if (active) setIsLoadingIds(false);
      });
    return () => {
      active = false;
    };
  }, [entityType]);

  function toggleColumn(columnValue: string) {
    setSelectedColumns((prev) =>
      prev.includes(columnValue)
        ? prev.filter((c) => c !== columnValue)
        : [...prev, columnValue]
    );
  }

  function selectAllColumns() {
    setSelectedColumns(columns.map((c) => c.value));
  }

  function deselectAllColumns() {
    setSelectedColumns([]);
  }

  function generateDefaultFilename(): string {
    const date = new Date().toISOString().slice(0, 10);
    return `${entityType}_export_${date}.xlsx`;
  }

  async function handleExport(event: React.FormEvent) {
    event.preventDefault();
    if (exportMutation.isPending || entityIds.length === 0 || selectedColumns.length === 0) return;

    const requestBody = {
      entity_type: entityType,
      ids: entityIds,
      columns: selectedColumns,
      filename: filename || undefined,
    };

    try {
      const blob = await exportMutation.mutateAsync(requestBody);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || generateDefaultFilename();
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      toast({
        title: "Export successful",
        description: `Downloaded ${formatNumber(entityIds.length)} ${entityType}(s)`,
      });
    } catch (error) {
      toast({
        title: "Export failed",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive",
      });
    }
  }

  function handleEntityTypeChange(value: typeof ENTITY_TYPES[number]["value"] | null) {
    if (!value) return;
    setEntityType(value);
    setSelectedColumns(getAvailableColumns(value).map((c) => c.value));
    setEntityIds([]);
    setAvailableIds([]);
    setIsLoadingIds(true);
  }

  function handleEntityIdsChange(value: string | string[]) {
    setEntityIds(Array.isArray(value) ? value : value ? [value] : []);
  }

  return (
    <Card className="w-full max-w-4xl">
      <CardHeader>
        <CardTitle>Export Data</CardTitle>
        <CardDescription>
          Select entities and columns to export to Excel format
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleExport} className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="entity-type">Entity Type</Label>
            <Select value={entityType} onValueChange={handleEntityTypeChange}>
              <SelectTrigger id="entity-type">
                <SelectValue placeholder="Select entity type" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel>Entities</SelectLabel>
                  {ENTITY_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="entity-ids">Entity IDs</Label>
              <span className="text-xs text-muted-foreground">
                {entityIds.length} selected
              </span>
            </div>
            <Combobox
              items={availableIds}
              value={entityIds}
              onChange={handleEntityIdsChange}
              placeholder="Search and select entities…"
              emptyLabel="No entities found"
              searchPlaceholder="Search entities…"
              multiple
              disabled={isLoadingIds}
            />
            {isLoadingIds && (
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Loader2 className="size-3 animate-spin" aria-hidden />
                Loading available entities…
              </p>
            )}
            {availableIds.length === 0 && !isLoadingIds && (
              <p className="text-xs text-muted-foreground">
                No entities available for this type. Enter IDs manually if needed.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="columns">Columns</Label>
              <div className="flex gap-1">
                <Button type="button" variant="ghost" size="sm" onClick={selectAllColumns}>
                  Select all
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={deselectAllColumns}>
                  Deselect all
                </Button>
              </div>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 max-h-60 overflow-y-auto border rounded-md p-3">
              {columns.map((column) => (
                <div key={column.value} className="flex items-center gap-2">
                  <Checkbox
                    id={`col-${column.value}`}
                    checked={selectedColumns.includes(column.value)}
                    onCheckedChange={() => toggleColumn(column.value)}
                  />
                  <Label htmlFor={`col-${column.value}`} className="text-sm cursor-pointer mb-0">
                    {column.label}
                  </Label>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="filename">Filename</Label>
            <Input
              id="filename"
              value={filename}
              onChange={(e) => setFilename(e.target.value)}
              placeholder={generateDefaultFilename()}
            />
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button
              type="submit"
              disabled={exportMutation.isPending || entityIds.length === 0 || selectedColumns.length === 0}
            >
              {exportMutation.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                  Exporting…
                </>
              ) : (
                <>
                  <Download className="size-4" aria-hidden />
                  Export to Excel
                </>
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}