from fastapi.testclient import TestClient

from vclogic_web.app import create_app


def test_health_is_versioned() -> None:
    client = TestClient(create_app(testing=True))

    assert client.get("/api/health").json() == {
        "schema": "vc-clone-web-health-v1",
        "status": "ok",
    }
