import json
from types import SimpleNamespace

from test_investor_catalog import bundle, catalog, DEFAULT
from test_assessment_service import _baseline, _project
from vclogic_web.assessment_service import CanonicalAssessmentService
from vclogic_web.project_store import PitchProjectStore
from vclogic_web.service import RehearsalWebService
from vclogic_web.models import CreateSessionRequest


def test_queued_assessment_uses_original_version_and_reuse_is_version_specific(tmp_path):
    bundle(tmp_path/'bundles'/'v1')
    registry = catalog(tmp_path)
    first = registry.select('new-vc')
    store = PitchProjectStore(tmp_path/'pipeline/projects')
    project = _project(store)
    calls = []
    def builder(**kwargs):
        calls.append(kwargs)
        return _baseline(kwargs['session_root']/'result')
    service = CanonicalAssessmentService(store=store, workspace=registry.workspace,
        rehearsal_config=registry.config, baseline_builder=builder, investor_catalog=registry)
    original = service.ensure_assessment(project.project_id, project.current_version_id, 'new-vc')
    bundle(tmp_path/'bundles'/'v2', text='Second memory')
    versions = registry.refresh()['investors'][0]['versions']
    second = next(v['version_id'] for v in versions if v['version_id'] != first.version_id)
    registry.update('new-vc', enabled=True, active_version=second)
    revised = service.ensure_assessment(project.project_id, project.current_version_id, 'new-vc')
    assert revised.assessment_id != original.assessment_id
    assert revised.investor_version_id == second
    assert service.ensure_assessment(project.project_id, project.current_version_id, 'new-vc').assessment_id == revised.assessment_id
    registry.update('new-vc', enabled=False, active_version=second)
    service.run_assessment(original.assessment_id)
    assert calls[0]['rehearsal_config'].rehearsal.input_root == first.config.rehearsal.input_root
    assert service.get_assessment(original.assessment_id).investor_version_id == first.version_id
    assert len(service.list_for_version(project.project_id, project.current_version_id)) == 2


class DeferredJobs:
    def __init__(self): self.jobs = {}
    def submit(self, key, action, run): self.jobs[key] = run
    def is_busy(self, key): return False


def test_direct_rehearsal_and_resume_keep_version_after_disable(tmp_path, monkeypatch):
    bundle(tmp_path/'bundles'/'v1')
    registry = catalog(tmp_path)
    original = registry.select('new-vc')
    jobs = DeferredJobs()
    service = RehearsalWebService(DEFAULT, workspace=registry.workspace, investor_catalog=registry, coordinator=jobs)
    calls = []
    monkeypatch.setattr('vclogic_web.service.rehearsal_cli.command_start', lambda config, args, **kw: calls.append(config))
    monkeypatch.setattr('vclogic_web.service.rehearsal_cli._resume', lambda config, *args, **kw: calls.append(config))
    monkeypatch.setattr(service, 'get_session', lambda sid: SimpleNamespace(status='awaiting_answer', current_assessment=None))
    monkeypatch.setattr(service, '_root', lambda sid: tmp_path)
    request = CreateSessionRequest(vc_slug='new-vc', investor_version_id=original.version_id,
        company_aliases=('Example',), pitch_text='Example pitch', authorize_provider_cost=True)
    job = service.create_session(request)
    registry.update('new-vc', enabled=False, active_version=original.version_id)
    jobs.jobs[job.session_id](lambda *args: None)
    service._resume(job.session_id, 'retry')
    jobs.jobs[job.session_id](lambda *args: None)
    assert [c.rehearsal.input_root for c in calls] == [original.config.rehearsal.input_root]*2


