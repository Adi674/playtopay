"""
Custom DRF exception handler — returns consistent error shapes.

All errors follow: { "error": "...", "code": "...", "details": {...} }
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from kyc.state_machine import InvalidTransitionError


def custom_exception_handler(exc, context):
    # Handle our custom InvalidTransitionError → 400
    if isinstance(exc, InvalidTransitionError):
        return Response(
            {"error": str(exc), "code": "invalid_transition"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = exception_handler(exc, context)

    if response is not None:
        original_data = response.data

        # Normalise DRF's various error formats into one shape
        if isinstance(original_data, dict):
            # Already has an 'error' key — leave it
            if "error" not in original_data:
                # DRF validation errors: {"field": ["msg"]} or {"detail": "msg"}
                if "detail" in original_data:
                    response.data = {
                        "error": str(original_data["detail"]),
                        "code": getattr(original_data.get("detail"), "code", "error"),
                    }
                else:
                    response.data = {
                        "error": "Validation failed.",
                        "code": "validation_error",
                        "details": original_data,
                    }
        elif isinstance(original_data, list):
            response.data = {
                "error": "Validation failed.",
                "code": "validation_error",
                "details": original_data,
            }

    return response
