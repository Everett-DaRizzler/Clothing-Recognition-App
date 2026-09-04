import asyncio
import json
import mimetypes
import uuid
import asyncio
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .ai.stylewell4b import StyleWell4BAnalyzer
from .config import Settings
from .db import Database
from .evaluation import score
from .outfit_engine import combination_id, explanation, generate_outfit, role_for_item, score_combination, test_wardrobe
from .personalization import score_personalization
from .schema import ATTRIBUTES, ClothingAnalysis, Correction, FavoriteUpdate, GroundTruth, OutfitCreate, OutfitFeedback, OutfitGenerationRequest, OutfitRating, OutfitReplacement, OutfitUpdate, PreferenceUpdate, WardrobeItemCreate, WardrobeItemUpdate
from .storage import LocalImageStorage

settings = Settings()
if not settings.model_is_allowed:
    raise RuntimeError("Active model must be HelloWorld0204/Classification-StyleWell-model")

app = FastAPI(title="AI Wardrobe Phase 3 API")
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


@app.patch("/wardrobe/{item_id}/favorite")
def favorite_wardrobe_item(item_id: str, favorite: FavoriteUpdate):
    item = db.set_favorite(item_id, favorite.isFavorite)
    if not item:
        raise HTTPException(404, "Clothing item not found")
    return item


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


def _outfit_generation_response(result):
    return result


def _personalized_generation(result, items, request):
    profile = db.get_personalization_profile()
    recent = db.recent_history(24)
    explicit = profile.get("explicit", {})
    learned = profile.get("learned", {})
    if not any(explicit.get(key) for key in ("preferredStyles", "dislikedStyles", "preferredColors", "dislikedColors", "preferredFits", "preferredOccasions")) and not any(learned.get(key) for key in ("styles", "items", "colors")) and not profile.get("favoriteItemIds") and not recent:
        return result, None
    live_by_id = {item["id"]: item for item in items}
    ranked = []
    for candidate in result.get("candidates", []):
        candidate_items = [live_by_id[item_id] for item_id in candidate["clothingItemIds"] if item_id in live_by_id]
        if not candidate_items:
            continue
        score = score_personalization(candidate["score"], candidate_items, profile, recent)
        ranked.append({**candidate, "items": candidate_items, "personalizedScore": score})
    if not ranked:
        return result, None
    ranked.sort(key=lambda candidate: (-candidate["personalizedScore"]["total"], -candidate["score"]["total"], candidate["combinationId"]))
    chosen = ranked[0]
    result["items"] = chosen["items"]
    result["clothingItemIds"] = chosen["clothingItemIds"]
    result["combinationId"] = chosen["combinationId"]
    result["missingRoles"] = [role for role in ("top", "bottom", "shoes") if role not in {role_for_item(item) for item in chosen["items"]}]
    result["isComplete"] = not result["missingRoles"]
    result["message"] = "" if result["isComplete"] else "This is the best available combination. Add the missing roles to complete the outfit."
    result["explanation"] = explanation(chosen["items"], {"occasion": request.occasion, "style": request.style, "season": request.season}, request.source)
    final_score = chosen["personalizedScore"]
    final_score["components"] = {**chosen["score"].get("components", {}), **final_score["components"]}
    result["score"] = final_score
    result["personalization"] = {"baseScore": chosen["score"], "personalization": final_score}
    result["candidates"] = [{key: value for key, value in {**candidate, "score": candidate["personalizedScore"]}.items() if key != "items"} for candidate in ranked[:8]]
    return result, chosen


@app.post("/outfits/generate")
def generate(request: OutfitGenerationRequest):
    if request.source == "test" and settings.environment != "development":
        raise HTTPException(404, "Developer outfit fixtures are disabled")
    items = test_wardrobe() if request.source == "test" else db.list_clothing_items()
    if request.anchorItemId and not any(item["id"] == request.anchorItemId for item in items):
        raise HTTPException(404, "Anchor clothing item not found")
    result = generate_outfit(items, request.occasion, request.style, request.season, request.anchorItemId, request.excludeCombinationIds, request.source, include_all_candidates=request.source == "wardrobe")
    chosen = None
    generation_id = uuid.uuid4().hex
    if result.get("available") and request.source == "wardrobe":
        result, chosen = _personalized_generation(result, items, request)
        db.record_history(result.get("clothingItemIds", []), request.occasion, request.style, request.season, result.get("score", {}).get("baseTotal", result.get("score", {}).get("total")), result.get("score", {}).get("total"), "generated", generation_id=generation_id)
    if not request.debug:
        result.pop("candidates", None)
        result.pop("rejected", None)
    result["filters"] = {"occasion": request.occasion, "style": request.style, "season": request.season}
    result["generationMethod"] = "deterministic-test" if request.source == "test" else "deterministic"
    result["generationId"] = generation_id
    return _outfit_generation_response(result)


