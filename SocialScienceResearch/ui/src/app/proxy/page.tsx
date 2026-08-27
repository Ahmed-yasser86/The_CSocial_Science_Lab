"use client";

import { useEffect, useState, type ReactNode } from "react";

interface ProxyConfig {
  proxy_enabled: boolean;
  proxy_host: string;
  proxy_port: number;
  proxy_username: string;
  proxy_password: string;
  proxy_verify: boolean;
  proxy_session: string;
  youtube_cookies_mode: string;
  youtube_cookies_browser: string;
  youtube_cookies_path: string;
  [key: string]: unknown;
}

const BASE = "/api/v1/social-science";
const EMPTY: ProxyConfig = {
  proxy_enabled: false,
  proxy_host: "",
  proxy_port: 0,
  proxy_username: "",
  proxy_password: "",
  proxy_verify: true,
  proxy_session: "",
  youtube_cookies_mode: "none",
  youtube_cookies_browser: "chrome",
  youtube_cookies_path: "",
};

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-foreground">{label}</span>
      {children}
    </label>
  );
}

const inputCls =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring";

export default function ProxySetupPage() {
  const [cfg, setCfg] = useState<ProxyConfig>(EMPTY);
  const [loaded, setLoaded] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [testResult, setTestResult] = useState<Record<string, unknown> | null>(
    null,
  );
  const [busy, setBusy] = useState<"save" | "test" | null>(null);

  function set<K extends keyof ProxyConfig>(key: K, value: ProxyConfig[K]) {
    setCfg((c) => ({ ...c, [key]: value }));
  }

  useEffect(() => {
    let cancelled = false;
    fetch(`${BASE}/scraper/proxy`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data) setCfg({ ...EMPTY, ...data });
      })
      .catch(() => undefined)
      .finally(() => !cancelled && setLoaded(true));
    return () => {
      cancelled = true;
    };
  }, []);

  async function save() {
    setBusy("save");
    setStatus("");
    try {
      const res = await fetch(`${BASE}/scraper/proxy`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(cfg),
      });
      if (!res.ok) throw new Error(await res.text());
      setCfg(await res.json());
      setStatus(
        "Saved. All YouTube extraction now routes through the proxy (applies live, no restart).",
      );
    } catch (e) {
      setStatus(`Save failed: ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  }

  async function test() {
    setBusy("test");
    setTestResult(null);
    setStatus("");
    try {
      const res = await fetch(`${BASE}/scraper/proxy/test`, {
        method: "POST",
        credentials: "include",
      });
      const data = await res.json();
      setTestResult(data);
      if (data?.ok) {
        const ip = data?.egress_ip ? ` Egress IP: ${data.egress_ip}.` : "";
        setStatus(`Proxy verified — YouTube reached through the proxy.${ip}`);
      } else {
        setStatus(`Test failed: ${data?.youtube?.reason ?? data?.error ?? "unknown error"}`);
      }
    } catch (e) {
      setStatus(`Test error: ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Proxy IP Setup</h1>
        <p className="text-sm text-muted-foreground">
          Route all YouTube extraction through a Decodo / rotating-residential
          proxy to avoid IP throttling. Credentials are stored in the workspace
          data directory and never logged.
        </p>
      </header>

      {!loaded ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <div className="space-y-4 rounded-lg border bg-card p-5">
          <label className="flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              checked={cfg.proxy_enabled}
              onChange={(e) => set("proxy_enabled", e.target.checked)}
              className="size-4"
            />
            Enable proxy
          </label>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Proxy host">
              <input
                className={inputCls}
                placeholder="dc.decodo.com"
              value={cfg.proxy_host ?? ""}
              onChange={(e) => set("proxy_host", e.target.value)}
              />
            </Field>
            <Field label="Proxy port">
              <input
                className={inputCls}
                type="number"
                placeholder="10001"
                value={cfg.proxy_port || ""}
                onChange={(e) => set("proxy_port", Number(e.target.value) || 0)}
              />
            </Field>
            <Field label="Username">
              <input
                className={inputCls}
                placeholder="spg9l1o1mp"
              value={cfg.proxy_username ?? ""}
              onChange={(e) => set("proxy_username", e.target.value)}
              />
            </Field>
            <Field label="Password">
              <input
                className={inputCls}
                type="password"
                placeholder="••••••••"
              value={cfg.proxy_password ?? ""}
              onChange={(e) => set("proxy_password", e.target.value)}
              />
            </Field>
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={cfg.proxy_verify}
              onChange={(e) => set("proxy_verify", e.target.checked)}
              className="size-4"
            />
            Verify TLS certificates
          </label>

          <Field label="Sticky session id (optional)">
            <input
              className={inputCls}
              placeholder="e.g. my-session-1 (appended as -session-<id> to the username)"
              value={cfg.proxy_session ?? ""}
              onChange={(e) => set("proxy_session", e.target.value)}
            />
          </Field>

          <div className="space-y-3 rounded-md border border-dashed p-4">
            <p className="text-sm font-medium text-foreground">
              YouTube cookies (clears the “Sign in to confirm you’re not a bot”
              challenge)
            </p>
            <Field label="Cookie source">
              <select
                className={inputCls}
                value={cfg.youtube_cookies_mode ?? "none"}
                onChange={(e) => set("youtube_cookies_mode", e.target.value)}
              >
                <option value="none">None</option>
                <option value="browser">
                  Read live from a browser on this machine
                </option>
                <option value="file">Load a cookies.txt file</option>
              </select>
            </Field>

            {cfg.youtube_cookies_mode === "browser" ? (
              <Field label="Browser">
                <input
                  className={inputCls}
                  placeholder="chrome, firefox, edge, brave…"
                value={cfg.youtube_cookies_browser ?? ""}
                onChange={(e) =>
                  set("youtube_cookies_browser", e.target.value)
                }
                />
              </Field>
            ) : null}

            {cfg.youtube_cookies_mode === "file" ? (
              <Field label="Path to cookies.txt (Netscape format)">
                <input
                  className={inputCls}
                  placeholder="/path/to/youtube_cookies.txt"
                  value={cfg.youtube_cookies_path ?? ""}
                  onChange={(e) => set("youtube_cookies_path", e.target.value)}
                />
              </Field>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-3 pt-2">
            <button
              onClick={save}
              disabled={busy !== null}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
            >
              {busy === "save" ? "Saving…" : "Save proxy"}
            </button>
            <button
              onClick={test}
              disabled={busy !== null}
              className="rounded-md border px-4 py-2 text-sm font-medium disabled:opacity-60"
            >
              {busy === "test" ? "Testing…" : "Test (YouTube via proxy)"}
            </button>
          </div>

          {status ? (
            <p className="text-sm text-muted-foreground">{status}</p>
          ) : null}

          {testResult ? (
            <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">
              {JSON.stringify(testResult, null, 2)}
            </pre>
          ) : null}
        </div>
      )}
    </div>
  );
}
