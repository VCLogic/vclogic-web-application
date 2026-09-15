# InvestorLens interface system

InvestorLens uses an **Evidence Dossier** visual language: an editorial case file rather than a generic analytics dashboard. The interface must make the underlying investment model inspectable while keeping founder rehearsal conversational.

## Visual foundations

- Graphite (`#090d11`) provides the application shell and investor register.
- Mineral paper (`#fbf8ef`) is the reading and working surface.
- Forest green (`#365d48`) marks evidence-grounded actions and positive signals.
- Brick (`#9a3f32`) and ochre (`#8c681d`) identify concern and unresolved context.
- `Barlow Condensed` is used for indexed editorial headings, `Inter` for controls and metadata, and `Source Serif 4` for evidence and long-form reading.
- Corners are nearly square. Hierarchy comes from rules, spacing, typography, and tonal surfaces—not floating rounded cards.

## Information architecture

The top level contains two places: **Investors** and **Rehearsals**.

- The investor register supports rapid comparison, showing one selected evidence-grounded profile at a time.
- A profile is a decision dossier: identity, Decision Atlas, then Investment Memory.
- The Decision Atlas defaults to recurring themes and exposes the complete searchable rationale inventory as a secondary view.
- Investment Memory mounts one chapter at a time, renders Markdown, paginates evidence search, and keeps provenance available without making it the primary reading experience.
- Pitch intake is a founder briefing paired with the selected investor identity.
- Processing states report public workflow stages and concise artifact-backed activity; complete technical history is disclosed on demand.
- Active rehearsal is a natural conversation. Assessment and pitch evidence remain secondary until the conversation is complete.

## Interaction rules

- Never imply that a simulation is the real investor or endorsed by them.
- Never expose hidden chain-of-thought, credentials, or raw provider payloads.
- Show provisional results only where their status is explicit.
- Preserve founder responses immediately and make retry paths visible.
- Every control must be keyboard accessible, with visible focus and semantic status/error messaging.
- At narrow widths, indexes may scroll horizontally, content becomes single-column, and complete data remains available without document-level horizontal overflow.

## Component patterns

- `AppShell`: persistent graphite header and skip link.
- `CaseIndex`: numbered local navigation for dossier or assessment sections.
- Register rows: compact investor comparison with a single selected preview.
- Ledger: small, factual coverage summary separated by rules.
- Evidence reader: index plus one mounted Markdown chapter.
- Conversation: investor prompt on warm paper, founder evidence on pale green, rationale labels as restrained tags.
- Terminal failure: concise diagnosis and recovery first; prior agent artifacts behind a disclosure.
