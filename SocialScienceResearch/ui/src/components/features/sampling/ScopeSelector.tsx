"use client";

import { useState } from "react";
import { Search, Globe2, Tv, User, Settings2, UserPlus, Database } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { cn } from "@/lib/utils";
import type { Channel } from "@/services/api";
import type { CollectionRun } from "@/lib/types";
import type { ComponentType } from "react";

export type ScopeType = "all" | "channel" | "author" | "custom";

export interface ScopeValue {
  scopeType: ScopeType;
  channelIds: string[];
  authorIds: string[];
  runScope: "all" | "specific";
  runIds: string[];
}

interface ScopeSelectorProps {
  value: ScopeValue;
  onChange: (value: ScopeValue) => void;
  channels?: Channel[];
  runs?: CollectionRun[];
  onSearchChannels?: (query: string) => void;
  channelLoading?: boolean;
}

const SCOPE_OPTIONS: { value: ScopeType; label: string; icon: ComponentType<{ className?: string }> }[] = [
  { value: "all", label: "All Data", icon: Globe2 },
  { value: "channel", label: "By Channel", icon: Tv },
  { value: "author", label: "By Author", icon: User },
  { value: "custom", label: "Custom", icon: Settings2 },
];

export function ScopeSelector({
  value,
  onChange,
  channels = [],
  runs = [],
  channelLoading = false,
}: ScopeSelectorProps) {
  const [authorInput, setAuthorInput] = useState("");
  const [showAuthorInput, setShowAuthorInput] = useState(false);

  function setScopeType(type: ScopeType) {
    onChange({
      ...value,
      scopeType: type,
      runScope: type === "channel" ? value.runScope : "all",
      runIds: type === "channel" ? value.runIds : [],
    });
  }

  function addAuthorId(id: string) {
    const trimmed = id.trim();
    if (trimmed && !value.authorIds.includes(trimmed)) {
      onChange({ ...value, authorIds: [...value.authorIds, trimmed] });
    }
    setAuthorInput("");
    setShowAuthorInput(false);
  }

  function removeAuthorId(id: string) {
    onChange({ ...value, authorIds: value.authorIds.filter((a) => a !== id) });
  }

  const runOptions = runs.map((r) => ({
    value: r.run_id,
    label: r.name
      ? `${r.name} (${r.run_id})`
      : `${r.run_type} run ${r.run_id}`,
  }));

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Label className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Scope
        </Label>
        <p className="text-xs text-muted-foreground">
          Choose the universe of data this sample draws from.
        </p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {SCOPE_OPTIONS.map((option) => {
            const Icon = option.icon;
            const active = value.scopeType === option.value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setScopeType(option.value)}
                aria-pressed={active}
                className={cn(
                  "flex items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
                  active
                    ? "border-primary/50 bg-primary/10 text-primary"
                    : "border-border bg-background text-muted-foreground hover:border-input hover:text-foreground"
                )}
              >
                <Icon className="size-3.5" aria-hidden />
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      {value.scopeType === "channel" && (
        <div className="space-y-4 rounded-xl border bg-muted/20 p-4">
          <div className="space-y-0.5">
            <Label className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Channels
            </Label>
            <p className="text-xs text-muted-foreground">
              Only comments/videos from these channels are sampled.
            </p>
          </div>
          <Combobox
            items={channels.map((c) => ({
              value: c.channel_id,
              label: c.title ? `${c.title} (${c.channel_id})` : c.channel_id,
            }))}
            value={value.channelIds}
            onChange={(val) =>
              onChange({ ...value, channelIds: Array.isArray(val) ? val : [val] })
            }
            placeholder={
              channelLoading ? "Loading channels…" : "Search and select channels…"
            }
            searchPlaceholder="Search channels…"
            multiple
            emptyLabel={channelLoading ? "Loading…" : "No channels found."}
          />
          {value.channelIds.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {value.channelIds.length} channel(s) selected
            </p>
          )}

          <div className="space-y-2 border-t border-border pt-3">
            <div className="space-y-0.5">
              <Label className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Collection runs
              </Label>
              <p className="text-xs text-muted-foreground">
                Sample all data in the selected channels, or only the data collected in specific runs.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => onChange({ ...value, runScope: "all", runIds: [] })}
                aria-pressed={value.runScope === "all"}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                  value.runScope === "all"
                    ? "border-primary/50 bg-primary/10 text-primary"
                    : "border-border bg-background text-muted-foreground hover:border-input hover:text-foreground"
                )}
              >
                <Database className="size-3.5" aria-hidden />
                All data
              </button>
              <button
                type="button"
                onClick={() => onChange({ ...value, runScope: "specific" })}
                aria-pressed={value.runScope === "specific"}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                  value.runScope === "specific"
                    ? "border-primary/50 bg-primary/10 text-primary"
                    : "border-border bg-background text-muted-foreground hover:border-input hover:text-foreground"
                )}
              >
                <Database className="size-3.5" aria-hidden />
                Specific runs
              </button>
            </div>
            {value.runScope === "specific" && (
              <Combobox
                items={runOptions}
                value={value.runIds}
                onChange={(val) =>
                  onChange({
                    ...value,
                    runIds: Array.isArray(val) ? val : [val],
                  })
                }
                placeholder={runs.length === 0 ? "No runs available…" : "Select runs…"}
                searchPlaceholder="Search runs…"
                multiple
                emptyLabel="No runs found."
              />
            )}
            {value.runScope === "specific" && value.runIds.length > 0 && (
              <p className="text-xs text-muted-foreground">
                {value.runIds.length} run(s) selected
              </p>
            )}
          </div>
        </div>
      )}

      {value.scopeType === "author" && (
        <div className="space-y-2 rounded-xl border bg-muted/20 p-4">
          <div className="space-y-0.5">
            <Label className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Authors
            </Label>
            <p className="text-xs text-muted-foreground">
              Only comments from these specific author IDs are sampled.
            </p>
          </div>
          <div className="space-y-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={authorInput}
                onChange={(e) => setAuthorInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && authorInput.trim()) {
                    e.preventDefault();
                    addAuthorId(authorInput);
                  }
                }}
                placeholder="Enter author ID and press Enter…"
                className="pl-8"
              />
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setShowAuthorInput(!showAuthorInput)}
              className="text-xs"
            >
              <UserPlus className="size-3.5" aria-hidden />
              {showAuthorInput ? "Hide" : "Show"} manual input
            </Button>
          </div>
          {value.authorIds.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {value.authorIds.map((id) => (
                <span
                  key={id}
                  className="inline-flex items-center gap-1 rounded-md border border-input bg-muted/50 px-2 py-0.5 text-xs"
                >
                  <span className="font-mono truncate max-w-[150px]">{id}</span>
                  <button
                    type="button"
                    onClick={() => removeAuthorId(id)}
                    className="ml-0.5 shrink-0 text-muted-foreground hover:text-foreground"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
          {value.authorIds.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {value.authorIds.length} author(s) selected
            </p>
          )}
        </div>
      )}

      {value.scopeType === "custom" && (
        <div className="space-y-1 rounded-xl border bg-muted/20 p-4">
          <Label className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Custom Scope
          </Label>
          <p className="text-xs text-muted-foreground">
            Use the filters below to define a custom scope.
          </p>
        </div>
      )}
    </div>
  );
}