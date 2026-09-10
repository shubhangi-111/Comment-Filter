import pytest
import os

# Set development env for testing auth fallbacks
os.environ["FLASK_ENV"] = "development"
os.environ["API_KEY"] = "test_system_key"

from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "healthy"

def test_api_moderate_unauthorized(client):
    response = client.post("/v1/moderate", json={"comment": "test comment"})
    assert response.status_code == 401

def test_api_moderate_authorized(client):
    headers = {"X-User-Id": "test_user_123"}
    response = client.post("/v1/moderate", json={"comment": "Awesome content!"}, headers=headers)
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "success"
    assert json_data["data"]["is_toxic"] is False

def test_batch_moderate_api(client):
    headers = {"X-User-Id": "test_user_123"}
    payload = {
        "platform": "YouTube",
        "comments": [
            {"comment": "Nice video!", "author_username": "@user1"},
            {"comment": "kys", "author_username": "@troll"}
        ]
    }
    response = client.post("/v1/moderate/batch", json=payload, headers=headers)
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "success"
    assert json_data["count"] == 2
    assert json_data["data"][1]["is_toxic"] is True

def test_logs_unauthorized(client):
    response = client.get("/api/logs")
    assert response.status_code == 401

def test_logs_authorized(client):
    headers = {"X-API-Key": "test_system_key"}
    response = client.get("/api/logs", headers=headers)
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "success"

def test_tenant_logs_isolation(client):
    headers = {"X-User-Id": "user_tenant_A"}
    client.post("/v1/moderate", json={"comment": "kys"}, headers=headers)
    
    response = client.get("/api/logs", headers=headers)
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "success"
    for item in json_data["data"]:
        assert item["user_id"] == "user_tenant_A"
