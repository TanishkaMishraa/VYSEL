"""Private filesystem storage for opaque image objects."""

import re
from pathlib import Path


def image_path(storage_dir: Path, storage_key: str) -> Path:
    """Resolve a database storage key while rejecting separators and traversal."""
    if not re.fullmatch(r"[a-f0-9]{32}\.(?:jpg|png)", storage_key):
        raise ValueError("Invalid image storage key")
    root = storage_dir.resolve()
    target = (root / storage_key).resolve()
    if target.parent != root:
        raise ValueError("Image storage key escapes configured root")
    return target


def store_image(storage_dir: Path, storage_key: str, content: bytes) -> Path:
    target = image_path(storage_dir, storage_key)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with target.open("xb") as stored:
            stored.write(content)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target


def delete_image(storage_dir: Path, storage_key: str) -> None:
    image_path(storage_dir, storage_key).unlink(missing_ok=True)
