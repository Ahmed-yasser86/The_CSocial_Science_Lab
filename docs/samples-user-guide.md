# Research Samples — User Guide

The **Research Samples** page (`/samples`) is where you create, inspect and
compare **reproducible samples** drawn from the YouTube data the platform has
collected (comments, videos, channels, recommendations).

> Everything is immutable: once saved, a sample never changes. Its *exact*
> membership and its definition are recorded verbatim so the design can be
> audited and re-run later.

The page is split into two tabs:

- **Sampling Workbench** — build a filtered population, choose a sampling
  method, and preview the result live.
- **Sample Library** — browse the samples you have saved, view their members,
  and compare two or more samples for overlap.

Header text reads: *"Create reproducible samples with advanced filtering,
combine into datasets, and organize into projects."*

---

## 1. Sampling Workbench

This is the tab you land on by default. It is laid out in three columns:

- **Left column** — Presets, Saved Queries, and the **Scope** selector.
- **Middle column** — **Filters** and **Sampling Method**.
- **Right column** — **Live Preview**.

Above all three sits a toolbar with **Save Query**, **Refresh Preview**, and
**Run Sample**. Below the columns is the **Labels & Save Options** card.

The workbench currently operates on **comments** (the page opens it with
`entityType="comment"`).

### 1.1 Presets (left column)

The **Presets** card applies a combination of scope, filters and sampling
method in one click. Clicking a preset reconfigures the whole workbench.

| Preset | What it does |
|---|---|
| **By Author(s)** — "Sample comments from specific users" | Sets scope to **By Author** and samples the full population of matching comments. |
| **By Channel** — "All comments in selected channels" | Sets scope to **By Channel** (choose one or more channels) and returns all their comments. |
| **By Video Criteria** — "Filter by video attributes (duration, views, date)" | Switches to the **Custom** scope; use the filter sections below to define the population. |
| **Random Sample** — "Random selection from all data" | Uses **All Data** scope with the **Random Sample** method, size 500. |
| **Stratified by Time** — "Balanced across months/weekdays" | Uses **All Data** with **Stratified Sample**, stratified by **Upload Month**, 50 per stratum. |
| **High Engagement** — "Comments with many likes/replies" | Applies Comment Filters (min **10 likes**, min **5 replies**, **Root comments only**) and takes a **Random Sample** of 500. |

If you save a query (toolbar → **Save Query**), it appears in a **Saved
Queries** card below Presets; click it to reload that exact workbench state
(note: saved queries live for the current session only).

### 1.2 Scope selector (left column)

**Scope Type** has four buttons:

