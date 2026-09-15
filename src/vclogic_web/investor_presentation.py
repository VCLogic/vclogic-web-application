"""Attributed presentation metadata for supported investor-like profiles."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, HttpUrl


class InvestorPresentation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    portrait_path: str
    portrait_alt: str
    source_profile_url: HttpUrl
    source_image_url: HttpUrl
    photo_attribution: str = "Photo: The Pitch"


INVESTOR_PRESENTATION: dict[str, InvestorPresentation] = {
    "charles-hudson-precursor-ventures": InvestorPresentation(
        portrait_path="/investors/charles-hudson-precursor-ventures.jpg",
        portrait_alt="Charles Hudson portrait",
        source_profile_url="https://www.thepitch.show/investors/charles-hudson-precursor-ventures",
        source_image_url="https://cdn.sanity.io/images/dlpvy1r0/production/a152dbb7c79eed308905c8df9260463b77c07f44-800x800.jpg",
    ),
    "elizabeth-yin-hustle-fund": InvestorPresentation(
        portrait_path="/investors/elizabeth-yin-hustle-fund.jpg",
        portrait_alt="Elizabeth Yin portrait",
        source_profile_url="https://www.thepitch.show/investors/elizabeth-yin-hustle-fund",
        source_image_url="https://cdn.sanity.io/images/dlpvy1r0/production/d4c93a662eceb5c08eaf66d74d7fa290103b42a6-711x711.jpg",
    ),
    "jillian-manus-structure-capital": InvestorPresentation(
        portrait_path="/investors/jillian-manus-structure-capital.jpg",
        portrait_alt="Jillian Manus portrait",
        source_profile_url="https://www.thepitch.show/investors/jillian-manus-structure-capital",
        source_image_url="https://cdn.sanity.io/images/dlpvy1r0/production/53b19c4e2c07a3aab5ec1a615a05b64eba5c03a3-800x800.jpg",
    ),
    "phil-nadel": InvestorPresentation(
        portrait_path="/investors/phil-nadel.jpg",
        portrait_alt="Phil Nadel portrait",
        source_profile_url="https://www.thepitch.show/investors/phil-nadel",
        source_image_url="https://cdn.sanity.io/images/dlpvy1r0/production/16148284caba85c57060cb8a2a7f19406b00de59-800x800.jpg",
    ),
    "jesse-middleton-flybridge": InvestorPresentation(
        portrait_path="/investors/jesse-middleton-flybridge.jpg",
        portrait_alt="Jesse Middleton portrait",
        source_profile_url="https://www.thepitch.show/investors/jesse-middleton-flybridge",
        source_image_url="https://cdn.sanity.io/images/dlpvy1r0/production/535313075fdfc1ba7c067739fe9482ffcf951f0a-501x501.jpg",
    ),
    "cyan-banister-long-journey-ventures": InvestorPresentation(
        portrait_path="/investors/cyan-banister-long-journey-ventures.jpg",
        portrait_alt="Cyan Banister portrait",
        source_profile_url="https://www.thepitch.show/investors/cyan-banister-long-journey-ventures",
        source_image_url="https://cdn.sanity.io/images/dlpvy1r0/production/648e281cc3d28569a73a1002a3d57bd3188912d6-1152x1152.jpg",
    ),
}
