DEFAULT_MAX_DRAFT_REVISIONS = 3


class MaxDraftRevisionsExceededError(RuntimeError):
    """Raised when reviewer/reviser rounds exceed the configured draft limit."""


def route_draft_review(draft, max_draft_revisions=DEFAULT_MAX_DRAFT_REVISIONS):
    """Return accept | revise for the editor review loop.

    * ``review is None`` → accept.
    * ``max_draft_revisions is None`` → allow endless revision loop.
    * ``draft_revision_count >= max`` → force-accept to avoid crashing the workflow.
    """
    if draft.get("review") is None:
        return "accept"

    if max_draft_revisions is None:
        return "revise"

    count = draft.get("draft_revision_count", 0)
    if count > max_draft_revisions:
        try:
            import logging

            logging.getLogger(__name__).warning(
                "Draft revision count %s exceeded max %s. Auto-accepting to keep the workflow running.",
                count,
                max_draft_revisions,
            )
        except Exception:
            print(
                f"Warning: draft revision count {count} exceeded max {max_draft_revisions}. Auto-accepting to keep the workflow running."
            )
        return "accept"

    return "revise"
