import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('dossier_sync', Path(__file__).parents[2]/'scripts/sync_investor_dossiers.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def test_version_mismatch_fails_before_any_attachment(tmp_path, monkeypatch):
    source, target = tmp_path/'source', tmp_path/'target'
    source.mkdir()
    target.mkdir()
    monkeypatch.setattr(sync, 'legacy_versions', lambda w: {s: ('source' if w == source else 'target') for s in sync.SLUGS})
    with pytest.raises(ValueError, match='refusing dossier attachment'):
        sync.sync(source, target, apply=True)
    assert list(target.iterdir()) == []


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    source, target = tmp_path/'source', tmp_path/'target'
    source.mkdir()
    target.mkdir()
    slug, version = sync.SLUGS[0], 'a'*64
    rows = [{'rationales': [{'taxonomy_label': 'Traction', 'confidence': 0.9}]}]
    payload = dict(schema='vc-profile-evidence-v1', vc_slug=slug, investor_version_id=version,
                   investigations=rows, investigations_sha256=sync.payload_digest(rows), provenance={})
    monkeypatch.setattr(sync, 'build_sidecars', lambda *_: {slug: payload})
    return source, target, payload


def test_dry_run_writes_nothing(prepared):
    source, target, _ = prepared
    result = sync.sync(source, target, apply=False)
    assert result['investors'][0]['investigation_count'] == 1
    assert list(target.iterdir()) == []


def test_idempotent_export_backs_up_divergent_sidecar(prepared):
    source, target, payload = prepared
    first = sync.sync(source, target, apply=True)
    path = target/first['investors'][0]['path']
    stat = path.stat().st_mtime_ns
    assert sync.sync(source, target, apply=True)['investors'][0]['changed'] is False
    assert path.stat().st_mtime_ns == stat
    path.write_text('{"older": true}')
    result = sync.sync(source, target, apply=True)['investors'][0]
    assert json.loads((target/result['backup']).read_text()) == {'older': True}
    assert json.loads(path.read_text()) == payload


def test_export_preserves_exact_source_payload_and_records_manifest_drift(tmp_path, monkeypatch):
    source = tmp_path
    registry = source/sync.REGISTRY
    registry.parent.mkdir()
    registry.write_text(json.dumps({'investors': {'sample': {'sources': [{'kind': 'summary_glob', 'path': '../outputs/sample/*/summary.json'}]}}}))
    folder = source/'outputs/sample/episode'
    (folder/'phase1').mkdir(parents=True)
    (folder/'summary.json').write_text('{}')
    investigation = {'rationales': [{'taxonomy_label': 'Traction', 'custom': 'retained exactly'}], 'custom': [1, 2]}
    (folder/'phase1/investigation.json').write_text(json.dumps(investigation))
    manifest = source/'manifest.json'
    manifest.write_text('{}')
    (folder/'input-provenance.json').write_text(json.dumps({'package_manifest_path': str(manifest), 'package_manifest_sha256': 'older-hash'}))
    monkeypatch.setattr(sync, 'ProfileService', lambda *a, **k: SimpleNamespace(
        _profile=lambda _: None, _canonical_key=lambda _: 'sample', _investigations=lambda _: (investigation,)))
    rows, provenance = sync.source_history(source, 'sample')
    assert rows == [investigation]
    assert provenance['investigations'][0]['input_provenance']['recorded_manifest_matches_current'] is False
    assert 'does not prove' in provenance['limitation']


def test_empty_historical_data_is_not_fabricated(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, 'legacy_versions', lambda _: {s: 'a'*64 for s in sync.SLUGS})
    monkeypatch.setattr(sync, 'source_history', lambda *_: ([], {}))
    with pytest.raises(ValueError, match='investigations are missing'):
        sync.build_sidecars(tmp_path, tmp_path)


def test_reimport_repairs_corrupt_sidecar_with_backup(prepared):
    source, target, payload = prepared
    path = target/sync.sync(source, target, apply=True)['investors'][0]['path']
    path.write_text('incomplete json {')
    row = sync.sync(source, target, apply=True)['investors'][0]
    assert (target/row['backup']).read_text() == 'incomplete json {'
    assert json.loads(path.read_text()) == payload
