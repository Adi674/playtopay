from rest_framework import serializers
from django.utils import timezone
from .models import KYCSubmission, NotificationEvent
from .validators import validate_documents_in_data


class KYCSubmissionSerializer(serializers.ModelSerializer):
    """Full read serializer — used for GET responses."""
    merchant_username = serializers.CharField(source="merchant.username", read_only=True)
    is_at_risk = serializers.SerializerMethodField()
    time_in_queue_hours = serializers.SerializerMethodField()

    class Meta:
        model = KYCSubmission
        fields = [
            "id",
            "merchant",
            "merchant_username",
            "reviewer",
            "status",
            "reviewer_note",
            # Personal
            "full_name",
            "email",
            "phone",
            # Business
            "business_name",
            "business_type",
            "monthly_volume_usd",
            # Documents
            "pan_document_url",
            "aadhaar_document_url",
            "bank_statement_url",
            # Timestamps
            "created_at",
            "updated_at",
            "submitted_at",
            # Computed
            "is_at_risk",
            "time_in_queue_hours",
        ]
        read_only_fields = [
            "id", "merchant", "status", "reviewer",
            "created_at", "updated_at", "submitted_at",
            "is_at_risk", "time_in_queue_hours",
        ]

    def get_is_at_risk(self, obj) -> bool:
        """Dynamically computed — never stored in DB."""
        return obj.is_at_risk

    def get_time_in_queue_hours(self, obj) -> float | None:
        secs = obj.time_in_queue_seconds
        if secs is None:
            return None
        return round(secs / 3600, 1)


class KYCSubmissionUpdateSerializer(serializers.ModelSerializer):
    """
    Write serializer for merchant draft updates.
    Accepts file uploads, validates them, uploads to storage, saves URLs.
    """
    pan_document = serializers.FileField(write_only=True, required=False)
    aadhaar_document = serializers.FileField(write_only=True, required=False)
    bank_statement = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = KYCSubmission
        fields = [
            "full_name", "email", "phone",
            "business_name", "business_type", "monthly_volume_usd",
            "pan_document", "aadhaar_document", "bank_statement",
        ]

    def validate(self, data):
        # Validate any uploaded files (size + magic bytes)
        file_fields = {}
        for field in ["pan_document", "aadhaar_document", "bank_statement"]:
            if field in data:
                file_fields[field] = data[field]
        validate_documents_in_data(file_fields)
        return data

    def update(self, instance, validated_data):
        from kyc.storage import upload_document

        # Handle file uploads — upload to Supabase/local and store URL
        file_field_map = {
            "pan_document":      "pan_document_url",
            "aadhaar_document":  "aadhaar_document_url",
            "bank_statement":    "bank_statement_url",
        }
        for file_field, url_field in file_field_map.items():
            file_obj = validated_data.pop(file_field, None)
            if file_obj:
                url = upload_document(file_obj, instance.id, file_field)
                setattr(instance, url_field, url)

        # Update remaining scalar fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class TransitionSerializer(serializers.Serializer):
    """Payload for reviewer state transition requests."""
    new_state = serializers.ChoiceField(choices=[
        "submitted", "under_review", "approved", "rejected", "more_info_requested"
    ])
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_new_state(self, value):
        # Reviewers cannot move submissions back to draft
        if value == "draft":
            raise serializers.ValidationError("Cannot transition to 'draft' via this endpoint.")
        return value


class NotificationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationEvent
        fields = ["id", "merchant", "event_type", "timestamp", "payload"]
        read_only_fields = fields
