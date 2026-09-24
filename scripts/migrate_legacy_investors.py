#!/usr/bin/env python3
"""Copy the six legacy runtime asset sets, with backups and offline validation.

Run with the web application's Python environment. The default is a dry run;
--apply copies changed files and repairs only the six legacy active selections.
Stop the web server during migration to avoid concurrent settings writes.
No embeddings are generated, models downloaded, or providers contacted.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile
from typing import Callable

from vc_clone_graph.rehearsal_bootstrap import prepare_live_package
from vc_clone_graph.rehearsal_config import load_rehearsal_config
from vclogic_web.investor_catalog import InvestorCatalog
from vclogic_web.investor_versions import atomic_json, digest, safe_file

SLUGS = (
    'charles-hudson-precursor-ventures', 'cyan-banister-long-journey-ventures',
    'elizabeth-yin-hustle-fund', 'jesse-middleton-flybridge',
    'jillian-manus-structure-capital', 'phil-nadel',
)
DEFAULT_CONFIG = 'configs/rehearsal-charles-v41-grounded.toml'


def assets(source: Path, config_path: str) -> list[str]:
    """Include runtime data only, never historical pitches, outputs, or snapshots."""
    config = load_rehearsal_config(safe_file(source, config_path), workspace=source)
    paths = [config_path, 'inputs/taxonomy/codebook_v_final.json',
             config.classification.canonical_config_path,
             config.classification.canonical_registry_path]
    folders = ['evaluation/rehearsal_classifier_registry']
    for slug in SLUGS:
        paths.extend([f'inputs/investors/{slug}.toml', f'inputs/indexes/{slug}.json',
                      f'inputs/indexes/{slug}.precedents.json'])
        folders.extend([f'inputs/wiki/{slug}', f'inputs/data/investors/{slug}/precedents',
                        f'inputs/data/investors/{slug}/portfolio-memory'])
    for relative in folders:
        folder = safe_file(source, relative)
        if not folder.is_dir():
            raise ValueError(f'missing source directory: {relative}')
        paths.extend(p.relative_to(source).as_posix() for p in folder.rglob('*') if p.is_file())
    result = sorted(set(p for p in paths if p))
    for relative in result:
        if not safe_file(source, relative).is_file():
            raise ValueError(f'missing source asset: {relative}')
    return result


def copy_changed(source: Path, target: Path, backup: Path, paths: list[str],
                 progress: Callable[[list[dict]], None] | None = None) -> list[dict]:
    copied = []
    for relative in paths:
        original, destination = safe_file(source, relative), safe_file(target, relative)
        expected = digest(original)
        if destination.exists() and digest(destination) == expected:
            continue
        old_hash = digest(destination) if destination.exists() else None
        if old_hash:
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, saved)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Replace atomically, without modifying any retained hard-linked snapshots.
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
        try:
            shutil.copy2(original, temporary)
            if digest(temporary) != expected:
                raise ValueError(f'source changed during migration: {relative}')
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        copied.append(dict(path=relative, sha256=expected, previous_sha256=old_hash))
        if progress:
            progress(copied)
    return copied


def repaired_preferences(preferences: dict, versions: dict[str, str],
                         previous_versions: dict[str, str] | None = None) -> dict:
    result = dict(preferences)
    for slug, version in versions.items():
        if slug not in SLUGS:
            raise ValueError(f'not a legacy investor: {slug}')
        choice = preferences.get(slug, {})
        selected = choice.get('active_version')
        if selected and not choice.get('automatic_pending') and selected != (previous_versions or {}).get(slug):
            continue
        result[slug] = {**preferences.get(slug, {}), 'active_version': version,
                        'enabled': preferences.get(slug, {}).get('enabled', True),
                        'automatic_pending': False}
    return result


def validate(workspace: Path, config_path: str, *, packages: bool) -> dict[str, str]:
    config = load_rehearsal_config(workspace / config_path, workspace=workspace)
    catalog = InvestorCatalog(workspace=workspace, config=config, bundle_roots=[])
    versions = {}
    # _legacy validates the exact installed catalog inputs without changing settings.
    for slug in SLUGS:
        row = catalog._legacy(workspace/f'inputs/investors/{slug}.toml', workspace/'inputs')
        if not row.ready:
            raise ValueError(f'{slug}: {row.error}')
        versions[slug] = row.version_id
    if packages:
        with tempfile.TemporaryDirectory(prefix='legacy-migration-') as directory:
            for slug in SLUGS:
                prepare_live_package(source_root=workspace/'inputs', destination_root=Path(directory)/slug,
                                     vc_slug=slug, episode_slug='999999-migration-smoke',
                                     pitch='We build scheduling software for small businesses.',
                                     target_company_aliases=('Migration Smoke Company',))
    return versions


def migrate(source: Path, target: Path, *, apply: bool, config_path: str = DEFAULT_CONFIG) -> dict:
    source, target = source.resolve(strict=True), target.resolve(strict=True)
    if source == target or source.is_relative_to(target) or target.is_relative_to(source):
        raise ValueError('source and destination must be separate workspaces')
    paths = assets(source, config_path)
    validate(source, config_path, packages=False)
    changes = [p for p in paths if not safe_file(target, p).exists()
               or digest(source/p) != digest(safe_file(target, p))]
    report = dict(source=str(source), target=str(target), dry_run=not apply,
                  checked_assets=len(paths), changes=changes)
    if not apply:
        return report
    settings = target/'outputs/web-investors/settings.json'
    original_settings = settings.read_bytes() if settings.exists() else None
    preferences = json.loads(original_settings) if original_settings is not None else {}
    if not isinstance(preferences, dict) or any(not isinstance(v, dict) for v in preferences.values()):
        raise ValueError('investor settings must be an object of preference objects')
    config = load_rehearsal_config(target/config_path, workspace=target)
    catalog = InvestorCatalog(workspace=target, config=config, bundle_roots=[])
    previous_versions = {}
    for slug in SLUGS:
        registry = target/f'inputs/investors/{slug}.toml'
        if registry.exists():
            previous_versions[slug] = catalog._legacy(registry, target/'inputs').version_id
    backup = target/'outputs/legacy-investor-migrations'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    backup.mkdir(parents=True)
    if settings.exists():
        saved = backup/'outputs/web-investors/settings.json'
        saved.parent.mkdir(parents=True)
        shutil.copy2(settings, saved)
    report['backup'] = str(backup)
    report['previous_versions'] = previous_versions
    report['status'] = 'in_progress'
    atomic_json(backup/'report.json', report)
    try:
        def progress(copied: list[dict]) -> None:
            report['copied'] = list(copied)
            atomic_json(backup/'report.json', report)

        report['copied'] = copy_changed(source, target, backup, changes, progress)
        versions = validate(target, config_path, packages=True)
        updated = repaired_preferences(preferences, versions, previous_versions)
        if (settings.read_bytes() if settings.exists() else None) != original_settings:
            raise ValueError('Investor settings changed during migration; rerun to preserve the latest choices.')
        if updated != preferences:
            atomic_json(settings, updated)
        report.update(status='validated', ready_versions=versions,
                      offline_live_packages=len(versions))
    except Exception as exc:
        report.update(status='failed', error=str(exc))
        raise
    finally:
        atomic_json(backup/'report.json', report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--config', default=DEFAULT_CONFIG)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(migrate(args.source, args.target, apply=args.apply, config_path=args.config), indent=2))


if __name__ == '__main__':
    main()
