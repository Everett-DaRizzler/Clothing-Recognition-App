import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .schema import ATTRIBUTES, LIST_ATTRIBUTES


def _json(value):
    return json.dumps(value if value is not None else [], ensure_ascii=False)


def _load(value, default):
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def conn(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def init(self):
        with self.conn() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS images(
                    id TEXT PRIMARY KEY, original_path TEXT, analysis_path TEXT,
                    thumbnail_path TEXT, metadata_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS ai_models(
                    id TEXT PRIMARY KEY, name TEXT, status TEXT, size TEXT,
                    version TEXT, hf_url TEXT, license TEXT
                );
                CREATE TABLE IF NOT EXISTS ai_model_runs(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, image_id TEXT,
                    model_id TEXT, model_version TEXT, started_at TEXT,
                    inference_time_ms INTEGER, raw_response TEXT,
                    parsed_response TEXT, error TEXT
                );
                CREATE TABLE IF NOT EXISTS predictions(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER,
                    image_id TEXT, model_id TEXT, payload_json TEXT
                );
                CREATE TABLE IF NOT EXISTS ground_truth_labels(
                    image_id TEXT PRIMARY KEY, payload_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS corrections(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, image_id TEXT,
                    attribute TEXT, original_value TEXT, corrected_value TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS evaluation_results(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, model_id TEXT,
                    payload_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS clothing_items(
                    id TEXT PRIMARY KEY,
                    image_id TEXT NOT NULL UNIQUE,
                    original_image_path TEXT NOT NULL,
                    thumbnail_path TEXT NOT NULL,
                    name TEXT NOT NULL,
                    brand TEXT,
                    category TEXT,
                    type TEXT,
                    color TEXT,
                    secondary_colors_json TEXT NOT NULL DEFAULT '[]',
                    pattern TEXT,
                    fabric TEXT,
                    fit TEXT,
                    style_json TEXT NOT NULL DEFAULT '[]',
                    occasions_json TEXT NOT NULL DEFAULT '[]',
                    seasons_json TEXT NOT NULL DEFAULT '[]',
                    ai_model_id TEXT NOT NULL,
                    ai_model_version TEXT NOT NULL,
                    ai_confidence_json TEXT NOT NULL DEFAULT '{}',
                    ai_prediction_json TEXT NOT NULL DEFAULT '{}',
                    user_corrected INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(image_id) REFERENCES images(id)
                );
                """
            )
            models = [
                ("stylewell-4b", "StyleWell 4B", "not_installed", "4B BF16 (~8.88 GB files)", "HelloWorld0204/Classification-StyleWell-model", "https://huggingface.co/HelloWorld0204/Classification-StyleWell-model", "MIT"),
                ("qwen3-vl-2b", "Qwen3-VL 2B", "not_installed", "2B BF16", "Denali-AI/qwen3-vl-2b-sft-grpo-v9", "https://huggingface.co/Denali-AI/qwen3-vl-2b-sft-grpo-v9", "Apache-2.0"),
                ("qwen3-vl-8b", "Qwen3-VL 8B", "not_installed", "8B", "future", "https://huggingface.co/Denali-AI/qwen3-vl-8b-garment-classifier", "Apache-2.0"),
            ]
            connection.executemany("INSERT OR IGNORE INTO ai_models VALUES (?,?,?,?,?,?,?)", models)

    def add_image(self, meta):
        with self.conn() as connection:
            connection.execute(
                "INSERT INTO images VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",
                (meta["imageId"], meta["originalPath"], meta["analysisPath"], meta["thumbnailPath"], json.dumps(meta)),
            )

    def run(self, image_id, analysis, error=None):
        with self.conn() as connection:
            cursor = connection.execute(
                "INSERT INTO ai_model_runs(image_id,model_id,model_version,started_at,inference_time_ms,raw_response,parsed_response,error) VALUES (?,?,?,?,?,?,?,?)",
                (image_id, analysis.modelId, analysis.modelVersion, _now(), analysis.inferenceTimeMs, analysis.rawResponse, analysis.model_dump_json(), error),
            )
            connection.execute(
                "INSERT INTO predictions(run_id,image_id,model_id,payload_json) VALUES (?,?,?,?)",
                (cursor.lastrowid, image_id, analysis.modelId, analysis.model_dump_json()),
            )

    def run_failure(self, image_id, model_id, model_version, error):
        with self.conn() as connection:
            connection.execute(
                "INSERT INTO ai_model_runs(image_id,model_id,model_version,started_at,error) VALUES (?,?,?,?,?)",
                (image_id, model_id, model_version, _now(), error),
            )

    def save_ground_truth(self, gt):
        with self.conn() as connection:
            connection.execute("INSERT OR REPLACE INTO ground_truth_labels VALUES (?,?,CURRENT_TIMESTAMP)", (gt.imageId, gt.model_dump_json()))

    def save_correction(self, image_id, correction):
        with self.conn() as connection:
            connection.execute(
                "INSERT INTO corrections(image_id,attribute,original_value,corrected_value) VALUES (?,?,?,?)",
                (image_id, correction.attribute, json.dumps(correction.originalAIValue), json.dumps(correction.correctedValue)),
            )

    def latest_prediction(self, image_id):
        with self.conn() as connection:
            row = connection.execute("SELECT payload_json FROM predictions WHERE image_id=? ORDER BY id DESC LIMIT 1", (image_id,)).fetchone()
            return json.loads(row["payload_json"]) if row else None

    def image_exists(self, image_id):
        with self.conn() as connection:
            return connection.execute("SELECT 1 FROM images WHERE id=?", (image_id,)).fetchone() is not None

    def image_paths(self, image_id):
        with self.conn() as connection:
            row = connection.execute("SELECT original_path, thumbnail_path FROM images WHERE id=?", (image_id,)).fetchone()
            return dict(row) if row else None

    def set_model_status(self, model_id, status):
        with self.conn() as connection:
            connection.execute("UPDATE ai_models SET status=? WHERE id=?", (status, model_id))

    def models(self):
        with self.conn() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM ai_models")]

    def _item(self, row):
        if row is None:
            return None
        item = dict(row)
        return {
            "id": item["id"], "imageId": item["image_id"],
            "name": item["name"], "brand": item["brand"], "category": item["category"],
            "type": item["type"], "color": item["color"],
            "secondaryColors": _load(item["secondary_colors_json"], []),
            "pattern": item["pattern"], "fabric": item["fabric"], "fit": item["fit"],
            "style": _load(item["style_json"], []), "occasion": _load(item["occasions_json"], []),
            "season": _load(item["seasons_json"], []), "aiModelId": item["ai_model_id"],
            "aiModelVersion": item["ai_model_version"], "aiConfidence": _load(item["ai_confidence_json"], {}),
            "aiPrediction": _load(item["ai_prediction_json"], {}), "userCorrected": bool(item["user_corrected"]),
            "createdAt": item["created_at"], "updatedAt": item["updated_at"],
        }

    def get_clothing_item(self, item_id):
        with self.conn() as connection:
            row = connection.execute("SELECT * FROM clothing_items WHERE id=?", (item_id,)).fetchone()
            return self._item(row)

    def clothing_item_for_image(self, image_id):
        with self.conn() as connection:
            row = connection.execute("SELECT * FROM clothing_items WHERE image_id=?", (image_id,)).fetchone()
            return self._item(row)

    def list_clothing_items(self, search="", category="All"):
        where, params = [], []
        if search.strip():
            terms = ["name", "brand", "category", "type", "color", "pattern", "fabric", "fit", "secondary_colors_json", "style_json", "occasions_json", "seasons_json"]
            haystack = " || ' ' || ".join(f"COALESCE({column}, '')" for column in terms)
            where.append(f"LOWER({haystack}) LIKE ?")
            params.append(f"%{search.strip().lower()}%")
        category_terms = {
            "Tops": ("top", "shirt", "blouse", "sweater", "hoodie", "polo", "tee"),
            "Bottoms": ("bottom", "pant", "jean", "short", "skirt", "trouser"),
            "Shoes": ("shoe", "boot", "sneaker", "sandal", "loafer"),
            "Outerwear": ("outerwear", "jacket", "coat", "parka", "vest"),
            "Accessories": ("accessor", "hat", "bag", "belt", "scarf", "watch"),
        }
        if category in category_terms:
            haystack = "LOWER(COALESCE(category, '') || ' ' || COALESCE(type, ''))"
            where.append("(" + " OR ".join(f"{haystack} LIKE ?" for _ in category_terms[category]) + ")")
            params.extend(f"%{term}%" for term in category_terms[category])
        query = "SELECT * FROM clothing_items" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY updated_at DESC"
        with self.conn() as connection:
            return [self._item(row) for row in connection.execute(query, params)]

    def create_clothing_item(self, image_id, values, generated_name, prediction=None):
        paths = self.image_paths(image_id)
        if not paths:
            raise ValueError("Image not found")
        existing = self.clothing_item_for_image(image_id)
        if existing:
            return existing
        item_id, now = uuid.uuid4().hex, _now()
        prediction = prediction or {key: values.get(key) for key in ("category", "type", "color", "secondaryColors", "pattern", "fabric", "fit", "style", "occasion", "season")}
        try:
            with self.conn() as connection:
                connection.execute(
                    """INSERT INTO clothing_items
                    (id,image_id,original_image_path,thumbnail_path,name,brand,category,type,color,secondary_colors_json,pattern,fabric,fit,style_json,occasions_json,seasons_json,ai_model_id,ai_model_version,ai_confidence_json,ai_prediction_json,user_corrected,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (item_id, image_id, paths["original_path"], paths["thumbnail_path"], generated_name, values.get("brand"), values.get("category"), values.get("type"), values.get("color"), _json(values.get("secondaryColors")), values.get("pattern"), values.get("fabric"), values.get("fit"), _json(values.get("style")), _json(values.get("occasion")), _json(values.get("season")), prediction.get("modelId", values.get("modelId", "stylewell-4b")), prediction.get("modelVersion", values.get("modelVersion", "HelloWorld0204/Classification-StyleWell-model")), _json(prediction.get("confidence", values.get("confidence", {}))), _json(prediction), 0, now, now),
                )
        except sqlite3.IntegrityError:
            existing = self.clothing_item_for_image(image_id)
            if existing:
                return existing
            raise
        return self.get_clothing_item(item_id)

    def update_clothing_item(self, item_id, updates):
        current = self.get_clothing_item(item_id)
        if not current:
            return None
        correction_values = []
        for attribute in ATTRIBUTES:
            if attribute in updates and updates[attribute] is not None and updates[attribute] != current.get(attribute):
                original = current["aiPrediction"].get(attribute)
                correction_values.append((current["imageId"], attribute, json.dumps(original), json.dumps(updates[attribute])))
        columns = {"secondaryColors": "secondary_colors_json", "style": "style_json", "occasion": "occasions_json", "season": "seasons_json"}
        editable = ("name", "brand", "category", "type", "color", "secondaryColors", "pattern", "fabric", "fit", "style", "occasion", "season")
        assignments, params = [], []
        for key in editable:
            if key in updates:
                assignments.append(f"{columns.get(key, key)}=?")
                params.append(_json(updates[key]) if key in LIST_ATTRIBUTES else updates[key])
        if assignments:
            assignments.extend(["user_corrected=?", "updated_at=?"])
            params.extend([1 if correction_values else int(current["userCorrected"]), _now(), item_id])
            with self.conn() as connection:
                connection.execute(f"UPDATE clothing_items SET {', '.join(assignments)} WHERE id=?", params)
                if correction_values:
                    connection.executemany("INSERT INTO corrections(image_id,attribute,original_value,corrected_value) VALUES (?,?,?,?)", correction_values)
        return self.get_clothing_item(item_id)

    def delete_clothing_item(self, item_id):
        with self.conn() as connection:
            cursor = connection.execute("DELETE FROM clothing_items WHERE id=?", (item_id,))
            return cursor.rowcount > 0

    def benchmark_rows(self):
        with self.conn() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM ground_truth_labels")]

    def predictions(self):
        with self.conn() as connection:
            return {row["image_id"]: json.loads(row["payload_json"]) for row in connection.execute("SELECT image_id,payload_json FROM predictions")}
