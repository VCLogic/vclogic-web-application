from pathlib import Path

from fastapi.testclient import TestClient

from vclogic_web import app, cli


def test_app_routes_services_to_pipeline_workspace(tmp_path, monkeypatch):
    calls = {}
    shared = object()
    def profile(catalog):
        calls['profile'] = catalog
        return object()
    def rehearsal(config_path, *, workspace, investor_catalog):
        calls['rehearsal'] = (config_path, workspace, investor_catalog)
        return object()
    monkeypatch.setattr(app, 'CatalogProfiles', profile)
    monkeypatch.setattr(app, 'RehearsalWebService', rehearsal)
    workspace = tmp_path / 'pipeline'
    application = app.create_app(pipeline_workspace=workspace, rehearsal_config=Path('configs/example.toml'), investor_catalog=shared)
    assert TestClient(application).get('/api/health').status_code == 200
    assert calls['profile'] is shared
    assert calls['rehearsal'] == (workspace / 'configs/example.toml', workspace, shared)


def test_cli_keeps_frontend_relative_to_app_checkout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    frontend = tmp_path / 'web/frontend/dist'
    frontend.mkdir(parents=True)
    (frontend / 'index.html').write_text('<main>VCLogic</main>')
    pipeline = tmp_path / 'pipeline'
    pipeline.mkdir()
    calls = {}
    def create(**kwargs):
        calls.update(kwargs)
        return 'application'
    monkeypatch.setattr(cli, 'create_app', create)
    monkeypatch.setattr(cli.uvicorn, 'run', lambda *a, **k: None)
    cli.main(['--pipeline-workspace', str(pipeline)])
    assert calls['pipeline_workspace'] == pipeline
    assert calls['static_root'] == frontend
    assert Path.cwd() == tmp_path
