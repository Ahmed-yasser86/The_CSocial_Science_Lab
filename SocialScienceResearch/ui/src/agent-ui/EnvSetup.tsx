"use client";

import { useEffect, useState } from "react";
import { Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const SECRET = /API_KEY|APIKEY|KEY$/i;

const LLM_PRESETS: { label: string; url: string }[] = [
  { label: "Custom / Other", url: "" },
  { label: "OpenAI", url: "https://api.openai.com/v1" },
  { label: "Mistral AI", url: "https://api.mistral.ai/v1" },
  { label: "NVIDIA NIM", url: "https://integrate.api.nvidia.com/v1" },
  { label: "OpenRouter", url: "https://openrouter.ai/api/v1" },
  { label: "Alibaba DashScope", url: "https://dashscope.aliyuncs.com/compatible-mode/v1" },
  { label: "MiniMax", url: "https://api.minimax.chat/v1" },
  { label: "GLM / Z.ai", url: "https://api.z.ai/api/paas/v4" },
  { label: "Suanli", url: "https://api.suanli.cn/v1" },
  { label: "Dahl", url: "https://inference.dahl.global/v1" },
];

const EMBEDDING_PRESETS: { label: string; value: string }[] = [
  { label: "Google GenAI (gemini-embedding-2-preview)", value: "google_genai:gemini-embedding-2-preview" },
  { label: "Cohere multilingual v3.0", value: "cohere:embed-multilingual-v3.0" },
  { label: "OpenAI text-embedding-3-large", value: "openai:text-embedding-3-large" },
];

const RETRIEVER_PRESETS = ["tavily", "mcp", "tavily,mcp"];

export function EnvSetup() {
  const [groups, setGroups] = useState<Record<string, string[]>>({});
  const [values, setValues] = useState<Record<string, string>>({});
  const [path, setPath] = useState("");
  const [status, setStatus] = useState<{ type: "ok" | "err"; msg: string }>({ type: "ok", msg: "" });
  const [busy, setBusy] = useState(false);
  const [customBase, setCustomBase] = useState(false);

  async function load() {
    try {
      const res = await fetch("/api/agent/env");
      const d = await res.json();
      setGroups(d.groups || {});
      setValues(d.values || {});
      setPath(d.path || "");
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function set(k: string, v: string) {
    setValues((prev) => ({ ...prev, [k]: v }));
  }

  async function save() {
    setBusy(true);
    setStatus({ type: "ok", msg: "" });
    try {
      const res = await fetch("/api/agent/env", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values }),
      });
      const d = await res.json();
      if (d.ok) {
        setStatus({ type: "ok", msg: `Saved ${d.written?.length || 0} keys to ${d.path}` });
      } else {
        setStatus({ type: "err", msg: JSON.stringify(d) });
      }
    } catch (e: any) {
      setStatus({ type: "err", msg: String(e?.message || e) });
    } finally {
      setBusy(false);
    }
  }

  const baseUrl = values["OPENAI_BASE_URL"] || "";
  const embedVal = values["EMBEDDING"] || "";
  const basePreset = LLM_PRESETS.find((p) => p.url === baseUrl);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold">
            <Settings2 className="size-4" /> Environment setup
          </h2>
          <p className="truncate font-mono text-[11px] text-muted-foreground" title={path}>
            {path}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="outline" size="sm" onClick={load}>
            Reload
          </Button>
          <Button size="sm" onClick={save} disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>

      {status.msg ? (
        <div
          className={
            "rounded-md border p-2 text-[11px] " +
            (status.type === "ok"
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-600"
              : "border-destructive/40 bg-destructive/10 text-destructive")
          }
        >
          {status.msg}
        </div>
      ) : null}

      {Object.entries(groups).map(([grp, keys]) => (
        <Card key={grp}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{grp.replace(/_/g, " ")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {grp === "LLM" ? (
              <div className="space-y-1">
                <label className="text-[11px] text-muted-foreground">Provider (base URL)</label>
                <select
                  className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                  value={basePreset ? basePreset.label : "custom"}
                  onChange={(e) => {
                    const p = LLM_PRESETS.find((x) => x.label === e.target.value);
                    if (p) {
                      setCustomBase(!p.url);
                      set("OPENAI_BASE_URL", p.url);
                    } else {
                      setCustomBase(true);
                    }
                  }}
                >
                  {LLM_PRESETS.map((p) => (
                    <option key={p.label} value={p.label}>
                      {p.label}
                      {p.url ? ` — ${p.url}` : " (enter manually)"}
                    </option>
                  ))}
                </select>
                {customBase || !basePreset ? (
                  <Input
                    className="text-xs"
                    placeholder="https://…/v1"
                    value={baseUrl}
                    onChange={(e) => set("OPENAI_BASE_URL", e.target.value)}
                  />
                ) : null}
              </div>
            ) : null}

            {grp === "EMBEDDING" ? (
              <div className="space-y-1">
                <label className="text-[11px] text-muted-foreground">Embedding provider</label>
                <select
                  className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                  value={EMBEDDING_PRESETS.find((p) => p.value === embedVal)?.value || "custom"}
                  onChange={(e) => {
                    if (e.target.value === "custom") return;
                    set("EMBEDDING", e.target.value);
                  }}
                >
                  {EMBEDDING_PRESETS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                  <option value="custom">Custom…</option>
                </select>
                {!EMBEDDING_PRESETS.find((p) => p.value === embedVal) ? (
                  <Input
                    className="text-xs"
                    value={embedVal}
                    onChange={(e) => set("EMBEDDING", e.target.value)}
                    placeholder="provider:model (e.g. cohere:embed-multilingual-v3.0)"
                  />
                ) : null}
              </div>
            ) : null}

            {grp === "SEARCH" ? (
              <div className="space-y-1">
                <label className="text-[11px] text-muted-foreground">Retriever</label>
                <select
                  className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
                  value={values["RETRIEVER"] || ""}
                  onChange={(e) => set("RETRIEVER", e.target.value)}
                >
                  <option value="">(unset)</option>
                  {RETRIEVER_PRESETS.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}

            {keys
              .filter(
                (k) =>
                  !(grp === "LLM" && k === "OPENAI_BASE_URL") &&
                  !(grp === "EMBEDDING" && k === "EMBEDDING") &&
                  !(grp === "SEARCH" && k === "RETRIEVER"),
              )
              .map((k) => (
                <div key={k} className="space-y-1">
                  <label className="text-[11px] text-muted-foreground">{k}</label>
                  <Input
                    className="text-xs"
                    type={SECRET.test(k) ? "password" : "text"}
                    value={values[k] ?? ""}
                    onChange={(e) => set(k, e.target.value)}
                    placeholder={/LLM$/.test(k) ? "provider:model" : ""}
                  />
                </div>
              ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
