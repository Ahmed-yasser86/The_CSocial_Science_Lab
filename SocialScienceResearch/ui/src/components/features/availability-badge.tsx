import { CircleCheck, CircleMinus, CircleOff } from "lucide-react";
import type { Availability } from "@/lib/types";
import { availabilityDescription, availabilityLabel } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const ICONS: Record<Availability, React.ComponentType<{ className?: string }>> = {
  available: CircleCheck,
  missing: CircleMinus,
  unsupported: CircleOff,
};

export function AvailabilityBadge({
  availability,
  withLabel = true,
}: {
  availability?: Availability | null;
  withLabel?: boolean;
}) {
  const Icon = ICONS[availability ?? "unsupported"];
  const label = availability ?? "unsupported";
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Badge
            variant={
              label === "available"
                ? "default"
                : label === "missing"
                  ? "secondary"
                  : "outline"
            }
          />
        }
      >
        <Icon className="size-3" aria-hidden />
        {withLabel ? availabilityLabel[label] : null}
        <span className="sr-only">{availabilityLabel[label]}</span>
      </TooltipTrigger>
      <TooltipContent>{availabilityDescription[label]}</TooltipContent>
    </Tooltip>
  );
}
