from pathlib import Path

from PIL import Image
from fastapi.testclient import TestClient

from wardrobe_backend import api
from wardrobe_backend.db import Database
from wardrobe_backend.outfit_engine import generate_outfit
from wardrobe_backend.personalization import score_personalization
from wardrobe_backend.schema import ClothingAnalysis


def add_item(db, tmp_path, key, name, category, item_type, color, styles):
    image_id = f"phase4-image-{key}"
    original = Path(tmp_path) / f"{image_id}.jpg"
    thumbnail = Path(tmp_path) / f"{image_id}-thumb.jpg"
    Image.new("RGB", (32, 32), "white").save(original)
    Image.new("RGB", (16, 16), "white").save(thumbnail)
    db.add_image({"imageId": image_id, "originalPath": str(original), "analysisPath": str(original), "thumbnailPath": str(thumbnail)})
    analysis = ClothingAnalysis(imageId=image_id, category=category, type=item_type, color=color, pattern="Solid", style=styles, occasion=["Everyday"], season=["Summer"])
    db.run(image_id, analysis)
    return db.create_clothing_item(image_id, {"category": category, "type": item_type, "color": color, "pattern": "Solid", "style": styles, "occasion": ["Everyday"], "season": ["Summer"]}, name)


def wardrobe(db, tmp_path):
    return [
        add_item(db, tmp_path, "classic-top", "Classic Polo", "Top", "Polo", "Navy", ["Classic"]),
        add_item(db, tmp_path, "street-top", "Street Hoodie", "Top", "Hoodie", "Black", ["Streetwear"]),
        add_item(db, tmp_path, "bottom", "Khaki Chinos", "Bottom", "Chinos", "Khaki", ["Classic"]),
        add_item(db, tmp_path, "shoes", "White Sneakers", "Shoes", "Sneakers", "White", ["Casual", "Classic"]),
    ]


def test_explicit_preferences_are_created_and_edited(tmp_path):
    db = Database(Path(tmp_path) / "prefs.sqlite3")
    saved = db.update_personalization({"preferredStyles": ["Classic"], "dislikedStyles": ["Streetwear"], "preferredColors": ["Navy"]})
    assert saved["explicit"]["preferredStyles"] == ["Classic"]
    edited = db.update_personalization({"preferredStyles": ["Minimal"], "dislikedStyles": []})
    assert edited["explicit"]["preferredStyles"] == ["Minimal"]
    assert edited["explicit"]["dislikedStyles"] == []


def test_favorites_feedback_reasons_and_learned_updates(tmp_path):
    db = Database(Path(tmp_path) / "signals.sqlite3")
    items = wardrobe(db, tmp_path)
    assert db.set_favorite(items[0]["id"], True)["isFavorite"] is True
    profile = db.record_feedback({"action": "like", "reason": None, "clothingItemIds": [items[0]["id"], items[2]["id"]], "style": "Classic"})
    assert profile["learned"]["styles"]["classic"] >= 1
    assert profile["learned"]["items"][items[0]["id"]] >= 1
    db.record_feedback({"action": "dislike", "reason": "colors", "clothingItemIds": [items[1]["id"]], "style": "Streetwear"})
    assert db.recent_feedback(2)[0]["reason"] == "colors"
    assert db.get_personalization_profile()["learned"]["styles"]["streetwear"] <= -1


def test_personalization_is_bounded_and_neutral_without_data(tmp_path):
    base = {"total": 80, "components": {"color": 9}, "reasons": []}
    items = [{"id": "fav", "name": "Navy Polo", "style": ["Classic"], "color": "Navy"}]
    neutral = score_personalization(base, items, {"explicit": {}, "learned": {}, "favoriteItemIds": []})
    assert neutral["total"] == 80 and neutral["personalizationBonus"] == 0
    strong = score_personalization(base, items, {"explicit": {"preferredStyles": ["Classic"], "dislikedStyles": []}, "learned": {"styles": {"classic": 10}, "items": {}, "colors": {}}, "favoriteItemIds": ["fav"]})
    assert strong["total"] <= 90
    assert strong["personalizationBonus"] <= 10


def test_personalized_generation_history_worn_reset_and_deleted_item(tmp_path, monkeypatch):
    db = Database(Path(tmp_path) / "api.sqlite3")
    items = wardrobe(db, tmp_path)
    monkeypatch.setattr(api, "db", db)
    client = TestClient(api.app)
    first = client.post("/outfits/generate", json={"occasion": "Everyday", "season": "Summer", "debug": True}).json()
    first_top = next(item for item in first["items"] if item["category"] == "Top")
    assert client.patch("/personalization", json={"preferredStyles": ["Classic"], "dislikedStyles": [first_top["style"][0]]}).status_code == 200
    generated = client.post("/outfits/generate", json={"occasion": "Everyday", "season": "Summer", "debug": True}).json()
    assert next(item for item in generated["items"] if item["category"] == "Top")["id"] != first_top["id"]
    assert client.patch(f"/wardrobe/{items[0]['id']}/favorite", json={"isFavorite": True}).json()["isFavorite"] is True
    assert generated["score"]["baseTotal"] >= 0
    assert "personalizationBonus" in generated["score"]
    assert generated["generationId"]
    client.post("/personalization/feedback", json={"action": "like", "generationId": generated["generationId"], "clothingItemIds": generated["clothingItemIds"], "style": "Classic"})
    assert client.post("/personalization/feedback", json={"action": "dislike", "generationId": generated["generationId"], "clothingItemIds": generated["clothingItemIds"], "reason": "too casual"}).status_code == 200
    saved = client.post("/outfits", json={"clothingItemIds": generated["clothingItemIds"], "generationMetadata": {"score": generated["score"]}}).json()
    assert any(entry["eventType"] == "saved" for entry in client.get("/personalization").json()["recentHistory"])
    assert client.post(f"/outfits/{saved['id']}/worn").json()["worn"] is True
    debug = client.get("/developer/personalization-lab").json()
    assert debug["recentFeedback"] and debug["itemSignals"]
    assert client.post("/personalization/reset-learned").json()["learned"]["styles"] == {}
    deleted_id = generated["clothingItemIds"][0]
    db.delete_clothing_item(deleted_id)
    degraded = client.get(f"/outfits/{saved['id']}").json()
    assert deleted_id in degraded["deletedItemIds"]
    assert client.delete(f"/outfits/{saved['id']}").json()["deleted"] is True
    assert client.get(f"/outfits/{saved['id']}").status_code == 404
