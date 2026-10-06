from fastapi.testclient import TestClient

from neosys_pharma.presentation.app import app


client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "application": "NeoSys Pharma",
    }