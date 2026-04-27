from django.urls import path
from .views import (
    MySubmissionView,
    SubmitKYCView,
    ReviewerQueueView,
    SubmissionDetailView,
    TransitionSubmissionView,
    ReviewerMetricsView,
    AllSubmissionsView,
    NotificationEventsView,
)

urlpatterns = [
    # Merchant
    path("my-submission/", MySubmissionView.as_view(), name="my-submission"),
    path("my-submission/submit/", SubmitKYCView.as_view(), name="submit-kyc"),

    # Reviewer
    path("queue/", ReviewerQueueView.as_view(), name="reviewer-queue"),
    path("submissions/", AllSubmissionsView.as_view(), name="all-submissions"),
    path("submissions/<int:pk>/", SubmissionDetailView.as_view(), name="submission-detail"),
    path("submissions/<int:pk>/transition/", TransitionSubmissionView.as_view(), name="transition"),
    path("metrics/", ReviewerMetricsView.as_view(), name="metrics"),
    path("notifications/", NotificationEventsView.as_view(), name="notifications"),
]
