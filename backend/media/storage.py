"""Where uploaded files live.

Every path is built here and nowhere else. That is what makes moving to object
storage later a change to this one module rather than a search across the
codebase.
"""

import hashlib
import shutil
from pathlib import Path

from django.conf import settings

HASH_READ_SIZE = 1024 * 1024


def _root() -> Path:
    return Path(settings.MEDIA_ROOT)


def partial_path(upload_id) -> str:
    """Where a transfer in progress accumulates. Not inside the user's folder:
    it is not their file until it is complete and verified."""
    return str(Path("uploads") / f"{upload_id}.part")


def asset_path(user_id: int, asset_id: int, filename: str) -> str:
    suffix = Path(filename).suffix[:16]
    return str(Path(str(user_id)) / str(asset_id) / f"source{suffix}")


def absolute(relative: str) -> Path:
    return _root() / relative


def append(relative: str, data: bytes) -> None:
    path = absolute(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(data)


def size(relative: str) -> int:
    path = absolute(relative)
    return path.stat().st_size if path.exists() else 0


def move(source: str, destination: str) -> None:
    target = absolute(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(absolute(source), target)


def delete(relative: str) -> None:
    path = absolute(relative)
    path.unlink(missing_ok=True)
    # Leave the user's folder, drop the per-asset one once it is empty.
    parent = path.parent
    if parent != _root() and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()


def checksum(relative: str) -> str:
    """Hash the stored file.

    Done in one pass at the end rather than incrementally: hashlib state cannot
    be persisted between requests, and a single sequential read of a few
    gigabytes is far cheaper than the machinery to avoid it.
    """
    digest = hashlib.sha256()
    with absolute(relative).open("rb") as handle:
        while chunk := handle.read(HASH_READ_SIZE):
            digest.update(chunk)
    return digest.hexdigest()
