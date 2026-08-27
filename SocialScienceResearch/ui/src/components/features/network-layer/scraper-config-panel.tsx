"use client";

import { useState } from "react";
import { Settings, ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  PRESETS,
  useApplyPreset,
  useScraperConfig,
  useUpdateScraperConfig,
} from "@/services/scraperConfig";
import { BudgetDashboard } from "@/components/features/network-layer/budget-dashboard";

function detectPreset(
  config: { request_delay_seconds: number; enrichment_concurrency: number } | undefined,
): string | null {
  if (!config) return null;
  for (const [key, preset] of Object.entries(PRESETS)) {
    if (
      config.request_delay_seconds === preset.request_delay_seconds &&
      config.enrichment_concurrency === preset.enrichment_concurrency
    ) {
      return key;
    }
  }
  return null;
}

export function ScraperConfigPanel() {
  const [open, setOpen] = useState(false);
  const configQuery = useScraperConfig();
  const updateMut = useUpdateScraperConfig();
  const presetMut = useApplyPreset();

  const config = configQuery.data;
  const activePreset = detectPreset(config);

  const [delay, setDelay] = useState<string>("");
  const [concurrency, setConcurrency] = useState<string>("");
  const [timeout, setTimeout_] = useState<string>("");

  function handleSave() {
    const body: Record<string, number> = {};
    if (delay !== "") body.request_delay_seconds = parseFloat(delay);
    if (concurrency !== "") body.enrichment_concurrency = parseInt(concurrency, 10);
    if (timeout !== "") body.socket_timeout = parseFloat(timeout);
    if (Object.keys(body).length === 0) return;
    updateMut.mutate(body, {
      onSuccess: () => {
        setDelay("");
        setConcurrency("");
        setTimeout_("");
      },
    });
  }

  return (
    <Card className="overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-2 p-3 text-left text-sm hover:bg-muted/50"
      >
        <div className="flex items-center gap-2">
          <Settings className="size-3.5 text-muted-foreground" aria-hidden />
          <span className="font-medium">Scrape Speed</span>
          {activePreset && (
            <Badge variant="secondary" className="text-[10px]">
              {PRESETS[activePreset].label}
            </Badge>
          )}
        </div>
        {open ? (
          <ChevronUp className="size-3.5 text-muted-foreground" />
        ) : (
          <ChevronDown className="size-3.5 text-muted-foreground" />
        )}
      </button>

      {open && (
        <div className="border-t px-3 pb-3 pt-3 space-y-3">
          {/* Presets */}
          <div className="space-y-1.5">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Presets
            </Label>
            <div className="grid grid-cols-3 gap-1.5">
              {Object.entries(PRESETS).map(([key, preset]) => (
                <button
                  key={key}
                  type="button"
                  disabled={presetMut.isPending}
                  onClick={() => presetMut.mutate(key)}
                  className={`rounded-md border px-2.5 py-1.5 text-left text-xs transition-colors ${
                    activePreset === key
                      ? "border-primary bg-primary/10 text-primary"
                      : "hover:bg-muted"
                  }`}
                >
                  <div className="font-medium">{preset.label}</div>
                  <div className="text-[10px] text-muted-foreground">
                    {preset.description}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Manual overrides */}
          <div className="space-y-1.5">
            <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Manual Override
            </Label>
            <div className="grid grid-cols-3 gap-2">
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">
                  Delay (s)
                </Label>
                <Input
                  type="number"
                  step="0.05"
                  min="0"
                  max="30"
                  placeholder={String(config?.request_delay_seconds ?? "?")}
                  value={delay}
                  onChange={(e) => setDelay(e.target.value)}
                  className="h-7 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">
                  Workers
                </Label>
                <Input
                  type="number"
                  step="1"
                  min="1"
                  max="20"
                  placeholder={String(config?.enrichment_concurrency ?? "?")}
                  value={concurrency}
                  onChange={(e) => setConcurrency(e.target.value)}
                  className="h-7 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">
                  Timeout (s)
                </Label>
                <Input
                  type="number"
                  step="5"
                  min="5"
                  max="120"
                  placeholder={String(config?.socket_timeout ?? "?")}
                  value={timeout}
                  onChange={(e) => setTimeout_(e.target.value)}
                  className="h-7 text-xs"
                />
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={handleSave}
              disabled={updateMut.isPending || (delay === "" && concurrency === "" && timeout === "")}
              className="mt-1 h-7 text-xs"
            >
              {updateMut.isPending ? (
                <Loader2 className="mr-1 size-3 animate-spin" />
              ) : null}
              Apply
            </Button>
          </div>

          {/* Current values */}
          {config && (
            <p className="text-[10px] text-muted-foreground">
              Current: {config.request_delay_seconds}s delay, {config.enrichment_concurrency} workers, {config.socket_timeout}s timeout
            </p>
          )}

          {/* Live budget telemetry (Phase 5) */}
          <BudgetDashboard />
        </div>
      )}
    </Card>
  );
}
