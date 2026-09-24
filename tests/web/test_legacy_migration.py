"""Migration safety: preserve divergent assets, snapshots, and user choices."""
import importlib.util
import os
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('legacy_migration', Path(__file__).parents[2]/'scripts/migrate_legacy_investors.py')
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def test_copy_backs_up_divergent_assets_without_mutating_retained_hardlinks(tmp_path):
    source, target, backup = [tmp_path/p for p in ('source', 'target', 'backup')]
    source.mkdir()
    target.mkdir()
    (source/'index.json').write_text('new index')
    (target/'index.json').write_text('old index')
    retained = target/'retained.json'
    os.link(target/'index.json', retained)
    changed = migration.copy_changed(source, target, backup, ['index.json'])
    assert len(changed) == 1
    assert (target/'index.json').read_text() == 'new index'
    assert (backup/'index.json').read_text() == 'old index'
    assert retained.read_text() == 'old index'
    assert migration.copy_changed(source, target, backup, ['index.json']) == []
    assert (backup/'index.json').read_text() == 'old index'


def test_selection_repair_preserves_disabled_and_nonlegacy_choices():
    slug = migration.SLUGS[0]
    existing = {slug: {'active_version': 'old', 'enabled': False},
                'mac-conwell': {'active_version': 'mac-version', 'enabled': True}}
    updated = migration.repaired_preferences(existing, {slug: 'ready-version'}, {slug: 'old'})
    assert updated[slug]['active_version'] == 'ready-version'
    assert updated[slug]['enabled'] is False
    assert updated['mac-conwell'] == existing['mac-conwell']
    assert existing[slug]['active_version'] == 'old'
    with pytest.raises(ValueError, match='not a legacy'):
        migration.repaired_preferences(existing, {'mac-conwell': 'different'})


def test_copy_rejects_symlink_target(tmp_path):
    source, target = tmp_path/'source', tmp_path/'target'
    source.mkdir()
    target.mkdir()
    (source/'index.json').write_text('new')
    protected = tmp_path/'protected'
    protected.write_text('original')
    (target/'index.json').symlink_to(protected)
    with pytest.raises(ValueError):
        migration.copy_changed(source, target, tmp_path/'backup', ['index.json'])
    assert protected.read_text() == 'original'


def test_selection_repair_preserves_explicit_alternative_bundle():
    slug = migration.SLUGS[0]
    preferences = {slug: {'active_version': 'chosen-bundle', 'enabled': False}}
    assert migration.repaired_preferences(preferences, {slug: 'installed-version'},
                                          {slug: 'previous-installed-version'}) == preferences


@pytest.fixture
def tiny_migration(tmp_path, monkeypatch):
    from types import SimpleNamespace
    source, target = tmp_path/'source', tmp_path/'target'
    source.mkdir()
    target.mkdir()
    (source/'index.json').write_text('new index')
    (target/'index.json').write_text('old index')
    slug = migration.SLUGS[0]
    registry = target/f'inputs/investors/{slug}.toml'
    registry.parent.mkdir(parents=True)
    registry.write_text('fixture')
    settings = target/'outputs/web-investors/settings.json'
    migration.atomic_json(settings, {slug: {'active_version': 'old', 'enabled': False},
                                     'mac-conwell': {'active_version': 'mac', 'enabled': True}})
    monkeypatch.setattr(migration, 'assets', lambda *_: ['index.json'])
    monkeypatch.setattr(migration, 'load_rehearsal_config', lambda *a, **k: None)
    monkeypatch.setattr(migration, 'InvestorCatalog', lambda **_: SimpleNamespace(
        _legacy=lambda *a: SimpleNamespace(version_id='old')))
    monkeypatch.setattr(migration, 'validate', lambda *a, **k: {slug: 'new'})
    return source, target, settings


def test_dry_run_does_not_write(tiny_migration):
    source, target, settings = tiny_migration
    before = {str(p): p.read_bytes() for p in target.rglob('*') if p.is_file()}
    report = migration.migrate(source, target, apply=False)
    assert report['changes'] == ['index.json']
    assert report['dry_run'] is True
    assert {str(p): p.read_bytes() for p in target.rglob('*') if p.is_file()} == before


def test_postcopy_failure_keeps_settings_and_records_backup(tiny_migration, monkeypatch):
    import json
    source, target, settings = tiny_migration
    original = settings.read_bytes()

    def validate(workspace, *_args, **_kwargs):
        if workspace == target:
            raise ValueError('incompatible fixture')
        return {}

    monkeypatch.setattr(migration, 'validate', validate)
    with pytest.raises(ValueError, match='incompatible fixture'):
        migration.migrate(source, target, apply=True)
    assert settings.read_bytes() == original
    report_path = next((target/'outputs/legacy-investor-migrations').glob('*/report.json'))
    report = json.loads(report_path.read_text())
    assert report['status'] == 'failed'
    assert [r['path'] for r in report['copied']] == ['index.json']
    assert (report_path.parent/'index.json').read_text() == 'old index'
    assert (report_path.parent/'outputs/web-investors/settings.json').read_bytes() == original


def test_concurrent_preferences_are_not_overwritten(tiny_migration, monkeypatch):
    import json
    source, target, settings = tiny_migration
    slug = migration.SLUGS[0]
    concurrent = {slug: {'active_version': 'another-choice', 'enabled': False},
                  'mac-conwell': {'active_version': 'new-mac', 'enabled': False}}

    def validate(workspace, *_args, **_kwargs):
        if workspace == target:
            migration.atomic_json(settings, concurrent)
        return {slug: 'new'}

    monkeypatch.setattr(migration, 'validate', validate)
    with pytest.raises(ValueError, match='settings changed during migration'):
        migration.migrate(source, target, apply=True)
    assert json.loads(settings.read_text()) == concurrent
