import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { EgoNetworkView } from "@/components/features/ego-network-view";
import { getVideoMeta } from "@/services/server-data";

export default async function NetworkVideoPage({
  params,
}: {
  params: Promise<{ videoId: string }>;
}) {
  const { videoId } = await params;
  const title = (await getVideoMeta(videoId)) ?? videoId;
  return (
    <div className="space-y-4">
      <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-xs text-muted-foreground">
        <Link href="/network" className="underline-offset-2 hover:underline">
          Network
        </Link>
        <ChevronRight className="size-3" aria-hidden />
        <span className="truncate">{title}</span>
      </nav>
      <EgoNetworkView videoId={videoId} />
    </div>
  );
}
