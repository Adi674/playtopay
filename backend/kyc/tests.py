"""
Tests for the KYC pipeline.
Focus areas: state machine enforcement, file validation, auth isolation.
"""
import io
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from users.models import CustomUser
from kyc.models import KYCSubmission
from kyc.state_machine import transition, InvalidTransitionError, VALID_TRANSITIONS


def make_user(username, role="merchant", password="testpass123"):
    user = CustomUser.objects.create_user(
        username=username, email=f"{username}@test.com",
        password=password, role=role
    )
    return user


def make_token(user):
    token, _ = Token.objects.get_or_create(user=user)
    return token.key


def make_submission(merchant, status="draft"):
    return KYCSubmission.objects.create(
        merchant=merchant,
        status=status,
        full_name="Test User",
        email="test@test.com",
        phone="9999999999",
        business_name="Test Biz",
        business_type="freelancer",
        monthly_volume_usd=5000,
        pan_document_url="https://example.com/pan.pdf",
        aadhaar_document_url="https://example.com/aadhaar.pdf",
        bank_statement_url="https://example.com/bank.pdf",
        submitted_at=timezone.now(),
    )


# ─────────────────────────────────────────────
# 1. State Machine Unit Tests
# ─────────────────────────────────────────────

class StateMachineUnitTests(TestCase):
    """Test the state machine in isolation — no HTTP layer."""

    def setUp(self):
        self.merchant = make_user("sm_merchant")

    def test_illegal_transition_approved_to_draft_raises(self):
        """Core requirement: approved → draft must be rejected."""
        submission = make_submission(self.merchant, status="approved")
        with self.assertRaises(InvalidTransitionError) as ctx:
            transition(submission, "draft")
        self.assertIn("terminal", str(ctx.exception).lower())

    def test_illegal_transition_rejected_to_submitted_raises(self):
        """rejected is terminal — no transitions out."""
        submission = make_submission(self.merchant, status="rejected")
        with self.assertRaises(InvalidTransitionError):
            transition(submission, "submitted")

    def test_illegal_transition_draft_to_approved_raises(self):
        """Cannot skip states — draft → approved is not allowed."""
        submission = make_submission(self.merchant, status="draft")
        with self.assertRaises(InvalidTransitionError):
            transition(submission, "approved")

    def test_legal_transition_draft_to_submitted(self):
        """Happy path: merchant submits their draft."""
        submission = KYCSubmission.objects.create(
            merchant=self.merchant, status="draft"
        )
        transition(submission, "submitted")
        submission.refresh_from_db()
        self.assertEqual(submission.status, "submitted")
        self.assertIsNotNone(submission.submitted_at)

    def test_legal_transition_under_review_to_approved(self):
        submission = make_submission(self.merchant, status="under_review")
        transition(submission, "approved", note="All docs valid.")
        submission.refresh_from_db()
        self.assertEqual(submission.status, "approved")
        self.assertEqual(submission.reviewer_note, "All docs valid.")

    def test_legal_transition_more_info_back_to_submitted(self):
        submission = make_submission(self.merchant, status="more_info_requested")
        transition(submission, "submitted")
        submission.refresh_from_db()
        self.assertEqual(submission.status, "submitted")

    def test_all_terminal_states_have_no_outbound(self):
        """Verify the state machine dict is correct for terminal states."""
        self.assertEqual(VALID_TRANSITIONS["approved"], [])
        self.assertEqual(VALID_TRANSITIONS["rejected"], [])


# ─────────────────────────────────────────────
# 2. API: Illegal transition via HTTP → 400
# ─────────────────────────────────────────────

