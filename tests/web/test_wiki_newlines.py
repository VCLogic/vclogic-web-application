from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from vclogic_web.catalog_profiles import CatalogProfiles
from vclogic_web.wiki_profiles import CORE


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_identical_installed_wiki_is_available_and_changed_wiki_is_not(tmp_path, newline):
    root = tmp_path / 'wiki'
    wiki = root / 'example'
    wiki.mkdir(parents=True)
    (wiki / '_manifest.json').write_text(json.dumps({'vc_slug': 'example'}), encoding='utf-8')
    (wiki / 'evidence.json').write_text('[]', encoding='utf-8')
    hashes = {}
    for name in CORE:
        raw = f'# Policy{newline}{newline}Founder knowledge.{newline}'.encode('utf-8')
        (wiki / name).write_bytes(raw)
        hashes[f'inputs/wiki/example/{name}'] = sha256(raw).hexdigest()
    state = dict(vc_slug='example', active_version='a' * 64, enabled=True, available=True)
    catalog = SimpleNamespace(
        workspace=tmp_path / 'pipeline',
        cached_settings=lambda: {'investors': [state]},
        _versions={'example': {'a' * 64: SimpleNamespace(ready=True, hashes=hashes)}},
    )
    profiles = CatalogProfiles(catalog, wiki_roots=[root])
    service, _, available = profiles._service('example')
    assert available
    assert profiles.list_profiles()[0].start_available
    assert service.runtime_hashes['persona.md'] == hashes['inputs/wiki/example/persona.md']
    (wiki / 'persona.md').write_bytes(b'# Different policy\n')
    assert not profiles._service('example')[2]
