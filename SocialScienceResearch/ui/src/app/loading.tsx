import { Loader2 } from "lucide-react";

export default function Loading() {
  return (
    <div
      className="flex min-h-40 flex-col items-center justify-center gap-3 text-muted-foreground"
      role="status"
      aria-live="polite"
    >
      <Loader2 className="size-5 animate-spin" aria-hidden />
      <p className="text-sm">Loading…</p>
    </div>
  );
}
