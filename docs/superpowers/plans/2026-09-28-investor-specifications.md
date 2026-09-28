# Investor configuration and specifications view

**User clarification:** Missing scope includes both dossiers and configuration/specification screens. Dossier restoration is already complete; this task exposes per-version prepared configuration without adding an editor or changing execution.

## Contract

- Read-only view at `/settings/investors/:vcSlug/specifications?version=<fingerprint>`, linked from Settings and the dossier.
- API reads the requested discovered version, or the active choice when no version is specified. Disabled versions remain inspectable. Unknown versions do not fall back silently.
- Show version identity/readiness, investor registry specifications, taxonomy/check tiers, assessment and rehearsal model/budget settings separately, embedding/retrieval settings, evidence capabilities and classifier/rehearsal settings.
- Fields come from the selected version's declared assets and parsed configuration. Only allowlisted public settings are exposed; no environment values, provider credentials, or arbitrary config dumps.
- Display prepared defaults and explain runtime/preset overrides; no provider calls, snapshots, new assessments, or setting mutations from viewing specifications.

## Work

- [x] Implement backend reader and version/security/partial-data tests.
- [x] Add API route and validation/error regression tests.
- [x] Build responsive view, link entry points, and frontend coverage.
- [x] Verify real legacy and onboarded configurations, disabled/version-switch behavior, full tests/build, and browser navigation.
- [x] Document behavior and record verification.

## Verification

- Backend: 168 passed, 3 skipped because archived canary outputs are unavailable.
- Frontend: 102 tests passed; production TypeScript/Vite build passed (existing chunk-size advisory).
- Targeted Playwright: 5 passed, 1 intentional viewport skip.
- Live browser: all seven investors and all four Mac versions inspected at desktop and 390px mobile width, with expanded taxonomy and no horizontal overflow. Preferences remained byte-for-byte unchanged. A mobile pass overlapped rebuilding the served assets; repeated after the build completed and all pages passed.
- Real active versions each expose 18 sections and 44 taxonomy terms. Incomplete versions retain verified identity and available configuration.
- Review fixes: nonpersisting discovery for specifications; hash validation before parsing; independent registry inspection for incomplete bundles; separate assessment terms when assessment/rehearsal taxonomies differ.
- No paid inference, assessment creation, or execution snapshots used in verification.
