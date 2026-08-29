import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight } from "@/components/ui/icon";
import { CommenterProfileView } from "@/components/features/commenters/commenter-profile-view";

export const metadata: Metadata = {
  title: "Commenter Profile",
};

export default async function NetworkCommenterProfilePage({
  params,
}: {
  params: Promise<{ authorKey: string }>;
}) {
  const { authorKey } = await params;
  return (
    <div className="space-y-4">
      <nav
        aria-label="Breadcrumb"
        className="flex items-center gap-1 text-xs text-muted-foreground"
      >
        <Link href="/network" className="underline-offset-2 hover:underline">
          Network
        </Link>
        <ChevronRight className="size-3" aria-hidden />
        <Link
          href="/network/commenters"
          className="underline-offset-2 hover:underline"
        >
          Commenters
        </Link>
        <ChevronRight className="size-3" aria-hidden />
        <span className="truncate">{authorKey}</span>
      </nav>
      <CommenterProfileView authorKey={authorKey} />
    </div>
  );
}

