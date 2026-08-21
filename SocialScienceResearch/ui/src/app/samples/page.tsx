"use client";

import { useState } from "react";
import { FlaskConical, Library, SlidersHorizontal } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SamplingWorkbench } from "@/components/features/sampling/SamplingWorkbench";
import { SampleLibrary } from "@/components/features/samples/sample-library";

export default function SamplesPage() {
  const [activeView, setActiveView] = useState<"workbench" | "library">("workbench");

  return (
    <div className="flex h-[calc(100vh-12rem)] flex-col space-y-6">
      <header className="flex-shrink-0 space-y-5">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <FlaskConical className="size-5" aria-hidden />
            </span>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">Research Samples</h1>
              <p className="max-w-2xl text-sm text-muted-foreground">
                Design reproducible samples from your YouTube corpus, record their exact
                criteria and membership, and compare overlap across runs.
              </p>
            </div>
          </div>
        </div>

        <Tabs
          value={activeView}
          onValueChange={(value) => setActiveView(value as "workbench" | "library")}
        >
          <TabsList variant="line">
            <TabsTrigger value="workbench">
              <SlidersHorizontal className="size-4" aria-hidden />
              Sampling Workbench
            </TabsTrigger>
            <TabsTrigger value="library">
              <Library className="size-4" aria-hidden />
              Sample Library
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </header>

      <div className="flex-1 overflow-hidden">
        {activeView === "workbench" ? (
          <SamplingWorkbench entityType="comment" />
        ) : (
          <SampleLibrary />
        )}
      </div>
    </div>
  );
}