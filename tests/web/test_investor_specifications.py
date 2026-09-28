import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from vc_clone_graph.rehearsal_config import RehearsalConfig
from vclogic_web.investor_specifications import specifications
from vclogic_web.investor_versions import InvestorVersion, digest


def make_version(root: Path, version: str, *, model: str, top_k: int) -> InvestorVersion:
    slug = 'example-vc'
    registry = root/f'inputs/investors/{slug}.toml'
    registry.parent.mkdir(parents=True)
    (root/f'inputs/wiki/{slug}').mkdir(parents=True)
    registry.write_text('vc_slug="example-vc"\ndisplay_name="Example VC"\nwiki_path="wiki/example-vc"\ncheck_tiers=["seed"]\nspeaker_names=["Example"]\n')
    taxonomy = root/'inputs/taxonomy/codebook_v_final.json'
    taxonomy.parent.mkdir()
    taxonomy.write_text(json.dumps([{'label': model, 'definition': 'Full term definition', 'coarse_parent': 'parent'}]))
    canonical = root/'canonical.toml'
    canonical.write_text(f'''[run]
vc_slug="example-vc"
episode_slug="live-pitch"
input_root="inputs"
output_root="outputs"
checkpoint_path="outputs/checkpoint.sqlite"
contract_version="v4.1"
mode="full"
[provider]
kind="openrouter"
model="{model}-assessment"
api_key_env="INSPECTOR_TEST_KEY"
base_url="https://private-endpoint.invalid/SECRET-ENDPOINT"
max_output_tokens=4096
[embedding]
kind="ollama"
model="canonical-embed"
[phase1]
min_iterations=1
max_iterations=2
model="{model}-phase1"
reasoning_effort="high"
planning_reasoning_effort="low"
planning_max_output_tokens=1024
max_output_tokens=2048
[phase2]
min_iterations=1
max_iterations=3
[retrieval]
top_k={top_k}
max_exact_reads=6
''')
    config = RehearsalConfig.model_validate(dict(
        rehearsal=dict(max_questions=8),
        provider=dict(kind='openrouter', model=model+'-rehearsal', api_key_env='INSPECTOR_TEST_KEY', base_url='SECRET-ENDPOINT'),
        embedding=dict(kind='ollama', model='rehearsal-embed'),
        retrieval=dict(top_k=top_k+1, max_exact_reads=9),
    ))
    return InvestorVersion(slug, version, 'Version '+version, 'Example VC', root,
        files={f'inputs/investors/{slug}.toml': registry,
               'inputs/taxonomy/codebook_v_final.json': taxonomy, 'canonical.toml': canonical},
        hashes={f'inputs/investors/{slug}.toml': digest(registry),
                'inputs/taxonomy/codebook_v_final.json': digest(taxonomy), 'canonical.toml': digest(canonical)},
        config=config, canonical_relative='canonical.toml', ready=True,
        capabilities={'wiki': True, 'precedents': True})


class Catalog:
    def __init__(self, rows):
        self._versions = {'example-vc': {r.version_id: r for r in rows}}

    def settings(self):
        return {'investors': [{'vc_slug': 'example-vc', 'enabled': False, 'active_version': 'a'}]}

    def refresh(self, *, persist_preferences=True):
        assert persist_preferences is False
        return self.settings()

    def select(self, *_):
        raise AssertionError('must not select an execution binding')

    binding = select


def fields(result, section):
    return {r['label']: r['value'] for s in result['sections'] if s['id'] == section for r in s['fields']}


def test_disabled_selected_version_has_distinct_assessment_and_rehearsal_specs_without_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv('INSPECTOR_TEST_KEY', 'SECRET-ENV-CANARY')
    row = make_version(tmp_path/'a', 'a', model='first', top_k=3)
    result = specifications(Catalog([row]), 'example-vc')
    assert result['active'] is True and result['enabled'] is False
    assert fields(result, 'assessment-provider')['Model'] == 'first-assessment'
    assert fields(result, 'rehearsal-provider')['Model'] == 'first-rehearsal'
    assert fields(result, 'assessment-phase1')['Model'] == 'first-phase1'
    assert fields(result, 'assessment-phase2')['Model'] == 'first-assessment'
    assert fields(result, 'assessment-phase1')['Planning max output tokens'] == 1024
    assert fields(result, 'assessment-retrieval')['Top k'] == 3
    assert fields(result, 'rehearsal-retrieval')['Top k'] == 4
    assert fields(result, 'identity')['Check tiers'] == ['seed']
    serialized = json.dumps(result)
    assert 'INSPECTOR_TEST_KEY' in serialized
    assert 'SECRET-ENV-CANARY' not in serialized and 'SECRET-ENDPOINT' not in serialized
    assert not list(tmp_path.rglob('binding.json'))
    assert not list(tmp_path.rglob('outputs'))


def test_explicit_version_never_mixes_taxonomy_or_config_from_selected_version(tmp_path):
    a = make_version(tmp_path/'a', 'a', model='first', top_k=3)
    b = make_version(tmp_path/'b', 'b', model='second', top_k=7)
    result = specifications(Catalog([a, b]), 'example-vc', 'b')
    assert result['active'] is False
    assert result['investor_version_id'] == 'b'
    assert result['taxonomy'] == [{'label': 'second', 'definition': 'Full term definition', 'coarse_parent': 'parent'}]
    assert fields(result, 'assessment-provider')['Model'] == 'second-assessment'
    assert fields(result, 'rehearsal-retrieval')['Top k'] == 8
    assert 'first' not in json.dumps(result)


