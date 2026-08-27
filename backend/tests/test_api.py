from fastapi.testclient import TestClient
from wardrobe_backend.api import app

client = TestClient(app)

def test_health_reports_service_and_cached_model():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["modelId"] == "stylewell-4b"
    assert isinstance(body["modelCached"], bool)

def test_private_lan_cors_preflight():
    response = client.options("/health", headers={"Origin":"http://192.168.0.56:8081","Access-Control-Request-Method":"GET"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://192.168.0.56:8081"

def test_public_origin_is_not_allowed_by_cors():
    response = client.options("/health", headers={"Origin":"https://example.com","Access-Control-Request-Method":"GET"})
    assert "access-control-allow-origin" not in response.headers
