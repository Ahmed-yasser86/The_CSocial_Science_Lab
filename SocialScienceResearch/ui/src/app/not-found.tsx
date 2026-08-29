import Link from "next/link";
import { Compass } from "@/components/ui/icon";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 rounded-xl border bg-card p-8 text-center text-card-foreground">
      <span className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Compass className="size-5" aria-hidden />
      </span>
      <div className="space-y-1">
        <h1 className="font-heading text-lg font-medium">Page not found</h1>
        <p className="max-w-md text-sm text-muted-foreground">
          The page you are looking for does not exist or has been moved.
        </p>
      </div>
      <Button render={<Link href="/" />} nativeButton={false} variant="outline" size="sm">
        Back to workspace
      </Button>
    </div>
  );
}

