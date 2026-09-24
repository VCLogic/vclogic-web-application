# Runtime Assets, VCLogic UI, and Automatic Portraits Implementation Plan

> **For agentic workers:** Execute independent asset, frontend, and portrait tasks in parallel; preserve all existing version bindings. User approved the scope with “Go”.

**Goal:** Make all seven installed VCs available, restore the latest VCLogic presentation, and automatically cache attributed portraits for newly onboarded VCs.

**Architecture:** Keep the assessment workspace as runtime owner. Migrate validated legacy inputs with backups and a repeatable local script. Merge only missing upstream UI changes into this application's version-aware frontend. Resolve portraits through a bounded trusted-source cache served by the backend, independent of frontend builds.

**Tech Stack:** Python/FastAPI, existing assessment engine, React/TypeScript/Vite, pytest/Vitest/Playwright.

## Task 1 — Runtime migration

- [x] Compare six legacy registry/wiki/index/corpus/config dependencies with the source LangGraph workspace.
- [x] Add scripts/migrate_legacy_investors.py and tests/web/test_legacy_migration.py covering dry-run, backup, idempotency, preserving unrelated investors, and failed validation.
- [x] Copy the compatible runtime assets to the assessment workspace, backing up divergent files and settings before changing them.
- [x] Select each migrated ready version without altering the user's enable/disable choice or Mac's settings.
- [x] Verify catalog readiness and offline engine package preparation for all migrated investors. No paid model calls.

## Task 2 — Frontend parity

- [x] Compare web/frontend to the source workspace and merge VCLogic branding plus missing founder assessment UI fixes.
- [x] Preserve settings navigation/routes, version-aware request IDs, stale selection checks, and historical assessment bindings.
- [x] Update relevant regression tests and run npm test -- --run --maxWorkers=2 and npm run build in web/frontend.

## Task 3 — Portrait integration

- [x] Add bounded trusted-source fetching, identity matching, positive and negative caching, and local runtime asset serving.
- [x] Preserve the existing six portraits, add regression coverage for aliases, redirects, failure/retry behavior, cache reuse, and malformed responses.
- [x] Verify actual Mac Conwell portrait retrieval from The Pitch with attribution and no frontend build requirement for future VCs.

## Task 4 — Integration verification

- [x] Confirm latest upstream Python presentation/API contracts are already present or port missing requirements.
- [x] Run .venv/bin/python -m pytest -q, frontend unit tests, production build, and applicable browser checks.
- [x] Inspect live gallery/settings/portrait behavior using a temporary verification server; preserve the user's running server.
- [x] Update README with migration and automatic portrait behavior, review changes, and record exact validation results.

## Execution notes

- Starting web commit: 8dfe2ba (feat/investor-version-settings).
- Initial source comparison confirms models.py, session_views.py, assessment_service.py, and profiles.py already contain the latest upstream API behavior, with local version/catalog adaptations.
- Existing running servers do not hot-reload Python. Final instructions must mention restarting the user's instance.


## Validation and review results

- Runtime migration checked 1,260 assets and changed only 12 index files. Original settings and Elizabeth's previous index are backed up in the assessment workspace at `outputs/legacy-investor-migrations/20260924T072605.963602Z`.
- All seven installed investors are enabled and available with no catalog discovery errors; Mac's selected version and previous enabled flags are unchanged.
- Six offline engine packages passed `prepare_live_package`, which also calls `verify_package`. No provider calls or model downloads occurred.
- Repeat migration copied zero files. Final report: `outputs/legacy-investor-migrations/20260924T072850.472345Z/report.json` in the assessment workspace.
- Independent backend review found explicit alternative-version overwrite, a settings compare/write concurrency window, and unbounded slow buffered reads. Fixed alternative selection preservation and streaming reads, with regression tests. Migration is documented as an offline operation with the server stopped; it detects changed settings but does not claim a shared cross-process transaction lock.
- Browser testing exposed first-request latency while loading 240 MB of indexes. Profiling attributed cold catalog validation to engine index integrity checks; warm responses measured under 0.5 seconds. Catalog validation now runs in application startup before readiness. A new test failed before the lifecycle fix and passes afterward. Browser startup timeout accommodates this initialization without extending page assertion timeouts.
- Backend suite: 134 passed, 3 skipped (missing archived canary data), one existing Starlette deprecation warning.
- Frontend suite: 94 passed across 25 test files. Production build passed with existing chunk-size advisory.
- Fresh-server Playwright smoke checks: 8 passed across desktop and mobile, including brand, gallery, rehearsal, and settings.
- Mac's actual portrait was automatically resolved and cached with The Pitch attribution (50,479 bytes, SHA256 `99eacafe0590bf2c62f5bdcae7a996f5ae87547b2a5a9f866974614063491470`).
- Remaining operational step: restart the user's running server to load new Python routes. Existing user processes were not terminated.

- Live browser inspection confirmed seven investor choices, Mac image served by `/api/investors/mac-conwell/portrait` at 800×800, and zero mobile document overflow. Desktop/mobile screenshots inspected at `/tmp/vclogic-mac-desktop.png` and `/tmp/vclogic-mac-mobile.png`.
