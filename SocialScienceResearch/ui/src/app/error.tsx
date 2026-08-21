"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 rounded-xl border bg-card p-8 text-center text-card-foreground">
      <span className="flex size-10 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <AlertTriangle className="size-5" aria-hidden />
      </span>
      <div className="space-y-1">
        <h1 className="font-heading text-lg font-medium">
          Something went wrong
        </h1>
        <p className="max-w-md text-sm text-muted-foreground">
          {error.message || "An unexpected error occurred while rendering this page."}
        </p>
        {error.digest ? (
          <p className="text-xs text-muted-foreground">Digest: {error.digest}</p>
        ) : null}
      </div>
      <Button type="button" variant="outline" size="sm" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
