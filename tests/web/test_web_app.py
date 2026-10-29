from fastapi.testclient import TestClient

from vclogic_web.app import create_app


def test_health_is_versioned() -> None:
    client = TestClient(create_app(testing=True))

    assert client.get("/api/health").json() == {
        "schema": "vc-clone-web-health-v1",
        "status": "ok",
    }


def test_catalog_validation_does_not_block_application_readiness() -> None:
    from threading import Event
    from unittest.mock import Mock

    catalog = Mock()
    started, release = Event(), Event()
    def refresh():
        started.set()
        assert release.wait(5)
    catalog.refresh.side_effect = refresh
    app = create_app(testing=True, investor_catalog=catalog, profile_service=Mock())
    catalog.refresh.assert_not_called()
    with TestClient(app) as client:
        try:
            assert started.wait(5)
            assert client.get('/api/health').json()['status'] == 'ok'
            catalog.refresh.assert_called_once_with()
        finally:
            release.set()
