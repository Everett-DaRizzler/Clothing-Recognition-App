from pathlib import Path
from PIL import Image, ImageFilter, ImageOps, ImageStat
class InvalidImage(ValueError): pass
def validate_and_prepare(source: Path, work: Path, thumb: Path, max_bytes: int) -> dict:
    if source.stat().st_size > max_bytes: raise InvalidImage("Image exceeds the upload size limit")
    if source.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".heic"}: raise InvalidImage("Unsupported image type")
    try:
        with Image.open(source) as raw:
            image = ImageOps.exif_transpose(raw).convert("RGB"); width, height = image.size
            gray = image.convert("L")
            warnings = []
            if ImageStat.Stat(gray).mean[0] < 45: warnings.append("Image may be too dark")
            if min(width, height) < 240: warnings.append("Image is small; include the whole clothing item")
            if ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).var[0] < 18: warnings.append("Image may be blurry")
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS); image.save(work, "JPEG", quality=92, optimize=True)
            thumb_image = ImageOps.contain(image, (320, 320)); thumb_image.save(thumb, "JPEG", quality=82, optimize=True)
        return {"width": width, "height": height, "qualityWarnings": warnings, "analysisPath": str(work), "thumbnailPath": str(thumb)}
    except Exception as exc: raise InvalidImage("The image is corrupt or unreadable") from exc
