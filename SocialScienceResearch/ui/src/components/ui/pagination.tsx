"use client"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Loader2 } from "lucide-react"

export interface PaginationProps {
  nextCursor?: string | null
  hasMore: boolean
  hasPrevious?: boolean
  onNext: () => void
  onPrev: () => void
  pageLabel: string
  loading?: boolean
  className?: string
}

export function Pagination({
  nextCursor,
  hasMore,
  hasPrevious = false,
  onNext,
  onPrev,
  pageLabel,
  loading = false,
  className,
}: PaginationProps) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 border-t bg-muted/20 px-4 py-3",
        className
      )}
    >
      <p className="text-xs text-muted-foreground">{pageLabel}</p>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onPrev}
          disabled={loading || !hasPrevious}
        >
          Previous
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onNext}
          disabled={loading || !hasMore || !nextCursor}
        >
          {loading ? (
            <>
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
              Loading…
            </>
          ) : (
            "Next"
          )}
        </Button>
      </div>
    </div>
  )
}
