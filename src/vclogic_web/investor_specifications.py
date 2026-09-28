"""Read-only, allowlisted inspection of an investor's declared version inputs."""
from __future__ import annotations

import json
import tomllib
from typing import Any

from vc_clone_graph.config import load_config
from vc_clone_graph.rehearsal_runtime import InvestorProfile

from .profile_identity import enrich_identity
from .investor_versions import digest

_PROVIDER = ('kind', 'model', 'api_key_env', 'max_output_tokens', 'request_timeout_seconds',
             'require_parameters', 'data_collection', 'structured_output_mode')
_EMBEDDING = ('kind', 'model', 'revision', 'normalize', 'document_prefix', 'query_prefix',
              'device', 'batch_size', 'require_complete_index')
_PHASE = ('min_iterations', 'max_iterations', 'reasoning_effort', 'planning_max_output_tokens',
          'planning_reasoning_effort', 'max_precedent_searches', 'max_precedent_reads')
_CLASSIFICATION = ('mode', 'live_contract_version', 'classifier_tiebreaker', 'minimum_probability_impact',
                   'minimum_questions', 'maximum_questions', 'fallback_to_rationale_only')
_QUESTION = ('enabled', 'top_k', 'candidate_pool_k', 'semantic_weight', 'rationale_weight',
             'lexical_weight', 'atomicity_bonus', 'long_question_penalty', 'multi_request_penalty',
             'duplicate_penalty', 'minimum_hybrid_score')


def _field(label: str, value: Any) -> dict:
    if isinstance(value, tuple):
        value = list(value)
    if not (value is None or isinstance(value, (str, bool, int, float))
            or isinstance(value, list) and all(isinstance(v, str) for v in value)):
        value = None
    return dict(label=label, value=value)


def _fields(value: Any, allowed: tuple[str, ...]) -> list[dict]:
    return [_field(name.replace('_', ' ').capitalize(), getattr(value, name, None)) for name in allowed]


