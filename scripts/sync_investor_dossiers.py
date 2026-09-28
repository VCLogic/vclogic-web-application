#!/usr/bin/env python3
"""Export source-project reference investigations into version-bound dossier sidecars.

Default: dry run. --apply writes compact sidecars, backing up divergent files.
This does not import assessments or claim historical runs used today's inputs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import glob
from hashlib import sha256
import json
from pathlib import Path
import shutil

from vc_clone_graph.rehearsal_config import load_rehearsal_config
from vclogic_web.investor_catalog import InvestorCatalog
from vclogic_web.investor_versions import atomic_json, digest, safe_file
from vclogic_web.profiles import ProfileService

SLUGS = ('charles-hudson-precursor-ventures', 'cyan-banister-long-journey-ventures',
         'elizabeth-yin-hustle-fund', 'jesse-middleton-flybridge',
         'jillian-manus-structure-capital', 'phil-nadel')
CONFIG = 'configs/rehearsal-charles-v41-grounded.toml'
REGISTRY = 'evaluation/canonical_runs_v4_v41_portfolio_2026-08-15.json'
LIMITATION = ('Source-project reference history for descriptive dossiers only. '
              'Current source and installed catalog fingerprints match; this does not '
              'prove historical executions used the current investor inputs or provide calibration evidence.')


def payload_digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def legacy_versions(workspace: Path) -> dict[str, str]:
    catalog = InvestorCatalog(workspace=workspace, config=load_rehearsal_config(workspace/CONFIG, workspace=workspace))
    versions = {}
    for slug in SLUGS:
        row = catalog._legacy(workspace/f'inputs/investors/{slug}.toml', workspace/'inputs')
        if not row.ready:
            raise ValueError(f'{workspace.name}/{slug}: {row.error}')
        versions[slug] = row.version_id
    return versions


def source_history(source: Path, slug: str) -> tuple[list[dict], dict]:
    service = ProfileService(source/'inputs', workspace=source)
    profile = service._profile(slug)
    registry_path = safe_file(source, REGISTRY)
    registry = json.loads(registry_path.read_text())
    entry = registry.get('investors', {}).get(service._canonical_key(profile), {})
    rows, provenance, seen = [], [], set()
    for declaration in entry.get('sources', []):
        pattern = declaration.get('path')
        if declaration.get('kind') != 'summary_glob' or not isinstance(pattern, str):
            continue
        for summary_name in glob.glob(str(registry_path.parent/pattern)):
            summary = Path(summary_name).resolve()
            if not summary.is_relative_to(source):
                raise ValueError('canonical summary escaped source workspace')
            summary = safe_file(source, summary.relative_to(source).as_posix())
            investigation = summary.parent/'phase1/investigation.json'
            if not investigation.is_file() or investigation in seen:
                continue
            seen.add(investigation)
            safe_file(source, investigation.relative_to(source).as_posix())
            payload = json.loads(investigation.read_text())
            if not isinstance(payload, dict):
                continue
            rows.append(payload)
            evidence = dict(path=investigation.relative_to(source).as_posix(), sha256=digest(investigation),
                            summary_path=summary.relative_to(source).as_posix(), summary_sha256=digest(summary))
            run_provenance = summary.parent/'input-provenance.json'
            if run_provenance.is_file():
                recorded = json.loads(run_provenance.read_text())
                evidence['input_provenance'] = dict(path=run_provenance.relative_to(source).as_posix(),
                                                    sha256=digest(run_provenance), recorded=recorded)
                manifest_name = recorded.get('package_manifest_path')
                if isinstance(manifest_name, str):
                    manifest = Path(manifest_name)
                    if not manifest.is_absolute():
                        manifest = source/manifest
                    if manifest.resolve().is_relative_to(source) and manifest.is_file():
                        manifest = safe_file(source, manifest.relative_to(source).as_posix())
                        current_hash = digest(manifest)
                        evidence['input_provenance'].update(current_manifest_sha256=current_hash,
                            recorded_manifest_matches_current=current_hash == recorded.get('package_manifest_sha256'))
            provenance.append(evidence)
    if rows != list(service._investigations(slug)):
        raise ValueError(f'{slug}: source investigations changed during export')
    return rows, dict(source_workspace=str(source), registry=dict(path=REGISTRY, sha256=digest(registry_path)),
                     investigations=provenance, limitation=LIMITATION)


def build_sidecars(source: Path, target: Path) -> dict[str, dict]:
    source_versions, target_versions = legacy_versions(source), legacy_versions(target)
    # Check every identity before preparing any writes.
    for slug in SLUGS:
        if source_versions[slug] != target_versions[slug]:
            raise ValueError(f'{slug}: source and installed investor versions differ; refusing dossier attachment')
    bundles = {}
    for slug in SLUGS:
        rows, provenance = source_history(source, slug)
        if not rows:
            raise ValueError(f'{slug}: canonical reference investigations are missing')
        provenance['source_investor_version_id'] = source_versions[slug]
        bundles[slug] = dict(schema='vc-profile-evidence-v1', vc_slug=slug,
                             investor_version_id=target_versions[slug], investigations=rows,
                             investigations_sha256=payload_digest(rows), provenance=provenance)
    return bundles


def sync(source: Path, target: Path, *, apply: bool) -> dict:
    source, target = source.resolve(strict=True), target.resolve(strict=True)
    if source == target:
        raise ValueError('source and target workspaces must differ')
    bundles = build_sidecars(source, target)
    report = dict(dry_run=not apply, source=str(source), target=str(target), investors=[])
    for slug, payload in bundles.items():
        relative = f"outputs/web-investors/profile-evidence/{slug}/{payload['investor_version_id']}.json"
        destination = safe_file(target, relative)
        try:
            existing = json.loads(destination.read_text()) if destination.exists() else None
        except ValueError:
            # Keep the original bytes in the backup and repair malformed exports.
            existing = None
        changed = existing != payload
        row = dict(vc_slug=slug, investor_version_id=payload['investor_version_id'],
                   investigation_count=len(payload['investigations']), changed=changed, path=relative)
        if apply and changed:
            if destination.exists():
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
                backup = destination.with_name(destination.name + f'.{stamp}.bak')
                shutil.copy2(destination, backup)
                row['backup'] = backup.relative_to(target).as_posix()
            atomic_json(destination, payload)
        report['investors'].append(row)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(sync(args.source, args.target, apply=args.apply), indent=2))


if __name__ == '__main__':
    main()
