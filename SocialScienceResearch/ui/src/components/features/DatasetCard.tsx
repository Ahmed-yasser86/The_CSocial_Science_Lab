"use client";

import { useState } from "react";
import { Trash2, Users, FolderPlus } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState, LoadingState } from "@/components/features/state";
import { useToast } from "@/components/ui/toast";
import { formatDateTime } from "@/lib/format";
import { getDataset, getDatasetMembers } from "@/services/datasets";
import type { Dataset } from "@/lib/dataset-types";
import type { Paginated } from "@/lib/types";

export function DatasetCard({
  dataset,
  onDelete,
  onAddToProject,
}: {
  dataset: Dataset;
  onDelete?: () => void;
  onAddToProject?: () => void;
}) {
  const [membersOpen, setMembersOpen] = useState(false);

  return (
    <>
      <Card className="flex flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium truncate">{dataset.name}</p>
            {dataset.description && (
              <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                {dataset.description}
              </p>
            )}
          </div>
          {onDelete && (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={`Delete dataset ${dataset.name}`}
              onClick={onDelete}
            >
              <Trash2 className="size-4" aria-hidden />
            </Button>
          )}
        </div>

        <div className="flex flex-wrap gap-1">
          <Badge variant="outline">{dataset.entity_type}</Badge>
          <Badge variant="secondary">
            {dataset.member_count.toLocaleString()} members
          </Badge>
          {dataset.source_samples && dataset.source_samples.length > 0 && (
            <Badge variant="outline">
              {dataset.source_samples.length} source samples
            </Badge>
          )}
        </div>

        {dataset.labels && Object.keys(dataset.labels).length > 0 && (
          <div className="flex flex-wrap gap-1">
            {Object.entries(dataset.labels).map(([category, categoryLabels]) =>
              Object.entries(
                (categoryLabels || {}) as Record<string, string>
              ).map(([key, value]) => (
                <Badge key={`${category}-${key}`} variant="secondary" className="text-[10px]">
                  {key}: {value}
                </Badge>
              ))
            )}
          </div>
        )}

        <div className="mt-auto flex items-center justify-between gap-2 border-t pt-2">
          <span className="text-xs text-muted-foreground">
            created {formatDateTime(dataset.created_at)}
          </span>
          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setMembersOpen(true)}
            >
              <Users className="size-3.5" aria-hidden />
              Members
            </Button>
            {onAddToProject && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onAddToProject}
              >
                <FolderPlus className="size-3.5" aria-hidden />
                Add to project
              </Button>
            )}
          </div>
        </div>
      </Card>

      <MembersDialog
        datasetId={dataset.dataset_id}
        datasetName={dataset.name}
        open={membersOpen}
        onOpenChange={setMembersOpen}
      />
    </>
  );
}

function MembersDialog({
  datasetId,
  datasetName,
  open,
  onOpenChange,
}: {
  datasetId: string;
  datasetName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { toast } = useToast();
  const [members, setMembers] = useState<Record<string, unknown>[] | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadMembers() {
    setLoading(true);
    try {
      await getDataset(datasetId);
      const allMembers: Record<string, unknown>[] = [];
      let cursor: string | undefined = undefined;

      do {
        const page: Paginated<Record<string, unknown>> = await getDatasetMembers(datasetId, cursor);
        allMembers.push(...page.items);
        cursor = page.next_cursor ?? undefined;
      } while (cursor);

      setMembers(allMembers);
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Failed to load members",
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setLoading(false);
    }
  }

  if (open && !members && !loading) {
    void loadMembers();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-mono">{datasetName}</DialogTitle>
          <DialogDescription>
            {members
              ? `${members.length.toLocaleString()} members`
              : "Loading members…"}
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <LoadingState label="Loading members…" />
        ) : members && members.length > 0 ? (
          <div className="max-h-96 overflow-y-auto rounded-md border">
            <Table aria-label="Dataset members">
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>Member id</TableHead>
                  <TableHead>Data</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((member, index) => {
                  const idKey = Object.keys(member).find((k) =>
                    ["id", "_id", "video_id", "comment_id", "channel_id"].includes(k)
                  );
                  const idValue = idKey ? String(member[idKey]) : `row-${index}`;

                  return (
                    <TableRow key={idValue}>
                      <TableCell className="text-right tabular-nums text-muted-foreground w-12">
                        {index + 1}
                      </TableCell>
                      <TableCell className="font-mono text-xs w-48">
                        {idValue}
                      </TableCell>
                      <TableCell className="font-mono text-xs max-w-xs truncate">
                        {JSON.stringify(member)}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        ) : (
          <EmptyState
            title="No members"
            description="This dataset has no member rows."
          />
        )}
      </DialogContent>
    </Dialog>
  );
}