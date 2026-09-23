"""Profile presentation using the same active versions as job execution."""
from .investor_catalog import InvestorCatalog
from .profiles import ProfileService


class CatalogProfiles:
    def __init__(self, catalog: InvestorCatalog):
        self.catalog = catalog
        self._services: dict[tuple[str, str], ProfileService] = {}

    def _service(self, slug):
        binding = self.catalog.select(slug)
        key = (slug, binding.version_id)
        if key not in self._services:
            # Historical evaluation registries are not calibration for a new version.
            self._services[key] = ProfileService(binding.input_root, workspace=binding.input_root.parent)
        return self._services[key], binding

    def list_profiles(self):
        cards = []
        for row in self.catalog.settings()['investors']:
            if row['enabled'] and row['available']:
                try:
                    service, binding = self._service(row['vc_slug'])
                    cards.extend(card.model_copy(update={'investor_version_id': binding.version_id})
                                 for card in service.list_profiles())
                except ValueError:
                    # A concurrent settings/source change will be shown on refresh.
                    continue
        return tuple(sorted(cards, key=lambda card: card.display_name))

    def profile(self, slug):
        service, binding = self._service(slug)
        profile = service.profile(slug)
        return profile.model_copy(update={'investor': profile.investor.model_copy(
            update={'investor_version_id': binding.version_id})})

    def search_memory(self, slug, *args, **kwargs):
        service, _ = self._service(slug)
        return service.search_memory(slug, *args, **kwargs)

    def rationale_graph(self, slug):
        service, _ = self._service(slug)
        return service.rationale_graph(slug)
