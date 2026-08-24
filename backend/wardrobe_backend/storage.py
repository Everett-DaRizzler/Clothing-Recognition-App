import shutil, uuid
from pathlib import Path
from .preprocessing import validate_and_prepare
class LocalImageStorage:
    def __init__(self, root: Path, max_bytes: int): self.root, self.max_bytes = root, max_bytes; root.mkdir(parents=True, exist_ok=True)
    def save(self, filename: str, content, content_type: str | None):
        if content_type and not content_type.startswith("image/"): raise ValueError("Upload must be an image")
        image_id = uuid.uuid4().hex; ext = Path(filename or "photo.jpg").suffix.lower() or ".jpg"; ext = ".jpg" if ext == ".jpeg" else ext; folder = self.root / image_id; folder.mkdir(); original = folder / f"original{ext}"
        try:
            with original.open("wb") as out:
                remaining = self.max_bytes + 1
                while remaining:
                    chunk = content.read(min(1024 * 1024, remaining))
                    if not chunk: break
                    out.write(chunk); remaining -= len(chunk)
            if original.stat().st_size > self.max_bytes: raise ValueError("Image exceeds the upload size limit")
            work, thumb = folder / "analysis.jpg", folder / "thumbnail.jpg"; meta = validate_and_prepare(original, work, thumb, self.max_bytes)
            return {"imageId": image_id, "originalPath": str(original), **meta}
        except Exception:
            shutil.rmtree(folder, ignore_errors=True); raise