def test_comparison_keeps_recorded_version_until_explicit_update(tmp_path):
    from vclogic_web.matching import MatchingService
    bundle(tmp_path/'bundles/v1')
    registry = catalog(tmp_path)
    first = registry.select('new-vc')
    store = PitchProjectStore(registry.workspace/'projects')
    project = _project(store)
    assessments = CanonicalAssessmentService(store=store, workspace=registry.workspace,
        rehearsal_config=registry.config, investor_catalog=registry)
    matching = MatchingService(store=store, assessments=assessments)
    original = matching.update_comparison(project.project_id, project.current_version_id, ('new-vc',))
    bundle(tmp_path/'bundles/v2', text='Second memory')
    second = next(v['version_id'] for v in registry.refresh()['investors'][0]['versions'] if v['version_id'] != first.version_id)
    registry.update('new-vc', enabled=True, active_version=second)
    assessments.ensure_assessment(project.project_id, project.current_version_id, 'new-vc')
    assert matching.get_comparison(project.project_id, project.current_version_id).assessments[0].assessment_id == original.assessments[0].assessment_id
    revised = matching.update_comparison(project.project_id, project.current_version_id, ('new-vc',), investor_versions={'new-vc':second})
    assert revised.assessments[0].investor_version_id == second
    assert revised.assessments[0].assessment_id != original.assessments[0].assessment_id


def test_assessment_rehearsal_uses_recorded_version_after_switch(tmp_path, monkeypatch):
    bundle(tmp_path/'bundles/v1')
    registry = catalog(tmp_path)
    first = registry.select('new-vc')
    store = PitchProjectStore(registry.workspace/'projects')
    project = _project(store)
    assessments = CanonicalAssessmentService(store=store, workspace=registry.workspace,
        rehearsal_config=registry.config, investor_catalog=registry,
        baseline_builder=lambda **kwargs: _baseline(kwargs['session_root']/'result'))
    row = assessments.ensure_assessment(project.project_id, project.current_version_id, 'new-vc')
    assessments.run_assessment(row.assessment_id)
    bundle(tmp_path/'bundles/v2', text='Second memory')
    second = next(v['version_id'] for v in registry.refresh()['investors'][0]['versions'] if v['version_id'] != first.version_id)
    registry.update('new-vc', enabled=False, active_version=second)
    jobs = DeferredJobs()
    service = RehearsalWebService(DEFAULT, workspace=registry.workspace, investor_catalog=registry,
        coordinator=jobs, assessment_service=assessments, project_store=store)
    captured = []
    monkeypatch.setattr('vclogic_web.service.rehearsal_cli.command_start', lambda config, args, **kw: captured.append(config))
    monkeypatch.setattr(service, 'get_session', lambda sid: SimpleNamespace(status='awaiting_answer', current_assessment=None))
    job = service.create_rehearsal_from_assessment(row.assessment_id, 'quick')
    jobs.jobs[job.session_id](lambda *args: None)
    assert captured[0].rehearsal.input_root == first.config.rehearsal.input_root
    restarted = RehearsalWebService(DEFAULT, workspace=registry.workspace, investor_catalog=catalog(tmp_path))
    assert restarted._session_binding(job.session_id).version_id == first.version_id


def test_legacy_comparison_keeps_original_assessment_when_adding_investor(tmp_path):
    from vclogic_web.matching import MatchingService
    bundle(tmp_path/'bundles/v1')
    registry = catalog(tmp_path)
    store = PitchProjectStore(registry.workspace/'projects')
    project = _project(store)
    assessments = CanonicalAssessmentService(store=store, workspace=registry.workspace, rehearsal_config=registry.config)
    original = assessments.ensure_assessment(project.project_id, project.current_version_id, 'new-vc')
    matching = MatchingService(store=store, assessments=assessments)
    comparison = matching.update_comparison(project.project_id, project.current_version_id, ('new-vc',))
    path = matching._comparison_path(project.project_id, project.current_version_id)
    payload = json.loads(path.read_text()); del payload['assessment_ids']; path.write_text(json.dumps(payload))
    assessments.investor_catalog = registry
    current = assessments.ensure_assessment(project.project_id, project.current_version_id, 'new-vc')
    assert current.assessment_id != original.assessment_id
    assert matching.get_comparison(project.project_id, project.current_version_id).assessments[0].assessment_id == original.assessment_id
    selected = registry.settings()['investors'][0]['active_version']
    registry.update('new-vc', enabled=False, active_version=selected)
    bundle(tmp_path/'bundles/other', slug='other-vc')
    registry.refresh()
    updated = matching.update_comparison(project.project_id, project.current_version_id, ('other-vc',))
    assert next(r for r in updated.assessments if r.vc_slug=='new-vc').assessment_id == original.assessment_id
