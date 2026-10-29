import secrets
import warnings
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.datastructures import UploadFile

MAX_PHOTO = 3 * 1024 * 1024


async def save_photo(upload, directory: Path):
    if upload is None:
        return None
    if not isinstance(upload, UploadFile):
        raise HTTPException(422, "Выберите файл изображения.")
    if not upload.filename:
        return None
    content = await upload.read(MAX_PHOTO + 1)
    if len(content) > MAX_PHOTO:
        raise HTTPException(413, "Фото должно быть не больше 3 МБ.")
    formats = {
        "JPEG": ("image/jpeg", {".jpg", ".jpeg"}),
        "PNG": ("image/png", {".png"}),
        "WEBP": ("image/webp", {".webp"}),
    }
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format not in formats:
                    raise ValueError("format")
                mime, suffixes = formats[image.format]
                if (
                    upload.content_type != mime
                    or Path(upload.filename).suffix.lower() not in suffixes
                    or image.width * image.height > 20_000_000
                ):
                    raise ValueError("type or dimensions")
                image.load()
                clean = ImageOps.exif_transpose(image).convert("RGB")
                clean.thumbnail((1600, 1600))
                name = secrets.token_hex(16) + ".jpg"
                clean.save(directory / name, "JPEG", quality=88)
        return "/uploads/" + name
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(
            422, "Нужно настоящее изображение JPG, PNG или WebP, до 20 млн пикселей."
        ) from None
