# User Story 1 — Advanced Commenter Behavioral Tracking & Cross-Video / Cross-Channel Analysis

## User Story

**As a Computational Social Science researcher,**

I want to select specific groups of videos from my existing research corpus using configurable selection and sampling criteria, identify specific commenters within those videos, and trace their observable interactions across videos, time periods, and channels,

**so that I can study individual digital participation patterns, compare how the same user behaves across different types of content and communities, reconstruct their observable conversation participation, and analyze how individual interactions contribute to the broader social network around the channel and its content.**

This feature extends the existing video, comment, sampling, and analytics capabilities. It does **not** replace them.

---

## 1. Custom Video Cohort for Behavioral Analysis

The researcher shall be able to define a specific subset of videos from the existing corpus before performing commenter-level analysis.

The video cohort may be selected using any combination of the existing video-selection capabilities, including:

* Specific date/time period.
* Specific channel.
* Multiple channels.
* Random sample.
* Stratified sample.
* Highest-viewed videos.
* Lowest-viewed videos.
* Highest-engagement videos.
* Lowest-engagement videos.
* Specific duration range.
* Specific upload time.
* Specific number of videos.
* Other existing video filtering criteria.

The selected cohort must become the **scope of the subsequent commenter analysis**.

### Example

> The 20 highest-viewed and 20 lowest-viewed videos from Channel A between 2020 and 2023. Then find all observable interactions made by User X across these videos.

The researcher must also be able to save and reuse the selected video cohort.

---

## 2. Individual Commenter Identification

The researcher shall be able to specify a particular commenter/user and retrieve their observable interactions within the selected research corpus.

The system should use the strongest available platform-level author identifier when available, while preserving the display name separately.

The researcher should be able to search for a specific commenter and determine:

* Which videos they interacted with.
* Which channels they interacted with.
* When they interacted.
* How they interacted.
* What they wrote.
* Whether they initiated or joined a discussion.
* Which comments they replied to.
* Who authored the comment they replied to.

The system must not treat the user's display name alone as sufficient identity resolution when a stronger platform identifier is available.

---

## 3. Complete Commenter Interaction History

For a selected commenter, the system shall retrieve all observable interactions within the selected corpus.

The interaction history must be organized across:

```text
Channel
    ↓
Video
    ↓
Interaction
    ↓
Comment / Reply
```

For every interaction, the system must preserve:

* User/author identifier when available.
* Display name.
* Comment ID.
* Video ID.
* Channel ID.
* Full comment text.
* Timestamp.
* Like count.
* Reply count.
* Interaction type.
* Parent comment ID when applicable.
* Parent comment text when applicable.
* Parent comment author when applicable.

The **full text of the user's comment is a mandatory research field**.

---

## 4. Comment vs Reply Identification

The system shall explicitly distinguish between:

### Root Comment

```text
User A
   └── Root Comment
```

### Reply

```text
User A
   └── Reply
          └── Parent Comment
```

For every reply, the researcher must be able to determine:

* The comment being replied to.
* The complete text of that comment.
* The author of that comment.
* Whether the parent comment was written by the same user.
* Whether it was written by another user.

---

## 5. Complete Conversation Context

A reply must never be returned as an isolated piece of text when its parent context is available.

```text
User B: "Original comment text..."

User A: "Reply text..."  (replied to above)
```

Preserve the relationship:

```text
User A → wrote → Reply A → replies_to → Comment B → written_by → User B
```

Navigate both directions:

**User → Reply → Parent Comment → Parent Author → Video → Channel**

and

**Video → Thread → Comments → Users → User interactions elsewhere.**

---

## 6. Cross-Video User Tracking

Follow a selected commenter across all relevant videos within the same channel:

```text
Channel A
 Video 1 → User X → Comment
 Video 7 → User X → Reply
 Video 12 → User X → Comment
 Video 31 → User X → Reply
```

Provide a consolidated behavioral view:

* Total interactions.
* Number of videos.
* Root comments.
* Replies.
* Interaction frequency.
* First and last observed interaction.
* Most active periods.
* Most interacted-with videos.
* Engagement received.
* Distribution of comments vs replies.

