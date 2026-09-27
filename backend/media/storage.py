import hashlib
import shutil
from collections.abc import Iterable
from pathlib import Path

from django.conf import settings

HASH_READ_SIZE = 1024 * 1024


def _root() -> Path:
    return Path(settings.MEDIA_ROOT)


def partial_path(upload_id) -> str:
    return str(Path("uploads") / f"{upload_id}.part")


def asset_path(user_id: int, asset_id: int, filename: str) -> str:
    suffix = Path(filename).suffix[:16]
    return str(Path(str(user_id)) / str(asset_id) / f"source{suffix}")


def absolute(relative: str) -> Path:
    return _root() / relative


def write_at(relative: str, offset: int, pieces: Iterable[bytes]) -> int:
    path = absolute(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("r+b" if path.exists() else "wb") as handle:
        handle.seek(offset)
        for piece in pieces:
            handle.write(piece)
            written += len(piece)
    return written


def move(source: str, destination: str) -> None:
    target = absolute(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(absolute(source), target)


def _remove_empty_asset_folder(folder: Path) -> None:
    if folder != _root() and folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()


def delete(relative: str) -> None:
    path = absolute(relative)
    path.unlink(missing_ok=True)
    _remove_empty_asset_folder(path.parent)


def checksum(relative: str) -> str:
    digest = hashlib.sha256()
    with absolute(relative).open("rb") as handle:
        while chunk := handle.read(HASH_READ_SIZE):
            digest.update(chunk)
    return digest.hexdigest()
