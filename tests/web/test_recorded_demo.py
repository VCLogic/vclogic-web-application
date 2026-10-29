import json
import pytest
from fastapi.testclient import TestClient
from vclogic_web.app import create_app
from vclogic_web.recorded_demo import RecordedDemo


def payload():
    return dict(company='Example', recorded_at='2026-01-01', pitch_sha256='a'*64, initial_pitch='Pitch',
        investors=[dict(name=f'Investor #{i+1}',firm=f'Firm #{i+1}',score=score,decision='In',positives=[],concerns=[],justification='Recorded') for i,score in enumerate([.63,.61,.26])],
        selected=0,exchanges=[dict(question='Why?',answer='Evidence',rationale_labels=[],before=.63,after=.57,impact='Recorded change')],
        final_score=.56,final_decision='In',final_justification='Synthesis',recommendations=['Measure outcomes'],revised_pitch='Draft',revision_note='Not reassessed')


def test_recorded_demo_requires_highest_fit_and_continuous_scores():
    RecordedDemo.model_validate(payload())
    bad=payload();bad['selected']=1
    with pytest.raises(ValueError):RecordedDemo.model_validate(bad)
    bad=payload();bad['exchanges'][0]['before']=.9
    with pytest.raises(ValueError):RecordedDemo.model_validate(bad)


def test_recorded_demo_api_reads_only_installed_local_export(tmp_path):
    client=TestClient(create_app(testing=True,pipeline_workspace=tmp_path))
    assert client.get('/api/demo/recorded').status_code==404
    p=tmp_path/'outputs/demos/shiftpilot.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(payload()))
    response=client.get('/api/demo/recorded')
    assert response.status_code==200 and response.json()['final_score']==.56
    p.write_text('{}')
    assert client.get('/api/demo/recorded').status_code==404
