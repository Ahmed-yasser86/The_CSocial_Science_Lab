"use client";

import { useState } from "react";
import { Loader2, Plus, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
import { useToast } from "@/components/ui/toast";
import { useCreateSample } from "@/services/samples";
import { SAMPLE_ENTITY_OPTIONS, type SampleEntityType } from "@/lib/sample-types";
import type { Sample } from "@/lib/sample-types";

const STRATEGY_OPTIONS = [
  { value: "simple_random", label: "Simple random" },
  { value: "systematic", label: "Systematic" },
  { value: "stratified", label: "Stratified" },
  { value: "cluster", label: "Cluster" },
  { value: "convenience", label: "Convenience" },
];

type CriteriaKeyType = "text" | "date" | "number" | "boolean" | "select";

interface PredefinedCriteriaKey {
  key: string;
  label: string;
  type: CriteriaKeyType;
  placeholder?: string;
  options?: { value: string; label: string }[];
}

export const PREDEFINED_CRITERIA_KEYS: PredefinedCriteriaKey[] = [
  { key: "channel_id", label: "Channel ID", type: "text", placeholder: "UC…" },
  { key: "channel_handle", label: "Channel handle", type: "text", placeholder: "@handle" },
  { key: "video_id", label: "Video ID", type: "text", placeholder: "dQw4w9WgXcQ" },
  { key: "video_url", label: "Video URL", type: "text", placeholder: "https://youtube.com/watch?v=…" },
  { key: "author_id", label: "Author ID", type: "text", placeholder: "Comment author id" },
  { key: "author_name", label: "Author name", type: "text", placeholder: "Comment author name" },
  { key: "category", label: "Category", type: "text", placeholder: "e.g. Education" },
  { key: "date_from", label: "Date from", type: "date" },
  { key: "date_to", label: "Date to", type: "date" },
  { key: "min_likes", label: "Min likes", type: "number" },
  { key: "max_likes", label: "Max likes", type: "number" },
  { key: "min_replies", label: "Min replies", type: "number" },
  { key: "max_replies", label: "Max replies", type: "number" },
  { key: "keyword", label: "Keyword", type: "text", placeholder: "e.g. climate" },
  { key: "live_only", label: "Live only", type: "boolean" },
  {
    key: "sampling_strategy",
    label: "Sampling strategy",
    type: "select",
    options: [
      { value: "simple_random", label: "Simple random" },
      { value: "systematic", label: "Systematic" },
      { value: "stratified", label: "Stratified" },
      { value: "cluster", label: "Cluster" },
      { value: "convenience", label: "Convenience" },
    ],
  },
];

const PREDEFINED_CRITERIA_KEYS_BY_KEY = new Map(
  PREDEFINED_CRITERIA_KEYS.map((key) => [key.key, key]),
);

interface CriteriaRow {
  key: string;
  value: string;
}

function buildCriteriaJson(rows: CriteriaRow[]): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const row of rows) {
    const def = PREDEFINED_CRITERIA_KEYS_BY_KEY.get(row.key);
    if (!def) continue;
    if (def.type === "boolean") {
      if (row.value === "true") result[row.key] = true;
      continue;
    }
    const value = row.value.trim();
    if (value === "") continue;
    if (def.type === "number") {
      const num = Number(value);
      if (!Number.isNaN(num)) result[row.key] = num;
    } else {
      result[row.key] = value;
    }
  }
  return result;
}

