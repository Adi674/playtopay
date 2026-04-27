"""
File upload validators.

We validate BOTH size AND actual file content (magic bytes).
We do NOT trust the Content-Type header or file extension — a malicious
user could rename a .exe to .pdf. Reading magic bytes catches that.

Magic byte signatures:
    PDF:  25 50 44 46  (%PDF)
    JPEG: FF D8 FF
    PNG:  89 50 4E 47 0D 0A 1A 0A
"""

from django.conf import settings
from rest_framework.exceptions import ValidationError


# (mime_type, byte_offset, magic_bytes)
MAGIC_SIGNATURES = [
    ("application/pdf", 0, b"%PDF"),
    ("image/jpeg",      0, b"\xff\xd8\xff"),
    ("image/png",       0, b"\x89PNG\r\n\x1a\n"),
]


def detect_mime_from_magic(file_obj) -> str | None:
    """
    Read the first 8 bytes and match against known magic signatures.
    Returns the mime type string, or None if unrecognised.
    Seeks back to 0 after reading so the file object is not consumed.
    """
    header = file_obj.read(8)
    file_obj.seek(0)  # critical: reset so the file can still be read/saved

    for mime_type, offset, magic in MAGIC_SIGNATURES:
        if header[offset: offset + len(magic)] == magic:
            return mime_type
    return None


def validate_document(file_obj) -> None:
    """
    Full validation for a KYC document upload.

    Checks (in order, cheapest first):
      1. File size ≤ MAX_UPLOAD_SIZE_BYTES
      2. Magic bytes match an allowed MIME type

    Raises rest_framework.exceptions.ValidationError on failure
    so DRF returns a 400 automatically with our error shape.
    """
    max_bytes = settings.MAX_UPLOAD_SIZE_BYTES  # 5 MB
    allowed_types = settings.ALLOWED_MIME_TYPES

    # --- Size check (cheapest — just read .size attribute) ---
    if file_obj.size > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        actual_mb = file_obj.size / (1024 * 1024)
        raise ValidationError(
            f"File '{file_obj.name}' is too large ({actual_mb:.1f} MB). "
            f"Maximum allowed size is {max_mb:.0f} MB."
        )

    # --- Magic bytes check (do NOT trust Content-Type header) ---
    detected_mime = detect_mime_from_magic(file_obj)

    if detected_mime is None:
        raise ValidationError(
            f"File '{file_obj.name}' has an unrecognised format. "
            f"Only PDF, JPG, and PNG are accepted."
        )

    if detected_mime not in allowed_types:
        raise ValidationError(
            f"File '{file_obj.name}' detected as '{detected_mime}', which is not allowed. "
            f"Accepted types: PDF, JPG, PNG."
        )


def validate_documents_in_data(files: dict) -> None:
    """
    Validate all document fields present in a multipart upload.
    Call this from the serializer's validate() method.
    """
    document_fields = ["pan_document", "aadhaar_document", "bank_statement"]
    for field in document_fields:
        if field in files and files[field]:
            validate_document(files[field])
