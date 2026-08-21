"use client";

import { useState } from "react";
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import type { ScrapeFilters } from "@/lib/network-expansion-types";

export const DEFAULT_EXPANSION_FILTERS: ScrapeFilters = {
  max_recommendations_per_video: null,
  collect_comments: true,
  comment_min_likes: null,
  comment_date_from: null,
  comment_date_to: null,
  max_comments_per_video: null,
  dedupe: true,
  only_new_targets: true,
  concurrency: null,
  projection: "video",
};

function numberOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function ScrapeFiltersDialog({
  open,
  onOpenChange,
  title,
  description,
  initial = DEFAULT_EXPANSION_FILTERS,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  initial?: ScrapeFilters;
  onConfirm: (filters: ScrapeFilters) => void;
}) {
  const [filters, setFilters] = useState<ScrapeFilters>({ ...initial });

  function update<K extends keyof ScrapeFilters>(key: K, value: ScrapeFilters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next: boolean) => {
        if (next) setFilters({ ...initial });
        onOpenChange(next);
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Projection</Label>
            <Select
              value={filters.projection ?? "video"}
              onValueChange={(value) => {
                if (value) update("projection", value);
              }}
              items={[
                { value: "video", label: "Video graph" },
                { value: "channel", label: "Channel graph" },
              ]}
            >
              <SelectTrigger aria-label="Projection">
                <SelectValue placeholder="Projection" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="video">Video graph</SelectItem>
                <SelectItem value="channel">Channel graph</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Max recs / video</Label>
              <Input
                type="number"
                min={1}
                placeholder="No limit"
                value={filters.max_recommendations_per_video ?? ""}
                onChange={(e) =>
                  update("max_recommendations_per_video", numberOrNull(e.target.value))
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label>Concurrency</Label>
              <Input
                type="number"
                min={1}
                placeholder="Default"
                value={filters.concurrency ?? ""}
                onChange={(e) => update("concurrency", numberOrNull(e.target.value))}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Min comment likes</Label>
            <Input
              type="number"
              min={0}
              placeholder="No minimum"
              value={filters.comment_min_likes ?? ""}
              onChange={(e) =>
                update(
                  "comment_min_likes",
                  e.target.value.trim() === ""
                    ? null
                    : Math.max(0, Number(e.target.value) || 0),
                )
              }
            />
          </div>

          <div className="space-y-1.5">
            <Label>Max comments / video</Label>
            <Input
              type="number"
              min={1}
              placeholder="No cap"
              value={filters.max_comments_per_video ?? ""}
              onChange={(e) =>
                update("max_comments_per_video", numberOrNull(e.target.value))
              }
            />
          </div>

          <div className="space-y-1.5">
            <Label>Comment date window</Label>
            <div className="flex items-center gap-2">
              <Input
                type="date"
                value={filters.comment_date_from ?? ""}
                onChange={(e) => update("comment_date_from", e.target.value || null)}
                aria-label="Comment date from"
              />
              <span className="text-muted-foreground">to</span>
              <Input
                type="date"
                value={filters.comment_date_to ?? ""}
                onChange={(e) => update("comment_date_to", e.target.value || null)}
                aria-label="Comment date to"
              />
            </div>
          </div>

          <div className="space-y-2">
            {(
              [
                ["collect_comments", "Collect comments"],
                ["dedupe", "Skip edges already observed"],
                ["only_new_targets", "Only enrich new target videos"],
              ] as const
            ).map(([key, label]) => (
              <div key={key} className="flex items-center gap-2">
                <Checkbox
                  checked={Boolean(filters[key])}
                  onCheckedChange={(value) => update(key, value === true)}
                  id={`filters-${key}`}
                />
                <Label htmlFor={`filters-${key}`} className="font-normal">
                  {label}
                </Label>
              </div>
            ))}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => onConfirm(filters)}>Start scrape</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
