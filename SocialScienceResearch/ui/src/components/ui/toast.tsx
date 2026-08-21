"use client"

import * as React from "react"
import { createContext, useCallback, useContext, useMemo, useState } from "react"

import { cn } from "@/lib/utils"
import { XIcon } from "lucide-react"

type ToastVariant = "default" | "destructive"

export interface Toast {
  id: string
  title?: string
  description?: string
  variant?: ToastVariant
  duration?: number
}

interface ToastContextValue {
  toasts: Toast[]
  toast: (toast: Omit<Toast, "id">) => string
  dismiss: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = useCallback(
    (input: Omit<Toast, "id">) => {
      const id = Math.random().toString(36).slice(2)
      setToasts((prev) => [...prev, { ...input, id }])
      const duration = input.duration ?? 5000
      if (duration > 0) {
        window.setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== id))
        }, duration)
      }
      return id
    },
    []
  )

  const value = useMemo(
    () => ({ toasts, toast, dismiss }),
    [toasts, toast, dismiss]
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      <Toaster />
    </ToastContext.Provider>
  )
}

function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error("useToast must be used within a ToastProvider")
  return ctx
}

function Toaster() {
  const { toasts, dismiss } = useToast()
  return (
    <div
      data-slot="toaster"
      className="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-full max-w-sm flex-col gap-2"
      aria-live="polite"
    >
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
      ))}
    </div>
  )
}

function ToastCard({
  toast,
  onDismiss,
}: {
  toast: Toast
  onDismiss: () => void
}) {
  const destructive = toast.variant === "destructive"
  return (
    <div
      role="status"
      data-slot="toast"
      data-variant={toast.variant ?? "default"}
      className={cn(
        "pointer-events-auto relative flex w-full items-start gap-2 overflow-hidden rounded-lg bg-popover p-3 pr-8 text-sm text-popover-foreground shadow-md ring-1 ring-foreground/10 animate-in fade-in-0 slide-in-from-bottom-2 duration-200",
        destructive && "border border-destructive/40"
      )}
    >
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        {toast.title ? (
          <p className="font-medium">{toast.title}</p>
        ) : null}
        {toast.description ? (
          <p className="text-muted-foreground">{toast.description}</p>
        ) : null}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="absolute top-2 right-2 inline-flex size-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        aria-label="Dismiss notification"
      >
        <XIcon className="size-3.5" aria-hidden />
      </button>
    </div>
  )
}

export { ToastProvider, useToast }
