"use client";

import { Search } from "lucide-react";
import type { LogEvent } from "../lib/logSchema";

export function SourcesList({ events }: { events: LogEvent[] }) {
  const items = events.filter(
    (e) =>
      (e.type === "retriever" && e.action === "start") ||
      (e.type === "tool_call" && /search|tavily|scrape|gdelt|socialcrawl/i.test(e.tool ?? "")),
  );

  if (items.length === 0) {
    return <p className="text-xs text-muted-foreground">No retrievals yet.</p>;
  }

  const recent = items.slice(-14).reverse();

  return (
    <ul className="space-y-1 text-xs">
      {recent.map((e, i) => {
        const ev = e as {
          type: string;
          tool?: string;
          query?: string;
          input?: unknown;
        };
        return (
          <li key={i} className="flex gap-2 text-muted-foreground">
            <Search className="mt-0.5 size-3 shrink-0" />
            <span className="truncate">
              {ev.type === "retriever"
                ? ev.query ?? ev.tool
                : `${ev.tool}: ${typeof ev.input === "string" ? ev.input : ""}`}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
