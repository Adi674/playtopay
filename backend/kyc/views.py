from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import KYCSubmission, NotificationEvent
from .serializers import (
    KYCSubmissionSerializer,
    KYCSubmissionUpdateSerializer,
    TransitionSerializer,
    NotificationEventSerializer,
)
from .permissions import IsMerchant, IsReviewer, IsOwnerMerchantOrReviewer
from .state_machine import transition, InvalidTransitionError


# ─────────────────────────────────────────────
# Merchant views
# ─────────────────────────────────────────────

class MySubmissionView(APIView):
    """
    GET  /api/v1/kyc/my-submission/  — merchant reads their own submission
    POST /api/v1/kyc/my-submission/  — create a new draft submission
    PUT  /api/v1/kyc/my-submission/  — update draft (save progress)
    """
    permission_classes = [IsAuthenticated, IsMerchant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_submission(self, request):
        try:
            return KYCSubmission.objects.get(merchant=request.user)
        except KYCSubmission.DoesNotExist:
            return None

    def get(self, request):
        submission = self._get_submission(request)
        if not submission:
            return Response(
                {"error": "No KYC submission found. Please create one.", "code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(KYCSubmissionSerializer(submission).data)

    def post(self, request):
        if self._get_submission(request):
            return Response(
                {"error": "You already have a KYC submission.", "code": "duplicate"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        submission = KYCSubmission.objects.create(merchant=request.user)
        # Run update logic if data was provided
        if request.data:
            serializer = KYCSubmissionUpdateSerializer(submission, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            submission = serializer.save()
        return Response(KYCSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)

    def put(self, request):
        submission = self._get_submission(request)
        if not submission:
            return Response(
                {"error": "No submission found.", "code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Only allow editing in draft or more_info_requested states
        if submission.status not in (
            KYCSubmission.STATUS_DRAFT, KYCSubmission.STATUS_MORE_INFO
        ):
            return Response(
                {
                    "error": f"Cannot edit a submission in '{submission.status}' state.",
                    "code": "not_editable",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = KYCSubmissionUpdateSerializer(submission, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        submission = serializer.save()
        return Response(KYCSubmissionSerializer(submission).data)


class SubmitKYCView(APIView):
    """
    POST /api/v1/kyc/my-submission/submit/
    Merchant submits their draft for review.
    Validates that required fields are filled before allowing submission.
    """
    permission_classes = [IsAuthenticated, IsMerchant]

    REQUIRED_FIELDS = [
        "full_name", "email", "phone",
        "business_name", "business_type", "monthly_volume_usd",
        "pan_document_url", "aadhaar_document_url", "bank_statement_url",
    ]

    def post(self, request):
        try:
            submission = KYCSubmission.objects.get(merchant=request.user)
        except KYCSubmission.DoesNotExist:
            return Response(
                {"error": "No submission found.", "code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate all required fields are filled
        missing = [f for f in self.REQUIRED_FIELDS if not getattr(submission, f, None)]
        if missing:
            return Response(
                {
                    "error": "Submission is incomplete. Please fill all required fields and upload all documents.",
                    "code": "incomplete_submission",
                    "missing_fields": missing,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            transition(submission, "submitted", actor=request.user)
        except InvalidTransitionError as e:
            return Response(
                {"error": str(e), "code": "invalid_transition"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(KYCSubmissionSerializer(submission).data)


# ─────────────────────────────────────────────
# Reviewer views
# ─────────────────────────────────────────────

class ReviewerQueueView(APIView):
    """
    GET /api/v1/kyc/queue/
    Returns submissions in review queue, oldest first.
    Includes SLA risk flag (computed dynamically).
    """
    permission_classes = [IsAuthenticated, IsReviewer]

    def get(self, request):
        queue = KYCSubmission.objects.filter(
            status__in=[KYCSubmission.STATUS_SUBMITTED, KYCSubmission.STATUS_UNDER_REVIEW]
        ).select_related("merchant").order_by("submitted_at")

        data = KYCSubmissionSerializer(queue, many=True).data
        return Response({"count": len(data), "results": data})


class SubmissionDetailView(APIView):
    """
    GET  /api/v1/kyc/submissions/<id>/  — reviewer views a submission
    """
    permission_classes = [IsAuthenticated, IsOwnerMerchantOrReviewer]

    def get(self, request, pk):
        try:
            submission = KYCSubmission.objects.select_related("merchant", "reviewer").get(pk=pk)
        except KYCSubmission.DoesNotExist:
            return Response(
                {"error": "Submission not found.", "code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        self.check_object_permissions(request, submission)
        return Response(KYCSubmissionSerializer(submission).data)


class TransitionSubmissionView(APIView):
    """
    POST /api/v1/kyc/submissions/<id>/transition/
    Reviewer triggers a state transition.
    """
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, pk):
        try:
            submission = KYCSubmission.objects.select_related("merchant").get(pk=pk)
        except KYCSubmission.DoesNotExist:
            return Response(
                {"error": "Submission not found.", "code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_state = serializer.validated_data["new_state"]
        note = serializer.validated_data.get("note", "")

        # Auto-assign reviewer on first review pick-up
        if new_state == "under_review" and not submission.reviewer:
            submission.reviewer = request.user

        try:
            transition(submission, new_state, actor=request.user, note=note)
        except InvalidTransitionError as e:
            return Response(
                {"error": str(e), "code": "invalid_transition"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(KYCSubmissionSerializer(submission).data)


class ReviewerMetricsView(APIView):
    """
    GET /api/v1/kyc/metrics/
    Dashboard summary: queue size, avg time in queue, 7-day approval rate.
    """
    permission_classes = [IsAuthenticated, IsReviewer]

    def get(self, request):
        now = timezone.now()
        week_ago = now - timedelta(days=7)

        queue_qs = KYCSubmission.objects.filter(
            status__in=[KYCSubmission.STATUS_SUBMITTED, KYCSubmission.STATUS_UNDER_REVIEW]
        )
        queue_count = queue_qs.count()
        at_risk_count = sum(1 for s in queue_qs if s.is_at_risk)

        # Average time in queue (hours) — only for queued submissions with a submitted_at
        times = [
            s.time_in_queue_seconds
            for s in queue_qs
            if s.time_in_queue_seconds is not None
        ]
        avg_time_hours = round(sum(times) / len(times) / 3600, 1) if times else 0

        # 7-day approval rate
        recent = KYCSubmission.objects.filter(submitted_at__gte=week_ago)
        total_recent = recent.count()
        approved_recent = recent.filter(status=KYCSubmission.STATUS_APPROVED).count()
        approval_rate = round(approved_recent / total_recent * 100, 1) if total_recent else 0

        # Total counts by status
        all_submissions = KYCSubmission.objects.all()
        status_counts = {}
        for s in KYCSubmission.STATUS_CHOICES:
            status_counts[s[0]] = all_submissions.filter(status=s[0]).count()

        return Response({
            "queue_count": queue_count,
            "at_risk_count": at_risk_count,
            "avg_time_in_queue_hours": avg_time_hours,
            "approval_rate_7d": approval_rate,
            "status_counts": status_counts,
        })


class AllSubmissionsView(APIView):
    """
    GET /api/v1/kyc/submissions/
    Reviewer sees all submissions (with optional status filter).
    """
    permission_classes = [IsAuthenticated, IsReviewer]

    def get(self, request):
        qs = KYCSubmission.objects.select_related("merchant", "reviewer").order_by("-updated_at")
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        data = KYCSubmissionSerializer(qs, many=True).data
        return Response({"count": len(data), "results": data})


class NotificationEventsView(APIView):
    """
    GET /api/v1/kyc/notifications/  — reviewer sees all events
    GET /api/v1/kyc/notifications/my/  — merchant sees their own events
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_reviewer():
            events = NotificationEvent.objects.select_related("merchant").all()[:100]
        else:
            events = NotificationEvent.objects.filter(merchant=request.user)[:50]
        return Response(NotificationEventSerializer(events, many=True).data)