def specifications(catalog: Any, slug: str, version_id: str | None = None) -> dict:
    """Inspect a current or explicit version without selecting or materializing it."""
    settings = catalog.refresh(persist_preferences=False)
    choice = next((r for r in settings['investors'] if r['vc_slug'] == slug), None)
    versions = catalog._versions.get(slug, {})
    if choice is None or not versions:
        raise ValueError('unknown investor profile')
    selected = version_id if version_id is not None else choice.get('active_version')
    if selected is None and len(versions) == 1:
        selected = next(iter(versions))
    if selected not in versions:
        raise ValueError('unknown investor version; choose an available version to inspect')
    row = versions[selected]
    result = dict(vc_slug=slug, display_name=row.display_name, investor_version_id=selected,
                  version_label=row.label, enabled=bool(choice.get('enabled')),
                  active=selected == choice.get('active_version'), ready=bool(row.ready),
                  error=None if row.ready else 'This investor version is unavailable; some specifications may be incomplete.',
                  sections=[], taxonomy=[], notes=[])

    def section(identifier: str, title: str, fields: list[dict]) -> None:
        result['sections'].append(dict(id=identifier, title=title, fields=fields))

    def issue(message: str) -> None:
        result['notes'].append(message)
        result['error'] = result['error'] or message

    def trusted_file(relative: str | None):
        path = row.files.get(relative) if relative else None
        if path is None:
            return None
        try:
            expected = row.hashes.get(relative)
            if not expected or path.stat().st_size > 1024 * 1024 or digest(path) != expected:
                raise ValueError('unverified file')
            return path
        except (OSError, ValueError):
            result['ready'] = False
            issue('Some declared specification files changed or lack verified hashes. Refresh the investor catalog before inspecting them.')
            return None

    registry = trusted_file(f'inputs/investors/{slug}.toml')
    if registry is not None:
        try:
            raw = tomllib.loads(registry.read_text())
            identity_files = {}
            for relative in row.files:
                if relative.startswith('source/') and relative.endswith('/profile.json'):
                    path = trusted_file(relative)
                    if path is not None:
                        identity_files[relative] = path
            if raw.get('vc_slug') != slug or not isinstance(raw.get('display_name'), str) or not raw['display_name'].strip():
                raise ValueError('identity mismatch')
            profile = enrich_identity(InvestorProfile(
                vc_slug=slug, display_name=raw['display_name'],
                firm=raw.get('firm', '') if isinstance(raw.get('firm', ''), str) else '',
                role=raw.get('role', 'Investor') if isinstance(raw.get('role', 'Investor'), str) else 'Investor',
                wiki_path=registry.parent.parent/f'wiki/{slug}', registry_path=registry,
            ), identity_files)
            result['display_name'] = profile.display_name
            section('identity', 'Investor identity', [
                _field('Name', profile.display_name), _field('Firm', profile.firm), _field('Role', profile.role),
                _field('Check tiers', raw.get('check_tiers', [])),
                _field('Speaker aliases', raw.get('speaker_names', [])),
            ])
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            issue('Investor identity metadata could not be read for this version.')
    else:
        issue('Investor identity metadata is missing from this version.')
    section('capabilities', 'Version capabilities', [
        _field(name.replace('_', ' ').capitalize(), bool(row.capabilities.get(name, False)))
        for name in ('wiki', 'precedents', 'portfolio_memory', 'classifier')])

    rehearsal = row.config
    canonical = None
    canonical_path = trusted_file(row.canonical_relative)
    if canonical_path is not None:
        try:
            canonical = load_config(canonical_path)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            issue('Canonical assessment configuration could not be read for this version.')
    else:
        issue('Canonical assessment configuration is missing from this version.')

    for prefix, title, config in (('assessment', 'Assessment', canonical), ('rehearsal', 'Rehearsal', rehearsal)):
        if config is None:
            continue
        section(prefix+'-provider', title+' provider', _fields(config.provider, _PROVIDER))
        section(prefix+'-embedding', title+' embedding', _fields(config.embedding, _EMBEDDING))
        section(prefix+'-retrieval', title+' wiki retrieval', _fields(config.retrieval, ('top_k', 'max_exact_reads')))
        section(prefix+'-precedents', title+' precedent retrieval', _fields(config.precedents,
                ('enabled', 'selection_policy', 'candidate_pool_k', 'in_slots', 'out_slots') +
                (('allow_full_transcript',) if prefix == 'assessment' else ())))
        section(prefix+'-portfolio', title+' portfolio memory', _fields(config.portfolio_memory,
                ('enabled', 'retrieval_top_k', 'candidate_pool_k') +
                (('require_complete_embeddings',) if prefix == 'assessment' else ())))
    if canonical is not None:
        section('assessment-contract', 'Assessment template contract', _fields(canonical.run, ('contract_version', 'mode')))
        for name in ('phase1', 'phase2'):
            phase = getattr(canonical, name)
            section('assessment-'+name, 'Assessment '+name.replace('phase', 'phase '), [
                _field('Model', phase.model or canonical.provider.model),
                _field('Model override', phase.model),
                _field('Max output tokens', phase.max_output_tokens or canonical.provider.max_output_tokens),
                *_fields(phase, _PHASE),
            ])
        if canonical.phase1_v44 is not None:
            section('assessment-phase1-v44', 'Assessment claim retrieval', _fields(canonical.phase1_v44,
                    ('taxonomy_top_k', 'claim_retrieval_top_k', 'max_wiki_reads_per_claim',
                     'max_precedent_reads_per_claim', 'max_revisits')))
    if canonical is not None:
        result['notes'].append('Assessment values describe the canonical template. Live execution binds the investor and pitch, uses session paths and full mode, and takes its contract version from rehearsal classification.')
    if rehearsal is not None:
        result['notes'].append('Rehearsal question limits are the smaller of the configured maximum and the selected depth: quick 3, standard 5, or deep 8. Classifier settings describe configuration, not a guarantee that a classifier artifact is loaded.')
        section('rehearsal-limits', 'Rehearsal limits', _fields(rehearsal.rehearsal,
                ('max_questions', 'max_output_tokens', 'reasoning_effort', 'repair_attempts')))
        section('classification', 'Rehearsal classification', _fields(rehearsal.classification, _CLASSIFICATION))
        section('question-memory', 'Rehearsal question memory', _fields(rehearsal.question_memory, _QUESTION))
    else:
        issue('Rehearsal configuration is missing from this version.')
    taxonomy_key = 'inputs/' + (rehearsal.rehearsal.taxonomy_path if rehearsal else 'taxonomy/codebook_v_final.json')
    taxonomy = trusted_file(taxonomy_key)
    try:
        if taxonomy is None:
            raise ValueError('missing taxonomy')
        terms = json.loads(taxonomy.read_text())
        if not isinstance(terms, list) or not terms:
            raise ValueError('invalid taxonomy')
        for term in terms:
            if not isinstance(term, dict) or not isinstance(term.get('label'), str):
                raise ValueError('invalid taxonomy term')
            result['taxonomy'].append(dict(label=term['label'],
                definition=term.get('definition') if isinstance(term.get('definition'), str) else None,
                coarse_parent=term.get('coarse_parent') if isinstance(term.get('coarse_parent'), str) else None))
    except (OSError, ValueError, TypeError):
        result['taxonomy'] = []
        issue('Taxonomy terms could not be read for this version.')
    if canonical is not None and rehearsal is not None and canonical.run.taxonomy_path != rehearsal.rehearsal.taxonomy_path:
        section('taxonomy-sources', 'Taxonomy sources', [
            _field('Assessment taxonomy', canonical.run.taxonomy_path),
            _field('Rehearsal taxonomy', rehearsal.rehearsal.taxonomy_path),
        ])
        result['notes'].append('Assessment and rehearsal select different taxonomy files. The main taxonomy list contains rehearsal terms; assessment terms are shown separately.')
        assessment_taxonomy = trusted_file('inputs/' + canonical.run.taxonomy_path)
        try:
            if assessment_taxonomy is None:
                raise ValueError('missing assessment taxonomy')
            terms = json.loads(assessment_taxonomy.read_text())
            if not isinstance(terms, list) or not terms or any(
                not isinstance(term, dict) or not isinstance(term.get('label'), str) for term in terms
            ):
                raise ValueError('invalid assessment taxonomy')
            section('assessment-taxonomy', 'Assessment taxonomy', [
                _field(term['label'], [value for value in (
                    term.get('definition'),
                    'Theme: ' + term['coarse_parent'] if isinstance(term.get('coarse_parent'), str) else None,
                ) if isinstance(value, str)]) for term in terms
            ])
        except (OSError, ValueError, TypeError):
            issue('The distinct assessment taxonomy could not be read from this version’s declared files.')
    result['notes'].append('Read-only specifications. Credential values and provider endpoint URLs are not exposed.')
    return result
