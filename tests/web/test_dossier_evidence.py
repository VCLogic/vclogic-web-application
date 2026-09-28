from hashlib import sha256
import json

from test_investor_catalog import bundle, catalog
from vclogic_web.catalog_profiles import CatalogProfiles


def write_evidence(service, version, *, slug='new-vc'):
    rows = [{'rationales': [{'taxonomy_label': 'founder_market_fit', 'direction': 'positive',
                            'confidence': 0.8, 'salience': 'primary'}]}]
    data = dict(schema='vc-profile-evidence-v1', vc_slug=slug, investor_version_id=version,
                investigations=rows, investigations_sha256=sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                provenance={'source_workspace': 'source-project'})
    path = service.root/'profile-evidence'/slug/f'{version}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return path


def test_import_restores_signature_and_gallery_without_changing_runtime_version(tmp_path):
    bundle(tmp_path/'bundles'/'v1')
    service = catalog(tmp_path)
    version = service.settings()['investors'][0]['active_version']
    profiles = CatalogProfiles(service)
    assert profiles.rationale_graph('new-vc').nodes == ()
    write_evidence(service, version)
    graph = profiles.rationale_graph('new-vc')
    assert len(graph.nodes) == 1
    assert graph.nodes[0].occurrence_count == 1
    assert graph.evidence_status == 'available'
    card = profiles.list_profiles()[0]
    assert card.recurring_positive_counts == {'founder_market_fit': 1}
    assert card.investor_version_id == version
    assert profiles.profile('new-vc').sections[0].body == 'First memory'


def test_history_does_not_leak_to_other_version_and_missing_data_is_explained(tmp_path):
    bundle(tmp_path/'bundles'/'v1')
    service = catalog(tmp_path)
    first = service.settings()['investors'][0]['active_version']
    write_evidence(service, first)
    profiles = CatalogProfiles(service)
    assert profiles.rationale_graph('new-vc').nodes
    bundle(tmp_path/'bundles'/'v2', text='New approach')
    second = next(row['version_id'] for row in service.refresh()['investors'][0]['versions'] if row['version_id'] != first)
    service.update('new-vc', enabled=True, active_version=second)
    graph = profiles.rationale_graph('new-vc')
    assert graph.nodes == ()
    assert graph.evidence_status == 'not_prepared'
    assert 'Investment Memory' in graph.evidence_note


def test_invalid_import_does_not_hide_wiki_or_break_gallery(tmp_path):
    bundle(tmp_path/'bundles'/'v1')
    service = catalog(tmp_path)
    version = service.settings()['investors'][0]['active_version']
    path = write_evidence(service, version)
    data = json.loads(path.read_text())
    data['investigations'][0]['rationales'][0]['direction'] = 'negative'
    path.write_text(json.dumps(data))
    profiles = CatalogProfiles(service)
    graph = profiles.rationale_graph('new-vc')
    assert graph.nodes == ()
    assert graph.evidence_status == 'invalid'
    assert profiles.profile('new-vc').sections
    assert profiles.list_profiles()[0].start_available


def test_unready_legacy_inspection_does_not_load_unbound_workspace_history(tmp_path):
    service = catalog(tmp_path)
    bundle(service.workspace, ready=False)
    registry = service.workspace/'evaluation/canonical_runs_v4_v41_portfolio_2026-08-15.json'
    registry.parent.mkdir()
    registry.write_text(json.dumps({'investors': {'new-vc': {'sources': [
        {'kind': 'summary_glob', 'path': '../outputs/old-run/*/summary.json'}]}}}))
    run = service.workspace/'outputs/old-run/pitch'
    (run/'phase1').mkdir(parents=True)
    (run/'summary.json').write_text('{}')
    (run/'phase1/investigation.json').write_text(json.dumps({'rationales': [
        {'taxonomy_label': 'founder_market_fit', 'direction': 'positive', 'confidence': 0.9}]}))
    profiles = CatalogProfiles(service)
    graph = profiles.rationale_graph('new-vc')
    assert not graph.nodes
    assert graph.evidence_status == 'not_prepared'
    assert profiles.profile('new-vc').sections
