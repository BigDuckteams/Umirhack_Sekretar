from fastapi.testclient import TestClient
from app.main import app

def test_health_endpoints():
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200

def test_policy_endpoint():
    with TestClient(app) as client:
        response = client.get("/v1/policies")
        assert response.status_code == 200
        assert response.json()["count"] >= 5
