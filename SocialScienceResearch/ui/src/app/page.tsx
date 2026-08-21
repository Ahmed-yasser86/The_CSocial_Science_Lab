import type { Metadata } from "next";
import { ResearchDesk } from "@/components/features/research-desk";

export const metadata: Metadata = {
  title: "Research Workspace",
};

export default function Home() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">Research Workspace</h1>
        <p className="text-sm text-muted-foreground">
          Collect YouTube data, inspect provenance, sample reproducibly, and
          analyze recommendation networks — all in one research workbench.
        </p>
      </header>
      <ResearchDesk />
    </div>
  );
}
