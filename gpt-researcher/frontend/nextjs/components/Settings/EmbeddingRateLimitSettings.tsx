import React, { useEffect, useState } from 'react';

interface ModuleSettings {
  tpm?: number | null;
  rpm?: number | null;
  encoding?: string | null;
}

interface EmbeddingRateLimitSettings {
  gpt_researcher?: ModuleSettings;
  content_homophily?: ModuleSettings;
  ingestion?: ModuleSettings;
}

type ModuleKey = keyof EmbeddingRateLimitSettings;

export default function EmbeddingRateLimitSettings() {
  const [settings, setSettings] = useState<EmbeddingRateLimitSettings | null>(null);
  const [status, setStatus] = useState<string>('');

  useEffect(() => {
    fetch('/api/settings/embedding-rate-limit')
      .then((r) => r.json())
      .then((data: EmbeddingRateLimitSettings) => setSettings(data))
      .catch(() => setStatus('Failed to load embedding rate-limit settings'));
  }, []);

  const update = (module: ModuleKey, field: string, value: string) => {
    setSettings((prev) => {
      const current = prev || {};
      const mod = current[module] || {};
      return { ...current, [module]: { ...mod, [field]: value === '' ? null : value } };
    });
  };

  const save = async () => {
    setStatus('Saving...');
    try {
      const res = await fetch('/api/settings/embedding-rate-limit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });
      if (!res.ok) throw new Error('save failed');
      setStatus('Saved');
    } catch (e) {
      setStatus('Save failed');
    }
  };

  if (!settings) {
    return <div className="form-group">Loading embedding rate-limit settings...</div>;
  }

  const mod = (m: ModuleKey) => settings[m] || {};

  return (
    <div className="form-group" style={{ border: '1px solid #ccc', padding: '0.5rem' }}>
      <h4>Embedding Rate Limits</h4>
      <p className="agent_question">
        Per-module embedding rate limits (tokens/min and requests/min). 0 = disabled.
        These are saved to the project config and applied to new embedding calls.
      </p>

      <label className="agent_question">GPT Researcher — Tokens/min (TPM)</label>
      <input
        type="number"
        min="0"
        className="form-control-static"
        value={mod('gpt_researcher').tpm ?? ''}
        onChange={(e) => update('gpt_researcher', 'tpm', e.target.value)}
      />

      <label className="agent_question">GPT Researcher — Requests/min (RPM)</label>
      <input
        type="number"
        min="0"
        className="form-control-static"
        value={mod('gpt_researcher').rpm ?? ''}
        onChange={(e) => update('gpt_researcher', 'rpm', e.target.value)}
      />

      <label className="agent_question">GPT Researcher — Token encoding</label>
      <input
        type="text"
        className="form-control-static"
        value={mod('gpt_researcher').encoding ?? ''}
        onChange={(e) => update('gpt_researcher', 'encoding', e.target.value)}
      />

      <label className="agent_question">Content Homophily (SNA) — Tokens/min (TPM)</label>
      <input
        type="number"
        min="0"
        className="form-control-static"
        value={mod('content_homophily').tpm ?? ''}
        onChange={(e) => update('content_homophily', 'tpm', e.target.value)}
      />

      <label className="agent_question">Ingestion — Requests/min (RPM, shared Gemini budget)</label>
      <input
        type="number"
        min="0"
        className="form-control-static"
        value={mod('ingestion').rpm ?? ''}
        onChange={(e) => update('ingestion', 'rpm', e.target.value)}
      />

      <button type="button" className="btn btn-primary" onClick={save}>
        Save embedding rate limits
      </button>
      <span style={{ marginLeft: '0.5rem' }}>{status}</span>
    </div>
  );
}
