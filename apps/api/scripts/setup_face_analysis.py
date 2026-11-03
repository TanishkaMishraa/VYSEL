"""Install MediaPipe and the face landmark model. Safe to re-run; does nothing when up to date.

    python scripts/setup_face_analysis.py           # install/download what is missing
    python scripts/setup_face_analysis.py --check   # verify only; exit 1 if anything is missing

1. MediaPipe is installed from requirements-mediapipe.txt with --no-deps (see that file for why).
2. The model bundle is downloaded from Google's MediaPipe model storage and must match the pinned
   SHA-256 before it is used. A mismatched or partial file is never kept.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
import urllib.request
from importlib import metadata
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_DIR))

from app.config import get_settings  # noqa: E402
from app.services.face_analysis import MODEL_SHA256, MODEL_URL  # noqa: E402

REQUIREMENTS = API_DIR / "requirements-mediapipe.txt"


def pinned_mediapipe_version() -> str:
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("mediapipe=="):
            return line.split("==", 1)[1].strip()
    raise SystemExit(f"No mediapipe== pin found in {REQUIREMENTS}")


def mediapipe_ok(version: str) -> bool:
    """The pinned version is installed and its vision tasks import (all runtime deps present)."""
    try:
        if metadata.version("mediapipe") != version:
            return False
    except metadata.PackageNotFoundError:
        return False
    probe = [sys.executable, "-c", "from mediapipe.tasks.python import vision"]
    return subprocess.call(probe, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0  # noqa: S603


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_ok(path: Path) -> bool:
    return path.is_file() and sha256(path) == MODEL_SHA256


def download_model(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".part", delete=False) as tmp:
        partial = Path(tmp.name)
    try:
        print(f"  Downloading {MODEL_URL}")
        urllib.request.urlretrieve(MODEL_URL, partial)  # noqa: S310 — fixed https URL, hash-verified below
        actual = sha256(partial)
        if actual != MODEL_SHA256:
            raise SystemExit(f"  Downloaded model hash {actual} does not match the pinned {MODEL_SHA256}; refusing to use it.")
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="verify only; do not install or download")
    args = parser.parse_args()

    version = pinned_mediapipe_version()
    model_path = get_settings().face_model_path
    problems = 0

    if mediapipe_ok(version):
        print(f"  + mediapipe {version} installed")
    elif args.check:
        print(f"  x mediapipe {version} is not installed. Run: python scripts/setup_face_analysis.py")
        problems += 1
    else:
        print(f"  Installing mediapipe {version} (without its OpenCV GUI dependency)...")
        pip = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q"]
        # Runtime deps first (an existing virtualenv may predate them), then MediaPipe itself.
        for extra in (["-r", str(API_DIR / "requirements.txt")], ["--no-deps", "-r", str(REQUIREMENTS)]):
            if subprocess.call(pip + extra) != 0:  # noqa: S603 — fixed argument list, no shell
                print("  x pip install failed; see the error above.")
                return 1
        print(f"  + mediapipe {version} installed")

    if model_ok(model_path):
        print(f"  + face model verified ({model_path.name}, sha256 {MODEL_SHA256[:12]}...)")
    elif args.check:
        print(f"  x face model missing or invalid at {model_path}. Run: python scripts/setup_face_analysis.py")
        problems += 1
    else:
        try:
            download_model(model_path)
        except OSError as exc:
            print(f"  x Could not download the face model: {exc}. Check your internet connection and retry.")
            return 1
        print(f"  + face model downloaded and verified ({model_path})")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
