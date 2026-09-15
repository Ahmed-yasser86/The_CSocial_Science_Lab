# Pipelines

> How data and representations flow end-to-end through the system — from collection to research evidence.

Each pipeline document follows the same contract: **Why** (research rationale) → **Inputs** → **Stages in order** → **Representation changes** → **Algorithms with real parameters** → **AI vs deterministic logic** → **Persistence** → **Failures** → **Limitations** → **Code paths**.

---

## Pipeline map

| Pipeline | Question it answers | Canonical document |
|---|---|---|
| **Network–semantic integration** (content homophily) | Is content inside structural communities also *semantically* similar? | [content-homophily.md](content-homophily.md) |
| **Recommendation crawling** | What does the platform connect, layer by layer? | [recommendation-crawling.md](recommendation-crawling.md) |
| **Echo-chamber signals (S1–S5)** | Do observed structures look like echo-chamber dynamics? | [../for-researchers/echo-chamber.md](../for-researchers/echo-chamber.md) |
| **Social network construction** | Who interacts with whom? | [../for-researchers/methodology.md](../for-researchers/methodology.md) (Social Network Construction) |
| **Commenter overlap / bridge detection** | Do audiences span communities? | [../for-researchers/methodology.md](../for-researchers/methodology.md) (Commenter Overlap Analysis) |
| **Reproducible sampling** | Which subset, chosen how, reproducibly? | [../for-researchers/sampling.md](../for-researchers/sampling.md) |
| **Graph-RAG intelligence agent** | What is known about a subject/audience/ecosystem from the web? | [../for-developers/ingestion-and-agent.md](../for-developers/ingestion-and-agent.md) |
| **Document ingestion (Tavily → Qdrant)** | What web content is searchable by meaning? | [../for-developers/ingestion-and-agent.md](../for-developers/ingestion-and-agent.md) |

---

## The representation chain (whole system)

```
recommendation edges (observed platform behavior)
  → directed graph → Louvain communities (structure)
  → transcripts (content) → chunks → embeddings → mean-pooled video vectors (meaning)
  → cosine similarities within vs between communities (structure × meaning)
  → permutation null + z / p (is the difference real?)
  → S1–S5 signals + composite (echo-chamber-like dynamics?)
  → research evidence (always with availability status + provenance)
```

The central scientific move of this repository is the middle step: **structure and meaning are measured independently, then compared**. See [Structure vs Meaning](../concepts/structure-vs-meaning.md) for why that separation matters.

---

## AI vs deterministic logic (global rule)

| Operation | Nature |
|---|---|
| Transcript embedding (Gemini `gemini-embedding-2-preview`) | Learned model — the only neural step in the CSS pipelines |
| LLM agents (GPT-Researcher / LangGraph intelligence pipeline) | Generative model — confined to `RetrievalPipeline/` + `gpt-researcher/`, never to measurement |
| Chunking, mean pooling, cosine, pair sampling, permutation test | Deterministic transformations / statistics |
| Louvain (seed=42), PageRank, HITS, centrality battery | Deterministic graph algorithms |
| Transcript retrieval, BFS crawl, fallback extraction | Retrieval / orchestration, deterministic given the same platform response |
| Echo composite score | Deterministic weighted mean over available signals |

Nothing in the measurement path asks an LLM to judge, classify, or explain. Similarity is computed, not generated. That is deliberate — see [Structure vs Meaning](../concepts/structure-vs-meaning.md).

---

## Conventions used in every pipeline document

- **Parameters are verbatim.** Defaults are quoted exactly as implemented (`seed=42`, `8000/200`, `0.10`, `10_000`, …) with file references.
- **Missing data is never zero.** Statuses are `available | missing | unsupported | insufficient_sample`, per [Reproducibility](../for-researchers/reproducibility.md).
- **Formulas are the implemented ones.** No invented math; each formula names what its vectors/scalars represent.
- **Limitations sit with the method**, not in an appendix nobody reads.
