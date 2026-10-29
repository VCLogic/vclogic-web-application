#!/usr/bin/env python3
"""Export three same-pitch assessments and a verified rehearsal as a local anonymous replay."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import tomllib

from vc_clone_graph.rehearsal_artifacts import RehearsalArtifactStore
from vclogic_web.models import CanonicalAssessmentDetail
from vclogic_web.session_views import SessionViewBuilder
from vclogic_web.recorded_demo import RecordedDemo


def export(assessments, session, registries):
    rows = [CanonicalAssessmentDetail.model_validate_json(Path(path).read_text()) for path in assessments]
    if len(rows) != 3 or len({row.vc_slug for row in rows}) != 3 or any(row.status != 'complete' for row in rows):
        raise ValueError('Provide three completed assessments for distinct investors')
    store = RehearsalArtifactStore.open(Path(session))
    verification = store.verify()
    view = SessionViewBuilder(store).build()
    if view.status not in {'complete', 'finished'} or not view.conversation:
        raise ValueError('Rehearsal must be complete with recorded answers')
    digest = sha256(store.pitch_path.read_bytes()).hexdigest()
    if any(row.pitch_sha256 != digest for row in rows) or verification['pitch_sha256'] != digest:
        raise ValueError('All assessments and the rehearsal must use the same pitch')
    selected = next((i for i, row in enumerate(rows) if row.vc_slug == view.vc_slug), None)
    if selected is None or rows[selected].investment_likelihood != view.initial_assessment.investment_likelihood:
        raise ValueError('Rehearsal baseline does not match the selected assessment')
    replacements = {'shiftpilot': 'Company #1'}
    labels = {row.vc_slug: f'Investor #{i + 1}' for i, row in enumerate(rows)}
    for path in Path(registries).glob('*.toml'):
        identity = tomllib.loads(path.read_text())
        slug = identity.get('vc_slug', '')
        label = labels.get(slug, 'Other investor')
        name = identity.get('display_name', '')
        for value in [slug, name, *name.split(), *identity.get('speaker_names', [])]:
            if len(value) > 2:
                replacements[value.lower()] = label
        firm = identity.get('firm', '')
        for value in [firm, re.sub(r'\s+(Ventures|Capital|Fund|Partners|Group)$', '', firm, flags=re.I)]:
            if len(value) > 3:
                replacements[value.lower()] = label.replace('Investor', 'Firm') if slug in labels else 'Other firm'
    pattern = re.compile(r'\b(?:' + '|'.join(re.escape(key) for key in sorted(replacements, key=len, reverse=True)) + r')\b', re.I)
    def scrub(text):
        text = re.sub(r'https?://\S+|/home/\S+', '[source omitted]', text)
        return pattern.sub(lambda match: replacements[match.group().lower()], text)
    report = store.read_json('founder-report.json')
    exchanges = []
    for index, turn in enumerate(view.conversation, 1):
        update = store.read_json(f'turns/turn-{index:02d}/update.json')
        exchanges.append(dict(question=scrub(turn.question), answer=scrub(turn.founder_answer or ''),
            rationale_labels=list(turn.rationale_labels), before=turn.investment_likelihood_before,
            after=turn.investment_likelihood_after, impact=scrub(update.get('update_summary', ''))))
    pitch = store.pitch_path.read_text()
    draft = pitch + '\n\n## Rehearsal clarifications to incorporate into the next pitch\n\n' + '\n\n'.join(
        f"### {row['question']}\n\n{row['answer']}" for row in exchanges)
    result = RecordedDemo(company='Company #1', recorded_at=store.read_json('manifest.json')['created_at'],
        pitch_sha256=digest, initial_pitch=scrub(pitch), selected=selected,
        investors=[dict(name=labels[row.vc_slug], firm=f'Firm #{i+1}', score=row.investment_likelihood,
            decision=row.decision, positives=list(row.positive_rationales), concerns=list(row.negative_rationales),
            justification=scrub(row.decision_justification or '')) for i, row in enumerate(rows)],
        exchanges=exchanges, final_score=view.current_assessment.investment_likelihood,
        final_decision=view.current_assessment.decision,
        final_justification=scrub(report['final_assessment'].get('decision_justification', '')),
        recommendations=[scrub(value) for value in report.get('pitch_improvement_suggestions', [])],
        revised_pitch=scrub(draft), revision_note='Editorial draft: original pitch plus recorded founder clarifications. No new facts added; this draft has not been reassessed.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assessments', type=Path, nargs=3, required=True)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--registries', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = export(args.assessments, args.session, args.registries)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.model_dump_json(indent=2) + '\n')
    print(f'Exported verified {len(result.exchanges)}-question replay to {args.output}')


if __name__ == '__main__':
    main()
