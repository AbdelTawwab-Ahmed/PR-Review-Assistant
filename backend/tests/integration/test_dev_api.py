from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


def test_dev_analyze_requires_azure_config() -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(azure_openai_endpoint="")
    response = TestClient(app).post(
        "/api/dev/analyze", json={"repo_full_name": "org/repo", "pr_number": 1}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
