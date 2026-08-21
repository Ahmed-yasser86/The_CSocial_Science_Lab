"use client";

import { Inbox, Loader2, AlertTriangle, HelpCircle, CircleOff, X, CheckCircle, AlertCircle } from "lucide-react";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import { useState, useEffect } from "react";

export function LoadingState({
  label = "Loading…",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-h-40 flex-col items-center justify-center gap-3 text-muted-foreground",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <Loader2 className="size-5 animate-spin" aria-hidden />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon: Icon = Inbox,
  className,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-h-40 flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-8 text-center",
        className,
      )}
    >
      <Icon className="size-6 text-muted-foreground" aria-hidden />
      <p className="text-sm font-medium">{title}</p>
      {description ? (
        <p className="max-w-md text-sm text-muted-foreground">{description}</p>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  message,
  detail,
  retry,
}: {
  message: string;
  detail?: string;
  retry?: () => void;
}) {
  return (
    <Alert variant="destructive" className="min-h-40 items-center justify-center">
      <AlertTriangle className="size-4" aria-hidden />
      <AlertTitle>Request failed</AlertTitle>
      <AlertDescription className="flex flex-col gap-2">
        <span>{message}</span>
        {detail ? <code className="text-xs">{detail}</code> : null}
        {retry ? (
          <button
            type="button"
            onClick={retry}
            className="w-fit rounded-md border border-border px-3 py-1 text-xs font-medium outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            Retry
          </button>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}

export function UnsupportedState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <Alert className="min-h-40 items-center justify-center">
      <CircleOff className="size-4" aria-hidden />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{description}</AlertDescription>
    </Alert>
  );
}

export function PartialState({
  title,
  description,
  icon: Icon = HelpCircle,
}: {
  title: string;
  description: string;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Alert className="min-h-40 items-center justify-center">
      <Icon className="size-4" aria-hidden />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{description}</AlertDescription>
    </Alert>
  );
}

export function Toast({
  message,
  type = "success",
  onClose,
}: {
  message: string;
  type?: "success" | "error" | "info";
  onClose?: () => void;
}) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      onClose?.();
    }, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  if (!visible) return null;

  const icons = {
    success: CheckCircle,
    error: AlertCircle,
    info: AlertTriangle,
  };

  const Icon = icons[type];
  const colors = {
    success: "border-green-500/50 bg-green-500/10 text-green-600 dark:text-green-400",
    error: "border-red-500/50 bg-red-500/10 text-red-600 dark:text-red-400",
    info: "border-blue-500/50 bg-blue-500/10 text-blue-600 dark:text-blue-400",
  };

  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-lg border px-4 py-3 shadow-lg min-w-[280px] max-w-md",
        colors[type]
      )}
      role="alert"
      aria-live="polite"
    >
      <Icon className="size-4 flex-shrink-0" aria-hidden />
      <p className="text-sm flex-1">{message}</p>
      {onClose && (
        <button
          type="button"
          onClick={() => {
            setVisible(false);
            onClose();
          }}
          className="flex-shrink-0 text-muted-foreground hover:text-foreground"
          aria-label="Dismiss"
        >
          <X className="size-4" aria-hidden />
        </button>
      )}
    </div>
  );
}
