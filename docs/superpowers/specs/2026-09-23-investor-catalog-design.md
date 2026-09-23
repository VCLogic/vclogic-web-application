# Automatic investor discovery and version settings

Status: approved by the user on 2026-09-23.

## Agreed behavior

Discover investors automatically from the existing onboarding process. Add a
settings page to enable or disable each investor and select one active version
per investor. Onboarding itself remains in the onboarding project.

## Current integration gaps

- ProfileService and RehearsalWebService capture separate investor lists at
  startup. New registrations do not appear until restart.
- Web assessment, rehearsal start, and rehearsal resume share the default
  configuration. Onboarding generates investor-specific configurations.
- Onboarding prepares separate bundle directories, but installation targets
  paths keyed only by investor slug and rejects differing existing files.
  Multiple prepared versions cannot currently coexist in that installed layout.
- Canonical assessment storage is keyed by pitch version and investor slug;
  it must distinguish investor versions to avoid reusing an older assessment.
- Two backend tests require exactly six investors; seven are now installed.

## Proposed design

### Discovery and identity

A shared investor catalog serves settings, profiles, assessment, matching, and
rehearsal. Discover existing installed registrations and bundles in configured
onboarding bundle directories. Local sibling setup defaults to the sibling
onboarding project's bundles directory when present; other deployments can
configure explicit directories. Refresh automatically without restarting the
server, with a refresh action in settings for immediate discovery.

The investor slug identifies the person/profile. A separate content fingerprint
identifies a version using the bundle's validated asset inventory and execution
configuration. Directory names are display labels, not version identities.
Deduplicate a prepared bundle and its installed copy when their content matches.
An existing profile without an onboarding manifest receives a legacy version
derived from its required assets and resolved configuration.

Validate manifest paths, asset hashes, registry identity, configurations, and
required assets before making a version available. Incomplete or invalid bundles
appear with an explanation in settings and cannot be activated. One invalid
bundle must not prevent discovery of other investors.

### Settings and activation

Add Settings → Investors. Each investor row shows its name, enabled state,
active version, available versions, creation date when supplied, readiness,
and available capabilities. The version selector and enable switch persist
across application restarts. Saving settings atomically prevents partial updates.

Existing investors remain enabled. A newly discovered investor with one ready
version is automatically enabled. If a new investor has multiple ready versions,
settings asks for a selection rather than guessing from directory names. New
versions of a known investor never replace its selected version automatically.
An explicitly disabled investor stays disabled when new versions arrive.

Disabling removes an investor from new assessment and rehearsal selections;
saved results remain readable and existing sessions can continue. Changing
the active version affects only newly submitted work. If the active version
becomes unavailable, report that state rather than silently selecting another.

### Version-specific execution and retained history

Materialize a validated version in an immutable, application-managed workspace
before its first use. Preserve the source bundle, indexed assets, taxonomy,
and resolved configuration. Keep mutable runtime outputs separate from the
immutable input snapshot. This allows multiple versions to coexist without
overwriting the assessment project's current installed investor files.

Resolve investor version and configuration once when a job is submitted. Persist
that selection on assessments, match rows, and rehearsal sessions. Include the
version identity in assessment reuse keys. A version switch during execution
cannot alter a queued or running job. Resume rehearsal with its recorded version,
not the version currently selected in settings.

Continue reading existing assessment/session artifacts without rewriting them
or claiming a historical version identity that was not recorded. Treat old
artifacts as legacy records and preserve their current resume behavior; new
version-specific assessments must not reuse those records as verified matches.

Use the onboarding-generated configuration when provided; legacy investors use
the resolved application default. Respect differences in precedent, portfolio,
and classifier support. Missing optional portraits use the existing initials
fallback. Historical percentiles are absent when no applicable reference data
exists; do not borrow another version's calibration.

### Frontend integration

Use the existing application layout and controls. Investor queries refresh on
navigation/focus and periodically while investor selection or settings is open.
Successful settings changes invalidate affected queries. Show only enabled,
ready, active versions in the gallery and new-work selectors. Reject stale
selections at the API with a clear recoverable response. Retain the existing
disclosure and profile-reading experience.

## Verification

- Add a new investor after app startup and confirm automatic discovery and use.
- Discover two bundles with the same investor slug and different fingerprints;
  select one version, switch it, and verify separate assessment reuse keys.
- Verify enable/disable and active-version choices survive restart and discovery.
- Confirm assessment, comparison, rehearsal start, and rehearsal resume use the
  recorded configuration and inputs even after an active-version change.
- Confirm invalid/incomplete bundles, missing sources, and duplicate copies are
  handled without breaking other investors or changing active selections.
- Confirm legacy records remain readable and existing resume behavior works.
- Replace fixed investor-count tests with assertions against controlled fixtures
  and discovered identities. Test the settings controls and browser flows.
- Run backend and frontend suites, production build, and relevant browser smoke
  tests. Offline engine doubles validate integration; report live model-backed
  verification separately if performed.

## Alternatives considered

1. Registry refresh alone: small change, but cannot support coexisting versions
   or preserve the configuration used by a previous session.
2. Shared catalog plus immutable version workspaces (recommended): supports
   existing installations and prepared bundles without changing onboarding's
   conflict rules, at the cost of storing version snapshots.
3. Change onboarding and engine installation to support versioned paths: a wider
   cross-project migration than needed for the web application's settings.

## Baseline verification

Backend: 81 passed, 2 failed because they expect six investors, 3 skipped for
missing archived sessions. Frontend: 87 passed and 2 timed out in the full run;
both affected files passed in an isolated single-worker rerun (17 tests).
Production frontend build passed. No live model-backed assessment was run.
