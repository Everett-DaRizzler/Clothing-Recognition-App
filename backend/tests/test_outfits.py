from PIL import Image
from fastapi.testclient import TestClient

from wardrobe_backend import api
from wardrobe_backend.db import Database
from wardrobe_backend.outfit_engine import (
    color_compatibility,
    generate_outfit,
    pattern_compatibility,
    score_combination,
    style_compatibility,
    test_wardrobe as fixture_wardrobe,
)
from wardrobe_backend.schema import ClothingAnalysis


def add_saved_item(db, tmp_path, item_id, name, category, item_type, color, style, occasion, season, pattern="Solid"):
    image_id = f"image-{item_id}"
    original = tmp_path / f"{image_id}.jpg"
    thumbnail = tmp_path / f"{image_id}-thumb.jpg"
    Image.new("RGB", (640, 640), "white").save(original)
    Image.new("RGB", (320, 320), "white").save(thumbnail)
    db.add_image({"imageId": image_id, "originalPath": str(original), "analysisPath": str(original), "thumbnailPath": str(thumbnail)})
    analysis = ClothingAnalysis(imageId=image_id, category=category, type=item_type, color=color, pattern=pattern, style=style, occasion=occasion, season=season)
    db.run(image_id, analysis)
    return db.create_clothing_item(image_id, {"category": category, "type": item_type, "color": color, "pattern": pattern, "style": style, "occasion": occasion, "season": season}, name)


def test_color_pattern_and_style_services_are_safe_and_tunable():
    assert color_compatibility("Navy", "Khaki") >= 8
    assert color_compatibility("Red", "Green") >= 8
    assert pattern_compatibility("Solid", "Graphic") > pattern_compatibility("Graphic", "Floral")
    assert style_compatibility(["Casual"], ["Casual"]) == 10
    assert style_compatibility(["Formal"], ["Sporty"]) < 5
    assert style_compatibility(["Formal"], ["Smart Casual"]) == style_compatibility(["Smart Casual"], ["Formal"])


def test_generation_scores_ranks_completeness_and_specific_item():
    items = fixture_wardrobe()
    result = generate_outfit(items, occasion="Everyday", style="Casual", season="Summer", anchor_item_id="test-navy-polo")
    assert result["available"] is True
    assert result["isComplete"] is True
    assert "test-navy-polo" in result["clothingItemIds"]
    assert len(result["clothingItemIds"]) == len(set(result["clothingItemIds"]))
    assert result["score"]["components"]["completeness"] == 10
    assert score_combination(result["items"], {"occasion": "Everyday", "style": "Casual", "season": "Summer"})["total"] >= 0
    assert result["explanation"].find("Navy Polo") >= 0


def test_generation_regenerates_without_immediate_duplicate_and_handles_missing_roles():
    items = fixture_wardrobe()
    first = generate_outfit(items, occasion="Everyday", style="Casual", season="Summer")
    second = generate_outfit(items, occasion="Everyday", style="Casual", season="Summer", excluded=[first["combinationId"]])
    assert second["combinationId"] != first["combinationId"]
    partial = generate_outfit([items[0]], occasion="Everyday")
    assert partial["available"] is True
    assert "bottom" in partial["missingRoles"] and "shoes" in partial["missingRoles"]
    empty = generate_outfit([])
    assert empty["available"] is False
    assert "bottom" in empty["missingRoles"]


def test_outfit_persistence_references_items_and_survives_deleted_item(tmp_path):
    db = Database(tmp_path / "wardrobe.sqlite3")
    top = add_saved_item(db, tmp_path, "top", "Navy Polo", "Top", "Polo", "Navy", ["Casual"], ["Everyday"], ["Summer"])
    bottom = add_saved_item(db, tmp_path, "bottom", "Khaki Chinos", "Bottom", "Chinos", "Khaki", ["Casual"], ["Everyday"], ["Summer"])
    outfit = db.create_outfit({"name": "Summer Casual", "clothingItemIds": [top["id"], bottom["id"]], "occasion": "Everyday", "style": "Casual", "season": "Summer", "generationMethod": "deterministic", "generationMetadata": {"score": 18}})
    assert len(outfit["clothingItems"]) == 2
    db.delete_clothing_item(bottom["id"])
    degraded = db.get_outfit(outfit["id"])
    assert degraded["clothingItemIds"] == [top["id"], bottom["id"]]
    assert degraded["deletedItemIds"] == [bottom["id"]]
    assert len(degraded["clothingItems"]) == 1
    rated = db.update_outfit(outfit["id"], {"userRating": 5})
    assert rated["userRating"] == 5


