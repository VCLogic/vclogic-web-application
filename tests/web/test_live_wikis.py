import json
from pathlib import Path

from test_investor_catalog import catalog
from vclogic_web.catalog_profiles import CatalogProfiles
from vclogic_web.wiki_profiles import WikiLibrary


def wiki(root, slug='new-vc', quote='Founders must understand their customers.'):
    path = root/slug
    path.mkdir(parents=True, exist_ok=True)
    files = {'_manifest.json': json.dumps({'vc_slug':slug,'generated_at':'2026-10-26'}),
        'validation.json': '{"valid":true,"errors":[]}',
        'README.md':'# New VC — investment memory',
        'persona.md':'# Decision policy\n\nA founder-focused investor.\n\n## founder_team\n\nLook for customer knowledge.',
        'theses.md':'# Investment theses\n\n## Early founders\n\nInvest early.',
        'portfolio_and_constraints.md':'# Portfolio\n\nSource-reported holdings.',
        'evidence.json':json.dumps([{'id':slug+'-1','label':'founder_market_fit','direction':'positive','quote':quote,'source':'interview:1','support':'explicit','interpretation':'Understand the customer.'}])}
    for name,text in files.items(): (path/name).write_text(text)
    return path


def test_wiki_without_onboarding_is_discovered_and_readable(tmp_path):
    c=catalog(tmp_path)
    root=c.workspace.parent/'vclogic-vc-investment-memory/wiki'
    wiki(root)
    profiles=CatalogProfiles(c)
    cards=profiles.list_profiles(include_unavailable=True)
    assert len(cards)==1 and not cards[0].start_available
    assert cards[0].recurring_positive_counts=={'founder_market_fit':1}
    profile=profiles.profile('new-vc')
    assert profile.investor.thesis_count==1
    assert profile.investor.policy_count==1
    assert profile.investor.evidence_count==1
    assert any(s.section_id=='theses.md' for s in profile.sections)
    graph=profiles.rationale_graph('new-vc')
    assert graph.evidence_basis=='wiki'
    assert graph.nodes[0].confidence is None
    assert not graph.edges
    results=profiles.search_memory('new-vc','founder_market_fit')
    assert results.results[0].excerpt=='Founders must understand their customers.'
    assert results.results[0].source_reference=='interview:1'
    assert not c.preferences_path.exists()


def test_wiki_edits_refresh_content_and_evidence_without_restart(tmp_path):
    c=catalog(tmp_path); root=c.workspace.parent/'vclogic-vc-investment-memory/wiki'
    path=wiki(root); profiles=CatalogProfiles(c)
    first=profiles.profile('new-vc')
    wiki(root,quote='A different verified quote.')
    (path/'theses.md').write_text('# Theses\n\n## Hardware\n\nPhysical products.\n\n## Software\n\nTools.')
    second=profiles.profile('new-vc')
    assert second.investor.memory_version!=first.investor.memory_version
    assert second.investor.thesis_count==2
    assert profiles.search_memory('new-vc','verified').results[0].excerpt=='A different verified quote.'


def test_archived_invalid_and_escaping_wikis_are_not_published(tmp_path):
    c=catalog(tmp_path); root=c.workspace.parent/'vclogic-vc-investment-memory/wiki'
    wiki(root/'_archived')
    path=wiki(root,slug='bad-vc'); (path/'_manifest.json').write_text('{"vc_slug":"wrong-vc"}')
    outside=wiki(tmp_path/'outside',slug='escape-vc'); root.joinpath('escape-vc').symlink_to(outside,target_is_directory=True)
    assert CatalogProfiles(c).list_profiles(include_unavailable=True)==()


def test_browsing_current_wikis_never_scans_runtime_indexes(tmp_path,monkeypatch):
    c=catalog(tmp_path); wiki(c.workspace.parent/'vclogic-vc-investment-memory/wiki')
    def forbidden(*args,**kwargs): raise AssertionError('runtime scan during browsing')
    monkeypatch.setattr(c,'settings',forbidden)
    monkeypatch.setattr(c,'refresh',forbidden)
    profiles=CatalogProfiles(c)
    assert profiles.list_profiles(include_unavailable=True)
    assert profiles.profile('new-vc').sections
    assert profiles.rationale_graph('new-vc').nodes


def test_flat_theses_and_exact_evidence_citations(tmp_path):
    c=catalog(tmp_path); root=c.workspace.parent/'vclogic-vc-investment-memory/wiki'
    path=wiki(root)
    (path/'theses.md').write_text('# Theses\n\n- First cited theme.\n- Second cited theme.')
    profiles=CatalogProfiles(c)
    assert profiles.profile('new-vc').investor.thesis_count==2
    assert profiles.search_memory('new-vc','new-vc-1').results[0].evidence_id=='new-vc-1'


