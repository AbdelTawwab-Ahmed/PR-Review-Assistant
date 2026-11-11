from fastapi.testclient import TestClient

from app.infrastructure.cache.memory_cache import InMemoryCache
from app.main import app, create_app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_cache_status() -> None:
    test_app = create_app()
    test_app.state.cache = InMemoryCache()
    client = TestClient(test_app)
    response = client.get("/api/health/ready")
    assert response.json() == {"status": "ok", "cache": "up"}