---

## 7. Cross-Channel User Tracking

Track the same observable commenter across multiple channels when reliably matchable:

```text
User X
 Channel A → Comment/Reply
 Channel B → Comment/Reply
 Channel C → Comment
```

Compare behavior between channels: interactions per channel, comments vs replies per channel, videos participated in per channel, frequency, temporal activity, avg/median engagement and length, types of videos, behavior changes between channels.

Must clearly distinguish **observable platform participation** from assumptions about the person's real-world identity.

---

## 8. User Behavioral Timeline

Chronological timeline per commenter. Analyze activity growth/decline, active/inactive periods, changes in comment/reply behavior, channel participation, video-selection preferences, interaction frequency.

---

## 9. User × Video Comparison

Compare behavior relative to video characteristics: high-view vs low-view, long vs short, time periods, Channel A vs B.

---

## 10. User × Cohort Analysis

Same commenter analyzed against different predefined video cohorts (top 10% views, bottom 10%, random, 2020–2021). Compare behavior across cohorts without redefining the corpus.

---

## 11. Multiple User Comparison

Compare multiple commenters: total interactions, videos, channels, root/reply counts, comment/reply ratio, active periods, frequency, length, engagement, cohorts, channel distribution, temporal activity.

---

## 12. User-to-User Interaction Relationships

Preserve observable reply relationships between accounts with evidence: reply_comment_id, parent_comment_id, reply_text, parent_comment_text, reply_author, parent_author, video_id, channel_id, timestamp. Usable later in the social-network graph.

---

## 13. Cross-Video and Cross-Channel Interaction Comparison

Compare interactions across videos in the same channel, videos across channels, users across videos, users across channels. Preserve interaction-level evidence.

---

## 14. User Behavioral Comparison Over Time

Divide a user's activity into arbitrary time periods and compare: interactions, comment/reply ratio, channels, videos, frequency, engagement, participation patterns, video-cohort participation. Longitudinal analysis of observable participation.

---

## 15. Graph Integration

All commenter-level data must be structured for direct integration into the existing Social Network Graph:

```text
User ──COMMENTED_ON──> Video
User ──WROTE──> Comment
Comment ──REPLIES_TO──> Comment
Comment ──BELONGS_TO──> Video
Comment ──WRITTEN_BY──> User
User ──REPLIED_TO──> User
Video ──PUBLISHED_BY──> Channel
```

Edges preserve: timestamp, interaction type, comment ID, parent comment ID, video ID, channel ID, comment text reference, engagement metrics.

---

## 16. Temporal Social-Interaction Analysis

Support temporal graph analysis (2020 → 2021 → 2022 → 2023): growth/decline of interaction networks, changes in active participants, user-to-user relationships, cross-channel participation, community structure, interaction density.

---

## 17. Future Extension — Semantic Comment Analysis

**Not part of the current implementation.** Preserve complete comment text and conversation context so a future NLP/LLM layer (sentiment, emotion, topic, stance, agreement, question/answer, toxicity) can be added without recollecting interactions.

---

## Acceptance Criteria

1. Define a specific video cohort using existing video filtering/sampling.
2. Select one or more specific commenters for analysis.
3. Retrieve all observable interactions within the selected corpus.
4. Preserve the complete text of every collected interaction.
5. Distinguish root comments from replies.
6. Identify the parent comment of every reply when available.
7. Retrieve the parent comment's complete text.
8. Identify the parent comment's author.
9. Determine same-author reply vs other-author reply.
10. Retrieve the complete video context for every interaction.
11. Track a commenter across multiple videos in the same channel.
12. Track across multiple channels when reliably matchable.
13. Compare same commenter across channels.
14. Compare same commenter across video cohorts.
15. Compare same commenter across time periods.
16. Compare multiple selected commenters.
17. Identify observable user-to-user reply relationships.
18. Preserve the underlying interaction evidence for every relationship.
19. Export/expose relationships for Social Network Graph construction.
20. Preserve timestamps for longitudinal analysis.
21. Keep semantic/NLP classification outside current scope while preserving raw data.