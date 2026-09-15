from pathlib import Path

from vclogic_web.investor_presentation import INVESTOR_PRESENTATION


EXPECTED = {
    "charles-hudson-precursor-ventures",
    "elizabeth-yin-hustle-fund",
    "jillian-manus-structure-capital",
    "phil-nadel",
    "jesse-middleton-flybridge",
    "cyan-banister-long-journey-ventures",
}


def test_all_supported_profiles_have_the_pitch_portrait_provenance() -> None:
    assert set(INVESTOR_PRESENTATION) == EXPECTED
    for slug, metadata in INVESTOR_PRESENTATION.items():
        assert metadata.portrait_path == f"/investors/{slug}.jpg"
        assert str(metadata.source_profile_url).startswith(
            "https://www.thepitch.show/investors/"
        )
        assert str(metadata.source_image_url).startswith(
            "https://cdn.sanity.io/images/dlpvy1r0/production/"
        )
        assert metadata.photo_attribution == "Photo: The Pitch"
        assert metadata.portrait_alt.endswith("portrait")


def test_downloaded_portraits_are_real_jpegs() -> None:
    root = Path("web/frontend/public/investors")
    for slug in EXPECTED:
        payload = (root / f"{slug}.jpg").read_bytes()
        assert payload.startswith(b"\xff\xd8\xff")
        assert len(payload) > 20_000