class StateMachineAPITests(TestCase):

    def setUp(self):
        self.reviewer = make_user("rev1", role="reviewer")
        self.merchant = make_user("merch1", role="merchant")
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {make_token(self.reviewer)}")

    def test_api_illegal_transition_returns_400(self):
        """
        approved → submitted is a valid new_state value (passes serializer)
        but illegal at the state machine layer → must return 400 with code=invalid_transition.
        """
        submission = make_submission(self.merchant, status="approved")
        response = self.client.post(
            f"/api/v1/kyc/submissions/{submission.id}/transition/",
            {"new_state": "submitted"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_transition")

    def test_api_approved_to_rejected_returns_400(self):
        """Already approved — cannot reject."""
        submission = make_submission(self.merchant, status="approved")
        response = self.client.post(
            f"/api/v1/kyc/submissions/{submission.id}/transition/",
            {"new_state": "rejected", "note": "Changed mind"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("terminal", response.data["error"].lower())

    def test_api_valid_transition_under_review_to_approved(self):
        submission = make_submission(self.merchant, status="under_review")
        response = self.client.post(
            f"/api/v1/kyc/submissions/{submission.id}/transition/",
            {"new_state": "approved", "note": "Looks good"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "approved")


# ─────────────────────────────────────────────
# 3. Auth Isolation Tests
# ─────────────────────────────────────────────

class AuthIsolationTests(TestCase):
    """Merchant A cannot see merchant B's submission."""

    def setUp(self):
        self.merchant_a = make_user("merchant_a")
        self.merchant_b = make_user("merchant_b")
        self.submission_b = make_submission(self.merchant_b, status="draft")
        self.client = APIClient()

    def test_merchant_cannot_read_other_merchants_submission(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {make_token(self.merchant_a)}")
        response = self.client.get(f"/api/v1/kyc/submissions/{self.submission_b.id}/")
        self.assertIn(response.status_code, [403, 404])

    def test_merchant_cannot_access_reviewer_queue(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {make_token(self.merchant_a)}")
        response = self.client.get("/api/v1/kyc/queue/")
        self.assertEqual(response.status_code, 403)

    def test_reviewer_can_read_any_submission(self):
        reviewer = make_user("rev_iso", role="reviewer")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {make_token(reviewer)}")
        response = self.client.get(f"/api/v1/kyc/submissions/{self.submission_b.id}/")
        self.assertEqual(response.status_code, 200)


# ─────────────────────────────────────────────
# 4. File Validation Tests
# ─────────────────────────────────────────────

class FileValidationTests(TestCase):

    def setUp(self):
        self.merchant = make_user("file_merchant")
        KYCSubmission.objects.create(merchant=self.merchant, status="draft")
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {make_token(self.merchant)}")

    def test_oversized_file_rejected(self):
        """A 6 MB file should return 400."""
        big_file = io.BytesIO(b"A" * (6 * 1024 * 1024))
        big_file.name = "big.pdf"
        big_file.size = 6 * 1024 * 1024
        # Patch name onto BytesIO for size detection
        from django.core.files.uploadedfile import InMemoryUploadedFile
        upload = InMemoryUploadedFile(
            big_file, "pan_document", "big.pdf", "application/pdf",
            6 * 1024 * 1024, None
        )
        response = self.client.put(
            "/api/v1/kyc/my-submission/",
            {"pan_document": upload},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_file_type_rejected(self):
        """A .exe file renamed to .pdf should be caught by magic bytes."""
        fake_exe = io.BytesIO(b"MZ\x90\x00" + b"\x00" * 100)  # PE magic bytes
        from django.core.files.uploadedfile import InMemoryUploadedFile
        upload = InMemoryUploadedFile(
            fake_exe, "pan_document", "malicious.pdf", "application/pdf",
            104, None
        )
        response = self.client.put(
            "/api/v1/kyc/my-submission/",
            {"pan_document": upload},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)


# ─────────────────────────────────────────────
# 5. SLA Tracking Tests
# ─────────────────────────────────────────────

class SLATests(TestCase):

    def test_submission_over_24h_is_at_risk(self):
        merchant = make_user("sla_merch")
        submission = KYCSubmission.objects.create(
            merchant=merchant,
            status="submitted",
            submitted_at=timezone.now() - timezone.timedelta(hours=25),
        )
        self.assertTrue(submission.is_at_risk)

    def test_submission_under_24h_not_at_risk(self):
        merchant = make_user("sla_merch2")
        submission = KYCSubmission.objects.create(
            merchant=merchant,
            status="submitted",
            submitted_at=timezone.now() - timezone.timedelta(hours=10),
        )
        self.assertFalse(submission.is_at_risk)

    def test_approved_submission_never_at_risk(self):
        merchant = make_user("sla_merch3")
        submission = KYCSubmission.objects.create(
            merchant=merchant,
            status="approved",
            submitted_at=timezone.now() - timezone.timedelta(hours=100),
        )
        self.assertFalse(submission.is_at_risk)
