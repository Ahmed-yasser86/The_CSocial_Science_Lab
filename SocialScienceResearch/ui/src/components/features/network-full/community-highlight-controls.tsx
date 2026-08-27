"use client";

import { communityColorFor } from "@/components/features/network-graph";
import type { CommunityEntity } from "@/lib/network-full-types";

interface CommunityHighlightControlsProps {
  communities: CommunityEntity[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

/** Compact community legend/selector. Clicking a community isolates it in the
 * graph (dims everything else); clicking again or "All" clears the highlight. */
export function CommunityHighlightControls({
  communities,
  selectedId,
  onSelect,
}: CommunityHighlightControlsProps) {
  if (communities.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Communities
      </span>
      <button
        type="button"
        onClick={() => onSelect(null)}
        className={`rounded-full border px-2.5 py-0.5 text-xs transition-colors ${
          selectedId === null
            ? "border-foreground/60 bg-foreground/10 text-foreground"
            : "border-border bg-transparent text-muted-foreground hover:border-foreground/40"
        }`}
      >
        All
      </button>
      {communities.map((c) => {
        const color = communityColorFor(c.community_id);
        const active = c.id === selectedId;
        return (
          <button
            key={c.id}
            type="button"
            onClick={() => onSelect(active ? null : c.id)}
            className={`flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs transition-colors ${
              active
                ? "border-foreground/60 bg-foreground/10 text-foreground"
                : "border-border bg-transparent text-muted-foreground hover:border-foreground/40"
            }`}
            title={`${c.label}: ${c.size} nodes`}
          >
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: color }}
            />
            {c.label}
            <span className="tabular-nums opacity-70">{c.size}</span>
          </button>
        );
      })}
    </div>
  );
}
