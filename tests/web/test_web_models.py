import pytest
from pydantic import ValidationError

from vclogic_web.models import CreateSessionRequest


def test_session_creation_requires_cost_authorization_and_company() -> None:
    with pytest.raises(ValidationError):
        CreateSessionRequest(
            vc_slug="charles-hudson-precursor-ventures",
            company_aliases=[],
            pitch_text="Pitch",
            authorize_provider_cost=False,
        )


def test_session_creation_normalizes_pitch() -> None:
    request = CreateSessionRequest(
        vc_slug="charles-hudson-precursor-ventures",
        company_aliases=["TargetCo"],
        pitch_text="  Founder pitch  ",
        authorize_provider_cost=True,
    )

    assert request.pitch_text == "Founder pitch\n"
    assert request.company_aliases == ("TargetCo",)
    assert request.rehearsal_depth == "standard"


def test_session_creation_accepts_a_rehearsal_depth() -> None:
    request = CreateSessionRequest(
        vc_slug="charles-hudson-precursor-ventures",
        company_aliases=["TargetCo"],
        pitch_text="Founder pitch",
        authorize_provider_cost=True,
        rehearsal_depth="quick",
    )

    assert request.rehearsal_depth == "quick"


def test_session_creation_rejects_an_unknown_rehearsal_depth() -> None:
    with pytest.raises(ValidationError):
        CreateSessionRequest(
            vc_slug="charles-hudson-precursor-ventures",
            company_aliases=["TargetCo"],
            pitch_text="Founder pitch",
            authorize_provider_cost=True,
            rehearsal_depth="endless",
        )
