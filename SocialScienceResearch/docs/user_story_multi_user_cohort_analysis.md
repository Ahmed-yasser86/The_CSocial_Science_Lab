# User Story 2 — Multi-User Cohort Behavioral Analysis, Interaction Networks & Cross-Channel Profiling

## User Story

**As a Computational Social Science researcher,**

I want to define large cohorts of YouTube users based on configurable research criteria, collect and analyze their observable comments and replies across precisely selected videos, channels, and time periods, and compare their interaction patterns both individually and collectively,

**so that I can study audience structure, user-to-user interaction networks, cross-channel participation, behavioral differences between users, shared audiences and videos, and the observable linguistic and interaction patterns that characterize how users engage with different creators and content ecosystems.**

The resulting dataset should provide the structured behavioral foundation required for **future user simulation / behavioral-profile modeling**, without implementing the simulation layer itself.

---

## 1. Multi-User Cohort Selection

Users may be selected by configurable criteria:

* Commented on specific videos.
* Commented within a specific date range.
* Participated in a specific channel.
* Participated across multiple channels.
* Minimum number of interactions.
* Minimum number of videos participated in.
* Appearing in a specific research cohort.
* Random / stratified sampling.
* Particular interaction pattern.
* Predefined list of identifiers.

Criteria may be combined.

---

## 2. Video Selection Must Be Fully Controllable

The user cohort analysis must inherit complete existing video-selection capabilities: channel(s), date range, upload period, duration, views (top/bottom), engagement, random/stratified sampling, number of videos, other metadata. Example: "All videos by Channels A, B, C between 2020–2023, longer than 10 minutes, top 20% by views." Result = observation universe.

---

## 3. Full Comment-Level Filtering

Fine-grained comment selection criteria:

* Temporal: date range, year, month, relative period after publication, before/after event, latest/oldest N%.
* Interaction type: root comments only / replies only / both / all.
* Engagement: min/max likes, top/bottom N%, min/max replies, most/least-replied.
* Content metadata: length, timestamp, author, parent comment, thread depth.

---

## 4. User Cohort → Complete Interaction Dataset

```text
Research Cohort → Selected Videos → Selected Comments → Participating Users → User Behavioral Dataset
```

Every interaction retains complete context: User, Comment, Parent Comment, Video, Channel, Timestamp, Engagement, Interaction Type. Must **not** flatten to user-level statistics only.

---

## 5. Population-Level Behavioral Analysis

Aggregate statistics and distributions for the cohort: total interactions, comments, replies, comment/reply ratio, videos, channels, interaction frequency, active periods, engagement, comment length, unique conversation partners / videos / channels.

---

## 6. User-to-User Social Network Construction

Construct interaction network from reply relationships: User A → User B. Support user nodes, reply relationships, frequency, timestamps, shared videos, shared channels, conversation relationships. Every edge traces back to underlying comments.

---

## 7. Interaction Weighting

Weighted relationships (User A → User B, replies = 37), retaining: number of replies, videos, channels, first/last interaction, temporal distribution, associated comments/threads. Distinguish one-time vs repeated relationships.

---

## 8. Audience / User Overlap

For each pair/group of users: shared videos, shared channels, shared creators, shared time periods, shared interaction environments. Measurable metrics: number of shared videos/channels, shared-user counts, Jaccard similarity, other configurable measures.

---

## 9. User × Channel Behavioral Matrix

Matrix of users × channels with interaction counts; drill-down per user/channel pair: comments, replies, videos, frequency, active periods, engagement, shared participants, interaction partners.

---

## 10. Same User, Different Channel Behavior

Isolate one user and compare behavior across selected channels (comments, replies, videos per channel). Preserve actual comments/contexts.

---

## 11. Same User, Different Videos Within One Channel

Intra-channel behavioral comparison across different videos from the same creator.

---

## 12. User Interaction Profile

Observable behavioral profile from collected data: interaction volume, comment/reply distribution, video participation, channel participation, temporal activity, engagement received, conversation participation, interaction partners, shared videos/channels. Each statistic traceable to raw interactions.

---

## 13. Observable Linguistic / Interaction Pattern Dataset

Preserve exact comment text, reply text, parent-comment text, timestamp, video/channel context, interaction type, conversation partner. Foundation for future linguistic-pattern analysis (no semantic classification now).

---

## 14. Creator-Specific Behavioral Analysis

Analyze how the same user/cohort interacts with different creators (mostly root comments vs mostly replies vs low frequency). Compare interaction structures across creator ecosystems.

---

## 15. Cross-Channel User Movement

Expose temporal transitions in channel participation (2020: A; 2021: A+B; 2022: B+C; 2023: C). Identify new/continued/reduced participation, overlap, repeated participation. Observable trajectories, not identity claims.

---

## 16. Cohort-to-Cohort Comparison

Create multiple user cohorts and compare: network structure, interaction volume, reply behavior, shared channels/videos, user overlap, temporal activity, interaction concentration.

---

## 17. Network Analysis

Metrics: degree, weighted degree, in/out-degree, betweenness, closeness, PageRank/eigenvector, density, connected components, community structure, reciprocity, clustering. Preserve temporal and interaction-level provenance.

---

## 18. Temporal Network Analysis

Analyze network across time: relationships emerged/disappeared, users became more central, communities expanded/contracted, cross-channel relationships changed, interaction density evolved.

---

## 19. Future Behavioral Simulation Foundation

Preserve observable behavioral evidence: interaction history, video preferences, channel participation, comment/reply behavior, temporal activity, interaction partners, shared videos/channels, raw linguistic data. No simulation implementation now.

---

## 20. Future Semantic Analysis Layer

**Not implemented now.** Preserve raw textual and contextual data: comment text + reply context + video context + channel context + timestamp + interaction relationship.

---

## Acceptance Criteria

1. Select a large cohort of users via configurable criteria.
2. Define exact videos analyzed.
3. Apply independent comment-level filters after video selection.
4. Choose root comments only / replies only / both / all.
5. Filter comments by arbitrary temporal criteria.
6. Filter by engagement and percentile criteria.
7. Retrieve complete observable interaction history for the cohort.
8. Preserve complete text of every relevant comment and reply.
9. Preserve parent-comment text and author for replies.
10. Determine root vs reply behavior.
11. Track users across multiple videos.
12. Track users across channels when reliably identifiable.
13. Compare same user across channels.
14. Compare same user across videos within one channel.
15. Compare multiple users.
16. Identify shared videos between users.
17. Identify shared channels between users.
18. Calculate user overlap and similarity.
19. Construct user-to-user interaction networks from replies.
20. Weight relationships by interaction frequency.
21. Analyze network structure and communities.
22. Analyze network evolution across time.
23. Compare different user cohorts.
24. Compare different video cohorts.
25. Preserve raw interaction evidence behind every result.
26. Export user/interactions structure for future graph analysis.
27. Preserve data required for future behavioral-profile/simulation layer.
28. Keep semantic inference outside current scope while preserving raw data.

---

## Core Research Capability

From "What happened in this video?" → "Who participated?" → "How did these users interact?" → "Which videos and channels do they share?" → "Does the same user behave differently with different creators or content?" → "How do individual patterns combine into evolving social networks and observable behavioral profiles across the YouTube ecosystem?"
