import os
import uuid
from django.conf import settings


def upload_document(file_obj, submission_id: int, field_name: str) -> str:
    ext = os.path.splitext(file_obj.name)[1].lower() or ".bin"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    storage_path = f"submissions/{submission_id}/{field_name}/{unique_name}"

    supabase_url = settings.SUPABASE_URL
    supabase_key = settings.SUPABASE_SERVICE_KEY
    bucket = settings.SUPABASE_BUCKET

    if supabase_url and supabase_key:
        return _upload_to_supabase(file_obj, storage_path, bucket, supabase_url, supabase_key)
    else:
        return _save_locally(file_obj, storage_path)


def _upload_to_supabase(file_obj, storage_path, bucket, supabase_url, supabase_key) -> str:
    from supabase import create_client
    client = create_client(supabase_url, supabase_key)
    file_bytes = file_obj.read()
    file_obj.seek(0)
    content_type = _get_content_type(file_obj)
    client.storage.from_(bucket).upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return client.storage.from_(bucket).get_public_url(storage_path)


def _save_locally(file_obj, storage_path: str) -> str:
    full_path = os.path.join(settings.MEDIA_ROOT, storage_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    file_obj.seek(0)
    with open(full_path, "wb") as f:
        for chunk in file_obj.chunks():
            f.write(chunk)

    # Full absolute URL so frontend can open the file directly
    backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")
    return f"{backend_url}{settings.MEDIA_URL}{storage_path}"


def _get_content_type(file_obj) -> str:
    name = getattr(file_obj, "name", "")
    ext = os.path.splitext(name)[1].lower()
    return {
        ".pdf":  "application/pdf",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
    }.get(ext, "application/octet-stream")