def test_chapters_are_lazy_and_reject_stale_or_unknown_reads(tmp_path):
    import pytest
    from vclogic_web.wiki_profiles import WikiChangedError
    c=catalog(tmp_path); root=c.workspace.parent/'vclogic-vc-investment-memory/wiki'
    path=wiki(root); profiles=CatalogProfiles(c)
    profile=profiles.profile('new-vc'); section=next(s for s in profile.sections if s.section_id=='persona.md')
    assert section.body=='' and not section.body_loaded
    assert profiles.chapter('new-vc','persona.md',section.memory_version).body.startswith('# Decision policy')
    with pytest.raises(ValueError): profiles.chapter('new-vc','../../settings.json')
    (path/'persona.md').write_text('# Changed policy\n\n## Team\n\nNew criteria.')
    with pytest.raises(WikiChangedError): profiles.chapter('new-vc','persona.md',section.memory_version)


def test_context_citations_preserve_source_but_do_not_become_rationales(tmp_path):
    c=catalog(tmp_path);root=c.workspace.parent/'vclogic-vc-investment-memory/wiki';path=wiki(root)
    (path/'context.json').write_text(json.dumps([{'id':'new-vc-1','quote':'Our fund backs Example Co.','claim':'Reported portfolio holding','source':'interview:1'}]))
    (path/'sources.md').write_text('# Sources\n\n## interview:1\n\nFounder interview\n\nURL: https://example.org/interview\n')
    profiles=CatalogProfiles(c)
    assert profiles.profile('new-vc').investor.evidence_count==1
    assert len(profiles.rationale_graph('new-vc').nodes)==1
    ctx=profiles.search_memory('new-vc','ctx:new-vc-1').results[0]
    assert ctx.excerpt=='Our fund backs Example Co.' and ctx.rationale_label is None
    assert ctx.source_url=='https://example.org/interview'
    assert profiles.search_memory('new-vc','ev:new-vc-1').results[0].excerpt.startswith('Founders')


def test_chapter_route_reports_missing_and_changed_memory(tmp_path):
    import pytest
    from fastapi import HTTPException
    from vclogic_web.app import create_app
    c=catalog(tmp_path); root=c.workspace.parent/'vclogic-vc-investment-memory/wiki'
    path=wiki(root); profiles=CatalogProfiles(c)
    app=create_app(testing=True, profile_service=profiles)
    endpoint=next(route.endpoint for route in app.routes if route.name=='investor_chapter')
    version=profiles.profile('new-vc').investor.memory_version
    assert endpoint('new-vc','persona.md',version).body_loaded
    with pytest.raises(HTTPException) as missing:
        endpoint('new-vc','missing.md',version)
    assert missing.value.status_code==404
    (path/'persona.md').write_text('# Updated policy')
    with pytest.raises(HTTPException) as changed:
        endpoint('new-vc','persona.md',version)
    assert changed.value.status_code==409
    assert '/api/investors/{vc_slug}/chapters/{section_id}' in app.openapi()['paths']


def test_wiki_cache_reuses_parsed_content_and_invalidates_removed_evidence(tmp_path):
    c=catalog(tmp_path);root=c.workspace.parent/'vclogic-vc-investment-memory/wiki';path=wiki(root)
    profiles=CatalogProfiles(c)
    first=profiles.wikis.service('new-vc')
    assert profiles.wikis.service('new-vc') is first
    (path/'evidence.json').write_text('[]')
    second=profiles.wikis.service('new-vc')
    assert second is not first
    assert second.rationale_graph('new-vc').nodes==()


def test_changed_wiki_is_not_advertised_as_the_old_assessment_input(tmp_path):
    from vclogic_web.investor_versions import InvestorVersion, atomic_json
    c=catalog(tmp_path);root=c.workspace.parent/'vclogic-vc-investment-memory/wiki';path=wiki(root)
    profiles=CatalogProfiles(c); service=profiles.wikis.service('new-vc')
    vid='a'*64
    c._versions={'new-vc':{vid:InvestorVersion('new-vc',vid,'Prepared','New VC',path,
        ready=True,hashes={f'inputs/wiki/new-vc/{name}':h for name,h in service.runtime_hashes.items()})}}
    atomic_json(c.preferences_path,{'new-vc':{'enabled':True,'active_version':vid}})
    assert profiles.list_profiles()[0].start_available
    (path/'persona.md').write_text('# Updated criteria\n\n## Team\nNew policy.')
    assert profiles.list_profiles()==()
    card=profiles.list_profiles(include_unavailable=True)[0]
    assert not card.start_available and card.memory_version!=service.memory_version
    assert c._preferences()['new-vc']['active_version']==vid


def test_anonymous_identity_catalog_does_not_validate_assessment_indexes(tmp_path, monkeypatch):
    c=catalog(tmp_path); wiki(c.workspace.parent/'vclogic-vc-investment-memory/wiki')
    def forbidden(*args,**kwargs): raise AssertionError('runtime scan during anonymous identity lookup')
    monkeypatch.setattr(c,'settings',forbidden)
    monkeypatch.setattr(c,'refresh',forbidden)
    rows=CatalogProfiles(c).identities()
    assert rows[0]['vc_slug']=='new-vc' and rows[0]['display_name']=='New VC-like Investor'
