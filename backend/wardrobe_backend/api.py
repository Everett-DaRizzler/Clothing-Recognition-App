import asyncio
import json
import mimetypes
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .ai.stylewell4b import StyleWell4BAnalyzer
from .config import Settings
from .db import Database
from .evaluation import score
from .schema import ATTRIBUTES, ClothingAnalysis, Correction, GroundTruth, WardrobeItemCreate, WardrobeItemUpdate
from .storage import LocalImageStorage

settings = Settings()
if not settings.model_is_allowed:
    raise RuntimeError("Active model must be HelloWorld0204/Classification-StyleWell-model")

app = FastAPI(title="AI Wardrobe Phase 2 API")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?::\d+)?$",
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

db = Database(settings.db_path)
storage = LocalImageStorage(settings.images_dir, settings.max_upload_bytes)
analyzer = StyleWell4BAnalyzer(settings.model_id, settings.model_revision, settings.device)


def generated_name(values):
    color = (values.get("color") or "").strip()
    item_type = (values.get("type") or "").strip()
    category = (values.get("category") or "").strip()
    words = [word for word in (color, item_type or category) if word]
    if not words:
        return "New Clothing Item"
    return " ".join(words).title()


@app.get("/health")
def health():
    return {"ok": True, "status": "ok", "modelId": "stylewell-4b", "modelName": settings.model_id, "modelCached": analyzer.is_cached()}


@app.get("/models")
def models():
    rows = db.models()
    for row in rows:
        if row["id"] == "stylewell-4b":
            row["status"] = "installed" if analyzer.is_cached() else "not_installed"
    return rows


@app.post("/analyze", response_model=ClothingAnalysis)
async def analyze(file: UploadFile = File(...)):
    meta = None
    try:
        meta = storage.save(file.filename or "photo.jpg", file.file, file.content_type)
        db.add_image(meta)
        result = await asyncio.wait_for(asyncio.to_thread(analyzer.analyze, Path(meta["analysisPath"]), meta["imageId"]), settings.inference_timeout_seconds)
        result.qualityWarnings = meta.get("qualityWarnings", [])
        db.set_model_status("stylewell-4b", "installed")
        db.run(meta["imageId"], result)
        return result
    except asyncio.TimeoutError:
        if meta:
            db.run_failure(meta["imageId"], analyzer.model_id, analyzer.model_name, "AI inference timed out")
        raise HTTPException(504, "AI inference timed out")
    except Exception as exc:
        if meta:
            db.run_failure(meta["imageId"], analyzer.model_id, analyzer.model_name, str(exc)[:500])
        raise HTTPException(422, "Analysis failed. Try again or choose another photo.") from exc


@app.get("/images/{image_id}/{variant}")
def image_variant(image_id: str, variant: str):
    if variant not in {"thumbnail", "original"}:
        raise HTTPException(404, "Image variant not found")
    paths = db.image_paths(image_id)
    if not paths:
        raise HTTPException(404, "Image not found")
    path = Path(paths["thumbnail_path"] if variant == "thumbnail" else paths["original_path"])
    if not path.is_file():
        raise HTTPException(404, "Image file not found")
    return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "image/jpeg", headers={"Cache-Control": "public, max-age=3600"})


@app.get("/wardrobe")
def wardrobe(search: str = "", category: str = "All"):
    return db.list_clothing_items(search=search, category=category)


@app.post("/wardrobe")
def create_wardrobe_item(item: WardrobeItemCreate):
    if not db.image_exists(item.imageId):
        raise HTTPException(404, "The analyzed image was not found")
    prediction = db.latest_prediction(item.imageId)
    if not prediction:
        raise HTTPException(409, "Analyze the image before saving it to the wardrobe")
    values = item.model_dump()
    return db.create_clothing_item(item.imageId, values, item.name.strip() if item.name and item.name.strip() else generated_name(values), prediction=prediction)


@app.get("/wardrobe/{item_id}")
def get_wardrobe_item(item_id: str):
    item = db.get_clothing_item(item_id)
    if not item:
        raise HTTPException(404, "Clothing item not found")
    return item


@app.patch("/wardrobe/{item_id}")
def update_wardrobe_item(item_id: str, updates: WardrobeItemUpdate):
    item = db.update_clothing_item(item_id, updates.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(404, "Clothing item not found")
    return item


@app.delete("/wardrobe/{item_id}")
def delete_wardrobe_item(item_id: str):
    if not db.delete_clothing_item(item_id):
        raise HTTPException(404, "Clothing item not found")
    return {"deleted": True, "id": item_id}


@app.post("/ground-truth")
def ground_truth(gt: GroundTruth):
    db.save_ground_truth(gt)
    return {"saved": True}


@app.post("/corrections")
def correction(image_id: str, correction: Correction):
    if not db.image_exists(image_id):
        raise HTTPException(404, "Image not found")
    if correction.attribute not in ATTRIBUTES:
        raise HTTPException(400, "Unsupported correction attribute")
    prediction = db.latest_prediction(image_id)
    if not prediction:
        raise HTTPException(409, "Analyze the image before saving a correction")
    correction.originalAIValue = prediction.get(correction.attribute)
    db.save_correction(image_id, correction)
    return {"saved": True}


@app.get("/benchmark")
def benchmark():
    return {"items": [json.loads(row["payload_json"]) for row in db.benchmark_rows()]}


@app.post("/evaluate")
def evaluate():
    return score(db.predictions(), [json.loads(row["payload_json"]) for row in db.benchmark_rows()])
