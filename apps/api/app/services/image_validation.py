"""Rule-based selfie format, safety, and quality validation."""

from __future__ import annotations

import warnings
from dataclasses import asdict, dataclass
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from app.config import Settings, get_settings

ALLOWED_FORMATS = {
    ".jpg": ("JPEG", "image/jpeg"),
    ".jpeg": ("JPEG", "image/jpeg"),
    ".png": ("PNG", "image/png"),
}


class ImageValidationError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class Check:
    passed: bool
    value: str | int | float
    threshold: str | int | float
    message: str


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    image_format: str
    width: int
    height: int
    blur_variance: float
    mean_brightness: float
    checks: dict[str, Check]
    errors: tuple[str, ...]

    def json_checks(self) -> dict[str, dict[str, str | int | float | bool]]:
        return {key: asdict(value) for key, value in self.checks.items()}


def _file_extension(filename: str) -> str:
    # Treat slash and backslash as separators regardless of host OS.
    leaf = filename.replace("\\", "/").rsplit("/", 1)[-1]
    return "." + leaf.rsplit(".", 1)[-1].lower() if "." in leaf else ""


def safe_filename(filename: str, image_format: str) -> str:
    leaf = filename.replace("\\", "/").rsplit("/", 1)[-1]
    stem = leaf.rsplit(".", 1)[0] if "." in leaf else "selfie"
    safe = "".join(ch for ch in stem if ch.isascii() and (ch.isalnum() or ch in "-_ "))
    safe = safe.strip().strip("-_")[:96] or "selfie"
    return f"{safe}.{'jpg' if image_format == 'JPEG' else 'png'}"


def validate_image(data: bytes, filename: str, content_type: str, settings: Settings | None = None) -> ValidationResult:
    cfg = settings or get_settings()
    if not data:
        raise ImageValidationError("EMPTY_UPLOAD", "Choose a non-empty JPG or PNG image.")
    if len(data) > cfg.selfie_max_file_size_bytes:
        limit_mib = cfg.selfie_max_file_size_bytes / (1024 * 1024)
        raise ImageValidationError("FILE_TOO_LARGE", f"Image must be {limit_mib:g} MiB or smaller.", 413)

    extension = _file_extension(filename)
    expected = ALLOWED_FORMATS.get(extension)
    if expected is None:
        raise ImageValidationError("UNSUPPORTED_FORMAT", "Use a JPG, JPEG, or PNG image.", 415)
    declared_type = content_type.lower().split(";", 1)[0].strip()
    if declared_type != expected[1]:
        raise ImageValidationError("MIME_MISMATCH", "The file type does not match its extension.", 415)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image_format = image.format or ""
                width, height = image.size
                if image_format != expected[0]:
                    raise ImageValidationError("FORMAT_MISMATCH", "The image content does not match its extension.", 415)
                if width > cfg.selfie_max_width or height > cfg.selfie_max_height or width * height > cfg.selfie_max_pixels:
                    raise ImageValidationError("IMAGE_DIMENSIONS_TOO_LARGE", "Image dimensions are too large to process safely.", 413)
                image.verify()
    except ImageValidationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageValidationError("IMAGE_DIMENSIONS_TOO_LARGE", "Image dimensions are too large to process safely.", 413) from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ImageValidationError("CORRUPT_IMAGE", "This image cannot be read. Export it again as JPG or PNG.") from None

    decode_flags = cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION
    decoded = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), decode_flags)
    if decoded is None or decoded.shape[:2] != (height, width):
        raise ImageValidationError("UNREADABLE_IMAGE", "This image could not be decoded. Try another image.")

    gray = cv2.cvtColor(decoded, cv2.COLOR_BGR2GRAY)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    dark_ratio = float(np.count_nonzero(gray < 25) / gray.size)
    bright_ratio = float(np.count_nonzero(gray > 245) / gray.size)
    resolution_ok = width >= cfg.selfie_min_width and height >= cfg.selfie_min_height
    blur_ok = blur >= cfg.selfie_min_blur_variance
    brightness_ok = cfg.selfie_min_brightness <= brightness <= cfg.selfie_max_brightness
    exposure_ok = dark_ratio <= cfg.selfie_max_dark_pixel_ratio and bright_ratio <= cfg.selfie_max_bright_pixel_ratio
    checks = {
        "resolution": Check(
            resolution_ok,
            f"{width}x{height}",
            f">={cfg.selfie_min_width}x{cfg.selfie_min_height}",
            "Resolution is sufficient."
            if resolution_ok
            else f"Use an image at least {cfg.selfie_min_width}x{cfg.selfie_min_height} pixels.",
        ),
        "blur": Check(
            blur_ok,
            round(blur, 2),
            cfg.selfie_min_blur_variance,
            "Sharpness is sufficient." if blur_ok else "The image looks blurry. Hold steady and retake it.",
        ),
        "brightness": Check(
            brightness_ok,
            round(brightness, 2),
            f"{cfg.selfie_min_brightness}-{cfg.selfie_max_brightness}",
            "Brightness is suitable."
            if brightness_ok
            else "The image is too dark. Use even lighting and retake it."
            if brightness < cfg.selfie_min_brightness
            else "The image is overexposed. Move out of direct light and retake it.",
        ),
        "exposure": Check(
            exposure_ok,
            round(max(dark_ratio, bright_ratio), 4),
            f"dark<={cfg.selfie_max_dark_pixel_ratio},bright<={cfg.selfie_max_bright_pixel_ratio}",
            "Exposure is suitable." if exposure_ok else "Highlights or shadows are clipped. Use even lighting and retake it.",
        ),
    }
    errors = tuple(check.message for check in checks.values() if not check.passed)
    return ValidationResult(not errors, image_format, width, height, blur, brightness, checks, errors)
