"use client";

import { AlertTriangle } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="min-h-full flex flex-col bg-background text-foreground antialiased">
        <main className="flex flex-1 items-center justify-center p-6">
          <div className="flex w-full max-w-md flex-col items-center gap-4 rounded-xl border bg-card p-8 text-center text-card-foreground">
            <span className="flex size-10 items-center justify-center rounded-full bg-destructive/10 text-destructive">
              <AlertTriangle className="size-5" aria-hidden />
            </span>
            <div className="space-y-1">
              <h1 className="text-lg font-semibold tracking-tight">
                Application error
              </h1>
              <p className="text-sm text-muted-foreground">
                {error.message || "A critical error prevented the app from loading."}
              </p>
              {error.digest ? (
                <p className="text-xs text-muted-foreground">Digest: {error.digest}</p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => reset()}
              className="inline-flex h-7 items-center justify-center rounded-lg border border-border bg-background px-2.5 text-sm font-medium transition-colors outline-none hover:bg-muted hover:text-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              Try again
            </button>
          </div>
        </main>
      </body>
    </html>
  );
}
