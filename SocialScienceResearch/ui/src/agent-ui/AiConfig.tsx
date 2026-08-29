"use client";

import { useEffect, useState } from "react";
import { Cpu, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Field = {
  env: string;
  label: string;
  kind: "chat_model" | "embedding" | "enum" | "url" | "secret" | "text";
  options?: string[];
  reveal_provider_credentials?: boolean;
};
type Service = {
  category: string;
  id: string;
  name: string;
  tier?: string;
  description?: string;
  fields: Field[];
};
type Provider = {
  label: string;
  chat?: boolean;
  embedding?: boolean;
  api_key_env?: string;
  base_url_env?: string;
  base_url?: string;
};

function fieldValue(values: Record<string, string>, env: string) {
  return values[env] ?? "";
}
function setField(values: Record<string, string>, env: string, v: string) {
  return { ...values, [env]: v };
}

export function AiConfig() {
  const [services, setServices] = useState<Service[]>([]);
  const [providers, setProviders] = useState<Record<string, Provider>>({});
  const [values, setValues] = useState<Record<string, string>>({});
  const [path, setPath] = useState("");
  const [status, setStatus] = useState<{ type: "ok" | "err"; msg: string }>({ type: "ok", msg: "" });
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const res = await fetch("/api/agent/ai-config");
      const d = await res.json();
      setServices(d.services || []);
      setProviders(d.providers || {});
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

  function save() {
    setBusy(true);
    setStatus({ type: "ok", msg: "" });
    fetch("/api/agent/env", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values }),
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.ok) setStatus({ type: "ok", msg: `Saved ${d.written?.length || 0} keys to ${d.path}` });
        else setStatus({ type: "err", msg: JSON.stringify(d) });
      })
      .catch((e) => setStatus({ type: "err", msg: String(e?.message || e) }))
      .finally(() => setBusy(false));
  }

  // providers filtered by capability for a field kind
  function providersFor(kind: string) {
    const cap = kind === "embedding" ? "embedding" : "chat";
    return Object.entries(providers).filter(([, p]) => p[cap as "embedding" | "chat"]);
  }

  function renderModelField(
    field: Field,
    current: string,
  ) {
    const idx = current.indexOf(":");
    const prov = idx >= 0 ? current.slice(0, idx) : "";
    const model = idx >= 0 ? current.slice(idx + 1) : current;
    const provList = providersFor(field.kind);
    const opts = provList.map(([id, p]) => ({ id, label: p.label }));
    if (prov && !opts.find((o) => o.id === prov)) opts.push({ id: prov, label: prov });
    const selected = providers[prov];
    return (
      <div className="space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <label className="text-[11px] text-muted-foreground">Provider</label>
            <select
              className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
              value={prov}
              onChange={(e) => {
                const np = e.target.value;
                setValues((v) => setField(v, field.env, np ? `${np}:${model}` : model));
              }}
            >
              <option value="">(unset)</option>
              {opts.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-[11px] text-muted-foreground">{field.label}</label>
              <Input
                className="text-xs"
                value={model}
                placeholder="provider:model  (e.g. moonshotai/Kimi-K2.6)"
                onChange={(e) => setValues((v) => setField(v, field.env, prov ? `${prov}:${e.target.value}` : e.target.value))}
              />
          </div>
        </div>
        {selected?.base_url_env ? (
          <div className="space-y-1">
            <label className="text-[11px] text-muted-foreground">Base URL</label>
            <Input
              className="text-xs"
              value={fieldValue(values, selected.base_url_env)}
              placeholder={selected.base_url || "https://…/v1"}
              onChange={(e) => setValues((v) => setField(v, selected.base_url_env!, e.target.value))}
            />
          </div>
        ) : null}
        {selected?.api_key_env ? (
          <div className="space-y-1">
            <label className="flex items-center gap-1 text-[11px] text-muted-foreground">
              <KeyRound className="size-3" /> {selected.label} API key
            </label>
            <Input
              className="text-xs"
              type="password"
              value={fieldValue(values, selected.api_key_env)}
              placeholder={selected.api_key_env}
              onChange={(e) => setValues((v) => setField(v, selected.api_key_env!, e.target.value))}
            />
          </div>
        ) : null}
      </div>
    );
  }

  function renderField(field: Field) {
    const current = fieldValue(values, field.env);
    if (field.kind === "chat_model" || field.kind === "embedding") {
      return renderModelField(field, current);
    }
    if (field.kind === "enum") {
      const sel = field.reveal_provider_credentials ? providers[current] : undefined;
      return (
        <div className="space-y-2">
          <div className="space-y-1">
            <label className="text-[11px] text-muted-foreground">{field.label}</label>
            <select
              className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
              value={current}
              onChange={(e) => setValues((v) => setField(v, field.env, e.target.value))}
            >
              <option value="">(unset)</option>
              {(field.options || []).map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </div>
          {sel?.api_key_env ? (
            <div className="space-y-1">
              <label className="flex items-center gap-1 text-[11px] text-muted-foreground">
                <KeyRound className="size-3" /> {sel.label} API key
              </label>
              <Input
                className="text-xs"
                type="password"
                value={fieldValue(values, sel.api_key_env)}
                placeholder={sel.api_key_env}
                onChange={(e) => setValues((v) => setField(v, sel.api_key_env!, e.target.value))}
              />
            </div>
          ) : null}
          {sel?.base_url_env ? (
            <div className="space-y-1">
              <label className="text-[11px] text-muted-foreground">Base URL</label>
              <Input
                className="text-xs"
                value={fieldValue(values, sel.base_url_env)}
                placeholder={sel.base_url || "https://…/v1"}
                onChange={(e) => setValues((v) => setField(v, sel.base_url_env!, e.target.value))}
              />
            </div>
          ) : null}
        </div>
      );
    }
    return (
      <div className="space-y-1">
        <label className="text-[11px] text-muted-foreground">{field.label}</label>
        <Input
          className="text-xs"
          type={field.kind === "secret" ? "password" : "text"}
          value={current}
          placeholder={field.env}
          onChange={(e) => setValues((v) => setField(v, field.env, e.target.value))}
        />
      </div>
    );
  }

  // group services by category, preserving order
  const categories: string[] = [];
  for (const s of services) if (!categories.includes(s.category)) categories.push(s.category);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold">
            <Cpu className="size-4" /> AI Services &amp; Models
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

      {categories.map((cat) => (
        <div key={cat} className="space-y-2">
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{cat}</h3>
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            {services
              .filter((s) => s.category === cat)
              .map((s) => (
                <Card key={s.id}>
                  <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0 pb-2">
                    <div>
                      <CardTitle className="text-sm">{s.name}</CardTitle>
                      {s.description ? (
                        <p className="mt-0.5 text-[11px] text-muted-foreground">{s.description}</p>
                      ) : null}
                    </div>
                    {s.tier ? (
                      <Badge variant="secondary" className="shrink-0 capitalize">
                        {s.tier}
                      </Badge>
                    ) : null}
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {s.fields.map((f) => (
                      <div key={f.env}>{renderField(f)}</div>
                    ))}
                  </CardContent>
                </Card>
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}
