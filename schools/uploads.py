from pathlib import PurePath
from uuid import uuid4

from django.core.exceptions import ValidationError

MAX_SCHOOL_ATTACHMENT_SIZE = 10 * 1024 * 1024
_ALLOWED_SIGNATURES = {
    ".pdf": lambda header: header.startswith(b"%PDF-"),
    ".png": lambda header: header.startswith(b"\x89PNG\r\n\x1a\n"),
    ".jpg": lambda header: header.startswith(b"\xff\xd8\xff"),
    ".jpeg": lambda header: header.startswith(b"\xff\xd8\xff"),
}


def validate_school_attachment(uploaded_file):
    """Allow only small PDF/JPEG/PNG files and verify their file signatures."""
    if uploaded_file.size > MAX_SCHOOL_ATTACHMENT_SIZE:
        raise ValidationError("Attachment must be 10 MB or smaller.")
    extension = PurePath(uploaded_file.name).suffix.lower()
    signature_check = _ALLOWED_SIGNATURES.get(extension)
    if signature_check is None:
        raise ValidationError("Only PDF, JPG, JPEG and PNG files are allowed.")
    position = uploaded_file.tell() if hasattr(uploaded_file, "tell") else 0
    header = uploaded_file.read(16)
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(position)
    if not signature_check(header):
        raise ValidationError("The file content does not match its allowed file type.")


def homework_attachment_path(instance, filename):
    extension = PurePath(filename).suffix.lower()
    return f"school_{instance.school_id}/homework/{uuid4().hex}{extension}"


def homework_submission_attachment_path(instance, filename):
    extension = PurePath(filename).suffix.lower()
    return f"school_{instance.school_id}/homework-submissions/{uuid4().hex}{extension}"
