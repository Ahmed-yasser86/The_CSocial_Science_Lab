"use client"

import * as React from "react"
import { Drawer as DrawerPrimitive } from "@base-ui/react/drawer"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { XIcon } from "lucide-react"

const SIDE_CLASSES: Record<
  "right" | "left" | "top" | "bottom",
  { position: string; slideIn: string; slideOut: string }
> = {
  right: {
    position: "inset-y-0 right-0 h-full w-full max-w-sm border-l",
    slideIn: "data-open:slide-in-from-right",
    slideOut: "data-closed:slide-out-to-right",
  },
  left: {
    position: "inset-y-0 left-0 h-full w-full max-w-sm border-r",
    slideIn: "data-open:slide-in-from-left",
    slideOut: "data-closed:slide-out-to-left",
  },
  top: {
    position: "inset-x-0 top-0 w-full max-h-[85vh] border-b",
    slideIn: "data-open:slide-in-from-top",
    slideOut: "data-closed:slide-out-to-top",
  },
  bottom: {
    position: "inset-x-0 bottom-0 w-full max-h-[85vh] border-t",
    slideIn: "data-open:slide-in-from-bottom",
    slideOut: "data-closed:slide-out-to-bottom",
  },
}

function Drawer({ ...props }: DrawerPrimitive.Root.Props) {
  return <DrawerPrimitive.Root data-slot="drawer" {...props} />
}

function DrawerTrigger({ ...props }: DrawerPrimitive.Trigger.Props) {
  return <DrawerPrimitive.Trigger data-slot="drawer-trigger" {...props} />
}

function DrawerPortal({ ...props }: DrawerPrimitive.Portal.Props) {
  return <DrawerPrimitive.Portal data-slot="drawer-portal" {...props} />
}

function DrawerClose({ ...props }: DrawerPrimitive.Close.Props) {
  return <DrawerPrimitive.Close data-slot="drawer-close" {...props} />
}

function DrawerOverlay({
  className,
  ...props
}: DrawerPrimitive.Backdrop.Props) {
  return (
    <DrawerPrimitive.Backdrop
      data-slot="drawer-overlay"
      className={cn(
        "fixed inset-0 isolate z-50 bg-black/10 duration-100 supports-backdrop-filter:backdrop-blur-xs data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0",
        className
      )}
      {...props}
    />
  )
}

function DrawerContent({
  className,
  side = "right",
  children,
  showCloseButton = true,
  ...props
}: DrawerPrimitive.Popup.Props & {
  side?: "right" | "left" | "top" | "bottom"
  showCloseButton?: boolean
}) {
  const sideClasses = SIDE_CLASSES[side]
  return (
    <DrawerPortal>
      <DrawerOverlay />
      <DrawerPrimitive.Viewport>
        <DrawerPrimitive.Popup
          data-slot="drawer-content"
          className={cn(
            "fixed z-50 flex flex-col overflow-hidden bg-popover text-sm text-popover-foreground shadow-md ring-1 ring-foreground/10 duration-100 outline-none data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0",
            sideClasses.position,
            sideClasses.slideIn,
            sideClasses.slideOut,
            className
          )}
          {...props}
        >
          {children}
          {showCloseButton && (
            <DrawerPrimitive.Close
              data-slot="drawer-close"
              render={
                <Button
                  variant="ghost"
                  className="absolute top-2 right-2"
                  size="icon-sm"
                />
              }
            >
              <XIcon />
              <span className="sr-only">Close</span>
            </DrawerPrimitive.Close>
          )}
        </DrawerPrimitive.Popup>
      </DrawerPrimitive.Viewport>
    </DrawerPortal>
  )
}

function DrawerHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="drawer-header"
      className={cn("flex flex-col gap-1.5 px-4 pt-4", className)}
      {...props}
    />
  )
}

function DrawerBody({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="drawer-body"
      className={cn("flex-1 overflow-y-auto px-4 py-4", className)}
      {...props}
    />
  )
}

function DrawerFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="drawer-footer"
      className={cn(
        "flex flex-col-reverse gap-2 border-t bg-muted/50 px-4 py-3 sm:flex-row sm:justify-end",
        className
      )}
      {...props}
    />
  )
}

function DrawerTitle({ className, ...props }: DrawerPrimitive.Title.Props) {
  return (
    <DrawerPrimitive.Title
      data-slot="drawer-title"
      className={cn("font-heading text-base leading-none font-medium", className)}
      {...props}
    />
  )
}

function DrawerDescription({
  className,
  ...props
}: DrawerPrimitive.Description.Props) {
  return (
    <DrawerPrimitive.Description
      data-slot="drawer-description"
      className={cn(
        "text-sm text-muted-foreground *:[a]:underline *:[a]:underline-offset-3 *:[a]:hover:text-foreground",
        className
      )}
      {...props}
    />
  )
}

export {
  Drawer,
  DrawerBody,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerOverlay,
  DrawerPortal,
  DrawerTitle,
  DrawerTrigger,
}
