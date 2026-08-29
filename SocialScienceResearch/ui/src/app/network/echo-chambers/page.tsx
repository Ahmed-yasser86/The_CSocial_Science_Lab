import type { Metadata } from "next";
import { Radio } from "@/components/ui/icon";
import { EchoChamberView } from "@/components/features/echo-chamber/echo-chamber-view";

export const metadata: Metadata = {
  title: "Echo Chambers",
};

export default function NetworkEchoChambersPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <Radio className="size-5 text-muted-foreground" aria-hidden />
          Echo chambers
        </h1>
        <p className="text-sm text-muted-foreground">
          Crawl recommendation layers around a seed video and read the observed
          structural signals: frontier collapse, community concentration,
          channel concentration and cross-layer repetition. Observed, never
          estimated.
        </p>
      </header>
      <EchoChamberView />
    </div>
  );
}

