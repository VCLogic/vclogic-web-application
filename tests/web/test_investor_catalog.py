from hashlib import sha256
import json
from pathlib import Path

import pytest
from vc_clone_graph.rehearsal_config import load_rehearsal_config
from vclogic_web.investor_catalog import InvestorCatalog


ENGINE = Path(__file__).resolve().parents[3]/"vclogic-vc-agentic-assessment"
DEFAULT = ENGINE/"configs/rehearsal-charles-v41-grounded.toml"

def bundle(root: Path, slug='new-vc', text='First memory', ready=True):
    files = {
        f'inputs/investors/{slug}.toml': f'vc_slug = "{slug}"\ndisplay_name = "New VC"\nwiki_path = "wiki/{slug}"\n',
        f'inputs/wiki/{slug}/persona.md': text,
        'inputs/taxonomy/codebook_v_final.json': '[]',
        f'configs/investors/{slug}/canonical.toml': (ENGINE/'configs/canonical-live-v41.toml').read_text().replace('live-investor', slug).replace('enabled = true', 'enabled = false'),
        f'configs/investors/{slug}/rehearsal.toml': DEFAULT.read_text().replace('configs/canonical-live-v41.toml', f'configs/investors/{slug}/canonical.toml').replace('enabled = true', 'enabled = false'),
    }
    for name, content in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    if ready:
        from vc_clone_graph.retrieval import HybridWikiIndex
        cfg = load_rehearsal_config(root/f'configs/investors/{slug}/rehearsal.toml')
        emb = cfg.embedding.model_dump()
        class Embedder:
            metadata = {'backend': emb['kind'], **{k: emb[k] for k in ('model', 'revision', 'normalize', 'document_prefix', 'query_prefix')}}
            def embed(self, texts):
                return [[1.0, 0.0] for text in texts]
        index = root/f'inputs/indexes/{slug}.json'
        index.parent.mkdir(parents=True, exist_ok=True)
        HybridWikiIndex.build(root/f'inputs/wiki/{slug}', Embedder(), require_complete_embeddings=True).save(index)
        files[index.relative_to(root).as_posix()] = index.read_text()
    metadata = dict(schema='vclogic-investor-bundle-v1', vc_slug=slug,
                    display_name='New VC', ready_for_assessment=ready,
                    capabilities={'wiki': True, 'precedents': False},
                    files={name: sha256(content.encode()).hexdigest() for name, content in files.items()})
    (root/'bundle.json').write_text(json.dumps(metadata))
    return root


def catalog(tmp_path):
    workspace = tmp_path/'pipeline'
    workspace.mkdir(exist_ok=True)
    return InvestorCatalog(workspace=workspace, config=load_rehearsal_config(DEFAULT, workspace=workspace), bundle_roots=[tmp_path/'bundles'])


def test_discovers_new_vc_and_persists_disabled_choice(tmp_path):
    service = catalog(tmp_path)
    assert service.settings()['investors'] == []
    bundle(tmp_path/'bundles'/'v1', ready=False)
    row = service.refresh()['investors'][0]
    assert row['vc_slug'] == 'new-vc'
    assert not row['versions'][0]['ready']
    service.update('new-vc', enabled=False, active_version=None)
    assert catalog(tmp_path).settings()['investors'][0]['enabled'] is False


def test_multiple_versions_are_distinct_and_not_automatically_selected(tmp_path):
    bundle(tmp_path/'bundles'/'v1', ready=False)
    bundle(tmp_path/'bundles'/'v2', text='Second memory', ready=False)
    row = catalog(tmp_path).settings()['investors'][0]
    assert len(row['versions']) == 2
    assert len({v['version_id'] for v in row['versions']}) == 2
    assert row['active_version'] is None


def test_invalid_bundle_is_isolated_and_cannot_escape_source(tmp_path):
    first = bundle(tmp_path/'bundles'/'bad')
    data = json.loads((first/'bundle.json').read_text())
    data['files']['../escape'] = 'a'*64
    (first/'bundle.json').write_text(json.dumps(data))
    bundle(tmp_path/'bundles'/'valid', slug='other-vc', ready=False)
    rows = catalog(tmp_path).settings()['investors']
    assert len(rows) == 2
    invalid = next(r for r in rows if r['vc_slug'] == 'new-vc')['versions'][0]
    assert not invalid['ready']
    assert 'path' in invalid['error'].lower()


def test_hash_tampering_is_reported(tmp_path):
    root = bundle(tmp_path/'bundles'/'v1')
    (root/'inputs/wiki/new-vc/persona.md').write_text('tampered')
    version = catalog(tmp_path).settings()['investors'][0]['versions'][0]
    assert not version['ready']
    assert 'hash' in version['error'].lower()


def test_rejects_unknown_and_unready_selection(tmp_path):
    bundle(tmp_path/'bundles'/'v1', ready=False)
    service = catalog(tmp_path)
    row = service.settings()['investors'][0]
    with pytest.raises(ValueError):
        service.update('new-vc', enabled=True, active_version=row['versions'][0]['version_id'])
    with pytest.raises(ValueError):
        service.select('unknown')


def test_snapshot_survives_source_removal_and_disable(tmp_path):
    import shutil
    root = bundle(tmp_path/'bundles'/'v1')
    service = catalog(tmp_path)
    row = service.settings()['investors'][0]
    assert row['enabled'], row
    selected = service.select('new-vc')
    assert selected.config.classification.canonical_config_path.startswith('outputs/web-investors/')
    assert selected.input_root != root/'inputs'
    service.update('new-vc', enabled=False, active_version=selected.version_id)
    shutil.rmtree(root)
    restored = catalog(tmp_path).binding('new-vc', selected.version_id)
    assert (restored.input_root/'wiki/new-vc/persona.md').read_text() == 'First memory'
    with pytest.raises(ValueError, match='disabled'):
        service.select('new-vc')


def test_new_version_never_changes_existing_selection(tmp_path):
    bundle(tmp_path/'bundles'/'v1')
    service = catalog(tmp_path)
    first = service.select('new-vc')
    bundle(tmp_path/'bundles'/'v2', text='Second memory')
    row = service.refresh()['investors'][0]
    assert row['active_version'] == first.version_id
    other = next(v['version_id'] for v in row['versions'] if v['version_id'] != first.version_id)
    service.update('new-vc', enabled=True, active_version=other)
    assert service.select('new-vc').version_id == other
    with pytest.raises(ValueError, match='changed'):
        service.select('new-vc', first.version_id)
    assert (service.binding('new-vc', first.version_id).input_root/'wiki/new-vc/persona.md').read_text() == 'First memory'


def test_settings_api_and_gallery_share_catalog(tmp_path):
    from fastapi.testclient import TestClient
    from vclogic_web.app import create_app
    service = catalog(tmp_path)
    client = TestClient(create_app(testing=True, investor_catalog=service))
    assert client.get('/api/investors').json()['investors'] == []
    bundle(tmp_path/'bundles'/'v1')
    settings = client.post('/api/settings/investors/refresh').json()
    selected = settings['investors'][0]['active_version']
    cards = client.get('/api/investors').json()['investors']
    assert cards[0]['investor_version_id'] == selected
    response = client.put('/api/settings/investors/new-vc', json={'enabled': False, 'active_version': selected})
    assert response.status_code == 200
    assert client.get('/api/investors').json()['investors'] == []
    assert client.put('/api/settings/investors/new-vc', json={'enabled': True, 'active_version': 'bad'}).status_code == 422
