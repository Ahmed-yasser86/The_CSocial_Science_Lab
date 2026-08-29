import type { Metadata } from "next";
import { MessageSquareShare } from "@/components/ui/icon";
import { CommenterOverlapView } from "@/components/features/commenters/commenter-overlap-view";

export const metadata: Metadata = {
  title: "Commenter Overlap",
};

export default function NetworkCommentersPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <MessageSquareShare className="size-5 text-muted-foreground" aria-hidden />
          Commenter overlap
        </h1>
        <p className="text-sm text-muted-foreground">
          Compare the audiences of videos and channels: shared commenters,
          Jaccard / overlap-coefficient similarity, bridge commenters and
          per-commenter activity profiles.
        </p>
      </header>
      <CommenterOverlapView />
    </div>
  );
}

