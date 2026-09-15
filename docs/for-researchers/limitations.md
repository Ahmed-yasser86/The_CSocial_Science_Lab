# Limitations & Threats to Validity

> The skeptic should find nothing hidden. Consolidated from the per-method limitations across the docs; each method section links back here and to its canonical page.

**Rule of the repo:** missing data is `available | missing | unsupported` (never zero, never imputed); structural signals are observed proxies (never proof of cognition or causation); sampling fractions are cost bounds (never representativeness claims). See [Reproducibility](reproducibility.md) for the enforcement mechanisms.

---

## Measurement

- **Co-commenting is indirect.** It captures shared participation, not reply structure, conversation quality, sentiment, or interaction strength. Lurkers (non-commenting viewers) are entirely absent. Identity resolution is `author_id`-first with `author_name` fallback — name changes and collisions blur identities.
- **Embeddings measure topical similarity, not ideology.** Cosine proximity = shared topic/vocabulary/framing in the model's space. Opposite sides of an argument routinely embed nearby. Model-relative: change the projector, change the geometry. Mean pooling additionally discards order and emphasis.
- **Recommendation edges are platform snapshots.** One crawl = one observation point under one controlled context. Personalized, time-varying, extraction best-effort. No user consumption, belief, or influence is observed.

## Sampling & coverage

- Only commented videos appear in the social network; only captioned videos in the semantic analysis. Commenters self-select; they are not the audience.
- Publicly accessible data only. Acquisition scope, ceilings (`MAX_COMMENTS_PER_VIDEO = 10000`, enrich caps), and opt-in transcripts (`DEFAULT_COLLECT_TRANSCRIPTS = False`) bound what exists to analyze.
- `sampling_fraction = 0.10`, pair caps, per-community caps, transcript budgets bound **cost**, not bias. Nothing about a 10% pair sample is automatically representative.

## Platform & temporal

- YouTube's API/page structure drifts; the three-layer fallback degrades gracefully but cannot guarantee completeness.
- Longitudinal analysis needs repeated crawls with temporal gaps; comment velocity and engagement are time-dependent.
- `MAX_LAYERS_TOTAL = 10` caps echo-analysis depth.

## Network-analytic

- Every graph decision (weight grammar, threshold, projection, bipartite→unipartite) shapes the structure it claims to measure. The co-comment graph is a projection with structural assumptions baked in.
- One partition, one seed: Louvain `seed=42` yields one community assignment; other algorithms, resolutions, and seeds differ. Findings are conditional on that partition.
- Permutation nulls assume label exchangeability; violated when labels correlate with availability or length.

## Causal & generalizability

- **Observational data cannot establish causation.** No manipulation, no counterfactual: recommendation structures do not show recommendation *effects*; community separation does not show psychological *isolation*; semantic similarity does not show ideological *polarization*.
- Findings are dataset-specific (domain, period, context). The **framework** is generalizable; any **result** is not, until replicated across domains, periods, and contexts.

## Composite & interpretive

- Echo-chamber verdicts (S1–S5 weights `0.35/0.30/0.20/0.15/0.15`, bands `<0.40 / 0.40–0.60 / 0.60–0.75 / >0.75`) are heuristic combinations, not validated instruments. A missing core signal (S1–S4) forces `inconclusive` — by design.
- `1.0` semantic similarity = geometric fit, not narrative agreement. High within-community similarity = content homophily (observed), nothing more, until paired with behavioral evidence.

---

## Per-method canonical pages

| Concern | Canonical detail |
|---|---|
| Content homophily | [Content-homophily pipeline](../pipelines/content-homophily.md) (§10) |
| Recommendation crawling | [Recommendation crawling](../pipelines/recommendation-crawling.md) (§9) |
| Echo-chamber signals | [Echo-chamber detection](echo-chamber.md) |
| Social / overlap methods | [Methodology](methodology.md) (per-section Limitations) |
| Sampling | [Sampling](sampling.md) |
| Ethics & scope | [Ethics](ethics.md) |
