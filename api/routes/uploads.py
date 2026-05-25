import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from core.config import settings
from core.dependencies import get_current_user
from models.user import User

router = APIRouter(prefix="/uploads", tags=["Uploads"])

_IMAGES_SUBDIR = "images"
_MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _detect_image_ext(data: bytes) -> str | None:
    """Return the file extension for a supported image, or None.

    Sniffs magic bytes from the actual content — we don't trust the
    client-supplied filename or Content-Type.
    """
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


@router.post("/image")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Store an uploaded image on disk and return its public URL.

    Generic: the returned URL can be saved into any *_url column
    (service.image_url, provider.profile_photo_url, category.icon_url, ...).
    """
    # Read with a hard cap (+1 byte) so an oversized upload can't exhaust memory.
    contents = await file.read(_MAX_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(contents) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit",
        )

    ext = _detect_image_ext(contents)
    if ext is None:
        raise HTTPException(
            status_code=400,
            detail="File is not a supported image (allowed: JPEG, PNG, GIF, WEBP)",
        )

    # Server-generated name — never reuse the client filename (path traversal).
    filename = f"{uuid.uuid4().hex}{ext}"
    dest_dir = os.path.join(settings.UPLOAD_DIR, _IMAGES_SUBDIR)
    os.makedirs(dest_dir, exist_ok=True)
    with open(os.path.join(dest_dir, filename), "wb") as out:
        out.write(contents)

    # Absolute URL built from the incoming request so it's host/port agnostic.
    # The path lines up with the StaticFiles mount registered in main.py.
    relative = f"{settings.MEDIA_URL_PATH}/{_IMAGES_SUBDIR}/{filename}"
    url = str(request.base_url).rstrip("/") + relative
    return {"url": url, "path": relative}
