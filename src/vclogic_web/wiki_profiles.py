"""Current generated wikis, independent of assessment indexes and historical runs."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import tomllib

from vc_clone_graph.rehearsal_runtime import InvestorProfile
from .dossier_evidence import signature
from .investor_versions import SLUG, safe_file
from .models import EvidenceView
from .profiles import ProfileService, _chapter_preview, _tokens

class WikiChangedError(ValueError):
    pass


CORE = ('persona.md', 'theses.md', 'portfolio_and_constraints.md')
TITLES = dict(zip(CORE, ('Decision policy', 'Investment theses', 'Portfolio and constraints')))


def read_text(path: Path) -> str:
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Wiki file exceeds the display size limit')
    return path.read_text(encoding='utf-8')


class WikiProfileService(ProfileService):
    def __init__(self, path, texts, manifest, profile, taxonomy_path, portraits):
        super().__init__(path.parent, workspace=path.parent, include_historical=False,
                         profile=profile, portrait_cache=portraits)
        self.texts = texts
        self.taxonomy_path = taxonomy_path
        self.manifest = manifest
        self.memory_version = sha256(json.dumps(texts, sort_keys=True).encode()).hexdigest()
        self.runtime_hashes = {name: sha256(text.encode()).hexdigest() for name, text in texts.items()
                              if name in CORE or name in ('context.md', 'sources.md') or name.startswith('evidence/')}
        raw = json.loads(texts.get('evidence.json', '[]'))
        if not isinstance(raw, list):
            raise ValueError('Wiki evidence must be a list')
        rows = {}
        for row in raw:
            if (not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k].strip()
                for k in ('id', 'label', 'quote', 'source'))
                or row.get('direction') not in {'positive', 'negative', 'neutral', 'mixed', 'unresolved'}):
                raise ValueError('Wiki evidence record is incomplete')
            if row['id'] in rows and rows[row['id']] != row:
                raise ValueError('Conflicting wiki evidence IDs')
            rows[row['id']] = row
        self.evidence = tuple(rows.values())
        context = json.loads(texts.get('context.json', '[]'))
        if not isinstance(context, list) or any(not isinstance(row, dict) or any(
            not isinstance(row.get(k), str) for k in ('id', 'source', 'quote', 'claim')) for row in context):
            raise ValueError('Wiki context record is incomplete')
        self.context = tuple({**row, 'id': 'ctx:' + row['id'], 'interpretation': row['claim'],
                              'support': 'source-reported context'} for row in context)
        self.sources = {}
        for block in re.split(r'^##\s+', texts.get('sources.md', ''), flags=re.M)[1:]:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            url = next((line[5:].strip() for line in lines if line.startswith('URL: ')), None)
            if url and not re.match(r'^https?://[^\s]+$', url):
                url = None
            self.sources[lines[0]] = (lines[1] if len(lines) > 1 else lines[0], url)
        self.note = (f"Current Investment Memory: {len(self.evidence)} labelled evidence excerpts from "
                     f"{len({r['source'] for r in self.evidence})} sources. Counts describe public-source evidence, "
                     "not investment decisions, causal importance, or model weights.")
        labels, sources = defaultdict(list), defaultdict(set)
        for row in self.evidence:
            labels[row['label']].append({**row, 'direction': 'unresolved' if row['direction'] == 'mixed' else row['direction']})
            sources[row['source']].add(row['label'])
        pairs = Counter()
        for source_labels in sources.values():
            ordered = sorted(source_labels)
            for i, left in enumerate(ordered):
                for right in ordered[i+1:]:
                    pairs[left, right] += 1
        self.aggregate = dict(labels), dict(pairs), len(sources)
        self.search_rows = [(row, _tokens(' '.join(str(row.get(k, '')) for k in
                            ('id', 'quote', 'label', 'source', 'interpretation')))) for row in (*self.evidence, *self.context)]
        self._response = None
        self.chapters = {}
        self._graph = None
        self._cached_card = None

    def _aggregate(self, slug):
        self._profile(slug)
        return self.aggregate

    def _taxonomy(self):
        if not self.taxonomy_path.is_file():
            return {}
        raw = json.loads(read_text(self.taxonomy_path))
        return {r['label']: r for r in raw if isinstance(r, dict) and isinstance(r.get('label'), str)}

    def _card(self, profile):
        if self._cached_card is None:
            card = super()._card(profile)
            self._cached_card = card.model_copy(update={
                'summary': _chapter_preview(self.texts['persona.md'], limit=420),
                'evidence_coverage': None, 'evidence_note': self.note, 'evidence_basis': 'wiki',
                'memory_version': self.memory_version, 'memory_generated_at': self.manifest.get('generated_at') if isinstance(self.manifest.get('generated_at'), str) else None,
                'evidence_count': len(self.evidence), 'source_count': self.aggregate[2],
                'policy_count': len(re.findall(r'^##\s+\S', self.texts['persona.md'], re.M)),
                'thesis_count': len(re.findall(r'^(?:[-*+] |[0-9]+[.)] )\S', self.texts['theses.md'], re.M)) or len(re.findall(r'^##\s+\S', self.texts['theses.md'], re.M)),
            })
        return self._cached_card

    def profile(self, slug):
        if self._response is None:
            from .models import InvestorProfileResponse, ProfileSection
            sections = []
            for name, text in self.texts.items():
                if not name.endswith('.md') or not text.strip():
                    continue
                title = TITLES.get(name) or next((line.lstrip('# ').strip() for line in text.splitlines() if line.startswith('#')), name)
                section = ProfileSection(section_id=name, title=title, body=text, memory_version=self.memory_version,
                    preview=_chapter_preview(text), character_count=len(text), source_paths=(f'{slug}/{name}',))
                self.chapters[name] = section
                sections.append(section.model_copy(update={'body': '', 'body_loaded': False}))
            self._response = InvestorProfileResponse(investor=self._card(self._profile(slug)), sections=tuple(sections))
        return self._response

    def chapter(self, slug, section_id, memory_version=None):
        self.profile(slug)
        if memory_version and memory_version != self.memory_version:
            raise WikiChangedError('Investment Memory changed. Refresh the dossier to read its current chapters.')
        if section_id not in self.chapters:
            raise ValueError('Unknown Investment Memory chapter')
        return self.chapters[section_id]

    def rationale_graph(self, slug):
        if self._graph is None:
            graph = super().rationale_graph(slug)
            self._graph = graph.model_copy(update={'nodes': tuple(node.model_copy(update={
                'confidence': None, 'salience': 'unresolved', 'investigation_count': None,
                'evidence_ids': tuple(row['id'] for row in self.aggregate[0][node.taxonomy_label]),
            }) for node in graph.nodes), 'evidence_status': 'available' if self.evidence else 'not_prepared',
                'evidence_note': self.note, 'evidence_basis': 'wiki', 'memory_version': self.memory_version})
        return self._graph

    def _search_memory_candidates(self, slug, query):
        self._profile(slug)
        tokens = _tokens(query)
        if not tokens:
            raise ValueError('memory search query is empty')
        results = []
        seen = set()
        for row, searchable in self.search_rows:
            needle = query.strip().removeprefix('ev:')
            score = 1000 if needle == row['id'] else len(tokens & searchable)
            if query.startswith(('ev:', 'ctx:')) and needle != row['id']:
                continue
            key = row['source'], row['quote'], row.get('label')
            if not score or key in seen:
                continue
            seen.add(key)
            results.append((score, EvidenceView(evidence_id=row['id'], source_kind='wiki',
                source_path=f'{slug}/' + ('context.json' if row['id'].startswith('ctx:') else 'evidence.json'),
                source_title=self.sources.get(row['source'], ('Investment Memory evidence', None))[0],
                source_url=self.sources.get(row['source'], ('', None))[1],
                excerpt=row['quote'], rationale_label=row.get('label'), direction=row.get('direction'),
                source_reference=row['source'], support=row.get('support'), interpretation=row.get('interpretation'))))
        return sorted(results, key=lambda item: (-item[0], item[1].evidence_id))


class WikiLibrary:
    def __init__(self, workspace, portraits, roots=None):
        self.workspace = workspace
        self.portraits = portraits
        self.roots = tuple(Path(p).resolve() for p in (roots if roots is not None else (
            Path(__file__).resolve().parents[2]/'wiki',
            workspace.parent/'vclogic-vc-investment-memory/wiki',
        )))
        self.cache = {}
        self.errors = {}

    def slugs(self):
        return sorted({p.name for root in self.roots if root.is_dir() for p in root.iterdir()
                       if SLUG.fullmatch(p.name) and p.is_dir() and not p.is_symlink()
                       and (p/'_manifest.json').is_file()})

    def service(self, slug):
        if not SLUG.fullmatch(slug):
            return None
        for root in self.roots:
            path = root/slug
            if not (path/'_manifest.json').is_file():
                continue
            try:
                # Read only declared wiki surfaces, never arbitrary collector JSON or symlinks.
                names = sorted({p.relative_to(path).as_posix() for p in path.rglob('*.md')})
                names += ['_manifest.json', 'evidence.json', 'context.json']
                if (path/'validation.json').exists():
                    names.append('validation.json')
                files = [safe_file(root, f'{slug}/{name}') for name in names]
                registry = self.workspace/f'inputs/investors/{slug}.toml'
                taxonomy = self.workspace/'inputs/taxonomy/codebook_v_final.json'
                stamp = tuple((str(p), signature(p)) for p in files + [registry, taxonomy])
                cached = self.cache.get(slug)
                if cached and cached[0] == stamp:
                    return cached[1]
                texts = {name: read_text(p) for name, p in zip(names, files) if p.is_file()}
                manifest = json.loads(texts['_manifest.json'])
                if manifest.get('vc_slug') != slug or any(not texts.get(name, '').strip() for name in CORE):
                    raise ValueError('Wiki identity or core chapters are incomplete')
                validation = json.loads(texts.get('validation.json', '{"valid":true}'))
                if validation.get('valid') is not True or validation.get('errors'):
                    raise ValueError('Wiki validation reports errors')
                heading = (texts.get('README.md', '').strip() or texts['persona.md']).splitlines()[0].lstrip('# ').split('—')[0].strip()
                identity = tomllib.loads(read_text(registry)) if registry.is_file() else {}
                if identity and identity.get('vc_slug') != slug:
                    raise ValueError('Registry identity does not match wiki')
                profile = InvestorProfile(slug, identity.get('display_name') or heading or slug.replace('-', ' ').title(),
                    identity.get('firm', ''), identity.get('role', 'Investor'), path, registry)
                service = WikiProfileService(path, texts, manifest, profile, taxonomy, self.portraits)
                # An edit during the read is retried on the next request, not published half-built.
                if stamp != tuple((str(p), signature(p)) for p in files + [registry, taxonomy]):
                    raise ValueError('Wiki is being updated; retry shortly')
                self.cache[slug] = stamp, service
                self.errors.pop(slug, None)
                return service
            except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
                self.cache.pop(slug, None)
                self.errors[slug] = f'Current wiki unavailable: {type(exc).__name__}. Check wiki identity, evidence and validation.'
                return None
        self.cache.pop(slug, None)
        return None
