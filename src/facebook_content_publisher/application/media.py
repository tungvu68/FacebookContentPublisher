"""Media validation and streaming hashing."""

import hashlib
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from facebook_content_publisher.domain.enums import MediaType

SUPPORTED_MEDIA = {
    ".jpg": (MediaType.IMAGE, "image/jpeg"),
    ".jpeg": (MediaType.IMAGE, "image/jpeg"),
    ".png": (MediaType.IMAGE, "image/png"),
    ".webp": (MediaType.IMAGE, "image/webp"),
    ".mp4": (MediaType.VIDEO, "video/mp4"),
}


@dataclass(frozen=True, slots=True)
class ValidatedMedia:
    path: Path
    media_type: MediaType
    mime_type: str
    file_size: int
    sha256: str


def calculate_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file incrementally without loading large video files into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def validate_media(path: Path) -> ValidatedMedia:
    """Validate supported media and return immutable metadata."""

    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError("media file does not exist")
    try:
        with resolved.open("rb"):
            pass
    except OSError as error:
        raise ValueError("media file is not readable") from error
    extension = resolved.suffix.lower()
    if extension not in SUPPORTED_MEDIA:
        raise ValueError("supported media: JPG, JPEG, PNG, WEBP, MP4")
    media_type, expected_mime = SUPPORTED_MEDIA[extension]
    mime_type = mimetypes.guess_type(resolved.name)[0] or expected_mime
    return ValidatedMedia(
        path=resolved,
        media_type=media_type,
        mime_type=mime_type,
        file_size=resolved.stat().st_size,
        sha256=calculate_sha256(resolved),
    )
