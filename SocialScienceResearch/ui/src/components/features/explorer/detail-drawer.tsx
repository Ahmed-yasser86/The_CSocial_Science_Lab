"use client";

import Link from "next/link";
import { GitBranch } from "lucide-react";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerBody,
  DrawerFooter,
} from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useRawRecord } from "@/services/explorer";
import { ProvenancePanel } from "@/components/features/explorer/provenance-panel";
import { LoadingState, ErrorState, EmptyState } from "@/components/features/state";
import { columnValueClass, formatCellValue } from "@/components/features/explorer/paginated-data-table";
import type { ExplorerColumn } from "@/lib/explorer-types";

export function DetailDrawer({
  open,
  onOpenChange,
  entity,
  entityId,
  row,
  columns,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entity: string;
  entityId: string;
  row: Record<string, unknown>;
  columns: ExplorerColumn[];
}) {
  const has = (value: unknown) =>
    value !== undefined && value !== null && String(value) !== "";
  const threadHref =
    entity === "comment" && has(row.video_id) && has(row.comment_id)
      ? `/videos/${row.video_id}?tab=comments&thread=${row.comment_id}`
      : null;

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent side="right" className="w-full max-w-xl">
        <DrawerHeader>
          <DrawerTitle className="flex items-center gap-2 font-mono">
            {entityId}
            <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-normal text-muted-foreground">
              {entity}
            </span>
          </DrawerTitle>
          <DrawerDescription>
            Persisted record and its collection provenance chain.
          </DrawerDescription>
        </DrawerHeader>
        <DrawerBody>
          <Tabs defaultValue="row">
            <TabsList>
              <TabsTrigger value="row">Row</TabsTrigger>
              <TabsTrigger value="raw">Raw JSON</TabsTrigger>
              <TabsTrigger value="provenance">Provenance</TabsTrigger>
            </TabsList>

            <TabsContent value="row" className="mt-4">
              <dl className="grid grid-cols-1 gap-x-6 gap-y-1">
                {Object.entries(row).map(([name, value]) => {
                  const meta = columns.find((c) => c.name === name);
                  return (
                    <div
                      key={name}
                      className="flex items-baseline justify-between gap-3 border-b border-border/50 pb-1"
                    >
                      <dt className="text-xs text-muted-foreground">{name}</dt>
                      <dd className={columnValueClass(meta?.data_type ?? "string")}>
                        {formatCellValue(value, meta?.data_type ?? "string")}
                      </dd>
                    </div>
                  );
                })}
              </dl>
            </TabsContent>

            <TabsContent value="raw" className="mt-4">
              <RawJsonView entity={entity} entityId={entityId} />
            </TabsContent>

            <TabsContent value="provenance" className="mt-4">
              <ProvenancePanel entity={entity} entityId={entityId} />
            </TabsContent>
          </Tabs>
        </DrawerBody>
        {threadHref ? (
          <DrawerFooter>
            <Button
              render={<Link href={threadHref} />}
              nativeButton={false}
              variant="outline"
              size="sm"
            >
              <GitBranch className="size-3.5" aria-hidden />
              View reply tree
            </Button>
          </DrawerFooter>
        ) : null}
      </DrawerContent>
    </Drawer>
  );
}

function RawJsonView({ entity, entityId }: { entity: string; entityId: string }) {
  const query = useRawRecord(entity, entityId);

  if (query.isLoading) return <LoadingState label="Loading raw record…" />;
  if (query.isError)
    return (
      <ErrorState
        message={
          query.error instanceof Error
            ? query.error.message
            : "Failed to load raw record"
        }
        retry={() => query.refetch()}
      />
    );

  const raw = query.data?.raw_json;
  if (!raw) return <EmptyState title="No raw payload" description="No raw_json was stored for this record." />;

  return (
    <pre className="max-h-[50vh] overflow-auto rounded-md border bg-muted/30 p-3 text-xs">
      {JSON.stringify(raw, null, 2)}
    </pre>
  );
}
