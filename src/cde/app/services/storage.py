"""File storage service for information container revisions."""

import hashlib
from pathlib import Path

from fastapi import UploadFile

from app.config import settings


async def save_file(
    project_id: str,
    container_id: str,
    revision_number: int,
    file: UploadFile,
) -> tuple[str, str, int]:
    """Save an uploaded file and return (file_path, sha256_hash, file_size).

    Files are stored at: uploads/{project_id}/{container_id}/rev{N}/{filename}
    """
    dir_path = (
        settings.UPLOAD_DIR / project_id / container_id / f"rev{revision_number}"
    )
    dir_path.mkdir(parents=True, exist_ok=True)

    file_path = dir_path / file.filename
    sha256 = hashlib.sha256()
    size = 0

    content = await file.read()
    sha256.update(content)
    size = len(content)

    file_path.write_bytes(content)

    return str(file_path), sha256.hexdigest(), size


def get_file_path(stored_path: str) -> Path:
    """Resolve a stored file path for download."""
    path = Path(stored_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {stored_path}")
    return path
