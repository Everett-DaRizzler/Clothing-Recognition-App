import asyncio, json
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import Settings
from .db import Database
from .storage import LocalImageStorage
from .schema import ATTRIBUTES, ClothingAnalysis, GroundTruth, Correction
from .ai.qwen3vl2b import Qwen3VL2BAnalyzer
from .evaluation import score
settings=Settings()
if not settings.model_is_allowed: raise RuntimeError("Phase 1 only permits Denali-AI/qwen3-vl-2b-sft-grpo-v9")
app=FastAPI(title="AI Wardrobe Phase 1 API"); app.add_middleware(CORSMiddleware, allow_origins=["*"] , allow_methods=["*"], allow_headers=["*"])
db=Database(settings.db_path); storage=LocalImageStorage(settings.images_dir, settings.max_upload_bytes); analyzer=Qwen3VL2BAnalyzer(settings.model_id, settings.model_revision, settings.device)
@app.get("/health")
def health(): return {"ok":True,"modelId":"qwen3-vl-2b","modelName":settings.model_id}
@app.get("/models")
def models(): return db.models()
@app.post("/analyze", response_model=ClothingAnalysis)
async def analyze(file: UploadFile=File(...)):
    try:
        meta=storage.save(file.filename or "photo.jpg", file.file, file.content_type); db.add_image(meta)
        result=await asyncio.wait_for(asyncio.to_thread(analyzer.analyze, meta["analysisPath"], meta["imageId"]), settings.inference_timeout_seconds); db.run(meta["imageId"],result); return result
    except asyncio.TimeoutError: raise HTTPException(504,"AI inference timed out")
    except Exception as exc: raise HTTPException(422, f"Analysis failed: {exc}")
@app.post("/ground-truth")
def ground_truth(gt: GroundTruth): db.save_ground_truth(gt); return {"saved":True}
@app.post("/corrections")
def correction(image_id: str, correction: Correction):
    if not db.image_exists(image_id): raise HTTPException(404, "Image not found")
    if correction.attribute not in ATTRIBUTES: raise HTTPException(400, "Unsupported correction attribute")
    db.save_correction(image_id, correction); return {"saved":True}
@app.get("/benchmark")
def benchmark(): return {"items":[json.loads(row["payload_json"]) for row in db.benchmark_rows()]}
@app.post("/evaluate")
def evaluate():
    result=score(db.predictions(), [json.loads(row["payload_json"]) for row in db.benchmark_rows()])
    return result
