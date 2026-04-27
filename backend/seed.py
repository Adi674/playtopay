"""
Seed script — creates test data for reviewers to poke around.

Run: python manage.py shell < seed.py
Or:  python seed.py (from backend directory with venv active)

Credentials after seeding:
  reviewer1 / Reviewer@123
  merchant1 / Merchant@123  (submission: draft)
  merchant2 / Merchant@123  (submission: under_review, with docs)
"""
import os
import sys
import django

# Allow running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.utils import timezone
from datetime import timedelta
from users.models import CustomUser
from kyc.models import KYCSubmission, NotificationEvent
from rest_framework.authtoken.models import Token


def seed():
    print("🌱 Seeding database...")

    # Clear existing test data (idempotent)
    for username in ["reviewer1", "merchant1", "merchant2"]:
        CustomUser.objects.filter(username=username).delete()

    # ── Reviewer ──────────────────────────────────
    reviewer = CustomUser.objects.create_user(
        username="reviewer1",
        email="reviewer1@playto.so",
        password="Reviewer@123",
        role="reviewer",
        first_name="Riya",
        last_name="Sharma",
    )
    Token.objects.get_or_create(user=reviewer)
    print(f"  ✓ Reviewer created: reviewer1 / Reviewer@123")

    # ── Merchant 1 — draft submission ─────────────
    merchant1 = CustomUser.objects.create_user(
        username="merchant1",
        email="merchant1@example.com",
        password="Merchant@123",
        role="merchant",
        first_name="Arjun",
        last_name="Patel",
    )
    Token.objects.get_or_create(user=merchant1)
    sub1 = KYCSubmission.objects.create(
        merchant=merchant1,
        status="draft",
        full_name="Arjun Patel",
        email="merchant1@example.com",
        phone="+91 98765 43210",
        business_name="Patel Digital Agency",
        business_type="agency",
        monthly_volume_usd=8000,
        # No documents yet — draft
    )
    print(f"  ✓ Merchant 1 created: merchant1 / Merchant@123  (status: draft, id: {sub1.id})")

    # ── Merchant 2 — under_review, submitted 30h ago (AT RISK) ─────────
    merchant2 = CustomUser.objects.create_user(
        username="merchant2",
        email="merchant2@example.com",
        password="Merchant@123",
        role="merchant",
        first_name="Priya",
        last_name="Singh",
    )
    Token.objects.get_or_create(user=merchant2)
    sub2 = KYCSubmission.objects.create(
        merchant=merchant2,
        reviewer=reviewer,
        status="under_review",
        full_name="Priya Singh",
        email="merchant2@example.com",
        phone="+91 87654 32109",
        business_name="Singh Freelance Studio",
        business_type="freelancer",
        monthly_volume_usd=3500,
        pan_document_url="https://via.placeholder.com/800x600.png?text=PAN+Document",
        aadhaar_document_url="https://via.placeholder.com/800x600.png?text=Aadhaar+Document",
        bank_statement_url="https://via.placeholder.com/800x600.png?text=Bank+Statement",
        submitted_at=timezone.now() - timedelta(hours=30),  # AT RISK — >24h in queue
    )
    # Log notification events for sub2
    NotificationEvent.objects.create(
        merchant=merchant2,
        event_type="kyc_submitted",
        payload={"submission_id": sub2.id, "new_state": "submitted"},
    )
    NotificationEvent.objects.create(
        merchant=merchant2,
        event_type="kyc_under_review",
        payload={"submission_id": sub2.id, "new_state": "under_review", "actor": "reviewer1"},
    )
    print(f"  ✓ Merchant 2 created: merchant2 / Merchant@123  (status: under_review, AT RISK, id: {sub2.id})")

    # Create django admin superuser
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", "admin@playto.so", "Admin@123", role="reviewer")
        print("  ✓ Django admin superuser: admin / Admin@123  → /admin/")

    print("\n✅ Seed complete!")
    print("\n📋 Login credentials:")
    print("  Role       Username    Password")
    print("  ─────────────────────────────────")
    print("  Reviewer   reviewer1   Reviewer@123")
    print("  Merchant   merchant1   Merchant@123  (draft)")
    print("  Merchant   merchant2   Merchant@123  (under_review / AT RISK)")


if __name__ == "__main__":
    seed()
