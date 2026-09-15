# Web application reference

Historical product description extracted from the original framework. For current setup and repository paths, see [the README](../README.md).



The local web application turns the canonical v4/v4.1 assessment and founder
rehearsal workflow into a single-user service. **My Pitches** stores each pitch
as an immutable, verified version before any provider call is required. The
**Assess your pitch** action on an investor profile lets a founder choose an
existing saved version or create a new pitch, then either save it for later or
authorize an assessment. A single investor remains a first-class path.

Each pitch version has one evolving **Investor comparison** rather than a stack
of duplicate shortlist runs. A founder can add one or more profiles; completed
canonical assessments are reused without another provider call, and only newly
selected profiles are submitted. Results are ordered by raw investment
likelihood; an empirical within-profile percentile is shown only when enough
historical reference decisions exist. The comparison is a fit estimate, not an
endorsement or a universal ranking of investors.

Completed assessments open as compact dossiers: verdict, likelihood,
confidence, positive and negative rationale signals, unresolved questions, and
a small source-diverse evidence set. The original model synthesis is available
in a closed disclosure rather than occupying the default page. Its `P-*`,
`W-*`, `H-*`, and `R*` technical references are rendered as numbered,
interactive citations that open the exact pitch passage, Investment Memory
excerpt, observed precedent, or Phase 1 rationale record. Raw identifiers remain
available only inside source details. Exact check-size language in the original
synthesis is explicitly treated as model-generated unless its linked evidence
supports it.

A completed canonical assessment is reusable. Public, artifact-backed progress
shows the Phase 1 rationale mapping and Phase 2 Investment Decision Synthesis
without exposing prompts, credentials, raw provider responses, or hidden model
reasoning. From the same assessment, the
founder can begin multiple Quick (up to 3 questions), Standard (up to 5), or
Deep (up to 8) rehearsal attempts without paying to rebuild Phase 1 and Phase 2.
The agent may finish earlier when another question is unlikely to change the
assessment. Each conversation remains attached to the exact pitch version and
investor-like profile that produced it. The pitch remains accessible during the
conversation, while the complete assessment is revealed when rehearsal ends.

The interface uses a dark, portrait-led investor gallery and an editorial
**Investor Decision Dossier** for each profile, then shifts to a light
analytical workspace for pitch briefing, questioning, and decision synthesis.
Completed rehearsals separate the conversation, assessment, and pitch evidence
into accessible views. The assessment includes an evidence-to-rationale
**Decision Path** and a likelihood timeline that distinguishes new evidence
from clarification or unresolved uncertainty. The project library records the
initial and current likelihood so founders can see how supplied evidence moved
the assessment instead of seeing only a final score.

The profile's **Decision Signature** ranks the recurring rationales that create
conviction, create concern, or remain contextual/unresolved. A concise
**Often considered together** section presents the strongest textual
associations as explicitly observed co-occurrence—not causal rules or claims
that one rationale produces another. The searchable and sortable complete
rationale inventory remains available in a collapsed disclosure. A **Find
supporting evidence** action carries the selected label into Investment Memory
search so every summary remains connected to its public-source evidence.

Investment Memory retains the full source-linked chapter text without rendering
the corpus as one long page. Core-profile and evidence chapters appear in an
indexed library, and only one selected chapter preview is rendered at a time.
Separate **Read complete chapter** and **Inspect sources** disclosures preserve
the full body and repository references without making them part of the default
page flow. Selecting another chapter replaces the reader; it does not truncate
or discard evidence.

Investment Memory search returns five deduplicated evidence items per page,
presents clean quotations and friendly source titles, and keeps evidence IDs,
public-source references, and repository paths in expandable source details.

Investor portraits are locally cached from the corresponding official The
Pitch investor profile pages. Each image has an allowlisted source URL, local
SHA-256 record, and visible attribution on the detailed profile. Refresh these
assets deterministically with `uv run python scripts/sync_investor_portraits.py`.

Every profile is explicitly presented as a simulation—not the real investor and
not endorsed by them. The browser performs no investment scoring: all decisions,
rationales, annotations, and evidence links are derived from verified backend
artifacts. A completed session can be resumed locally or exported as a safe ZIP;
raw model calls, credentials, checkpoints, and hidden reasoning are excluded.