def test_outfit_api_generate_save_replace_rating_and_fixture_boundary(tmp_path, monkeypatch):
    db = Database(tmp_path / "wardrobe.sqlite3")
    top = add_saved_item(db, tmp_path, "top", "Navy Polo", "Top", "Polo", "Navy", ["Casual"], ["Everyday"], ["Summer"])
    alternate_top = add_saved_item(db, tmp_path, "top-alt", "White Tee", "Top", "Tee", "White", ["Casual"], ["Everyday"], ["Summer"])
    bottom = add_saved_item(db, tmp_path, "bottom", "Khaki Chinos", "Bottom", "Chinos", "Khaki", ["Casual"], ["Everyday"], ["Summer"])
    shoes = add_saved_item(db, tmp_path, "shoes", "White Sneakers", "Shoes", "Sneakers", "White", ["Casual"], ["Everyday"], ["Summer"])
    monkeypatch.setattr(api, "db", db)
    client = TestClient(api.app)
    generated = client.post("/outfits/generate", json={"occasion": "Everyday", "style": "Casual", "season": "Summer", "debug": True})
    assert generated.status_code == 200
    body = generated.json()
    assert set(body["clothingItemIds"]) == {top["id"], bottom["id"], shoes["id"]}
    saved = client.post("/outfits", json={"name": "Navy Weekend", "clothingItemIds": body["clothingItemIds"], "occasion": "Everyday", "style": "Casual", "season": "Summer", "generationMetadata": body["score"]})
    assert saved.status_code == 200
    outfit_id = saved.json()["id"]
    assert any(item["id"] == outfit_id for item in client.get("/outfits").json())
    assert client.get(f"/outfits/{outfit_id}").status_code == 200
    assert client.patch(f"/outfits/{outfit_id}", json={"name": "Updated Weekend"}).json()["name"] == "Updated Weekend"
    replaced = client.post(f"/outfits/{outfit_id}/replace", json={"role": "top", "clothingItemId": alternate_top["id"]})
    assert replaced.status_code == 200
    assert alternate_top["id"] in replaced.json()["clothingItemIds"]
    assert client.post(f"/outfits/{outfit_id}/replace", json={"role": "shoes", "clothingItemId": alternate_top["id"]}).status_code == 422
    assert client.patch(f"/outfits/{outfit_id}/rating", json={"userRating": 4}).json()["userRating"] == 4
    fixture_debug = client.post("/outfits/generate", json={"source": "test", "debug": True}).json()
    assert fixture_debug["generationMethod"] == "deterministic-test" and fixture_debug["items"][0]["id"].startswith("test-")
    fixture_public = client.post("/outfits/generate", json={"source": "test", "debug": False}).json()
    assert "candidates" not in fixture_public and "rejected" not in fixture_public
    assert client.get("/developer/outfit-test-wardrobe").json()["items"]
    assert client.post("/outfits", json={"clothingItemIds": ["test-navy-polo"]}).status_code == 422
    assert client.post("/outfits", json={"clothingItemIds": [top["id"], bottom["id"], shoes["id"]], "occasion": "Nope"}).status_code == 422
    assert client.post("/outfits/generate", json={"occasion": "Not an occasion"}).status_code == 422
    assert client.post("/outfits/generate", json={"anchorItemId": "missing-anchor"}).status_code == 404
    assert client.delete(f"/outfits/{outfit_id}").json()["deleted"] is True
    assert client.get(f"/outfits/{outfit_id}").status_code == 404
