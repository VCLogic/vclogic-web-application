# InvestorLens

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Founders preparing to pitch a particular type of venture-capital investor. They need to understand how that investor is likely to interpret the company, practice answering investor-specific questions, and improve the evidence in the pitch.
- Researchers and project collaborators examining individualized venture-capital decision logic. They need to inspect source-linked investor profiles, rationale patterns, evidence, and completed rehearsal outputs without losing provenance.

Both journeys are equally important. The product must not make the research interface feel like an administrative afterthought or make the founder experience feel like a thin wrapper around research artifacts.

## Product Purpose

InvestorLens converts scattered public traces of an individual venture capitalist into an auditable model of observable investment logic. It uses that model to analyze pitches, conduct interactive founder rehearsals, and expose the rationales and supporting evidence behind an assessment.

Success means that a founder can complete the full journey from investor selection to pitch rehearsal and assessment without understanding the implementation, while a researcher can inspect how the investor model was constructed and trace conclusions back to their sources.

## Positioning

InvestorLens is not a generic pitch scorer and does not merely prompt a general-purpose language model to imitate an investor. Its distinctive mechanism combines an investor-specific, source-linked Investment Memory; a theory-informed venture-capital rationale taxonomy; retrieval of relevant evidence and precedents; structured rationale analysis; investment-decision synthesis; and an interactive rehearsal that updates the assessment from founder-provided evidence.

## Operating Context

The web application supports two connected workflows:

1. Founder workflow: compare investor-like profiles, select one, submit a pitch, wait while the canonical assessment is constructed, answer adaptive questions in a conversational rehearsal, and review the completed assessment and evidence.
2. Research workflow: inspect an investor profile, explore recurring decision rationales and their relationships, search the Investment Memory, read source-linked chapters and evidence, and inspect saved rehearsal sessions.

The interface may reorganize navigation and information architecture substantially, provided both workflows remain complete and connected.

## Capabilities and Constraints

- Preserve all existing routes and capabilities, although route presentation and navigation may be reorganized.
- Preserve the canonical wiki-based assessment, rationale analysis, decision synthesis, adaptive rehearsal, completed assessment, pitch annotations, evidence inspection, session library, investor profiles, Investment Memory search, and rationale inventory.
- Preserve the distinction between an active conversation and the final assessment. Provisional decisions and scores must remain hidden during rehearsal.
- Preserve source provenance, evidence identifiers, verified artifacts, investor-simulation disclosures, and the distinction between the simulated profile and the real investor.
- Founder answers remain unverified founder-provided evidence unless independently checked.
- The application is a local, single-user prototype using the existing React, TypeScript, FastAPI, and LangGraph implementation.
- The redesign changes the web application and its information architecture, not the underlying assessment or classification methodology.

## Brand Commitments

- Product name: InvestorLens.
- Investor identities must be described as investor-like simulations, such as “Charles Hudson-like Investor,” rather than as the real person.
- The voice should be direct, intellectually serious, transparent about uncertainty, and understandable to non-technical founders and business researchers.
- Existing investor portraits may be retained with their attribution and simulation disclosure.

## Evidence on Hand

- Six investor-like profiles with portraits and structured profile metadata.
- Source-linked Investment Memories generated from public materials.
- A venture-capital decision-rationale taxonomy with definitions.
- Historical pitch decisions and precedent material used by the configured assessment pipeline.
- Saved rehearsal sessions, structured rationale outputs, assessments, evidence references, and usage records.
- Existing screenshots in `docs/screenshots/` document the current interface and its information-density problems; they are evidence of product content, not visual authority for the redesign.

No testimonials, commercial adoption claims, or external validation claims should be invented.

## Product Principles

1. Conversation first, assessment second: founders should experience a credible rehearsal rather than an exposed processing dashboard.
2. Auditable by design: researchers must be able to move from a conclusion to its rationale and source evidence.
3. Progressive disclosure: present the right depth for the current task instead of showing every artifact simultaneously.
4. One product, two serious journeys: founder preparation and research inspection share the same underlying investor model and should feel deliberately connected.
5. Explicit uncertainty: distinguish observed evidence, founder claims, modeled inference, and unresolved questions.

## Accessibility & Inclusion

The redesigned web application must support keyboard navigation, visible focus, semantic controls, readable contrast, responsive layouts, reduced motion, zoom and enlarged text, and clear alternatives to graph-only information.
