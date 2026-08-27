import io
import json

from PIL import Image
from fastapi.testclient import TestClient

from wardrobe_backend import api
from wardrobe_backend.db import Database
from wardrobe_backend.schema import ClothingAnalysis
from wardrobe_backend.storage import LocalImageStorage


def add_image(db, tmp_path, image_id="image-1"):
    original = tmp_path / f"{image_id}.jpg"
    thumbnail = tmp_path / f"{image_id}-thumb.jpg"
    Image.new("RGB", (640, 640), "navy").save(original)
    Image.new("RGB", (320, 320), "navy").save(thumbnail)
    db.add_image({"imageId": image_id, "originalPath": str(original), "analysisPath": str(original), "thumbnailPath": str(thumbnail)})


def values():
    return {
        "category": "Top", "type": "Polo", "color": "Black", "secondaryColors": [],
        "pattern": "Solid", "fabric": "Cotton", "fit": "Regular", "style": ["Casual"],
        "occasion": ["Everyday"], "season": ["Summer"], "confidence": {"color": 0.9},
        "modelId": "stylewell-4b", "modelVersion": "HelloWorld0204/Classification-StyleWell-model",
    }


def add_prediction(db, image_id):
    analysis = ClothingAnalysis(imageId=image_id, **values())
    db.run(image_id, analysis)


def test_clothing_item_create_search_filter_edit_delete_and_image_survives(tmp_path):
    db = Database(tmp_path / "wardrobe.sqlite3")
    add_image(db, tmp_path)
    item = db.create_clothing_item("image-1", values(), "Black Polo")
    assert item["id"] and item["imageId"] == "image-1"
    assert item["aiPrediction"]["color"] == "Black"
    assert db.create_clothing_item("image-1", values(), "Duplicate")['id'] == item['id']
    assert len(db.list_clothing_items(search="casual", category="Tops")) == 1

    updated = db.update_clothing_item(item["id"], {"color": "Navy", "style": ["Casual", "Vintage"]})
    assert updated["color"] == "Navy"
    assert updated["userCorrected"] is True
    assert updated["aiPrediction"]["color"] == "Black"
    with db.conn() as connection:
        correction = connection.execute("SELECT original_value, corrected_value FROM corrections WHERE image_id=?", ("image-1",)).fetchone()
    assert json.loads(correction["original_value"]) == "Black"
    assert json.loads(correction["corrected_value"]) == "Navy"

    assert db.delete_clothing_item(item["id"]) is True
    assert db.get_clothing_item(item["id"]) is None
    assert db.image_exists("image-1") is True


def test_wardrobe_api_crud_and_image_association(tmp_path, monkeypatch):
    db = Database(tmp_path / "wardrobe.sqlite3")
    add_image(db, tmp_path, "api-image")
    add_prediction(db, "api-image")
    monkeypatch.setattr(api, "db", db)
    client = TestClient(api.app)
    payload = {"imageId": "api-image", "name": "Navy Polo", "color": "Navy", **values()}
    payload["color"] = "Navy"

    created = client.post("/wardrobe", json=payload)
    assert created.status_code == 200
    item = created.json()
    assert item["name"] == "Navy Polo"
    assert item["color"] == "Navy"
    assert item["aiPrediction"]["color"] == "Black"
    assert client.post("/wardrobe", json=payload).json()["id"] == item["id"]
    assert client.get(f"/wardrobe/{item['id']}").status_code == 200
    assert len(client.get("/wardrobe?search=navy&category=Tops").json()) == 1
    edited = client.patch(f"/wardrobe/{item['id']}", json={"color": "Navy", "name": "Navy Polo"})
    assert edited.status_code == 200 and edited.json()["color"] == "Navy"
    assert client.delete(f"/wardrobe/{item['id']}").json()["deleted"] is True
    assert client.get(f"/wardrobe/{item['id']}").status_code == 404
    assert client.post("/wardrobe", json={"imageId": "missing", **values()}).status_code == 404


def test_image_variant_endpoint_uses_stored_file(tmp_path, monkeypatch):
    db = Database(tmp_path / "wardrobe.sqlite3")
    add_image(db, tmp_path, "variant-image")
    monkeypatch.setattr(api, "db", db)
    response = TestClient(api.app).get("/images/variant-image/thumbnail")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")


def test_secondary_color_correction_is_preserved(tmp_path):
    db = Database(tmp_path / "wardrobe.sqlite3")
    add_image(db, tmp_path)
    item_values = values()
    item_values["secondaryColors"] = ["White"]
    item = db.create_clothing_item("image-1", item_values, "Black Polo")
    updated = db.update_clothing_item(item["id"], {"secondaryColors": ["Gray"]})
    assert updated["secondaryColors"] == ["Gray"]
    assert updated["aiPrediction"]["secondaryColors"] == ["White"]
    assert updated["userCorrected"] is True


class FakeAnalyzer:
    model_id = "stylewell-4b"
    model_name = "HelloWorld0204/Classification-StyleWell-model"

    def is_cached(self):
        return True

    def analyze(self, image_path, image_id):
        return ClothingAnalysis(imageId=image_id, category="Top", type="Tee", color="Black", pattern="Solid")


class FailingAnalyzer(FakeAnalyzer):
    def analyze(self, image_path, image_id):
        raise RuntimeError("simulated model failure")


def jpeg_bytes(color, size=(100, 100)):
    image = Image.new("RGB", size, color)
    output = io.BytesIO()
    image.save(output, "JPEG")
    return output.getvalue()


def test_analyze_returns_quality_feedback_and_records_failed_runs(tmp_path, monkeypatch):
    db = Database(tmp_path / "wardrobe.sqlite3")
    monkeypatch.setattr(api, "db", db)
    monkeypatch.setattr(api, "storage", LocalImageStorage(tmp_path / "images", 1_000_000))
    monkeypatch.setattr(api, "analyzer", FakeAnalyzer())
    client = TestClient(api.app)
    response = client.post("/analyze", files={"file": ("dark.jpg", jpeg_bytes("black"), "image/jpeg")})
    assert response.status_code == 200
    assert response.json()["qualityWarnings"]
    assert db.latest_prediction(response.json()["imageId"])["type"] == "Tee"

    monkeypatch.setattr(api, "analyzer", FailingAnalyzer())
    failed = client.post("/analyze", files={"file": ("failure.jpg", jpeg_bytes("white"), "image/jpeg")})
    assert failed.status_code == 422
    with db.conn() as connection:
        assert connection.execute("SELECT error FROM ai_model_runs WHERE error IS NOT NULL").fetchone()["error"] == "simulated model failure"
