"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useSaveSession, useActiveSessionQuery } from "@/services/queries";
import type { SessionContext } from "@/services/session";

export const ACTIVE_SESSION_STORAGE_KEY = "ssr-active-session";
export const ADHOC_SESSION_STORAGE_KEY = "ssr-adhoc-session";

export interface ActiveSession {
  activeProjectId: string;
  activeDatasetId: string | null;
}

export interface StoredActiveSession extends ActiveSession {
  updatedAt: string;
}

// ---------------------------------------------------------------------------
// Pure persistence/reconciliation primitives (unit-tested in session.test.ts)
// ---------------------------------------------------------------------------
export function parseStoredSession(raw: string | null): StoredActiveSession | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<StoredActiveSession>;
    if (!parsed || typeof parsed.activeProjectId !== "string" || !parsed.activeProjectId) {
      return null;
    }
    return {
      activeProjectId: parsed.activeProjectId,
      activeDatasetId:
        typeof parsed.activeDatasetId === "string" ? parsed.activeDatasetId : null,
      updatedAt: typeof parsed.updatedAt === "string" ? parsed.updatedAt : "",
    };
  } catch {
    return null;
  }
}

export function serializeStoredSession(
  session: ActiveSession,
  updatedAt: string,
): string {
  return JSON.stringify({ ...session, updatedAt } satisfies StoredActiveSession);
}

export interface ReconcileResult {
  session: ActiveSession | null;
  pushLocal: boolean;
}

/** Merge local (localStorage) and server session state. The newer timestamp
 *  wins; a winning local state still needs to be pushed to the server. */
export function reconcileSessions(
  local: StoredActiveSession | null,
  server: SessionContext | null | undefined,
): ReconcileResult {
  const remoteSession: ActiveSession | null = server?.active_project_id
    ? {
        activeProjectId: server.active_project_id,
        activeDatasetId: server.active_dataset_id ?? null,
      }
    : null;
  if (!local && !remoteSession) return { session: null, pushLocal: false };
  if (!local) return { session: remoteSession, pushLocal: false };
  const localSession: ActiveSession = {
    activeProjectId: local.activeProjectId,
    activeDatasetId: local.activeDatasetId,
  };
  if (!remoteSession) return { session: localSession, pushLocal: true };
  const localTime = Date.parse(local.updatedAt);
  const serverTime = Date.parse(server?.updated_at ?? "");
  if (Number.isNaN(serverTime)) return { session: localSession, pushLocal: true };
  if (Number.isNaN(localTime)) return { session: remoteSession, pushLocal: false };
  if (serverTime > localTime) return { session: remoteSession, pushLocal: false };
  return { session: localSession, pushLocal: true };
}

// ---------------------------------------------------------------------------
// Storage access (mirrors lib/lab-session.ts: post-mount restore + memory
// fallback when localStorage is unavailable)
// ---------------------------------------------------------------------------
function getStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    const s = window.localStorage;
    s.setItem("__ssr_probe__", "1");
    s.removeItem("__ssr_probe__");
    return s;
  } catch {
    return null;
  }
}

const memory = new Map<string, string>();

function readRaw(key: string): string | null {
  const s = getStorage();
  if (s) {
    try {
      return s.getItem(key);
    } catch {
      /* fall through to memory */
    }
  }
  return memory.get(key) ?? null;
}

function writeRaw(key: string, value: string): void {
  const s = getStorage();
  if (s) {
    try {
      s.setItem(key, value);
      return;
    } catch {
      /* fall through to memory */
    }
  }
  memory.set(key, value);
}

function removeRaw(key: string): void {
  const s = getStorage();
  if (s) {
    try {
      s.removeItem(key);
      return;
    } catch {
      /* fall through to memory */
    }
  }
  memory.delete(key);
}

export function loadStoredActiveSession(): StoredActiveSession | null {
  return parseStoredSession(readRaw(ACTIVE_SESSION_STORAGE_KEY));
}

export function saveStoredActiveSession(
  session: ActiveSession,
  updatedAt = new Date().toISOString(),
): void {
  writeRaw(
    ACTIVE_SESSION_STORAGE_KEY,
    serializeStoredSession(session, updatedAt),
  );
}

export function clearStoredActiveSession(): void {
  removeRaw(ACTIVE_SESSION_STORAGE_KEY);
}

/** "Explore without a project" dismisses the welcome panel per browser. */
export function loadAdhocFlag(): boolean {
  return readRaw(ADHOC_SESSION_STORAGE_KEY) === "true";
}

export function saveAdhocFlag(): void {
  writeRaw(ADHOC_SESSION_STORAGE_KEY, "true");
}

export function clearAdhocFlag(): void {
  removeRaw(ADHOC_SESSION_STORAGE_KEY);
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------
export interface ActiveSessionValue {
  hydrated: boolean;
  session: ActiveSession | null;
  setActiveSession: (projectId: string, datasetId: string | null) => void;
  clearActiveSession: () => void;
}

const ActiveSessionContext = createContext<ActiveSessionValue | null>(null);

export function ActiveSessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<ActiveSession | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const reconciledRef = useRef(false);
  const saveMutation = useSaveSession();
  const serverQuery = useActiveSessionQuery();

  useEffect(() => {
    setSession(loadStoredActiveSession());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated || reconciledRef.current) return;
    if (serverQuery.isLoading || serverQuery.isError) return;
    reconciledRef.current = true;
    const stored = loadStoredActiveSession();
    const result = reconcileSessions(stored, serverQuery.data ?? null);
    setSession(result.session);
    if (!result.session) {
      clearStoredActiveSession();
    } else if (result.pushLocal) {
      // Local record keeps its own timestamp; mirror it to the server.
      saveMutation.mutate({
        active_project_id: result.session.activeProjectId,
        active_dataset_id: result.session.activeDatasetId,
      });
    } else {
      saveStoredActiveSession(result.session, serverQuery.data?.updated_at);
    }
  }, [hydrated, serverQuery.data, serverQuery.isLoading, serverQuery.isError, saveMutation]);

  const setActiveSession = useCallback(
    (projectId: string, datasetId: string | null) => {
      const next = { activeProjectId: projectId, activeDatasetId: datasetId };
      setSession(next);
      saveStoredActiveSession(next);
      saveMutation.mutate({
        active_project_id: projectId,
        active_dataset_id: datasetId,
      });
    },
    [saveMutation],
  );

  const clearActiveSession = useCallback(() => {
    setSession(null);
    clearAdhocFlag();
    clearStoredActiveSession();
    saveMutation.mutate({
      active_project_id: null,
      active_dataset_id: null,
    });
  }, [saveMutation]);

  const value = useMemo<ActiveSessionValue>(
    () => ({ hydrated, session, setActiveSession, clearActiveSession }),
    [hydrated, session, setActiveSession, clearActiveSession],
  );

  return (
    <ActiveSessionContext.Provider value={value}>
      {children}
    </ActiveSessionContext.Provider>
  );
}

export function useActiveSession(): ActiveSessionValue {
  const value = useContext(ActiveSessionContext);
  return (
    value ?? {
      hydrated: false,
      session: null,
      setActiveSession: () => {},
      clearActiveSession: () => {},
    }
  );
}
