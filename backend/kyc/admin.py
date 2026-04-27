from django.contrib import admin
from .models import KYCSubmission, NotificationEvent


@admin.register(KYCSubmission)
class KYCSubmissionAdmin(admin.ModelAdmin):
    list_display = ["merchant", "status", "business_name", "submitted_at", "is_at_risk"]
    list_filter = ["status", "business_type"]
    search_fields = ["merchant__username", "full_name", "business_name"]
    readonly_fields = ["created_at", "updated_at", "submitted_at"]

    def is_at_risk(self, obj):
        return obj.is_at_risk
    is_at_risk.boolean = True


@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
    list_display = ["merchant", "event_type", "timestamp"]
    list_filter = ["event_type"]
    readonly_fields = ["merchant", "event_type", "timestamp", "payload"]
