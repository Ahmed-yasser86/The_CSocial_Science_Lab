"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { postNetworkTestDifference } from "@/services/networkFull";
import type {
  TestDifferenceRequest,
  TestDifferenceResult,
  TestDifferenceScope,
} from "@/lib/network-full-types";

const METRICS = [
  "centrality:degree",
  "centrality:closeness",
  "centrality:eigenvector",
  "centrality:betweenness",
  "centrality:pagerank",
  "centrality:harmonic",
  "centrality:constraint",
  "centrality:effective_size",
  "centrality:bridging",
  "centrality:clustering",
  "avg_clustering",
  "transitivity",
  "density",
  "modularity",
  "assortativity",
];

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border p-3">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 font-mono text-lg">{value}</div>
    </div>
  );
}

/** N4b — statistical comparison (permutation/bootstrap) between two network
 * slices, rendered as side-by-side metric cards with delta, p-value and CI. */
export function StatisticalTestPanel({ runId }: { runId?: string | null }) {
  const [family, setFamily] = useState<"recommendation" | "commenter">(
    "recommendation",
  );
  const [metric, setMetric] = useState<string>("centrality:betweenness");
  const [method, setMethod] = useState<"permutation" | "bootstrap">(
    "permutation",
  );
  const [nIter, setNIter] = useState<number>(200);
  const [scopeA, setScopeA] = useState<string>(runId ?? "");
  const [scopeB, setScopeB] = useState<string>(runId ?? "");

  const mutation = useMutation<TestDifferenceResult, Error, TestDifferenceRequest>({
    mutationFn: (body) => postNetworkTestDifference(body),
  });

  const buildScope = (text: string): TestDifferenceScope => {
    if (family === "commenter") {
      const ids = text
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      return { video_ids: ids, projection: "commenter" };
    }
    return text.trim() ? { run_id: text.trim(), projection: "video" } : { projection: "video" };
  };

  const run = () => {
    mutation.mutate({
      family,
      scope_a: buildScope(scopeA),
      scope_b: buildScope(scopeB),
      metric,
      method,
      n_iter: nIter,
      seed: 42,
    });
  };

  const result = mutation.data;
  const scopeLabel =
    family === "commenter" ? "video IDs (comma-separated)" : "run id";

  return (
    <Card className="space-y-4 p-4">
      <div>
        <h3 className="text-sm font-semibold">Statistical comparison (N4b)</h3>
        <p className="text-xs text-muted-foreground">
          Permutation/bootstrap test for a difference in means between two
          network slices. Node-level metrics return a p-value; global-only
          metrics (modularity, assortativity) report the observed delta only.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-1">
          <Label className="text-xs">Family</Label>
          <Select
            value={family}
            onValueChange={(v) => setFamily(v as "recommendation" | "commenter")}
          >
            <SelectTrigger aria-label="Comparison family">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="recommendation">Recommendation</SelectItem>
              <SelectItem value="commenter">Audience</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Metric</Label>
          <Select value={metric} onValueChange={(v) => setMetric(v ?? "")}>
            <SelectTrigger aria-label="Comparison metric">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {METRICS.map((m) => (
                <SelectItem key={m} value={m}>
                  {m}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Method</Label>
          <Select
            value={method}
            onValueChange={(v) => setMethod(v as "permutation" | "bootstrap")}
          >
            <SelectTrigger aria-label="Resampling method">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="permutation">Permutation</SelectItem>
              <SelectItem value="bootstrap">Bootstrap</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Iterations (≤1000)</Label>
          <Input
            type="number"
            min={1}
            max={1000}
            value={nIter}
            onChange={(e) => setNIter(Number(e.target.value))}
            aria-label="Resampling iterations"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label className="text-xs">Scope A {scopeLabel}</Label>
          <Input
            value={scopeA}
            onChange={(e) => setScopeA(e.target.value)}
            placeholder={family === "commenter" ? "v1,v2" : "run id"}
            aria-label="Scope A"
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Scope B {scopeLabel}</Label>
          <Input
            value={scopeB}
            onChange={(e) => setScopeB(e.target.value)}
            placeholder={family === "commenter" ? "v1,v2" : "run id"}
            aria-label="Scope B"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button onClick={run} disabled={mutation.isPending}>
          {mutation.isPending ? "Running…" : "Run test"}
        </Button>
        {mutation.isError ? (
          <span className="text-xs text-destructive">
            {mutation.error.message}
          </span>
        ) : null}
      </div>

      {result ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <Stat
              label={`Scope A (${result.n_nodes_a})`}
              value={result.statistic_a == null ? "—" : result.statistic_a.toFixed(4)}
            />
            <Stat
              label={`Scope B (${result.n_nodes_b})`}
              value={result.statistic_b == null ? "—" : result.statistic_b.toFixed(4)}
            />
            <Stat
              label="Δ (A−B)"
              value={result.observed_delta == null ? "—" : result.observed_delta.toFixed(4)}
            />
            <Stat
              label="p-value"
              value={result.p_value == null ? "n/a" : result.p_value.toFixed(4)}
            />
            <Stat
              label="95% CI"
              value={
                result.ci95
                  ? `[${result.ci95[0].toFixed(3)}, ${result.ci95[1].toFixed(3)}]`
                  : "n/a"
              }
            />
          </div>
          {result.p_value != null ? (
            <p className="text-xs text-muted-foreground">
              {result.p_value < 0.05
                ? "Significant at α=0.05 (seeded, reproducible)."
                : "Not significant at α=0.05."}{" "}
              Method {result.method}, seed {result.seed}, n_iter {result.n_iter}.
            </p>
          ) : null}
          {result.note ? (
            <p className="text-xs text-muted-foreground">{result.note}</p>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
