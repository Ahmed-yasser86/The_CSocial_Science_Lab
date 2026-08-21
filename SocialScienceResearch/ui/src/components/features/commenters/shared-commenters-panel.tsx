"use client";

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/features/state";
import type {
  BridgeCommenter,
  TopSharedCommenter,
} from "@/lib/commenter-overlap-types";

function CommenterRow({
  author_key,
  author_name,
  identity_kind,
  primary,
  secondary,
  detail,
}: {
  author_key: string;
  author_name?: string | null;
  identity_kind: "id" | "name";
  primary: string;
  secondary?: string;
  detail?: React.ReactNode;
}) {
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
      <Link
        href={`/network/commenters/${encodeURIComponent(author_key)}`}
        className="font-medium underline underline-offset-2 hover:text-foreground"
      >
        {author_name ?? author_key}
      </Link>
      <span className="text-xs text-muted-foreground">{author_key}</span>
      <Badge variant="outline" className="text-[10px]">
        {identity_kind === "id" ? "id-backed" : "name-only"}
      </Badge>
      <span className="text-xs tabular-nums text-muted-foreground">{primary}</span>
      {secondary ? (
        <span className="text-xs tabular-nums text-muted-foreground">{secondary}</span>
      ) : null}
      {detail ? <span className="ml-auto">{detail}</span> : null}
    </li>
  );
}

export function BridgeCommentersPanel({
  commenters,
  limit = 25,
}: {
  commenters: BridgeCommenter[];
  limit?: number;
}) {
  const rows = commenters.slice(0, limit);
  return (
    <Card className="p-4">
      <h4 className="mb-2 text-sm font-medium">
        Bridge commenters{" "}
        <span className="font-normal text-muted-foreground">
          ({commenters.length})
        </span>
      </h4>
      {rows.length ? (
        <ul className="divide-y divide-border">
          {rows.map((commenter) => (
            <CommenterRow
              key={commenter.author_key}
              author_key={commenter.author_key}
              author_name={commenter.author_name}
              identity_kind={commenter.identity_kind}
              primary={`${commenter.entity_count} entities · ${commenter.comment_count} comments`}
              secondary={`${commenter.video_count} videos · ${commenter.channel_count} channels`}
              detail={
                <span className="text-xs tabular-nums text-muted-foreground">
                  {commenter.entities.length
                    ? commenter.entities
                        .slice(0, 4)
                        .map((e) => e.entity_id.slice(0, 8))
                        .join(", ")
                    : ""}
                </span>
              }
            />
          ))}
        </ul>
      ) : (
        <EmptyState title="No bridge commenters" />
      )}
    </Card>
  );
}

export function TopSharedCommentersPanel({
  commenters,
}: {
  commenters: TopSharedCommenter[];
}) {
  return (
    <Card className="p-4">
      <h4 className="mb-2 text-sm font-medium">
        Top shared commenters{" "}
        <span className="font-normal text-muted-foreground">
          ({commenters.length})
        </span>
      </h4>
      {commenters.length ? (
        <ul className="divide-y divide-border">
          {commenters.map((commenter) => (
            <CommenterRow
              key={commenter.author_key}
              author_key={commenter.author_key}
              author_name={commenter.author_name}
              identity_kind={commenter.identity_kind}
              primary={`${commenter.entity_count} entities · ${commenter.comment_count} comments`}
              secondary={`${commenter.video_count} videos · ${commenter.channel_count} channels`}
            />
          ))}
        </ul>
      ) : (
        <EmptyState title="No shared commenters" />
      )}
    </Card>
  );
}
