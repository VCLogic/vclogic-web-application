from unittest.mock import Mock

from fastapi.testclient import TestClient

from vclogic_web.app import create_app


def test_specs_route_passes_explicit_version_without_changing_settings(monkeypatch):
    catalog = Mock()
    inspector = Mock(return_value={'vc_slug': 'sample', 'investor_version_id': 'a'*64})
    monkeypatch.setattr('vclogic_web.app.specifications', inspector, raising=False)
    client = TestClient(create_app(testing=True, investor_catalog=catalog, profile_service=Mock()))
    response = client.get('/api/settings/investors/sample/specifications', params={'version': 'a'*64})
    assert response.status_code == 200
    inspector.assert_called_once_with(catalog, 'sample', 'a'*64)
    catalog.select.assert_not_called()
    catalog.update.assert_not_called()


def test_specs_route_validates_version_and_returns_unknown_as_not_found(monkeypatch):
    inspector = Mock(side_effect=ValueError('Unknown investor version.'))
    monkeypatch.setattr('vclogic_web.app.specifications', inspector, raising=False)
    client = TestClient(create_app(testing=True, investor_catalog=Mock(), profile_service=Mock()))
    assert client.get('/api/settings/investors/sample/specifications?version=../bad').status_code == 422
    inspector.assert_not_called()
    response = client.get('/api/settings/investors/sample/specifications')
    assert response.status_code == 404
    assert response.json()['detail'] == 'Unknown investor version.'
