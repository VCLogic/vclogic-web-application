"""Validated investor inputs and retained execution bindings."""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from types import SimpleNamespace
from typing import Any

from vc_clone_graph.config import load_config
from vc_clone_graph.rehearsal_config import RehearsalConfig, load_rehearsal_config
from vc_clone_graph.rehearsal_runtime import _registry_profile, _taxonomy, _load_portfolio
from vc_clone_graph.retrieval import HybridWikiIndex
from vc_clone_graph.precedents import PrecedentCorpus


SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
VERSION = re.compile(r'^[0-9a-f]{64}$')


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.write-')
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def safe_file(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if not relative or path.is_absolute() or '..' in path.parts or '\\' in relative or any(ord(c) < 32 for c in relative):
        raise ValueError('invalid investor asset path')
    target = root / relative
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('investor asset path escapes its source')
    if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != root.parent):
        raise ValueError('investor asset path contains a symlink')
    return target


def digest(path: Path) -> str:
    h = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


@dataclass
class InvestorVersion:
    vc_slug: str
    version_id: str
    label: str
    display_name: str
    source: Path
    files: dict[str, Path] = field(default_factory=dict)
    hashes: dict[str, str] = field(default_factory=dict)
    config: RehearsalConfig | None = None
    canonical_relative: str | None = None
    ready: bool = False
    error: str | None = None
    created_at: str | None = None
    capabilities: dict[str, bool] = field(default_factory=dict)
    legacy: bool = False
    installed: bool = False

    def public(self) -> dict:
        return dict(version_id=self.version_id, label=self.label, ready=self.ready,
                    error=self.error, created_at=self.created_at, capabilities=self.capabilities)


@dataclass(frozen=True)
class ExecutionBinding:
    vc_slug: str
    version_id: str
    workspace: Path
    input_root: Path
    config: RehearsalConfig


def check_inputs(root: Path, slug: str, config: RehearsalConfig, *, indexes: bool) -> None:
    profile = _registry_profile(root, root / f'investors/{slug}.toml')
    if profile.vc_slug != slug or profile.wiki_path != (root/f'wiki/{slug}').resolve():
        raise ValueError('investor registration identity mismatch')
    taxonomy = root / config.rehearsal.taxonomy_path
    if not taxonomy.is_file():
        raise ValueError('investor taxonomy is missing')
    _taxonomy(taxonomy)
    if indexes:
        embedding = config.embedding.model_dump()
        identity = SimpleNamespace(metadata={'backend': embedding['kind'], **{
            key: embedding[key] for key in ('model', 'revision', 'normalize', 'document_prefix', 'query_prefix')
        }})
        HybridWikiIndex.load(root/f'indexes/{slug}.json', root/f'wiki/{slug}', identity,
                            require_complete_embeddings=True)
        if config.precedents.enabled:
            PrecedentCorpus.load(root/f'indexes/{slug}.precedents.json', root/f'data/investors/{slug}/precedents',
                                 identity, require_complete_embeddings=True)
        _load_portfolio(config, root, slug, identity, excluded_episode_slug=None)


