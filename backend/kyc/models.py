from django.db import models
from django.conf import settings
from django.utils import timezone


class KYCSubmission(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_UNDER_REVIEW = "under_review"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_MORE_INFO = "more_info_requested"

    STATUS_CHOICES = [
        (STATUS_DRAFT,      "Draft"),
        (STATUS_SUBMITTED,  "Submitted"),
        (STATUS_UNDER_REVIEW, "Under Review"),
        (STATUS_APPROVED,   "Approved"),
        (STATUS_REJECTED,   "Rejected"),
        (STATUS_MORE_INFO,  "More Info Requested"),
    ]

    BUSINESS_TYPE_CHOICES = [
        ("agency",      "Agency"),
        ("freelancer",  "Freelancer"),
        ("ecommerce",   "E-Commerce"),
        ("saas",        "SaaS"),
        ("other",       "Other"),
    ]

    # Ownership
    merchant = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kyc_submission",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_reviews",
        limit_choices_to={"role": "reviewer"},
    )

    # State
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    reviewer_note = models.TextField(blank=True, default="")

    # Personal details
    full_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    # Business details
    business_name = models.CharField(max_length=200, blank=True)
    business_type = models.CharField(
        max_length=50, choices=BUSINESS_TYPE_CHOICES, blank=True
    )
    monthly_volume_usd = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    # Document URLs (stored as Supabase public URLs, or local path in dev)
    pan_document_url = models.URLField(max_length=500, blank=True)
    aadhaar_document_url = models.URLField(max_length=500, blank=True)
    bank_statement_url = models.URLField(max_length=500, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["submitted_at", "created_at"]

    def __str__(self):
        return f"KYC({self.merchant.username}) — {self.status}"

    @property
    def is_at_risk(self) -> bool:
        """
        Dynamically computed — never stored.
        Returns True if submission has been in queue >24 hours without resolution.
        """
        if self.status not in (self.STATUS_SUBMITTED, self.STATUS_UNDER_REVIEW):
            return False
        if self.submitted_at is None:
            return False
        threshold = timezone.now() - timezone.timedelta(hours=24)
        return self.submitted_at < threshold

    @property
    def time_in_queue_seconds(self) -> float | None:
        """Seconds since submission. None if not yet submitted."""
        if self.submitted_at is None:
            return None
        return (timezone.now() - self.submitted_at).total_seconds()


class NotificationEvent(models.Model):
    """
    Audit log of notification events that should be sent to merchants.
    We record here instead of actually sending emails.
    """
    merchant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_events",
    )
    event_type = models.CharField(max_length=100)  # e.g. 'kyc_submitted', 'kyc_approved'
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"Notification({self.merchant.username}, {self.event_type}, {self.timestamp})"
