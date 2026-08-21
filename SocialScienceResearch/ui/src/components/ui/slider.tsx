"use client"

import * as React from "react"
import { Slider as SliderPrimitive } from "@base-ui/react/slider"

import { cn } from "@/lib/utils"

type SliderProps = SliderPrimitive.Root.Props & {
  orientation?: "horizontal" | "vertical"
}

function Slider({ className, orientation = "horizontal", ...props }: SliderProps) {
  const horizontal = orientation === "horizontal"
  return (
    <SliderPrimitive.Root
      data-slot="slider"
      orientation={orientation}
      className={cn(
        "flex gap-2",
        horizontal ? "w-full flex-col" : "h-full flex-row",
        className
      )}
      {...props}
    >
      <SliderPrimitive.Label className="text-sm font-medium" />
      <SliderPrimitive.Control
        className={cn(
          "relative flex w-full touch-none items-center rounded-full select-none",
          horizontal ? "h-1.5" : "h-full w-1.5 flex-col"
        )}
      >
        <SliderPrimitive.Track
          className={cn(
            "relative flex-1 rounded-full bg-muted",
            horizontal ? "h-1.5" : "w-1.5"
          )}
        >
          <SliderPrimitive.Indicator className="rounded-full bg-primary" />
        </SliderPrimitive.Track>
        <SliderPrimitive.Thumb
          className={cn(
            "block size-3.5 rounded-full border border-primary/50 bg-background shadow transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 hover:bg-primary/10 disabled:pointer-events-none disabled:opacity-50"
          )}
        />
      </SliderPrimitive.Control>
      <SliderPrimitive.Value className="text-sm text-muted-foreground tabular-nums" />
    </SliderPrimitive.Root>
  )
}

export { Slider }