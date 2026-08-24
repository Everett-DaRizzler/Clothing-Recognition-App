import json, sqlite3
from pathlib import Path
class Database:
    def __init__(self, path: Path): self.path = path; path.parent.mkdir(parents=True, exist_ok=True); self.init()
    def conn(self): c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row; return c
    def init(self):
        with self.conn() as c:
            c.executescript("""CREATE TABLE IF NOT EXISTS images(id TEXT PRIMARY KEY, original_path TEXT, analysis_path TEXT, thumbnail_path TEXT, metadata_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS ai_models(id TEXT PRIMARY KEY, name TEXT, status TEXT, size TEXT, version TEXT, hf_url TEXT, license TEXT);
            CREATE TABLE IF NOT EXISTS ai_model_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, image_id TEXT, model_id TEXT, model_version TEXT, started_at TEXT, inference_time_ms INTEGER, raw_response TEXT, parsed_response TEXT, error TEXT);
            CREATE TABLE IF NOT EXISTS predictions(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, image_id TEXT, model_id TEXT, payload_json TEXT);
            CREATE TABLE IF NOT EXISTS ground_truth_labels(image_id TEXT PRIMARY KEY, payload_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS corrections(id INTEGER PRIMARY KEY AUTOINCREMENT, image_id TEXT, attribute TEXT, original_value TEXT, corrected_value TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS evaluation_results(id INTEGER PRIMARY KEY AUTOINCREMENT, model_id TEXT, payload_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);""")
            models=[("stylewell-4b","StyleWell 4B","not_installed","4B BF16 (~8.88 GB files)","HelloWorld0204/Classification-StyleWell-model","https://huggingface.co/HelloWorld0204/Classification-StyleWell-model","MIT"),("qwen3-vl-2b","Qwen3-VL 2B","not_installed","2B BF16","Denali-AI/qwen3-vl-2b-sft-grpo-v9","https://huggingface.co/Denali-AI/qwen3-vl-2b-sft-grpo-v9","Apache-2.0"),("qwen3-vl-8b","Qwen3-VL 8B","not_installed","8B","future","https://huggingface.co/Denali-AI/qwen3-vl-8b-garment-classifier","Apache-2.0")]
            c.executemany("INSERT OR IGNORE INTO ai_models VALUES (?,?,?,?,?,?,?)", models)
    def add_image(self, meta):
        with self.conn() as c: c.execute("INSERT INTO images VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",(meta["imageId"],meta["originalPath"],meta["analysisPath"],meta["thumbnailPath"],json.dumps(meta)))
    def run(self, image_id, analysis, error=None):
        with self.conn() as c:
            cur=c.execute("INSERT INTO ai_model_runs(image_id,model_id,model_version,started_at,inference_time_ms,raw_response,parsed_response,error) VALUES (?,?,?,?,?,?,?,?)",(image_id,analysis.modelId,analysis.modelVersion,"CURRENT_TIMESTAMP",analysis.inferenceTimeMs,analysis.rawResponse,analysis.model_dump_json(),error)); c.execute("INSERT INTO predictions(run_id,image_id,model_id,payload_json) VALUES (?,?,?,?)",(cur.lastrowid,image_id,analysis.modelId,analysis.model_dump_json()))
    def save_ground_truth(self, gt):
        with self.conn() as c: c.execute("INSERT OR REPLACE INTO ground_truth_labels VALUES (?,?,CURRENT_TIMESTAMP)",(gt.imageId,gt.model_dump_json()))
    def save_correction(self, image_id, correction):
        with self.conn() as c: c.execute("INSERT INTO corrections(image_id,attribute,original_value,corrected_value) VALUES (?,?,?,?)",(image_id,correction.attribute,json.dumps(correction.originalAIValue),json.dumps(correction.correctedValue)))
    def image_exists(self, image_id):
        with self.conn() as c: return c.execute("SELECT 1 FROM images WHERE id=?", (image_id,)).fetchone() is not None
    def set_model_status(self, model_id, status):
        with self.conn() as c: c.execute("UPDATE ai_models SET status=? WHERE id=?", (status, model_id))
    def models(self):
        with self.conn() as c: return [dict(r) for r in c.execute("SELECT * FROM ai_models")]
    def benchmark_rows(self):
        with self.conn() as c: return [dict(r) for r in c.execute("SELECT * FROM ground_truth_labels")]
    def predictions(self):
        with self.conn() as c: return {r["image_id"]: json.loads(r["payload_json"]) for r in c.execute("SELECT image_id,payload_json FROM predictions")}
