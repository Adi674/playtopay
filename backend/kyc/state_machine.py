"""
State machine for KYC submission lifecycle.

This is the SINGLE source of truth for all state transitions.
No other part of the codebase should modify submission.status directly —
always call transition() so enforcement and notification logging happen together.

Legal transitions:
    draft               → submitted
    submitted           → under_review
    under_review        → approved | rejected | more_info_requested
    more_info_requested → submitted
    approved            → (terminal — no outbound transitions)
    rejected            → (terminal — no outbound transitions)
"""

from django.utils import timezone


class InvalidTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""
    pass


# The entire state machine lives in this one dict.
# Key = current state, Value = list of valid next states.
VALID_TRANSITIONS = {
    "draft":                ["submitted"],
    "submitted":            ["under_review"],
    "under_review":         ["approved", "rejected", "more_info_requested"],
    "more_info_requested":  ["submitted"],
    "approved":             [],   # terminal
    "rejected":             [],   # terminal
}

# Human-readable state labels for error messages
STATE_LABELS = {
    "draft":                "Draft",
    "submitted":            "Submitted",
    "under_review":         "Under Review",
    "more_info_requested":  "More Info Requested",
    "approved":             "Approved",
    "rejected":             "Rejected",
}


def get_allowed_transitions(current_state: str) -> list[str]:
    """Return the list of states this submission can move to."""
    return VALID_TRANSITIONS.get(current_state, [])


def can_transition(current_state: str, new_state: str) -> bool:
    """Return True if the transition is legal, False otherwise."""
    return new_state in get_allowed_transitions(current_state)


def transition(submission, new_state: str, actor=None, note: str = "") -> None:
    """
    Attempt to move a submission to new_state.

    - Validates the transition against VALID_TRANSITIONS.
    - Raises InvalidTransitionError (HTTP 400) on illegal moves.
    - Saves the submission and logs a notification event.
    - Sets submitted_at timestamp when moving to 'submitted'.

    Args:
        submission: KYCSubmission instance
        new_state:  Target state string
        actor:      User performing the transition (for audit log)
        note:       Optional reviewer note (reason for rejection, etc.)

    Raises:
        InvalidTransitionError: if the transition is not allowed
    """
    current = submission.status
    allowed = get_allowed_transitions(current)

    if new_state not in allowed:
        if not allowed:
            detail = f"'{STATE_LABELS.get(current, current)}' is a terminal state — no further transitions are possible."
        else:
            allowed_labels = [STATE_LABELS.get(s, s) for s in allowed]
            detail = (
                f"Cannot move from '{STATE_LABELS.get(current, current)}' "
                f"to '{STATE_LABELS.get(new_state, new_state)}'. "
                f"Allowed next states: {', '.join(allowed_labels)}."
            )
        raise InvalidTransitionError(detail)

    # Stamp submitted_at the first time a merchant submits
    if new_state == "submitted" and submission.submitted_at is None:
        submission.submitted_at = timezone.now()

    submission.status = new_state

    if note:
        submission.reviewer_note = note

    submission.save(update_fields=["status", "submitted_at", "reviewer_note", "updated_at"])

    # Log notification event (import here to avoid circular imports)
    from kyc.notifications import log_notification
    log_notification(submission=submission, new_state=new_state, actor=actor)
