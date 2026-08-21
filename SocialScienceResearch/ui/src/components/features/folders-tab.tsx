"use client";

import { useState } from "react";
import { Folder, Copy, Check, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, ErrorState } from "@/components/features/state";
import { useSystemFolders } from "@/services/queries";
import { useToast } from "@/components/ui/toast";
import type { SystemFolders } from "@/lib/types";

type FolderItem = {
  key: keyof SystemFolders;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
};

const FOLDER_ITEMS: FolderItem[] = [
  {
    key: "workbook_path",
    label: "Workbook",
    icon: Folder,
    description: "Research workbook directory",
  },
  {
    key: "transcripts_dir",
    label: "Transcripts",
    icon: FileText,
    description: "Video transcript files",
  },
  {
    key: "datasets_dir",
    label: "Datasets",
    icon: Folder,
    description: "Exported dataset files",
  },
  {
    key: "samples_dir",
    label: "Samples",
    icon: Folder,
    description: "Sampling output directories",
  },
  {
    key: "data_dir",
    label: "Data",
    icon: Folder,
    description: "Root data directory",
  },
];

export function FoldersTab() {
  const { toast } = useToast();
  const query = useSystemFolders();
  const [copiedKey, setCopiedKey] = useState<keyof SystemFolders | null>(null);

  async function copyToClipboard(path: string, key: keyof SystemFolders) {
    try {
      await navigator.clipboard.writeText(path);
      setCopiedKey(key);
      toast({ title: "Copied", description: `${String(key)} path copied to clipboard` });
      setTimeout(() => setCopiedKey(null), 2000);
    } catch {
      toast({
        title: "Failed to copy",
        description: "Could not copy to clipboard",
        variant: "destructive",
      });
    }
  }

  if (query.isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FOLDER_ITEMS.map((item) => (
          <Card key={item.key} className="animate-pulse">
            <CardContent className="pt-6">
              <div className="space-y-2">
                <div className="h-8 w-1/3 bg-muted rounded" />
                <div className="h-4 w-full bg-muted rounded" />
                <div className="h-4 w-3/4 bg-muted rounded" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (query.isError) {
    return (
      <ErrorState
        message="Failed to load system folders"
        detail={query.error instanceof Error ? query.error.message : String(query.error)}
        retry={() => query.refetch()}
      />
    );
  }

  const folders = query.data as SystemFolders | undefined;

  if (!folders) {
    return <EmptyState title="No folder data" description="System folders information is unavailable." />;
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {FOLDER_ITEMS.map((item) => {
        const path = folders[item.key];
        return (
          <Card key={item.key}>
            <CardContent className="pt-6">
              <div className="flex items-start gap-3">
                <div className="shrink-0 mt-0.5">
                  <item.icon className="size-5 text-muted-foreground" aria-hidden />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {item.label}
                  </p>
                  <p className="text-xs text-muted-foreground">{item.description}</p>
                  <div className="mt-2 flex items-center gap-2">
                    <code className="flex-1 text-xs font-mono bg-muted px-2 py-1 rounded truncate block">
                      {path}
                    </code>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => copyToClipboard(path, item.key)}
                      disabled={copiedKey === item.key}
                      aria-label={`Copy ${item.label} path`}
                    >
                      {copiedKey === item.key ? (
                        <Check className="size-4 text-emerald-500" aria-hidden />
                      ) : (
                        <Copy className="size-4" aria-hidden />
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}