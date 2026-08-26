import type { CollectionStatus } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

const STATUS_META: Record<
  CollectionStatus | "cancelled" | "interrupted",
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" | "ghost" }
> = {
  pending: { label: "Pending", variant: "ghost" },
  running: { label: "Running", variant: "secondary" },
  success: { label: "Success", variant: "default" },
  partial: { label: "Partial", variant: "outline" },
  failed: { label: "Failed", variant: "destructive" },
  cancelled: { label: "Cancelled", variant: "outline" },
  interrupted: { label: "Interrupted", variant: "destructive" },
};

export function RunStatusBadge({ status }: { status: CollectionStatus | string }) {
  const meta =
    STATUS_META[status as CollectionStatus | "cancelled" | "interrupted"] ??
    STATUS_META.pending;
  return (
    <Badge variant={meta.variant}>
      <span
        aria-hidden
        className="inline-flex size-1.5 rounded-full bg-current"
      />
      {meta.label}
      <span className="sr-only">{meta.label}</span>
    </Badge>
  );
}