@app.get("/developer/outfit-test-wardrobe")
def outfit_test_wardrobe():
    if settings.environment != "development":
        raise HTTPException(404, "Developer outfit fixtures are disabled")
    return {"items": test_wardrobe(), "notice": "Developer-only fictional data. These items are never inserted into the real wardrobe."}


@app.get("/outfits")
def outfits():
    return db.list_outfits()


@app.post("/outfits")
def create_outfit(outfit: OutfitCreate):
    values = outfit.model_dump()
    try:
        saved = db.create_outfit(values)
        score_data = values.get("generationMetadata", {}).get("score", {})
        db.record_history(saved["clothingItemIds"], saved.get("occasion"), saved.get("style"), saved.get("season"), score_data.get("baseTotal", score_data.get("total")), score_data.get("total"), "saved", outfit_id=saved["id"])
        return saved
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/outfits/{outfit_id}")
def get_outfit(outfit_id: str):
    outfit = db.get_outfit(outfit_id)
    if not outfit:
        raise HTTPException(404, "Outfit not found")
    return outfit


@app.patch("/outfits/{outfit_id}")
def update_outfit(outfit_id: str, updates: OutfitUpdate):
    try:
        outfit = db.update_outfit(outfit_id, updates.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not outfit:
        raise HTTPException(404, "Outfit not found")
    return outfit


@app.delete("/outfits/{outfit_id}")
def delete_outfit(outfit_id: str):
    if not db.delete_outfit(outfit_id):
        raise HTTPException(404, "Outfit not found")
    return {"deleted": True, "id": outfit_id}


@app.post("/outfits/{outfit_id}/replace")
def replace_outfit_item(outfit_id: str, replacement: OutfitReplacement):
    outfit = db.get_outfit(outfit_id)
    if not outfit:
        raise HTTPException(404, "Outfit not found")
    replacement_item = db.get_clothing_item(replacement.clothingItemId)
    if not replacement_item:
        raise HTTPException(404, "Replacement clothing item not found")
    if role_for_item(replacement_item) != replacement.role:
        raise HTTPException(422, "Replacement item does not match the selected outfit role")
    live_by_id = {item["id"]: item for item in outfit["clothingItems"]}
    item_roles = outfit.get("generationMetadata", {}).get("itemRoles", {})
    item_ids = []
    removed_missing = False
    for item_id in outfit["clothingItemIds"]:
        item = live_by_id.get(item_id)
        if item and role_for_item(item) == replacement.role:
            continue
        if not item and item_roles.get(item_id) == replacement.role and not removed_missing:
            removed_missing = True
            continue
        item_ids.append(item_id)
    item_ids.append(replacement.clothingItemId)
    try:
        updated = db.update_outfit(outfit_id, {"clothingItemIds": item_ids}, allow_missing=True)
        live_items = updated["clothingItems"]
        filters = {"occasion": updated.get("occasion"), "style": updated.get("style"), "season": updated.get("season")}
        metadata = {"score": score_combination(live_items, filters), "combinationId": combination_id(live_items), "explanation": explanation(live_items, filters), "itemRoles": {item["id"]: role_for_item(item) for item in live_items}}
        return db.update_outfit(outfit_id, {"generationMetadata": metadata})
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.patch("/outfits/{outfit_id}/rating")
def rate_outfit(outfit_id: str, rating: OutfitRating):
    try:
        outfit = db.update_outfit(outfit_id, {"userRating": rating.userRating})
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not outfit:
        raise HTTPException(404, "Outfit not found")
    return outfit


@app.get("/personalization")
def personalization():
    return db.personalization_debug()


@app.patch("/personalization")
def update_personalization(preferences: PreferenceUpdate):
    return db.update_personalization(preferences.model_dump())


@app.post("/personalization/reset-learned")
def reset_learned_personalization():
    return db.reset_learned_preferences()


@app.post("/personalization/feedback")
def personalization_feedback(feedback: OutfitFeedback):
    values = feedback.model_dump()
    if feedback.outfitId:
        outfit = db.get_outfit(feedback.outfitId)
        if not outfit:
            raise HTTPException(404, "Outfit not found")
        values["clothingItemIds"] = outfit["clothingItemIds"]
        values["occasion"] = outfit.get("occasion")
        values["style"] = outfit.get("style")
        values["season"] = outfit.get("season")
    return db.record_feedback(values)


@app.get("/developer/personalization-lab")
def personalization_lab():
    if settings.environment != "development":
        raise HTTPException(404, "Developer personalization tools are disabled")
    return db.personalization_debug()


@app.post("/outfits/{outfit_id}/worn")
def mark_outfit_worn(outfit_id: str):
    outfit = db.get_outfit(outfit_id)
    if not outfit:
        raise HTTPException(404, "Outfit not found")
    history_id = db.record_history(outfit["clothingItemIds"], outfit.get("occasion"), outfit.get("style"), outfit.get("season"), outfit.get("generationMetadata", {}).get("score", {}).get("baseTotal"), outfit.get("generationMetadata", {}).get("score", {}).get("total"), "worn", outfit_id=outfit_id)
    return {"worn": True, "historyId": history_id, "outfit": outfit}


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
