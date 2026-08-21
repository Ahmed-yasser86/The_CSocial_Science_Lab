import type { Metadata } from "next";
import { RunLedger } from "@/components/features/run-ledger";

export const metadata: Metadata = {
  title: "Runs",
};

export default function RunsPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">Provenance ledger</h1>
        <p className="text-sm text-muted-foreground">
          Every collection run is recorded here — what was collected, when, from
          which source, how many entities succeeded or failed, and which
          configuration produced it.
        </p>
      </header>
      <RunLedger />
    </div>
  );
}
