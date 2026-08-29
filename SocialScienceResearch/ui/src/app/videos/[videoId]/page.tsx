import Link from "next/link";
import { ChevronRight } from "@/components/ui/icon";
import { VideoWorkspace } from "@/components/features/video-workspace";
import { getVideoMeta } from "@/services/server-data";

const TABS = ["overview", "engagement", "comments", "recommendations"] as const;

export default async function VideoPage({
  params,
  searchParams,
}: {
  params: Promise<{ videoId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { videoId } = await params;
  const sp = await searchParams;
  const rawTab = typeof sp.tab === "string" ? sp.tab : "overview";
  const tab = (TABS as readonly string[]).includes(rawTab) ? rawTab : "overview";
  const title = (await getVideoMeta(videoId)) ?? videoId;

  return (
    <div className="space-y-4">
      <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-xs text-muted-foreground">
        <Link href="/" className="underline-offset-2 hover:underline">
          Workspace
        </Link>
        <ChevronRight className="size-3" aria-hidden />
        <span className="truncate">{title}</span>
      </nav>
      <VideoWorkspace videoId={videoId} initialTab={tab as "overview" | "engagement" | "comments" | "recommendations"} />
    </div>
  );
}

