"""
Notification event logger.
Records what emails/webhooks *should* be sent — does not actually send.
"""
from kyc.models import NotificationEvent

# Map state → event_type label
STATE_EVENT_MAP = {
    "submitted":            "kyc_submitted",
    "under_review":         "kyc_under_review",
    "approved":             "kyc_approved",
    "rejected":             "kyc_rejected",
    "more_info_requested":  "kyc_more_info_requested",
}


def log_notification(submission, new_state: str, actor=None) -> NotificationEvent | None:
    """
    Create a NotificationEvent record for the given state transition.
    Returns the created event, or None if no mapping exists.
    """
    event_type = STATE_EVENT_MAP.get(new_state)
    if not event_type:
        return None

    payload = {
        "submission_id": submission.id,
        "merchant_id": submission.merchant_id,
        "merchant_username": submission.merchant.username,
        "new_state": new_state,
        "reviewer_note": submission.reviewer_note,
    }
    if actor:
        payload["actor_id"] = actor.id
        payload["actor_username"] = actor.username

    return NotificationEvent.objects.create(
        merchant=submission.merchant,
        event_type=event_type,
        payload=payload,
    )
