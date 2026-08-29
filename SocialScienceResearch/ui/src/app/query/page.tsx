import type { Metadata } from "next";
import Link from "next/link";
import { SlidersHorizontal } from "@/components/ui/icon";
import type { QueryGroup } from "@/lib/types";
import { QueryWorkspace } from "@/components/features/query-workspace";
import { buttonVariants } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Query Builder · Social Science Research",
};

function deserializeRoot(raw: string | null | undefined): QueryGroup | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as QueryGroup;
    if (
      parsed &&
      typeof parsed === "object" &&
      "operator" in parsed &&
      "conditions" in parsed
    ) {
      return parsed;
    }
  } catch {
    // malformed URL payload → fall back to empty builder
  }
  return null;
}

export default async function QueryPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const rawEntity = Array.isArray(params.entity) ? params.entity[0] : params.entity;
  const rawRoot = Array.isArray(params.root) ? params.root[0] : params.root;
  const initialEntity = (
    ["video", "comment", "channel", "recommendation", "author"] as string[]
  ).includes(rawEntity ?? "")
    ? (rawEntity as "video")
    : "video";

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-lg font-medium">
            <SlidersHorizontal className="size-4 text-muted-foreground" aria-hidden />
            Query Builder
          </h1>
          <p className="text-sm text-muted-foreground">
            Define a research population with a condition funnel. Rank operators
            work against the current corpus; only observed values match.
          </p>
        </div>
        <Link
          href="/data"
          className={buttonVariants({ variant: "outline", size: "sm" })}
        >
          Browse data
        </Link>
      </header>

      <QueryWorkspace
        initialEntity={initialEntity}
        initialRoot={deserializeRoot(rawRoot)}
      />
    </div>
  );
}