def test_unready_missing_configs_and_malformed_files_return_partial_specs(tmp_path):
    row = make_version(tmp_path/'a', 'a', model='first', top_k=3)
    row.ready = False
    row.error = 'Internal diagnostic containing SECRET-ENV-CANARY'
    row.config = None
    row.files['canonical.toml'].write_text('invalid toml = SECRET-ENDPOINT')
    row.files['inputs/taxonomy/codebook_v_final.json'].write_text('{}')
    result = specifications(Catalog([row]), 'example-vc')
    assert not result['ready'] and result['error']
    assert result['taxonomy'] == []
    assert fields(result, 'identity')['Speaker aliases'] == ['Example']
    assert any('Rehearsal configuration is missing' in x for x in result['notes'])
    assert 'SECRET' not in json.dumps(result)


def test_missing_identity_and_config_remain_inspectable(tmp_path):
    row = InvestorVersion('example-vc', 'a', 'Unavailable', 'Example VC', tmp_path)
    result = specifications(Catalog([row]), 'example-vc')
    assert result['sections'] and result['error'] and result['taxonomy'] == []


def test_unknown_slug_and_version_raise(tmp_path):
    catalog = Catalog([make_version(tmp_path/'a', 'a', model='first', top_k=3)])
    with pytest.raises(ValueError, match='unknown investor profile'):
        specifications(catalog, 'missing')
    with pytest.raises(ValueError, match='unknown investor version'):
        specifications(catalog, 'example-vc', 'missing')


def test_changed_canonical_file_is_not_presented_under_cached_version(tmp_path):
    row = make_version(tmp_path/'a', 'a', model='first', top_k=3)
    path = row.files['canonical.toml']
    path.write_text(path.read_text().replace('first-assessment', 'tampered-assessment'))
    result = specifications(Catalog([row]), 'example-vc')
    assert result['ready'] is False
    assert result['error']
    assert 'tampered-assessment' not in json.dumps(result)
    assert fields(result, 'assessment-provider') == {}
    assert fields(result, 'rehearsal-provider')['Model'] == 'first-rehearsal'


def test_unverified_files_are_not_exposed(tmp_path):
    row = make_version(tmp_path/'a', 'a', model='first', top_k=3)
    row.hashes = {}
    row.ready = False
    result = specifications(Catalog([row]), 'example-vc')
    assert result['taxonomy'] == []
    assert fields(result, 'identity') == {}
    assert fields(result, 'assessment-provider') == {}
    assert any('verified hashes' in note for note in result['notes'])


def test_identity_is_available_when_wiki_directory_is_missing(tmp_path):
    row = make_version(tmp_path/'a', 'a', model='first', top_k=3)
    (tmp_path/'a/inputs/wiki/example-vc').rmdir()
    row.ready = False
    result = specifications(Catalog([row]), 'example-vc')
    assert fields(result, 'identity')['Name'] == 'Example VC'
    assert fields(result, 'identity')['Check tiers'] == ['seed']
    assert fields(result, 'identity')['Speaker aliases'] == ['Example']


def test_distinct_assessment_taxonomy_has_its_own_verified_terms(tmp_path):
    row = make_version(tmp_path/'a', 'a', model='first', top_k=3)
    canonical = row.files['canonical.toml']
    canonical.write_text(canonical.read_text().replace('mode="full"', 'mode="full"\ntaxonomy_path="taxonomy/assessment.json"'))
    row.hashes['canonical.toml'] = digest(canonical)
    taxonomy = tmp_path/'a/inputs/taxonomy/assessment.json'
    taxonomy.write_text(json.dumps([{'label': 'assessment-only', 'definition': 'Assessment definition', 'coarse_parent': 'assessment-theme'}]))
    row.files['inputs/taxonomy/assessment.json'] = taxonomy
    row.hashes['inputs/taxonomy/assessment.json'] = digest(taxonomy)
    result = specifications(Catalog([row]), 'example-vc')
    assert result['taxonomy'][0]['label'] == 'first'
    assert fields(result, 'assessment-taxonomy') == {'assessment-only': ['Assessment definition', 'Theme: assessment-theme']}
    del row.files['inputs/taxonomy/assessment.json']
    result = specifications(Catalog([row]), 'example-vc')
    assert fields(result, 'assessment-taxonomy') == {}
    assert any('distinct assessment taxonomy could not be read' in n for n in result['notes'])


def test_cold_catalog_inspection_does_not_save_or_enable_choices(tmp_path):
    from test_investor_catalog import bundle, catalog
    bundle(tmp_path/'bundles'/'v1')
    service = catalog(tmp_path)
    result = specifications(service, 'new-vc')
    assert result['ready'] is True
    assert result['enabled'] is False and result['active'] is False
    assert not service.preferences_path.exists()
    assert not list(service.root.glob('versions/*/*/binding.json'))
