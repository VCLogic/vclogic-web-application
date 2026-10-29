"""Active-version profiles, with explicit read-only previews and legacy references."""
import tomllib
from .investor_catalog import InvestorCatalog
from vc_clone_graph.rehearsal_runtime import _registry_profile
from .profiles import ProfileService
from .portraits import PortraitCache
from .dossier_evidence import load_profile_evidence, reference_paths, LEGACY_SLUGS, signature
from .profile_identity import enrich_identity
from .wiki_profiles import WikiLibrary, WikiProfileService


class CatalogProfiles:
    def __init__(self, catalog: InvestorCatalog, *, wiki_roots=None):
        self.catalog = catalog
        self.portraits = PortraitCache(catalog.workspace)
        self.wikis = WikiLibrary(catalog.workspace, self.portraits, wiki_roots)
        self._services: dict[tuple, ProfileService] = {}

    def identities(self):
        rows = {}
        roots = [self.catalog.workspace.parent / 'vc-digital-twins/langgraph-vc-clone-framework/inputs/investors',
                 self.catalog.workspace / 'inputs/investors']
        for path in (path for root in roots for path in root.glob('*.toml')):
            try:
                row = tomllib.loads(path.read_text())
                slug = row['vc_slug']
                rows[slug] = {key: row.get(key) or rows.get(slug, {}).get(key, '') for key in ('vc_slug', 'display_name', 'firm')}
            except (OSError, ValueError, KeyError):
                continue
        for slug in self.wikis.slugs():
            service = self.wikis.service(slug)
            if service:
                card = service.list_profiles()[0]
                existing = rows.get(slug, {})
                rows[slug] = dict(vc_slug=slug, display_name=card.display_name,
                                  firm=card.firm or existing.get('firm', ''))
        return tuple(rows[slug] for slug in sorted(rows))

    def _runtime_service(self, slug, state=None):
        state = state or next((row for row in self.catalog.settings()['investors'] if row['vc_slug'] == slug), None)
        if state is None:
            raise ValueError('No active investor version. Choose one in Settings.')
        version = self.catalog._versions.get(slug, {}).get(state['active_version'])
        if version is None:
            candidates = [row for row in self.catalog._versions.get(slug, {}).values() if row.ready]
            installed = [row for row in candidates if row.installed]
            choices = installed if len(installed) == 1 else candidates
            if len(choices) != 1:
                raise ValueError('The selected investor version is unavailable. Choose one in Settings.')
            # Inspection only. Execution still requires the saved active version.
            version = choices[0]
        inputs = version.files[f'inputs/investors/{slug}.toml'].parent.parent
        evidence_path = self.catalog.root/'profile-evidence'/slug/f'{version.version_id}.json'
        key = (slug, version.version_id, str(inputs), signature(evidence_path),
               tuple((str(path), signature(path)) for path in reference_paths(self.catalog.root/'profile-evidence', slug)))
        if key not in self._services:
            if version.ready:
                service = ProfileService(inputs, portrait_cache=self.portraits, workspace=inputs.parent, include_historical=False,
                    dossier_evidence=load_profile_evidence(self.catalog.root/'profile-evidence', slug, version.version_id),
                    profile=enrich_identity(_registry_profile(inputs, inputs/f'investors/{slug}.toml'), version.files))
            elif version.legacy:
                # Preserve inspection of installed legacy profiles even when indexes need repair.
                inputs = self.catalog.config.resolve_path(self.catalog.config.rehearsal.input_root)
                service = ProfileService(inputs, portrait_cache=self.portraits, workspace=self.catalog.workspace,
                    include_historical=False, dossier_evidence=load_profile_evidence(self.catalog.root/'profile-evidence', slug, version.version_id),
                    profile=enrich_identity(_registry_profile(inputs, inputs/f'investors/{slug}.toml'), version.files))
            else:
                raise ValueError(version.error or 'Investor version is not ready.')
            self._services[key] = service
        return self._services[key], version.version_id, state['enabled'] and state['available']

    def _service(self, slug, state=None):
        wiki = self.wikis.service(slug)
        if wiki is None:
            return self._runtime_service(slug, state)
        state = state or next((row for row in self.catalog.cached_settings()['investors'] if row['vc_slug'] == slug), None)
        version_id = state['active_version'] if state else None
        version = self.catalog._versions.get(slug, {}).get(version_id)
        matches = bool(version and version.ready and all(
            version.hashes.get(f'inputs/wiki/{slug}/{name}') == value for name, value in wiki.runtime_hashes.items()))
        return wiki, version_id, bool(state and state['enabled'] and state['available'] and matches)

    def _card(self, service, version_id, available):
        card = service.list_profiles()[0]
        wiki = isinstance(service, WikiProfileService)
        note = None if available else (
            'This wiki is ready to read. Prepare or update its assessment bundle and select a ready version in Settings to assess with this memory.' if wiki else
            'The saved version is unavailable. Showing a ready version for inspection; choose it in Settings before assessing.')
        return card.model_copy(update={'investor_version_id': version_id, 'start_available': available,
            'selection_note': note, 'memory_note': ('Displaying the current generated wiki. Assessment readiness is checked separately.' if wiki else self.wikis.errors.get(card.vc_slug))})

    def list_profiles(self, *, include_unavailable=False):
        live_slugs = self.wikis.slugs()
        settings = self.catalog.cached_settings() if live_slugs else self.catalog.settings()
        rows = {row['vc_slug']: row for row in settings['investors']}
        cards = []
        slugs = set(rows) | (set(live_slugs) if include_unavailable else set())
        renamed_phil = 'phil-nadel-forefront-venture-partners' in slugs and rows.get('phil-nadel-forefront-venture-partners', {}).get('enabled', True)
        for slug in sorted(slugs):
            if renamed_phil and slug == 'phil-nadel':
                continue
            state = rows.get(slug)
            if state and not state['enabled']:
                continue
            try:
                if state is None and self.wikis.service(slug) is None:
                    continue
                service, version_id, available = self._service(slug, state)
                if include_unavailable or available:
                    cards.append(self._card(service, version_id, available))
            except (ValueError, OSError):
                continue
        return tuple(sorted(cards, key=lambda card: card.display_name))

    def profile(self, slug):
        service, version_id, available = self._service(slug)
        profile = service.profile(slug)
        reference_sections = ()
        legacy_slug = LEGACY_SLUGS.get(slug)
        source = self.catalog.workspace.parent/'vc-digital-twins/langgraph-vc-clone-framework'
        registry = source/f'inputs/investors/{legacy_slug}.toml'
        if legacy_slug and registry.is_file():
            try:
                historical = ProfileService(source/'inputs', workspace=source, include_historical=False,
                    profile=_registry_profile(source/'inputs', registry))
                reference_sections = historical.profile(legacy_slug).sections
            except (OSError, ValueError):
                pass
        reference_graph = None
        if isinstance(service, WikiProfileService):
            history = load_profile_evidence(self.catalog.root/'profile-evidence', slug, version_id or '')
            if history.investigations:
                historical = ProfileService(service.input_root, workspace=service.workspace,
                    profile=service._profile(slug), include_historical=False, dossier_evidence=history)
                historical._taxonomy = service._taxonomy
                reference_graph = historical.rationale_graph(slug)
        return profile.model_copy(update={'investor': self._card(service, version_id, available),
            'reference_graph': reference_graph, 'reference_sections': reference_sections,
            'reference_note': 'Earlier LangGraph Investment Memory, retained for reference. These chapters are not the inputs for the current assessment version.' if reference_sections else None})

    def chapter(self, slug, section_id, memory_version=None):
        service, _, _ = self._service(slug)
        if isinstance(service, WikiProfileService):
            return service.chapter(slug, section_id, memory_version)
        for section in service.profile(slug).sections:
            if section.section_id == section_id:
                return section
        raise ValueError('Unknown Investment Memory chapter')

    def search_memory(self, slug, *args, **kwargs):
        service, _, _ = self._service(slug)
        return service.search_memory(slug, *args, **kwargs)

    def rationale_graph(self, slug):
        service, _, _ = self._service(slug)
        return service.rationale_graph(slug)

    def portrait(self, slug):
        service, _, _ = self._service(slug)
        return service.portrait(slug)
