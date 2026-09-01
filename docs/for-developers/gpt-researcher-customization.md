# GPT-Researcher Customization

This project includes a **customized fork** of [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) at `gpt-researcher/`. A pristine copy of the original is kept at `GPT-Researcher-Original/` for reference.

## Overview

The fork is **not a divergent rewrite** — surgical additions to upstream codebase (15 files changed, 1028 insertions) tailored for this project's specific needs.

## Key Customizations

| Customization | File | Purpose |
|---|---|---|
| Embedding rate limiting | `gpt_researcher/memory/embeddings.py` | `RateLimitedEmbedder` via `GPT_RESEARCHER_EMBED_TPM`/`_RPM` env vars |
| MCP tool selection | `gpt_researcher/prompts.py` | Domain-aware taxonomy (`web_research_*`, `socialcrawl_*`, `gdelt_cloud_*`) |
| **Customized system prompts** | `gpt_researcher/prompts.py` | Every agent prompt rewritten for domain-specific use cases |
| Context compression | `gpt_researcher/context/compression.py` | `ValidContentFilter` + `SafeEmbeddingsFilter` (no empty results) |
| Config bootstrapping | `gpt_researcher/config/config.py` | `_load_root_env()` ensures `.env` vars available regardless of CWD |
| Tool input normalization | `gpt_researcher/mcp/normalization.py` | Prevents server rejections from malformed tool args |

## Customized System Prompts

Every agent prompt in `gpt_researcher/prompts.py` has been rewritten for domain-specific use cases:

### Query Summarizer
Summarizes long multi-page research queries into structured audience intelligence summaries:
```
You are an expert Audience Intelligence & Influence System Query Analyzer.
Your task is to analyze the following detailed research request and extract a high-precision,
multi-dimensional research summary specifically structured for audience ecosystem modeling,
influence topology, and research tool selection.

STRUCTURE THE SUMMARY AROUND THESE CORE PILLARS:
1. SUBJECT IDENTITY & WORLDVIEW
2. AUDIENCE ECOSYSTEM & SEGMENTATION
3. DISSEMINATION TOPOLOGY & INFLUENCE PATHWAYS
4. RHETORICAL & COMMUNICATION SYSTEM
5. PRIMARY RESEARCH OBJECTIVES & GAPS
```

### MCP Tool Selection
Instructs the LLM to select the most relevant MCP tools using domain-aware server semantics:
```
SERVER SEMANTICS (inferred from tool-name prefixes):
- web_research_*      -> General web search / web research
- socialcrawl_*       -> Social-media platforms
- gdelt_cloud_*       -> GDELT global news & events database
- energy_* / risk_* / filings_* ... -> Specialized structured data
```

### Research Report Generation
Generates APA-formatted research reports with in-text citations and reference lists.

### Subtopic Reports
Writes detailed subtopic report sections with:
- Content uniqueness (avoids overlap with existing reports)
- H2 for main subtopic, H3 for subsections
- In-text citations
- Minimum 800 words per section

## Embedding Rate Limiting

The fork integrates a `RateLimitedEmbedder` from `Ingestion_Pipline` into gpt-researcher's memory/embeddings layer:

- **Environment variables:**
  - `GPT_RESEARCHER_EMBED_TPM` — tokens per minute limit
  - `GPT_RESEARCHER_EMBED_RPM` — requests per minute limit

- **UI controls:** Embedding rate-limit settings available in the frontend

## Context Compression Hardening

Two new filters prevent common failure modes:

1. **`ValidContentFilter`** — prevents `IndexError` on empty documents
2. **`SafeEmbeddingsFilter`** — never returns empty results; falls back to top-k by similarity

## Config Bootstrapping

`_load_root_env()` in `config.py` ensures `.env` variables are always available regardless of CWD or import order. This fixes issues where the backend starts from a different directory than the project root.

## Tool Input Normalization

`gpt_researcher/mcp/normalization.py` provides centralized MCP tool-input normalization:
- `raw_args` → `query` for `SEARCH_WEB`
- Category alias mapping for `SEARCH_STORIES`
- Prevents server rejections from malformed tool arguments
