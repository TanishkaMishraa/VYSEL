"""Delete expired image files and metadata. Schedule this script daily."""

import logging

from app.config import get_settings
from app.db import SessionLocal, utcnow
from app.models import ImageUpload
from app.services.image_storage import delete_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()
    deleted = 0
    with SessionLocal() as db:
        expired = db.query(ImageUpload).filter(ImageUpload.expires_at <= utcnow()).all()
        for image in expired:
            try:
                delete_image(settings.selfie_storage_dir, image.storage_key)
            except ValueError:
                log.exception("Refusing to delete image with invalid storage key: %s", image.id)
                continue
            db.delete(image)
            deleted += 1
        db.commit()
    log.info("Expired image cleanup removed %d image(s)", deleted)
    return deleted


if __name__ == "__main__":
    main()
