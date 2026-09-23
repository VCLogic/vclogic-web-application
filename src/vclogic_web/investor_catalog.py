"""One catalog for discovery, persistent choices, and version-specific execution."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from threading import RLock
from time import monotonic
from typing import Iterable

from vc_clone_graph.rehearsal_config import RehearsalConfig, load_rehearsal_config
from vc_clone_graph.rehearsal_runtime import _registry_profile
from vc_clone_graph.config import load_config
from .investor_versions import (
    ExecutionBinding, InvestorVersion, SLUG, VERSION, atomic_json, check_inputs,
    digest, load_binding, materialize, read_bundle, safe_file,
)


class InvestorCatalog:
    def __init__(self, *, workspace: Path, config: RehearsalConfig,
                 bundle_roots: Iterable[Path] | None = None) -> None:
        self.workspace = Path(workspace).resolve()
        self.config = config
        self.root = self.workspace/'outputs/web-investors'
        self.preferences_path = self.root/'settings.json'
        self.bundle_roots = tuple(Path(p).resolve() for p in (
            bundle_roots if bundle_roots is not None else
            [self.workspace.parent/'vclogic-vc-investor-onboarding/bundles']))
        self._guard = RLock()
        self._versions: dict[str, dict[str, InvestorVersion]] = {}
        self._cache: dict[Path, tuple[tuple, InvestorVersion]] = {}
        self._errors: list[str] = []
        self._last_refresh = 0.0

    def _preferences(self) -> dict:
        if not self.preferences_path.exists():
            return {}
        try:
            data = json.loads(self.preferences_path.read_text())
            if not isinstance(data, dict):
                raise ValueError('settings must be an object')
            return data
        except (OSError, ValueError) as exc:
            raise ValueError('Investor settings could not be read; restore settings.json before making changes.') from exc

    @staticmethod
    def _signature(paths: Iterable[Path]) -> tuple:
        result = []
        for path in sorted(set(paths)):
            try:
                stat = path.stat()
                result.append((str(path), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size))
            except OSError:
                result.append((str(path), None))
        return tuple(result)

    def _bundle(self, manifest: Path) -> InvestorVersion:
        # Hash/index verification is reused only while every declared file's stat is unchanged.
        raw = json.loads(manifest.read_text())
        if not isinstance(raw, dict) or not isinstance(raw.get('files'), dict):
            raise ValueError('invalid bundle manifest')
        installed = manifest.parent.parent == self.workspace/'onboarding'
        paths = [manifest]
        for relative in raw.get('files', {}):
            root = self.workspace if installed and not relative.startswith('source/') else manifest.parent
            paths.append(safe_file(root, relative))
        signature = self._signature(paths)
        cached = self._cache.get(manifest)
        if cached and cached[0] == signature:
            return cached[1]
        row = read_bundle(manifest, self.workspace)
        self._cache[manifest] = (signature, row)
        return row

    def _legacy(self, registry: Path, inputs: Path) -> InvestorVersion:
        profile = _registry_profile(inputs, registry)
        slug = profile.vc_slug
        if not SLUG.fullmatch(slug):
            raise ValueError('invalid investor identity')
        source_config = self.workspace/f'configs/investors/{slug}/rehearsal.toml'
        config = load_rehearsal_config(source_config, workspace=self.workspace) if source_config.exists() else self.config
        template = config.classification.canonical_config_path
        if not template:
            raise ValueError('investor lacks a canonical assessment configuration')
        canonical = safe_file(self.workspace, template)
        paths = {f'inputs/investors/{slug}.toml': registry,
                 'inputs/taxonomy/codebook_v_final.json': inputs/'taxonomy/codebook_v_final.json',
                 'configs/canonical.toml': canonical}
        for folder, destination in ((profile.wiki_path, f'inputs/wiki/{slug}'),
                                    (inputs/f'data/investors/{slug}', f'inputs/data/investors/{slug}'),
                                    (self.workspace/'evaluation/rehearsal_classifier_registry', 'evaluation/rehearsal_classifier_registry')):
            if folder.is_dir():
                for path in folder.rglob('*'):
                    if path.is_file():
                        paths[f'{destination}/{path.relative_to(folder).as_posix()}'] = path
        for path in (inputs/'indexes').glob(f'{slug}*.json'):
            paths[f'inputs/indexes/{path.name}'] = path
        signature = self._signature(paths.values()) + (config.model_dump_json(),)
        cached = self._cache.get(registry)
        if cached and cached[0] == signature:
            return cached[1]
        row = InvestorVersion(slug, '', 'Installed profile', profile.display_name, self.workspace,
                              files=paths, config=config, canonical_relative='configs/canonical.toml', legacy=True, installed=True)
        try:
            for relative, path in paths.items():
                safe_file(self.workspace, path.relative_to(self.workspace).as_posix())
                row.hashes[relative] = digest(path)
            load_config(canonical)
            check_inputs(inputs, slug, config, indexes=True)
            row.ready = True
        except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
            row.error = str(exc)
        row.version_id = sha256(json.dumps([row.hashes, config.model_dump(mode='json')], sort_keys=True).encode()).hexdigest()
        row.capabilities = dict(wiki=True, precedents=config.precedents.enabled,
                                portfolio_memory=config.portfolio_memory.enabled,
                                classifier=config.classification.classifier_tiebreaker)
        self._cache[registry] = (signature, row)
        return row

    def refresh(self) -> dict:
        with self._guard:
            versions: dict[str, dict[str, InvestorVersion]] = {}
            self._errors = []
            manifests = set((self.workspace/'onboarding').glob('*/bundle.json'))
            for root in self.bundle_roots:
                if (root/'bundle.json').is_file():
                    manifests.add(root/'bundle.json')
                manifests.update(root.glob('*/bundle.json'))
            installed_slugs = set()
            for path in sorted(manifests):
                try:
                    try:
                        row = self._bundle(path)
                    except (ValueError, TypeError, KeyError):
                        # Produce a visible invalid version when a manifest has a usable identity.
                        row = read_bundle(path, self.workspace)
                    candidates = versions.setdefault(row.vc_slug, {})
                    existing = candidates.get(row.version_id)
                    if existing is None or (row.ready and not existing.ready) or (row.ready == existing.ready and row.installed):
                        row.installed = row.installed or bool(existing and existing.installed)
                        candidates[row.version_id] = row
                    elif row.installed:
                        existing.installed = True
                    if path.parent == self.workspace/'onboarding'/row.vc_slug:
                        installed_slugs.add(row.vc_slug)
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    self._errors.append(f'{path.parent.name}: {exc}')
            inputs = self.config.resolve_path(self.config.rehearsal.input_root)
            for path in sorted((inputs/'investors').glob('*.toml')):
                if path.stem in installed_slugs:
                    continue
                try:
                    row = self._legacy(path, inputs)
                    versions.setdefault(row.vc_slug, {})[row.version_id] = row
                except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
                    self._errors.append(f'{path.stem}: {exc}')
            self._versions = versions
            preferences = self._preferences()
            changed = False
            for slug, candidates in versions.items():
                if slug not in preferences or preferences[slug].get('automatic_pending', False):
                    ready = [row.version_id for row in candidates.values() if row.ready]
                    installed = [row.version_id for row in candidates.values() if row.installed]
                    active = installed[0] if len(installed) == 1 else (ready[0] if len(ready) == 1 else None)
                    preferences[slug] = dict(enabled=active is not None, active_version=active, automatic_pending=active is None)
                    changed = True
            if changed:
                atomic_json(self.preferences_path, preferences)
            self._last_refresh = monotonic()
            return self._settings(preferences)

    def _settings(self, preferences: dict) -> dict:
        rows = []
        for slug in sorted(set(preferences) | set(self._versions)):
            choice = preferences.get(slug, {})
            candidates = self._versions.get(slug, {})
            active = candidates.get(choice.get('active_version'))
            rows.append(dict(vc_slug=slug, display_name=next(iter(candidates.values())).display_name if candidates else slug,
                             enabled=bool(choice.get('enabled')), active_version=choice.get('active_version'),
                             available=bool(active and active.ready),
                             versions=[row.public() for row in candidates.values()]))
        return dict(investors=rows, discovery_errors=self._errors)

    def settings(self) -> dict:
        with self._guard:
            if self._last_refresh and monotonic() - self._last_refresh < 5:
                return self._settings(self._preferences())
            return self.refresh()

    def update(self, slug: str, *, enabled: bool, active_version: str | None) -> dict:
        with self._guard:
            self.refresh()
            preferences = self._preferences()
            if slug not in preferences:
                raise ValueError('unknown investor profile')
            current = preferences[slug]
            selected = self._versions.get(slug, {}).get(active_version)
            # A missing selection may be retained while disabling, but never introduced.
            if (enabled or active_version != current.get('active_version')) and (not selected or not selected.ready):
                raise ValueError('Select a ready investor version before enabling it.')
            preferences[slug] = dict(enabled=enabled, active_version=active_version, automatic_pending=False)
            atomic_json(self.preferences_path, preferences)
            return self._settings(preferences)

    def select(self, slug: str, expected_version: str | None = None) -> ExecutionBinding:
        with self._guard:
            self.settings()
            selected = self._preferences().get(slug, {})
            version = selected.get('active_version')
            if not selected.get('enabled') or not version:
                raise ValueError('Investor is disabled or has no active version. Refresh the investor list.')
            if expected_version and expected_version != version:
                raise ValueError('The active investor version changed. Refresh the investor list and try again.')
            candidate = self._versions.get(slug, {}).get(version)
            if not candidate or not candidate.ready:
                raise ValueError('The active investor version is unavailable. Choose a ready version in Settings.')
            return self.binding(slug, version)

    def binding(self, slug: str, version_id: str) -> ExecutionBinding:
        with self._guard:
            if not SLUG.fullmatch(slug) or not VERSION.fullmatch(version_id):
                raise ValueError('invalid investor version identity')
            destination = self.root/'versions'/slug/version_id
            if (destination/'binding.json').is_file():
                binding = load_binding(destination, self.workspace)
                if binding.vc_slug != slug or binding.version_id != version_id:
                    raise ValueError('retained investor identity mismatch')
                return binding
            candidate = self._versions.get(slug, {}).get(version_id)
            if candidate is None:
                self.refresh()
                candidate = self._versions.get(slug, {}).get(version_id)
            if candidate is None:
                raise ValueError('The recorded investor version is unavailable.')
            try:
                return materialize(candidate, destination, self.workspace, self.config)
            except OSError as exc:
                raise ValueError('Investor assets changed or could not be retained. Refresh investors and check the bundle and available disk space.') from exc
