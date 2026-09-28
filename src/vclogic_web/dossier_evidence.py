"""Read explicitly version-bound reference history for investor dossiers.

These observations describe the imported source-project record. They are not
proof that historical runs used the current runtime inputs, or calibration data.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class DossierEvidence:
    investigations: tuple[dict[str, Any], ...] = ()
    status: Literal['available', 'not_prepared', 'invalid'] = 'not_prepared'
    note: str = ('Historical decision assessments have not been imported for this investor version. '
                 'Its investment criteria and source evidence remain available in Investment Memory below.')


def signature(path: Path) -> tuple:
    try:
        stat = path.stat()
        return (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
    except OSError:
        return ()


def load_evidence(path: Path, slug: str, version_id: str) -> DossierEvidence:
    if not path.exists():
        return DossierEvidence()
    try:
        if path.is_symlink() or path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('invalid dossier evidence file')
        raw = json.loads(path.read_text())
        if (raw['schema'] != 'vc-profile-evidence-v1' or raw['vc_slug'] != slug
                or raw['investor_version_id'] != version_id):
            raise ValueError('dossier identity mismatch')
        rows = raw['investigations']
        if not isinstance(rows, list):
            raise ValueError('invalid investigations')
        digest = sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if raw['investigations_sha256'] != digest:
            raise ValueError('dossier content digest mismatch')
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('rationales'), list):
                raise ValueError('invalid historical investigation')
            for rationale in row['rationales']:
                if (not isinstance(rationale, dict) or not isinstance(rationale.get('taxonomy_label'), str)
                        or rationale.get('direction') not in {'positive', 'negative', 'neutral', 'unresolved'}):
                    raise ValueError('invalid historical rationale')
                confidence = rationale.get('confidence', 0)
                if not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
                    raise ValueError('invalid rationale confidence')
        if not rows:
            return DossierEvidence()
        return DossierEvidence(tuple(rows), 'available',
            f'Reference history: {len(rows)} source-project assessments; '
            'not calibration for the active investor version.')
    except (OSError, ValueError, KeyError, TypeError):
        return DossierEvidence(status='invalid', note=(
            'The historical decision record for this investor version could not be verified. '
            'Re-import its dossier evidence. Investment Memory remains available below.'))
