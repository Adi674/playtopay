# EXPLAINER.md

## 1. The State Machine

**Where it lives:** `backend/kyc/state_machine.py` — one file, nothing else.

```python
VALID_TRANSITIONS = {
    "draft":                ["submitted"],
    "submitted":            ["under_review"],
    "under_review":         ["approved", "rejected", "more_info_requested"],
    "more_info_requested":  ["submitted"],
    "approved":             [],   # terminal
    "rejected":             [],   # terminal
}

def transition(submission, new_state: str, actor=None, note: str = "") -> None:
    current = submission.status
    allowed = get_allowed_transitions(current)

    if new_state not in allowed:
        if not allowed:
            detail = f"'{STATE_LABELS.get(current, current)}' is a terminal state — no further transitions are possible."
        else:
            allowed_labels = [STATE_LABELS.get(s, s) for s in allowed]
            detail = (
                f"Cannot move from '{STATE_LABELS.get(current, current)}' "
                f"to '{STATE_LABELS.get(new_state, new_state)}'. "
                f"Allowed next states: {', '.join(allowed_labels)}."
            )
        raise InvalidTransitionError(detail)

    submission.status = new_state
    # ... save + log
```

**How illegal transitions are prevented:** Every view that changes status calls `transition()`. No view ever sets `submission.status = x` directly. If the transition isn't in the dict, `InvalidTransitionError` is raised before any DB write. The custom exception handler converts this to a 400 with `code: "invalid_transition"`.

---

## 2. The Upload

**Validation code** (`backend/kyc/validators.py`):

```python
MAGIC_SIGNATURES = [
    ("application/pdf", 0, b"%PDF"),
    ("image/jpeg",      0, b"\xff\xd8\xff"),
    ("image/png",       0, b"\x89PNG\r\n\x1a\n"),
]

def validate_document(file_obj) -> None:
    # 1. Size check — cheapest, done first
    if file_obj.size > settings.MAX_UPLOAD_SIZE_BYTES:  # 5 MB
        raise ValidationError(f"File too large ({actual_mb:.1f} MB). Max 5 MB.")

    # 2. Magic bytes — read first 8 bytes, seek back to 0
    header = file_obj.read(8)
    file_obj.seek(0)  # critical: reset so the file can still be saved

    for mime_type, offset, magic in MAGIC_SIGNATURES:
        if header[offset: offset + len(magic)] == magic:
            detected = mime_type
            break
    else:
        detected = None

    if detected not in settings.ALLOWED_MIME_TYPES:
        raise ValidationError(f"Unsupported file type. Accepted: PDF, JPG, PNG.")
```

**What happens with a 50 MB file:** The size check fires first (it only reads the `.size` attribute — no file reading needed). Returns 400 immediately: `"File too large (50.0 MB). Max 5 MB."` The file is never read into memory fully.

**Why magic bytes and not Content-Type:** The `Content-Type` header is sent by the client and can be trivially faked. A `.exe` file renamed to `.pdf` would pass a Content-Type check. Magic bytes read the actual file content and cannot be spoofed without making it a valid PDF/image.

---

## 3. The Queue

**Query powering the reviewer dashboard:**

```python
# In ReviewerQueueView.get()
queue = KYCSubmission.objects.filter(
    status__in=[KYCSubmission.STATUS_SUBMITTED, KYCSubmission.STATUS_UNDER_REVIEW]
).select_related("merchant").order_by("submitted_at")
```

**Why this way:**
- `status__in=[...]` — only active queue states. Draft/approved/rejected are not reviewer business.
- `select_related("merchant")` — avoids N+1 queries when serializing merchant username.
- `.order_by("submitted_at")` — oldest first (FIFO). Merchants who have been waiting longest get reviewed first.

**SLA flag:**

```python
# In KYCSubmission model (property — never stored in DB)
@property
def is_at_risk(self) -> bool:
    if self.status not in (self.STATUS_SUBMITTED, self.STATUS_UNDER_REVIEW):
        return False
    if self.submitted_at is None:
        return False
    threshold = timezone.now() - timezone.timedelta(hours=24)
    return self.submitted_at < threshold
```

Exposed as `SerializerMethodField` in the read serializer. This is intentionally **not a DB column** — a stored boolean would go stale the moment the clock crosses the 24-hour threshold. By computing it dynamically every time, it is always accurate.

---

## 4. The Auth

**How merchant A is stopped from seeing merchant B's submission:**

```python
# backend/kyc/permissions.py
class IsOwnerMerchantOrReviewer(BasePermission):
    message = "You do not have permission to access this submission."

    def has_object_permission(self, request, view, obj):
        if request.user.is_reviewer():
            return True
        # Merchant: only their own submission passes
        return obj.merchant_id == request.user.id
```

This is applied at the object level in `SubmissionDetailView`:

```python
class SubmissionDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerMerchantOrReviewer]

    def get(self, request, pk):
        submission = KYCSubmission.objects.get(pk=pk)
        self.check_object_permissions(request, submission)  # ← enforced here
        return Response(KYCSubmissionSerializer(submission).data)
```

Additionally, the merchant's primary interface (`MySubmissionView`) uses `KYCSubmission.objects.get(merchant=request.user)` — it never accepts a submission ID from the client, so there is no way to enumerate other submissions through that endpoint.

Role separation: reviewers and merchants are different `role` values on a single `CustomUser` model. `IsMerchant` and `IsReviewer` permission classes gate endpoints at the view level before any object lookup even happens.

---

## 5. The AI Audit

**Tool used:** Claude (Anthropic)

**What it gave me (wrong):**

When writing the file upload validator, the AI-generated first draft read the magic bytes but forgot to seek the file pointer back:

```python
# AI-generated (buggy)
def detect_mime_from_magic(file_obj):
    header = file_obj.read(8)
    # ← MISSING: file_obj.seek(0)
    for mime_type, offset, magic in MAGIC_SIGNATURES:
        if header[offset: offset + len(magic)] == magic:
            return mime_type
    return None
```

**What I caught:** After the validator ran, the file pointer was at position 8. When Django/Supabase later tried to read the file to save/upload it, it would read from byte 8 onward — producing a truncated, corrupt file. For small files (under 8 bytes), it would produce an empty file entirely. This would not raise an error; it would silently corrupt every uploaded document.

**What I replaced it with:**

```python
def detect_mime_from_magic(file_obj) -> str | None:
    header = file_obj.read(8)
    file_obj.seek(0)  # ← critical fix: reset so the file can be read/saved downstream
    for mime_type, offset, magic in MAGIC_SIGNATURES:
        if header[offset: offset + len(magic)] == magic:
            return mime_type
    return None
```

The fix is one line. The consequence of missing it would have been every uploaded KYC document being silently corrupted — merchants would pass validation but their documents would be unreadable by reviewers. This is exactly the kind of subtle bug that only shows up in real usage, not in a quick "does it work" test.
