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
                CREATE TABLE IF NOT EXISTS outfits(
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    clothing_item_ids_json TEXT NOT NULL,
                    occasion TEXT,
                    style TEXT,
                    season TEXT,
                    generation_method TEXT NOT NULL,
                    generation_metadata_json TEXT NOT NULL DEFAULT '{}',
                    user_rating INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS user_preferences(
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    explicit_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS preference_signals(
                    signal_type TEXT NOT NULL,
                    signal_key TEXT NOT NULL,
                    positive_count INTEGER NOT NULL DEFAULT 0,
                    negative_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(signal_type, signal_key)
                );
                CREATE TABLE IF NOT EXISTS clothing_favorites(
                    clothing_item_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outfit_feedback(
                    id TEXT PRIMARY KEY,
                    generation_id TEXT,
                    outfit_id TEXT,
                    clothing_item_ids_json TEXT NOT NULL DEFAULT '[]',
                    occasion TEXT,
                    style TEXT,
                    season TEXT,
                    action TEXT NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outfit_history(
                    id TEXT PRIMARY KEY,
                    generation_id TEXT,
                    outfit_id TEXT,
                    clothing_item_ids_json TEXT NOT NULL DEFAULT '[]',
                    occasion TEXT,
                    style TEXT,
                    season TEXT,
                    base_score REAL,
                    personalized_score REAL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL
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
        with self.conn() as connection:
            is_favorite = connection.execute("SELECT 1 FROM clothing_favorites WHERE clothing_item_id=?", (item["id"],)).fetchone() is not None
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
            "isFavorite": is_favorite,
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
            connection.execute("DELETE FROM clothing_favorites WHERE clothing_item_id=?", (item_id,))
            return cursor.rowcount > 0

    def set_favorite(self, item_id, is_favorite):
        if not self.get_clothing_item(item_id):
            return None
        with self.conn() as connection:
            if is_favorite:
                connection.execute("INSERT OR IGNORE INTO clothing_favorites(clothing_item_id,created_at) VALUES (?,?)", (item_id, _now()))
            else:
                connection.execute("DELETE FROM clothing_favorites WHERE clothing_item_id=?", (item_id,))
        return self.get_clothing_item(item_id)

    def _explicit_preferences(self):
        with self.conn() as connection:
            row = connection.execute("SELECT explicit_json FROM user_preferences WHERE id=1").fetchone()
        return _load(row["explicit_json"], {}) if row else {}

    def get_personalization_profile(self):
        with self.conn() as connection:
            signals = connection.execute("SELECT * FROM preference_signals ORDER BY updated_at DESC").fetchall()
            favorites = [row["clothing_item_id"] for row in connection.execute("SELECT clothing_item_id FROM clothing_favorites")]
        styles, item_signals, colors = {}, {}, {}
        for row in signals:
            value = row["positive_count"] - row["negative_count"]
            if row["signal_type"] == "style": styles[row["signal_key"].lower()] = value
            elif row["signal_type"] == "item": item_signals[row["signal_key"]] = value
            elif row["signal_type"] == "color": colors[row["signal_key"].lower()] = value
        return {"explicit": self._explicit_preferences(), "learned": {"styles": styles, "items": item_signals, "colors": colors}, "favoriteItemIds": favorites}

    def update_personalization(self, values):
        explicit = {key: values.get(key, []) for key in ("preferredStyles", "dislikedStyles", "preferredColors", "dislikedColors", "preferredFits", "preferredOccasions")}
        if values.get("notes") is not None:
            explicit["notes"] = values["notes"]
        with self.conn() as connection:
            connection.execute("INSERT INTO user_preferences(id,explicit_json,updated_at) VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET explicit_json=excluded.explicit_json,updated_at=excluded.updated_at", (json.dumps(explicit, ensure_ascii=False), _now()))
        return self.get_personalization_profile()

    def reset_learned_preferences(self):
        with self.conn() as connection:
            connection.execute("DELETE FROM preference_signals")
        return self.get_personalization_profile()

    def record_history(self, item_ids, occasion=None, style=None, season=None, base_score=None, personalized_score=None, event_type="generated", generation_id=None, outfit_id=None):
        history_id = uuid.uuid4().hex
        with self.conn() as connection:
            connection.execute("INSERT INTO outfit_history(id,generation_id,outfit_id,clothing_item_ids_json,occasion,style,season,base_score,personalized_score,event_type,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (history_id, generation_id, outfit_id, _json(item_ids), occasion, style, season, base_score, personalized_score, event_type, _now()))
        return history_id

    def recent_history(self, limit=24):
        with self.conn() as connection:
            rows = connection.execute("SELECT rowid,* FROM outfit_history ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": row["id"], "generationId": row["generation_id"], "outfitId": row["outfit_id"], "clothingItemIds": _load(row["clothing_item_ids_json"], []), "occasion": row["occasion"], "style": row["style"], "season": row["season"], "baseScore": row["base_score"], "personalizedScore": row["personalized_score"], "eventType": row["event_type"], "createdAt": row["created_at"]} for row in rows]

    def record_feedback(self, values):
        item_ids = list(dict.fromkeys(values.get("clothingItemIds") or []))
        action = values["action"]
        with self.conn() as connection:
            connection.execute("INSERT INTO outfit_feedback(id,generation_id,outfit_id,clothing_item_ids_json,occasion,style,season,action,reason,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (uuid.uuid4().hex, values.get("generationId"), values.get("outfitId"), _json(item_ids), values.get("occasion"), values.get("style"), values.get("season"), action, values.get("reason"), _now()))
            rows = connection.execute("SELECT id,style_json,color FROM clothing_items WHERE id IN ({})".format(",".join("?" for _ in item_ids)), item_ids).fetchall() if item_ids else []
            delta_column = "positive_count" if action == "like" else "negative_count"
            for row in rows:
                for value in set(_load(row["style_json"], [])):
                    connection.execute("INSERT INTO preference_signals(signal_type,signal_key,positive_count,negative_count,updated_at) VALUES ('style',?,?,?,?) ON CONFLICT(signal_type,signal_key) DO UPDATE SET " + delta_column + "=" + delta_column + "+1,updated_at=excluded.updated_at", (str(value), 1 if action == "like" else 0, 1 if action == "dislike" else 0, _now()))
                if row["color"]:
                    value = str(row["color"])
                    connection.execute("INSERT INTO preference_signals(signal_type,signal_key,positive_count,negative_count,updated_at) VALUES ('color',?,?,?,?) ON CONFLICT(signal_type,signal_key) DO UPDATE SET " + delta_column + "=" + delta_column + "+1,updated_at=excluded.updated_at", (value, 1 if action == "like" else 0, 1 if action == "dislike" else 0, _now()))
                item_id = row["id"]
                if item_id:
                    connection.execute("INSERT INTO preference_signals(signal_type,signal_key,positive_count,negative_count,updated_at) VALUES ('item',?,?,?,?) ON CONFLICT(signal_type,signal_key) DO UPDATE SET " + delta_column + "=" + delta_column + "+1,updated_at=excluded.updated_at", (item_id, 1 if action == "like" else 0, 1 if action == "dislike" else 0, _now()))
        return self.get_personalization_profile()

    def recent_feedback(self, limit=20):
        with self.conn() as connection:
            rows = connection.execute("SELECT rowid,* FROM outfit_feedback ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": row["id"], "generationId": row["generation_id"], "outfitId": row["outfit_id"], "clothingItemIds": _load(row["clothing_item_ids_json"], []), "occasion": row["occasion"], "style": row["style"], "season": row["season"], "action": row["action"], "reason": row["reason"], "createdAt": row["created_at"]} for row in rows]

    def personalization_debug(self):
        profile = self.get_personalization_profile()
        with self.conn() as connection:
            favorites = [self._item(row) for row in connection.execute("SELECT c.* FROM clothing_items c JOIN clothing_favorites f ON f.clothing_item_id=c.id")]
            signals = [dict(row) for row in connection.execute("SELECT * FROM preference_signals ORDER BY updated_at DESC")]
        return {**profile, "favoriteItems": favorites, "itemSignals": signals, "recentFeedback": self.recent_feedback(), "recentHistory": self.recent_history()}

    def _outfit(self, row):
        if row is None:
            return None
        outfit = dict(row)
        item_ids = _load(outfit["clothing_item_ids_json"], [])
        items = []
        missing = []
        with self.conn() as connection:
            for item_id in item_ids:
                item_row = connection.execute("SELECT * FROM clothing_items WHERE id=?", (item_id,)).fetchone()
                if item_row:
                    items.append(self._item(item_row))
                else:
                    missing.append(item_id)
        metadata = _load(outfit["generation_metadata_json"], {})
        return {
            "id": outfit["id"], "name": outfit["name"], "clothingItemIds": item_ids,
            "clothingItems": items, "deletedItemIds": missing, "deletedItemRoles": {item_id: metadata.get("itemRoles", {}).get(item_id) for item_id in missing}, "occasion": outfit["occasion"],
            "style": outfit["style"], "season": outfit["season"], "generationMethod": outfit["generation_method"],
            "generationMetadata": metadata, "userRating": outfit["user_rating"],
            "createdAt": outfit["created_at"], "updatedAt": outfit["updated_at"],
        }

    def _validate_outfit_item_ids(self, item_ids):
        unique_ids = list(dict.fromkeys(item_ids))
        with self.conn() as connection:
            rows = connection.execute(
                "SELECT id FROM clothing_items WHERE id IN ({})".format(",".join("?" for _ in unique_ids)), unique_ids
            ).fetchall() if unique_ids else []
        found = {row["id"] for row in rows}
        return unique_ids, [item_id for item_id in unique_ids if item_id not in found]

    def create_outfit(self, values):
        item_ids, missing = self._validate_outfit_item_ids(values["clothingItemIds"])
        if missing:
            raise ValueError(f"Clothing items not found: {', '.join(missing)}")
        outfit_id, now = uuid.uuid4().hex, _now()
        with self.conn() as connection:
            connection.execute(
                "INSERT INTO outfits(id,name,clothing_item_ids_json,occasion,style,season,generation_method,generation_metadata_json,user_rating,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (outfit_id, values.get("name") or "Saved Outfit", _json(item_ids), values.get("occasion"), values.get("style"), values.get("season"), values.get("generationMethod", "deterministic"), json.dumps(values.get("generationMetadata", {}), ensure_ascii=False), values.get("userRating"), now, now),
            )
        return self.get_outfit(outfit_id)

    def get_outfit(self, outfit_id):
        with self.conn() as connection:
            row = connection.execute("SELECT * FROM outfits WHERE id=?", (outfit_id,)).fetchone()
        return self._outfit(row)

    def list_outfits(self):
        with self.conn() as connection:
            rows = connection.execute("SELECT * FROM outfits ORDER BY updated_at DESC").fetchall()
        return [self._outfit(row) for row in rows]

    def update_outfit(self, outfit_id, updates, allow_missing=False):
        current = self.get_outfit(outfit_id)
        if not current:
            return None
        if "clothingItemIds" in updates:
            item_ids, missing = self._validate_outfit_item_ids(updates["clothingItemIds"])
            if missing and not allow_missing:
                raise ValueError(f"Clothing items not found: {', '.join(missing)}")
            updates["clothingItemIds"] = item_ids
        columns = {"clothingItemIds": "clothing_item_ids_json", "generationMethod": "generation_method", "generationMetadata": "generation_metadata_json", "userRating": "user_rating"}
        editable = ("name", "clothingItemIds", "occasion", "style", "season", "generationMethod", "generationMetadata", "userRating")
        assignments, params = [], []
        for key in editable:
            if key in updates:
                assignments.append(f"{columns.get(key, key)}=?")
                params.append(_json(updates[key]) if key == "clothingItemIds" else json.dumps(updates[key], ensure_ascii=False) if key == "generationMetadata" else updates[key])
        if assignments:
            assignments.append("updated_at=?")
            params.extend([_now(), outfit_id])
            with self.conn() as connection:
                connection.execute(f"UPDATE outfits SET {', '.join(assignments)} WHERE id=?", params)
        return self.get_outfit(outfit_id)

    def delete_outfit(self, outfit_id):
        with self.conn() as connection:
            cursor = connection.execute("DELETE FROM outfits WHERE id=?", (outfit_id,))
            return cursor.rowcount > 0

    def benchmark_rows(self):
        with self.conn() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM ground_truth_labels")]

    def predictions(self):
        with self.conn() as connection:
            return {row["image_id"]: json.loads(row["payload_json"]) for row in connection.execute("SELECT image_id,payload_json FROM predictions")}
