"use client";

import { useState } from "react";
import { Trash2, Users } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getSample } from "@/services/samples";
import { EmptyState, LoadingState } from "@/components/features/state";
import { formatDateTime } from "@/lib/format";
import type { Sample } from "@/lib/sample-types";

export function SampleCard({
  sample,
  onDelete,
}: {
  sample: Sample;
  onDelete?: (sampleId: string) => void;
}) {
  const [membersOpen, setMembersOpen] = useState(false);
  const [members, setMembers] = useState<string[] | null>(null);
  const [membersLoading, setMembersLoading] = useState(false);

  async function openMembers() {
    setMembersOpen(true);
    setMembersLoading(true);
    try {
      const full = await getSample(sample.sample_id);
      setMembers(full.member_ids ?? []);
    } finally {
      setMembersLoading(false);
    }
  }

  return (
    <>
      <Card className="flex flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-0.5">
            <p className="text-sm font-medium">{sample.sample_id}</p>
            <div className="flex flex-wrap gap-1">
              <Badge variant="outline">{sample.entity_type}</Badge>
              <Badge variant="secondary">{sample.strategy}</Badge>
            </div>
          </div>
          {onDelete ? (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={`Delete sample ${sample.sample_id}`}
              onClick={() => onDelete(sample.sample_id)}
            >
              <Trash2 className="size-4" aria-hidden />
            </Button>
          ) : null}
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <Stat label="Population" value={sample.population_size.toLocaleString()} />
          <Stat label="Sample size" value={sample.sample_size.toLocaleString()} />
          <Stat label="Seed" value={sample.seed === null ? "—" : String(sample.seed)} />
          <Stat label="Overflow" value={sample.overflow ? "chunked" : "single"} />
        </dl>

        {sample.criteria_json && Object.keys(sample.criteria_json).length > 0 ? (
          <div className="rounded-md border bg-muted/20 p-2">
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Criteria
            </p>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
              {Object.entries(sample.criteria_json).map(([key, value]) => (
                <div
                  key={key}
                  className="flex min-w-0 items-baseline justify-between gap-2"
                >
                  <dt className="shrink-0 font-mono text-[11px] text-muted-foreground">
                    {key}
                  </dt>
                  <dd className="truncate font-mono text-xs" title={formatCriteriaValue(value)}>
                    {formatCriteriaValue(value)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}

        <div className="mt-auto flex items-center justify-between gap-2 border-t pt-2">
          <span className="text-xs text-muted-foreground">
            created {formatDateTime(sample.created_at)}
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void openMembers()}
          >
            <Users className="size-3.5" aria-hidden />
            Members
          </Button>
        </div>
      </Card>

      <Dialog open={membersOpen} onOpenChange={setMembersOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle className="font-mono">{sample.sample_id}</DialogTitle>
            <DialogDescription>
              Ordered member ids of the sample ({sample.sample_size.toLocaleString()}).
            </DialogDescription>
          </DialogHeader>
          {membersLoading ? (
            <LoadingState label="Loading members…" />
          ) : members && members.length > 0 ? (
            <div className="max-h-80 overflow-auto rounded-md border">
              <Table aria-label="Sample members">
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>Member id</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {members.map((member, index) => (
                    <TableRow key={member}>
                      <TableCell className="text-right tabular-nums text-muted-foreground">
                        {index + 1}
                      </TableCell>
                      <TableCell className="font-mono text-xs">{member}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <EmptyState
              title="No members"
              description="This sample has no member rows."
            />
          )}
          <DialogFooter showCloseButton />
        </DialogContent>
      </Dialog>
    </>
  );
}

function formatCriteriaValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-border/50 pb-1">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  );
}
