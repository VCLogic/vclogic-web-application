"""Profile presentation using the same active versions as job execution."""
from .investor_catalog import InvestorCatalog
from vc_clone_graph.rehearsal_runtime import _registry_profile
from .profiles import ProfileService


class CatalogProfiles:
    def __init__(self, catalog: InvestorCatalog):
        self.catalog = catalog
        self._services: dict[tuple[str, str, str], ProfileService] = {}

    def _service(self, slug):
        state = next((row for row in self.catalog.settings()['investors'] if row['vc_slug'] == slug), None)
        if state is None or not state['active_version']:
            raise ValueError('No active investor version. Choose one in Settings.')
        version = self.catalog._versions.get(slug, {}).get(state['active_version'])
        if version is None:
            raise ValueError('The selected investor version is unavailable.')
        inputs = version.files[f'inputs/investors/{slug}.toml'].parent.parent
        key = (slug, version.version_id, str(inputs))
        if key not in self._services:
            if version.ready:
                service = ProfileService(inputs, workspace=inputs.parent, include_historical=False,
                    profile=_registry_profile(inputs, inputs/f'investors/{slug}.toml'))
            elif version.legacy:
                # Preserve inspection of installed legacy profiles even when indexes need repair.
                inputs = self.catalog.config.resolve_path(self.catalog.config.rehearsal.input_root)
                service = ProfileService(inputs, workspace=self.catalog.workspace,
                    profile=_registry_profile(inputs, inputs/f'investors/{slug}.toml'))
            else:
                raise ValueError(version.error or 'Investor version is not ready.')
            self._services[key] = service
        return self._services[key], version.version_id, state['enabled'] and state['available']

    def list_profiles(self):
        cards = []
        for row in self.catalog.settings()['investors']:
            if row['enabled'] and row['available']:
                try:
                    service, version_id, available = self._service(row['vc_slug'])
                    cards.extend(card.model_copy(update={'investor_version_id': version_id, 'start_available': available})
                                 for card in service.list_profiles() if card.vc_slug == row['vc_slug'])
                except ValueError:
                    # A concurrent settings/source change will be shown on refresh.
                    continue
        return tuple(sorted(cards, key=lambda card: card.display_name))

    def profile(self, slug):
        service, version_id, available = self._service(slug)
        profile = service.profile(slug)
        return profile.model_copy(update={'investor': profile.investor.model_copy(
            update={'investor_version_id': version_id, 'start_available': available})})

    def search_memory(self, slug, *args, **kwargs):
        service, _, _ = self._service(slug)
        return service.search_memory(slug, *args, **kwargs)

    def rationale_graph(self, slug):
        service, _, _ = self._service(slug)
        return service.rationale_graph(slug)
