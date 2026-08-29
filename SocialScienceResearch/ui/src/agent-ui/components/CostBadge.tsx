"use client";

import { Coins } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function CostBadge({ tokens }: { tokens: number }) {
  return (
    <Badge variant="secondary" className="gap-1">
      <Coins className="size-3.5" />
      {tokens.toLocaleString()} tokens
    </Badge>
  );
}
