import json
import shutil
from test_investor_catalog import bundle, catalog
from test_dossier_evidence import write_evidence
from vclogic_web.catalog_profiles import CatalogProfiles


def test_replaced_version_remains_visible_but_cannot_start(tmp_path):
    root = bundle(tmp_path/'bundles/v1')
    cat = catalog(tmp_path)
    old = cat.settings()['investors'][0]['active_version']
    shutil.rmtree(root)
    bundle(tmp_path/'bundles/v2', text='Refreshed memory')
    cat.refresh()
    cards = CatalogProfiles(cat).list_profiles(include_unavailable=True)
    assert CatalogProfiles(cat).list_profiles() == ()
    assert len(cards) == 1
    assert not cards[0].start_available
    assert cards[0].selection_note
    assert cat._preferences()['new-vc']['active_version'] == old


def test_legacy_reference_history_survives_memory_refresh(tmp_path):
    slug = 'charles-hudson-precursor-ventures'
    bundle(tmp_path/'bundles/v1', slug=slug)
    cat = catalog(tmp_path)
    old = cat.settings()['investors'][0]['active_version']
    write_evidence(cat, old, slug=slug)
    bundle(tmp_path/'bundles/v2', slug=slug, text='Current memory')
    current = next(v['version_id'] for v in cat.refresh()['investors'][0]['versions'] if v['version_id'] != old)
    cat.update(slug, enabled=True, active_version=current)
    profiles = CatalogProfiles(cat)
    graph = profiles.rationale_graph(slug)
    assert len(graph.nodes) == 1
    assert 'earlier' in graph.evidence_note.lower()
    assert old in graph.evidence_note
    assert profiles.profile(slug).investor.investor_version_id == current
    assert profiles.profile(slug).sections[0].body == 'Current memory'


def test_old_chapters_are_separate_from_current_memory(tmp_path):
    slug = 'charles-hudson-precursor-ventures'
    bundle(tmp_path/'bundles/v1', slug=slug, text='Current memory')
    cat = catalog(tmp_path)
    source = cat.workspace.parent/'vc-digital-twins/langgraph-vc-clone-framework'
    bundle(source, slug=slug, text='Original LangGraph chapter')
    profile = CatalogProfiles(cat).profile(slug)
    assert profile.sections[0].body == 'Current memory'
    assert profile.reference_sections[0].body == 'Original LangGraph chapter'
    assert 'earlier' in profile.reference_note.lower()


def test_invalid_exact_history_never_falls_back(tmp_path):
    slug = 'charles-hudson-precursor-ventures'
    bundle(tmp_path/'bundles/v1', slug=slug)
    cat = catalog(tmp_path)
    old = cat.settings()['investors'][0]['active_version']
    write_evidence(cat, old, slug=slug)
    bundle(tmp_path/'bundles/v2', slug=slug, text='Current memory')
    current = next(v['version_id'] for v in cat.refresh()['investors'][0]['versions'] if v['version_id'] != old)
    cat.update(slug, enabled=True, active_version=current)
    path = write_evidence(cat, current, slug=slug)
    path.write_text('{}')
    graph = CatalogProfiles(cat).rationale_graph(slug)
    assert graph.evidence_status == 'invalid'
    assert not graph.nodes


def test_phil_renamed_identity_uses_explicit_legacy_reference(tmp_path):
    slug = 'phil-nadel-forefront-venture-partners'
    bundle(tmp_path/'bundles/v1', slug=slug)
    cat = catalog(tmp_path)
    cat.settings()
    write_evidence(cat, 'a'*64, slug='phil-nadel')
    assert CatalogProfiles(cat).rationale_graph(slug).nodes


def test_different_earlier_histories_are_not_combined(tmp_path):
    slug = 'charles-hudson-precursor-ventures'
    bundle(tmp_path/'bundles/v1', slug=slug)
    cat = catalog(tmp_path)
    cat.settings()
    write_evidence(cat, 'a'*64, slug=slug)
    path = write_evidence(cat, 'b'*64, slug=slug)
    raw = json.loads(path.read_text())
    raw['investigations'][0]['rationales'][0]['direction'] = 'negative'
    from hashlib import sha256
    raw['investigations_sha256'] = sha256(json.dumps(raw['investigations'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    path.write_text(json.dumps(raw))
    graph = CatalogProfiles(cat).rationale_graph(slug)
    assert not graph.nodes
    assert 'Multiple' in graph.evidence_note


def test_renamed_phil_is_only_listed_once(tmp_path):
    for slug in ('phil-nadel', 'phil-nadel-forefront-venture-partners'):
        bundle(tmp_path/'bundles'/slug, slug=slug)
    profiles = CatalogProfiles(catalog(tmp_path))
    assert [r.vc_slug for r in profiles.list_profiles(include_unavailable=True)] == ['phil-nadel-forefront-venture-partners']
    assert profiles.profile('phil-nadel').investor.vc_slug == 'phil-nadel'


def test_gallery_endpoint_does_not_add_unavailable_investors_to_assessment_picker(tmp_path):
    from vclogic_web.app import create_app
    root = bundle(tmp_path/'bundles/v1')
    cat = catalog(tmp_path)
    cat.settings()
    shutil.rmtree(root)
    bundle(tmp_path/'bundles/v2', text='Current memory')
    cat.refresh()
    app = create_app(testing=True, investor_catalog=cat)
    endpoint = next(route.endpoint for route in app.routes if route.path == '/api/investors')
    assert endpoint().investors == ()
    cards = endpoint(include_unavailable=True).investors
    assert len(cards) == 1 and not cards[0].start_available
