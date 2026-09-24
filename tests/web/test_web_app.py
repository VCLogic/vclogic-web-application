from fastapi.testclient import TestClient

from vclogic_web.app import create_app


def test_health_is_versioned() -> None:
    client = TestClient(create_app(testing=True))

    assert client.get("/api/health").json() == {
        "schema": "vc-clone-web-health-v1",
        "status": "ok",
    }


def test_catalog_is_validated_before_application_becomes_ready() -> None:
    from unittest.mock import Mock

    catalog = Mock()
    app = create_app(testing=True, investor_catalog=catalog, profile_service=Mock())
    catalog.refresh.assert_not_called()
    with TestClient(app) as client:
        catalog.refresh.assert_called_once_with()
        assert client.get('/api/health').json()['status'] == 'ok'