- **All Data** — the whole collected corpus.
- **By Channel** — pick channels from a search box (**"Search and select
  channels…"**); the count below updates ("N channel(s) selected").
- **By Author** — type an author ID and press Enter (**"Enter author ID and
  press Enter…"**). Each added ID becomes a removable chip; the count below
  shows "N author(s) selected".
- **Custom** — a message explains: *"Use the filters below to define a custom
  scope."* Scope is then shaped entirely by the filter sections.

### 1.3 Filters (middle column)

The **Filters** card contains four collapsible sections.

**Author Filters**
- **Exclude video author** — checkbox to exclude comments made by the video
  uploader.
- **Exclude Author IDs** — comma-separated IDs to exclude (*"Enter author IDs,
  separated by commas"*).
- **Include Author IDs** — comma-separated IDs to include.

**Video Filters**
- **Duration** — dropdown: *Any duration*, *Short (<60s)*, *Medium (1-5min)*,
  *Long (5-20min)*, *Very long (>20min)*.
- **Views Range** — Min views / Max views numeric fields.
- **Upload Date Range** — two date pickers.
- **Tags** — add tags one at a time; a video must have at least one of them.
- **Category** — free-text category name.

**Comment Filters**
- **Likes Range** — Min likes / Max likes.
- **Replies Range** — Min replies / Max replies.
- **Comment Type** — *All comments*, *Root comments only*, *Replies only*.
- **Keywords** — add keywords one at a time; comments must contain at least
  one.
- **Keyword Match Mode** — *Match any* or *Match all* keywords.

**Temporal Filters**
- **Video Published Date** — two date pickers.
- **Comment Date** — note that comment dates use the global date filter in the
  main data panel rather than this screen.

### 1.4 Sampling Method (middle column)

Pick how records are chosen from the filtered population.

- **Full Population** — "Return all matching records. No sampling applied."
- **Random Sample** — "Select a random subset of the population." Reveals:
  - **Sample Size** (a count, placeholder `500`).
  - **Or Percent (%)** (placeholder `10`) — an alternative to a fixed count.
  - **Seed (optional)** (placeholder *Auto-generated*) — leave blank for a new
    random seed each run; set a number to reproduce the same draw.
- **Stratified Sample** — "Balanced selection across groups (strata)." Reveals:
  - **Stratification Variable** — *Upload Month*, *Upload Weekday*, *Channel*,
    *Author*, *Views Quartile*.
  - **Samples Per Stratum** (placeholder `50`).

### 1.5 Live Preview (right column)

The **Live Preview** card shows what the current configuration would return:

- **Population** — number of records matching your filters.
- **Sample size** — how many would be in the sample.
- **Sample IDs** — the first 10 IDs, with "**+ N more**" when larger.

Before the first run the IDs area reads *"Run the sample to see IDs"*.
Use **Refresh Preview** (or the refresh icon in the card) to update the numbers
after changing scope, filters or method — nothing is saved by doing this; it is
just a dry run.

### 1.6 Labels & Save Options (below the columns)

The **Labels & Save Options** card attaches metadata so a sample is easy to
identify and reproduce later.

**Research Labels**
- **Research Question** — pick a suggested question or type your own
  (*"Select or type custom..."*). Suggestions include: *What is the
  distribution of opinions on X?*, *How do engagement patterns differ across
  groups?*, *What topics dominate the conversation?*, *How does sentiment vary
  over time?*.
- **Methodology** — pick from *Random sampling*, *Stratified sampling*, *Quota
  sampling*, *Snowball sampling*, *Convenience sampling*, or *Custom*.
- **Notes** — a free-text area (*"Additional notes..."*).

**Custom Labels**
- Click **Add Custom Label**, give it a **Key** (e.g. `population`,
  `timeframe`) and a **Value**. Labels appear as `key = value` chips and can be
  removed.

**Save As**
- **Individual Sample** — "Save as a standalone sample in the library."
- **Add to Dataset** — "Combine with other samples into a dataset." Reveals a
  **Dataset Name** field, an **Or Select Existing** dropdown, and a button
  *"Create Dataset with N members"*.

> Current behavior: the **Datasets** and **Projects** tabs inside the workbench
> are placeholders ("management coming soon"), and the "Create Dataset" action
> is not yet wired to storage. To persist a sample today, use the **New
> sample** dialog in the Sample Library (section 2.1).

---

## 2. Sample Library

The **Sample Library** tab lists every persisted sample. It has two sub-tabs:
**Library** and **Compare**.

### 2.1 New sample (persisting a sample)

Click **New sample** to open a dialog titled *"New sample"*:

> "Persist an immutable, reproducible sample. Member ids and criteria are
> recorded verbatim so the design can be audited and re-run."

Fields:

- **Entity type** — *Video*, *Comment*, *Channel*, *Recommendation*.
- **Strategy** — *Simple random*, *Systematic*, *Stratified*, *Cluster*,
  *Convenience*.
- **Seed (optional)** — a number; blank is recorded as no seed.
- **Population size** — the size of the population the sample was drawn from
  (required).
- **Population query hash (optional)** — a sha256 of the population
  definition.
- **Member ids** — the actual members, pasted id-by-id ("id_1, id_2, id_3 …
  space or comma separated").
- **Criteria JSON (optional)** — the definition as JSON, e.g.
  `{"sample":"video comments"}`.

Press **Save sample** to persist it. A success message shows the new sample id
and member count.

### 2.2 The Library list

Each sample is a card showing:

- Its **sample id** (e.g. a run id), with badges for **entity type** and
  **strategy**.
- Stats: **Population**, **Sample size**, **Seed** (dash when none), and
  **Overflow** (*chunked* or *single*).
- The saved **criteria JSON** (when present).
- A **created** timestamp (UTC) and a **Members** button.

**Members** opens a dialog with the *"Ordered member ids of the sample (N)"*
in a numbered table. Use the trash icon on a card to delete that sample.

If you have no samples yet the library shows: *"No samples yet — Create an
immutable sample to preserve a population definition and its exact
membership."*

### 2.3 Compare

The **Compare** tab computes how much saved samples overlap:

- Click two or more sample id chips, then **Compare selected**.
- ("Select two or more samples to compute pairwise overlap, union and Jaccard
  similarity.")

The **Overlap result** shows badges for the number of samples, the **union**
size, and **shared by all** count, plus a per-pair table: **Sample A | Sample B
| Intersection | Union | Jaccard**. When saved criteria differ, a
"Criteria differences vs first sample" list highlights which fields changed.
Use **Re-run** to compare again or **Clear selection** to start over.

---

## 3. Glossary

| Term | Meaning |
|---|---|
| **Sample** | A persisted, immutable set of members drawn from a defined population. |
| **Population** | The set of records that match your scope + filters before sampling. |
| **Member id** | The id of one entity (comment, video, channel…) inside a sample. |
| **Seed** | A number that makes a random/stratified draw reproducible; same seed ⇒ same members. |
| **Stratum** | A group used for balanced selection (e.g. upload month). |
| **Root comment** | A top-level comment (as opposed to a reply to another comment). |
| **Overflow** | Whether the result was stored as a single blob or split into chunk(s). |
| **Jaccard** | Overlap metric = intersection ÷ union of two samples. |
| **Criteria JSON** | The saved definition (filters, strategy, seed…) attached to a sample. |

---

## 4. Known behaviors & gotchas

- **The Workbench preview does not save anything.** *Run Sample* / *Refresh
  Preview* only compute a preview. Persist samples via **Sample Library →
  New sample**.
- In the **Random Sample** method you can supply a **Sample Size** *or* a
  **Percent**, or leave both to the preset default (500).
- Leave **Seed** blank for a new random draw each run. To reproduce a preprint
  or paper figure later, record the seed value you used.
- **Saved Queries** are held in memory for the current browser session only —
  they are not stored on the server.
- **Entity type** in the workbench is fixed to **comments** on this page; the
  **New sample** dialog also supports Video, Channel and Recommendation.
- **Datasets** and **Projects** tabs and the "Create Dataset with N members"
  button are not yet functional; datasets are listed as "coming soon".
- The **High Engagement** preset only targets root comments; replies are
  excluded by design.
- Samples are immutable — you cannot edit one after saving; delete and recreate
  instead.