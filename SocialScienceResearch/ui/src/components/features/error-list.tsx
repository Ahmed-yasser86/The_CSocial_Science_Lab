import { CircleAlert, RefreshCw } from "@/components/ui/icon";
import type { CollectionError } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import { Badge } from "@/components/ui/badge";

const RETRYABLE_HINTS: Record<string, string> = {
  network: "Transient network issue — retry the collection.",
  rate_limit: "The source rate-limited the request — wait and retry.",
  recommendation_unsupported:
    "All recommendation providers returned no data (library fields, the INNERTUBE /next endpoint, and watch-page dumps). Recorded as an explicit error, never fabricated.",
};

export function ErrorList({ errors }: { errors: CollectionError[] }) {
  if (errors.length === 0) return null;
  return (
    <ul className="space-y-2">
      {errors.map((error) => (
        <li
          key={error.error_id}
          className="flex items-start gap-2 rounded-md border border-border/60 bg-muted/40 p-2.5 text-sm"
        >
          <CircleAlert
            className="mt-0.5 size-4 shrink-0 text-destructive"
            aria-hidden
          />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{error.error_type}</Badge>
              {error.entity_id ? (
                <code className="text-xs text-muted-foreground">
                  {error.entity_type} {error.entity_id}
                </code>
              ) : (
                <span className="text-xs text-muted-foreground">
                  {error.entity_type}
                </span>
              )}
              {error.retryable ? (
                <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <RefreshCw className="size-3" aria-hidden />
                  retryable
                </span>
              ) : null}
              {error.occurred_at ? (
                <span className="ml-auto text-xs text-muted-foreground">
                  {formatDateTime(error.occurred_at)}
                </span>
              ) : null}
            </div>
            <p className="mt-1 break-words">{error.message}</p>
            {RETRYABLE_HINTS[error.error_type] ? (
              <p className="mt-1 text-xs text-muted-foreground">
                {RETRYABLE_HINTS[error.error_type]}
              </p>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