export function SampleBuilder({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (sample: Sample) => void;
}) {
  const { toast } = useToast();
  const [entityType, setEntityType] = useState<SampleEntityType>("video");
  const [strategy, setStrategy] = useState("simple_random");
  const [seed, setSeed] = useState("");
  const [populationSize, setPopulationSize] = useState("");
  const [memberIds, setMemberIds] = useState("");
  const [criteriaRows, setCriteriaRows] = useState<CriteriaRow[]>([]);
  const [pendingKey, setPendingKey] = useState("");
  const [rawCriteria, setRawCriteria] = useState("");
  const [rawMode, setRawMode] = useState(false);
  const [populationQueryHash, setPopulationQueryHash] = useState("");

  const create = useCreateSample();

  function reset() {
    setEntityType("video");
    setStrategy("simple_random");
    setSeed("");
    setPopulationSize("");
    setMemberIds("");
    setCriteriaRows([]);
    setPendingKey("");
    setRawCriteria("");
    setRawMode(false);
    setPopulationQueryHash("");
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  const availableKeys = PREDEFINED_CRITERIA_KEYS.filter(
    (key) => !criteriaRows.some((row) => row.key === key.key),
  ).map((key) => ({ value: key.key, label: key.label }));

  function addAttribute(key: string) {
    if (!key || criteriaRows.some((row) => row.key === key)) return;
    setCriteriaRows((prev) => [...prev, { key, value: "" }]);
    setPendingKey("");
  }

  function updateAttribute(key: string, value: string) {
    setCriteriaRows((prev) =>
      prev.map((row) => (row.key === key ? { ...row, value } : row)),
    );
  }

  function removeAttribute(key: string) {
    setCriteriaRows((prev) => prev.filter((row) => row.key !== key));
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const ids = memberIds
      .split(/[\s,]+/)
      .map((part) => part.trim())
      .filter(Boolean);
    const population = Number(populationSize);
    if (!population || population < 0) {
      toast({
        variant: "destructive",
        title: "Invalid population size",
        description: "Enter the size of the population the sample was drawn from.",
      });
      return;
    }
    let criteriaJson: Record<string, unknown> | undefined;
    if (rawMode) {
      if (rawCriteria.trim()) {
        try {
          const parsed = JSON.parse(rawCriteria) as unknown;
          if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
            throw new Error("criteria must be a JSON object");
          }
          criteriaJson = parsed as Record<string, unknown>;
        } catch {
          toast({
            variant: "destructive",
            title: "Invalid criteria JSON",
            description: "Criteria must be a valid JSON object.",
          });
          return;
        }
      }
    } else {
      const built = buildCriteriaJson(criteriaRows);
      if (Object.keys(built).length > 0) criteriaJson = built;
    }
    create.mutate(
      {
        entity_type: entityType,
        strategy,
        seed: seed === "" ? null : Number(seed),
        population_size: population,
        member_ids: ids,
        criteria_json: criteriaJson,
        population_query_hash: populationQueryHash.trim(),
      },
      {
        onSuccess: (sample) => {
          toast({
            title: "Sample saved",
            description: `${sample.sample_id} · ${sample.sample_size} members`,
          });
          onCreated?.(sample);
          onOpenChange(false);
        },
        onError: (error) => {
          toast({
            variant: "destructive",
            title: "Could not save sample",
            description: error instanceof Error ? error.message : "Unknown error",
          });
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New sample</DialogTitle>
          <DialogDescription>
            Persist an immutable, reproducible sample. Member ids and criteria
            are recorded verbatim so the design can be audited and re-run.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Entity type">
              <Select
                value={entityType}
                onValueChange={(value) =>
                  setEntityType((value ?? "video") as SampleEntityType)
                }
                items={SAMPLE_ENTITY_OPTIONS.map((o) => ({
                  value: o.value,
                  label: o.label,
                }))}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SAMPLE_ENTITY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>

            <Field label="Strategy">
              <Select
                value={strategy}
                onValueChange={(value) => setStrategy(value ?? "simple_random")}
                items={STRATEGY_OPTIONS}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STRATEGY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Seed (optional)">
              <Input
                id="sample-seed"
                type="number"
                value={seed}
                onChange={(event) => setSeed(event.target.value)}
                autoComplete="off"
              />
            </Field>

            <Field label="Population size">
              <Input
                id="sample-population"
                type="number"
                min={0}
                value={populationSize}
                onChange={(event) => setPopulationSize(event.target.value)}
                aria-label="Population size"
                required
                autoComplete="off"
              />
            </Field>
          </div>

          <Field label="Population query hash (optional)">
            <Input
              id="sample-query-hash"
              value={populationQueryHash}
              onChange={(event) => setPopulationQueryHash(event.target.value)}
              placeholder="sha256 of the population definition"
              autoComplete="off"
            />
          </Field>

          <Field label="Member ids">
            <Textarea
              id="sample-members"
              value={memberIds}
              onChange={(event) => setMemberIds(event.target.value)}
              placeholder="id_1, id_2, id_3 … (space or comma separated)"
              rows={4}
            />
          </Field>

          <Field label="Criteria (optional)">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Checkbox
                  checked={rawMode}
                  onCheckedChange={(checked) => setRawMode(checked === true)}
                  aria-label="Use raw JSON for criteria"
                />
                <span>Use raw JSON</span>
              </div>

              {rawMode ? (
                <Textarea
                  id="sample-criteria-raw"
                  value={rawCriteria}
                  onChange={(event) => setRawCriteria(event.target.value)}
                  aria-label="Raw criteria JSON"
                  placeholder='{"sample": "video comments", "min_likes": 100}'
                  rows={4}
                />
              ) : (
                <div className="space-y-2 rounded-md border bg-muted/20 p-2">
                  {criteriaRows.length === 0 ? (
                    <p className="py-1 text-xs text-muted-foreground">
                      No criteria yet — pick an attribute below to start.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {criteriaRows.map((row) => {
                        const def = PREDEFINED_CRITERIA_KEYS_BY_KEY.get(row.key);
                        if (!def) return null;
                        return (
                          <div key={row.key} className="flex items-center gap-2">
                            <div className="min-w-0 flex-1 space-y-1">
                              <div className="flex items-baseline justify-between gap-2">
                                <span className="truncate text-xs font-medium">
                                  {def.label}
                                </span>
                                <code className="shrink-0 font-mono text-[10px] text-muted-foreground">
                                  {def.key}
                                </code>
                              </div>
                              <ValueInput
                                def={def}
                                row={row}
                                onChange={updateAttribute}
                              />
                            </div>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              aria-label={`Remove ${def.key}`}
                              onClick={() => removeAttribute(row.key)}
                            >
                              <X className="size-3.5" aria-hidden />
                            </Button>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  <div className="flex items-center gap-2">
                    <Combobox
                      items={availableKeys}
                      value={pendingKey}
                      onChange={(value) =>
                        setPendingKey(typeof value === "string" ? value : "")
                      }
                      placeholder="Add attribute…"
                      searchPlaceholder="Search attributes…"
                      emptyLabel="All attributes added"
                      className="h-7 text-xs"
                      contentClassName="w-64"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={
                        !pendingKey ||
                        criteriaRows.some((row) => row.key === pendingKey)
                      }
                      onClick={() => addAttribute(pendingKey)}
                    >
                      <Plus className="size-3.5" aria-hidden />
                      Add
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </Field>

          <DialogFooter showCloseButton>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                  Saving…
                </>
              ) : (
                <>
                  <Plus className="size-4" aria-hidden />
                  Save sample
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ValueInput({
  def,
  row,
  onChange,
}: {
  def: PredefinedCriteriaKey;
  row: CriteriaRow;
  onChange: (key: string, value: string) => void;
}) {
  if (def.type === "date") {
    return (
      <Input
        type="date"
        value={row.value}
        onChange={(event) => onChange(row.key, event.target.value)}
        aria-label={`${def.key} value`}
        autoComplete="off"
      />
    );
  }
  if (def.type === "number") {
    return (
      <Input
        type="number"
        value={row.value}
        onChange={(event) => onChange(row.key, event.target.value)}
        placeholder={def.placeholder}
        aria-label={`${def.key} value`}
        autoComplete="off"
      />
    );
  }
  if (def.type === "boolean") {
    return (
      <div className="flex h-8 items-center">
        <Checkbox
          checked={row.value === "true"}
          onCheckedChange={(checked) =>
            onChange(row.key, checked === true ? "true" : "false")
          }
          aria-label={`${def.label} (${def.key})`}
        />
      </div>
    );
  }
  if (def.type === "select") {
    return (
      <Select
        value={row.value}
        onValueChange={(value) => onChange(row.key, value ?? "")}
        items={def.options}
      >
        <SelectTrigger aria-label={`${def.key} value`} className="w-full">
          <SelectValue placeholder="Choose…" />
        </SelectTrigger>
        <SelectContent>
          {def.options?.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }
  return (
    <Input
      value={row.value}
      onChange={(event) => onChange(row.key, event.target.value)}
      placeholder={def.placeholder}
      aria-label={`${def.key} value`}
      autoComplete="off"
    />
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  );
}