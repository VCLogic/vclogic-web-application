# Investor catalog implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan inline, with test-first changes and a final independent review.

**Goal:** Automatically discover investor bundles, persist enabled/active-version settings, and bind new work to retained investor versions.

**Architecture:** A shared InvestorCatalog scans registrations and bundle manifests, validates and fingerprints versions, and persists preferences. ExecutionBinding creates an immutable asset snapshot within the pipeline workspace while keeping the existing output locations. Profile and job services consume the same catalog. Settings uses existing UI components and styling.

**Tech Stack:** Python/Pydantic/FastAPI, React/TypeScript/TanStack Query, pytest/Vitest/Playwright.

**Spec:** `docs/superpowers/specs/2026-09-23-investor-catalog-design.md` (approved).

## Task 1: Catalog and settings API

Files: new `src/vclogic_web/investor_catalog.py`, `src/vclogic_web/investor_versions.py`, `tests/web/test_investor_catalog.py`; modify `app.py`, `cli.py`, `profiles.py`.

- [ ] Write fixture-based tests for discovering an investor after startup, disabled persistence, selection of two versions, invalid manifest isolation, snapshots surviving source removal, and hash/path validation.
- [ ] Run `.venv/bin/python -m pytest tests/web/test_investor_catalog.py -q`; expect failure before implementation.
- [ ] Implement these interfaces:
  ```python
  class InvestorCatalog:
      def refresh(self) -> dict: ...
      def settings(self) -> dict: ...
      def update(self, slug: str, *, enabled: bool, active_version: str | None) -> dict: ...
      def select(self, slug: str) -> ExecutionBinding: ...
      def binding(self, slug: str, version_id: str) -> ExecutionBinding: ...
  ```
  Use a lock and atomic JSON replacement for settings; SHA-256 inventory/config identities; safe relative manifest paths; staged copies then rename for snapshots; reject stale/disabled selections. Bind configuration to the retained input root and canonical template, preserve shared runtime output directories.
- [ ] Add GET `/api/settings/investors`, POST `/api/settings/investors/refresh`, PUT `/api/settings/investors/{slug}`. Add repeatable `--investor-bundles` and shared catalog creation in the application factory. Profiles use the active snapshot and avoid historical calibration for new bundle versions.
- [ ] Run catalog tests and existing profile/API tests; replace exactly-six assertions with discovered identity sets. Commit tested changes.

## Task 2: Version-bound execution

Files: `assessment_service.py`, `service.py`, `models.py`, `matching.py`; new `tests/web/test_investor_version_execution.py`.

- [ ] Write tests proving two versions get distinct assessment IDs, a queued assessment retains its version after a settings change, and rehearsal start/resume use the saved binding after disable or restart.
- [ ] Run the new tests and observe the missing version behavior.
- [ ] Add nullable `investor_version_id` to assessment/match/session presentation models. Assessments use `slug--fingerprint` directories (legacy paths still readable). Save binding before queuing. Select recorded bindings for execution, without consulting active settings on resume.
- [ ] Persist comparison assessment IDs rather than selecting whichever assessment shares the slug. Do not reuse historical scores for fingerprinted assessments.
- [ ] Verify `.venv/bin/python -m pytest tests/web -q` and commit.

## Task 3: Investor settings interface

Files: new `web/frontend/src/features/settings/InvestorSettings.tsx`, `.css`, `.test.tsx`; modify `api/client.ts`, `api/types.ts`, `app/App.tsx`, `components/AppShell.tsx` and investor selectors.

- [ ] Write tests for loading, saving enabled/active selection, readiness explanations, and failed-save recovery.
- [ ] Run targeted Vitest tests; expect failure before implementation.
- [ ] Add a Settings navigation item and `/settings/investors` route. Render an accessible form per investor with checkbox, version selector, save action, status and error messages. Query settings every 30 seconds and invalidate investor/profile queries after saving. Automatically refresh investor selection queries.
- [ ] Show an empty-gallery link to settings when no investors are enabled; preserve selected investor version with new-work requests to reject stale selections.
- [ ] Run `npm test -- --run --maxWorkers=2` and `npm run build`; commit.

## Task 4: End-to-end checks and documentation

Files: `README.md`, browser tests, approved spec/plan.

- [ ] Document automatic discovery, configured bundle roots, enable defaults, version retention, legacy compatibility, settings persistence and local single-user operation.
- [ ] Run backend suite, frontend suite, build, and browser smoke tests including settings at desktop/mobile sizes. Inspect screenshots once and correct concrete defects.
- [ ] Obtain one independent code review of version identity, snapshot integrity, disabled-state enforcement, legacy compatibility, and stale selections. Fix important findings and rerun affected tests.
- [ ] Record validation and any live-model limitations; commit final changes.

## Execution ledger

- Baseline: backend 81 pass / 2 fixed-count failures / 3 archived-data skips. Frontend timed-out tests passed isolated, build passed.
- Ruling: work on a dedicated branch in the existing checkout to retain editable sibling dependencies and the user's workspace. No merge or publish is part of this task.
