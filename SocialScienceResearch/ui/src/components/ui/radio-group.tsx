"use client"

import * as React from "react"
import { RadioGroup as RadioGroupPrimitive } from "@base-ui/react/radio-group"
import { Radio as RadioPrimitive } from "@base-ui/react/radio"

import { cn } from "@/lib/utils"
import { CheckIcon } from "lucide-react"

function RadioGroup({
  className,
  ...props
}: RadioGroupPrimitive.Props) {
  return (
    <RadioGroupPrimitive
      data-slot="radio-group"
      className={cn("grid gap-2", className)}
      {...props}
    />
  )
}

function RadioGroupItem({
  className,
  children,
  ...props
}: RadioPrimitive.Root.Props) {
  return (
    <RadioPrimitive.Root
      data-slot="radio-group-item"
      className={cn(
        "group/radio-item relative flex cursor-default items-center gap-2 rounded-md border border-transparent py-1 pr-2 text-sm outline-none select-none focus-visible:ring-[3px] focus-visible:ring-ring/50 data-checked:border-input data-checked:bg-muted/40 data-disabled:pointer-events-none data-disabled:opacity-50",
        className
      )}
      {...props}
    >
      <span className="flex size-4 shrink-0 items-center justify-center rounded-full border border-input transition-colors group-data-checked/radio-item:border-primary group-data-checked/radio-item:bg-primary group-data-checked/radio-item:text-primary-foreground">
        <RadioPrimitive.Indicator className="grid place-content-center [&>svg]:size-3">
          <CheckIcon aria-hidden />
        </RadioPrimitive.Indicator>
      </span>
      {children ? (
        <span className="flex-1">{children}</span>
      ) : null}
    </RadioPrimitive.Root>
  )
}

export { RadioGroup, RadioGroupItem }
