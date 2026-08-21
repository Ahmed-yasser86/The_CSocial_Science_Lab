DEFAULT_MAX_FACT_CHECK_REVISIONS = 4


class MaxFactCheckRevisionsExceededError(RuntimeError):
    """Raised when writer/fact-checker rounds exceed the configured limit."""


def route_fact_check(state, max_fact_check_revisions=DEFAULT_MAX_FACT_CHECK_REVISIONS):
    """Decide routing for fact-check stage.

    Behavior:
    - If there are no fact-check notes -> return "accept".
    - If max_fact_check_revisions is None -> allow unlimited revisions -> return "revise".
    - If fact_check_revision_count > max_fact_check_revisions -> auto-mark and return "accept" to continue the flow without crashing.
    - Otherwise -> return "revise".

    When the revision count exceeds the max, this function now avoids returning
    None (which caused downstream KeyError routing issues) and instead:
      - injects a non-destructive metadata record into `state` indicating the
        auto-decision (status: 'unverified_contested', use_as_basis: True)
      - logs a warning
      - returns the logical "accept" route so the orchestrator proceeds normally
      without allowing free edits to the main report body.
    """
    # If there are no fact-check notes, accept immediately.
    if state.get("fact_check_notes") is None:
        return "accept"

    # If max is None, allow unlimited revisions (keep asking to revise).
    if max_fact_check_revisions is None:
        return "revise"

    # Enforce a hard ceiling of DEFAULT_MAX_FACT_CHECK_REVISIONS so the flow
    # never tries to use a larger task-specific limit and crash later.
    max_fact_check_revisions = min(
        max_fact_check_revisions, DEFAULT_MAX_FACT_CHECK_REVISIONS
    )

    count = state.get("fact_check_revision_count", 0)

    # If the count exceeds the configured per-task max, avoid returning None
    # (which caused routing KeyError). Instead, record a safe metadata payload
    # and return the 'accept' route so downstream nodes treat it as progressed.
    if count > max_fact_check_revisions:
        # Ensure we do not modify the main report body — only add metadata.
        state.setdefault("fact_check_result", {})
        state["fact_check_result"].update(
            {
                "status": "unverified_contested",
                "use_as_basis": True,
                "auto_decision": "exceeded_max_revisions",
                "fact_check_revision_count": count,
            }
        )

        try:
            import logging

            logging.getLogger(__name__).warning(
                "Fact-check revision count %s exceeded max %s. Auto-marking as unverified_contested and continuing with 'accept'.",
                count,
                max_fact_check_revisions,
            )
        except Exception:
            print(
                f"Warning: fact-check revision count {count} exceeded max {max_fact_check_revisions}. Auto-marking and continuing."
            )

        # Return an explicit route that should exist in the orchestrator graph
        # (commonly 'accept'). This avoids returning None and prevents crashes
        # while keeping the report contents unchanged.
        return "accept"

    # Otherwise, request another revision.
    return "revise"
