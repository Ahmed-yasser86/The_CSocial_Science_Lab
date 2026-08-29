"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { ReportVal } from "../lib/logSchema";

export function ReportCard({ kind, report }: { kind: string; report: ReportVal }) {
  const [open, setOpen] = useState(false);
  const content = typeof report.content === "string" ? report.content : "";
  const sourceCount = Array.isArray(report.sources) ? report.sources.length : 0;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-2">
        <CardTitle className="text-sm capitalize">{kind} intelligence</CardTitle>
        <Badge variant="outline">{sourceCount} sources</Badge>
      </CardHeader>
      <CardContent className="space-y-2 text-xs text-muted-foreground">
        <div className="flex gap-3">
          <span>{content.length.toLocaleString()} chars</span>
          {typeof report.costs === "number" && (
            <span>cost ${report.costs.toFixed(4)}</span>
          )}
        </div>
        {content && (
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            onClick={() => setOpen((o) => !o)}
          >
            {open ? "Hide" : "Preview"}
          </Button>
        )}
        {open && (
          <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-muted/40 p-2 text-[11px]">
            {content.slice(0, 1400)}
          </pre>
        )}
      </CardContent>
    </Card>
  );
}