def read_bundle(manifest: Path, workspace: Path) -> InvestorVersion:
    raw = json.loads(manifest.read_text())
    if not isinstance(raw, dict):
        raise ValueError('bundle manifest must be an object')
    slug = raw.get('vc_slug', '')
    if not isinstance(slug, str) or not SLUG.fullmatch(slug):
        raise ValueError('invalid investor identity')
    declared = raw.get('files')
    identity = sha256(json.dumps(declared, sort_keys=True).encode()).hexdigest()
    row = InvestorVersion(slug, identity, manifest.parent.name, str(raw.get('display_name') or slug),
                          manifest.parent, created_at=raw.get('created_at'))
    try:
        if raw.get('schema') != 'vclogic-investor-bundle-v1' or not isinstance(declared, dict) or not declared:
            raise ValueError('unsupported or empty investor bundle manifest')
        installed = manifest.parent == workspace/'onboarding'/slug
        row.installed = installed
        if not isinstance(raw.get('capabilities'), dict):
            raise ValueError('bundle capabilities must be an object')
        row.capabilities = {str(k): v for k, v in raw.get('capabilities', {}).items() if isinstance(v, bool)}
        prefixes = (f'inputs/investors/{slug}.toml', f'inputs/wiki/{slug}/',
                    f'inputs/data/investors/{slug}/', f'inputs/indexes/{slug}',
                    'inputs/taxonomy/', f'configs/investors/{slug}/', 'source/', f'evaluation/labels/{slug}.json')
        for relative, expected in declared.items():
            # Validate before checking the allow-list so path errors stay actionable.
            safe_file(row.source, relative)
            if not relative.startswith(prefixes):
                raise ValueError('bundle contains an unsupported asset path')
            if not isinstance(expected, str) or not VERSION.fullmatch(expected):
                raise ValueError('invalid asset hash')
            source_relative = f'onboarding/{slug}/{relative}' if installed and relative.startswith('source/') else relative
            source = safe_file(workspace if installed else row.source, source_relative)
            if not source.is_file() or digest(source) != expected:
                raise ValueError(f'asset hash mismatch or missing file: {relative}')
            row.files[relative] = source
            row.hashes[relative] = expected
        rehearsal = f'configs/investors/{slug}/rehearsal.toml'
        canonical = f'configs/investors/{slug}/canonical.toml'
        row.config = load_rehearsal_config(row.files[rehearsal])
        canonical_config = load_config(row.files[canonical])
        row.canonical_relative = canonical
        if row.config.classification.canonical_config_path != canonical or canonical_config.run.vc_slug != slug:
            raise ValueError('bundle configuration identity mismatch')
        if row.config.rehearsal.input_root != 'inputs' or canonical_config.run.input_root != 'inputs':
            raise ValueError('bundle input path must be inputs')
        if row.config.precedents.enabled != row.capabilities.get('precedents', False) or canonical_config.precedents.enabled != row.config.precedents.enabled:
            raise ValueError('bundle precedent capabilities disagree')
        if row.config.portfolio_memory.enabled != row.capabilities.get('portfolio_memory', False) or canonical_config.portfolio_memory.enabled != row.config.portfolio_memory.enabled:
            raise ValueError('bundle portfolio capabilities disagree')
        inputs = (workspace if installed else row.source)/'inputs'
        required = {f'inputs/investors/{slug}.toml', f'inputs/{row.config.rehearsal.taxonomy_path}', rehearsal, canonical}
        if raw.get('ready_for_assessment') is True:
            required.add(f'inputs/indexes/{slug}.json')
            if row.config.precedents.enabled:
                required.add(f'inputs/indexes/{slug}.precedents.json')
        for folder in (inputs/f'wiki/{slug}', inputs/f'data/investors/{slug}'):
            if folder.is_dir():
                required.update('inputs/' + path.relative_to(inputs).as_posix() for path in folder.rglob('*') if path.is_file())
        if required - row.files.keys():
            raise ValueError('bundle manifest omits required execution assets')
        if canonical_config.embedding != row.config.embedding:
            raise ValueError('canonical and rehearsal embedding settings disagree')
        check_inputs(inputs, slug, row.config, indexes=raw.get('ready_for_assessment') is True)
        row.ready = raw.get('ready_for_assessment') is True
        if not row.ready:
            row.error = 'Onboarding has not finished building the required indexes.'
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        row.error = str(exc)
    return row


def materialize(row: InvestorVersion, destination: Path, workspace: Path, default: RehearsalConfig) -> ExecutionBinding:
    if not row.ready or row.config is None or not row.canonical_relative:
        raise ValueError(row.error or 'investor version is not ready')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        with tempfile.TemporaryDirectory(dir=destination.parent, prefix='.snapshot-') as temporary:
            stage = Path(temporary)/'version'
            stage.mkdir()
            for relative, source in row.files.items():
                target = safe_file(stage, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                if digest(target) != row.hashes[relative]:
                    raise ValueError('investor inputs changed while retaining the version; refresh and try again')
            check_inputs(stage/'inputs', row.vc_slug, row.config, indexes=True)
            config = row.config.model_copy(deep=True)
            prefix = destination.relative_to(workspace).as_posix()
            rehearsal = config.rehearsal.model_copy(update={
                'input_root': f'{prefix}/inputs',
                'output_root': default.rehearsal.output_root,
                'checkpoint_path': f'{prefix}/runtime/checkpoints.sqlite',
            })
            classification = config.classification.model_copy(update={
                'canonical_config_path': f'{prefix}/{row.canonical_relative}',
                'registry_path': f'{prefix}/{row.config.classification.registry_path}',
                'canonical_registry_path': f'{prefix}/{row.config.classification.canonical_registry_path}',
            })
            config = config.model_copy(update={'rehearsal': rehearsal, 'classification': classification})
            atomic_json(stage/'binding.json', dict(vc_slug=row.vc_slug, version_id=row.version_id,
                        config=config.model_dump(mode='json'), hashes=row.hashes))
            os.rename(stage, destination)
    return load_binding(destination, workspace)


def load_binding(destination: Path, workspace: Path) -> ExecutionBinding:
    try:
        return _load_binding(destination, workspace)
    except (OSError, KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError('Retained investor version is unavailable or invalid. Restore its snapshot to resume this work.') from exc


def _load_binding(destination: Path, workspace: Path) -> ExecutionBinding:
    data = json.loads((destination/'binding.json').read_text())
    # Recheck retained inputs before executing; runtime outputs are outside this inventory.
    for relative, expected in data['hashes'].items():
        if digest(safe_file(destination, relative)) != expected:
            raise ValueError('retained investor version integrity check failed')
    config = RehearsalConfig.model_validate(data['config'])
    config._workspace = workspace
    return ExecutionBinding(data['vc_slug'], data['version_id'], workspace,
                            config.resolve_path(config.rehearsal.input_root), config)
