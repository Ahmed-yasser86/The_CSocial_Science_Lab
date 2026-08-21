import type { ValueWithAvailability } from "@/lib/types";
import { formatCompact, formatDateTime } from "@/lib/format";
import { Card } from "@/components/ui/card";
import { AvailabilityBadge } from "@/components/features/availability-badge";

export function MetricTile({
  label,
  value,
  observedAt,
  suffix,
}: {
  label: string;
  value?: ValueWithAvailability | null;
  observedAt?: string | null;
  suffix?: string;
}) {
  const display =
    !value || value.value === null
      ? "—"
      : `${formatCompact(value.value)}${suffix ? ` ${suffix}` : ""}`;

  return (
    <Card className="flex flex-col gap-2 p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        <AvailabilityBadge availability={value?.availability} withLabel={false} />
      </div>
      <p className="text-2xl font-semibold tabular-nums">{display}</p>
      {observedAt ? (
        <p className="text-xs text-muted-foreground">
          observed {formatDateTime(observedAt)}
        </p>
      ) : null}
    </Card>
  );
}
