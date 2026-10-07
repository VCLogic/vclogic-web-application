<img src="web/frontend/public/favicon.svg" alt="VCLogic logo" width="80" height="80">

# VCLogic Web Application

A web workspace for exploring investor decision profiles, assessing founder pitches, comparing investor fit, and rehearsing investor questions. Built with **React, TypeScript, and FastAPI**, using the [VCLogic assessment engine](https://github.com/VCLogic/vclogic-vc-agentic-assessment) for execution.

Investor profiles are simulations based on source evidence. They do not represent the real investors or imply endorsement.

## What you can do

- **Explore investor dossiers:** decision signatures, recurring rationales, full Investment Memory chapters, and source-linked evidence.
- **Save and assess pitches:** maintain pitch versions, compare assessments across investors, and inspect supporting evidence.
- **Rehearse questions:** start Quick, Standard, or Deep sessions from assessments and review completed conversations.
- **Manage investors:** automatically discover prepared onboarding bundles, enable or disable investors, and select one active version per investor.
- **Inspect specifications:** view version-specific taxonomy, model and token settings, retrieval configuration, and rehearsal policies.

## Requirements

- Python **3.11–3.13** and [uv](https://docs.astral.sh/uv/).
- Node.js **22.12+** and npm for the frontend build.
- A sibling checkout of `vclogic-vc-agentic-assessment`, with the required investor inputs, configuration, and indexes prepared.
- Provider credentials and embedding resources required by your chosen engine configuration for live assessments and rehearsals.

The web repository contains application code. It does **not** ship the complete investor runtime library, historical assessments, credentials, or downloaded models. Follow the [assessment engine setup](https://github.com/VCLogic/vclogic-vc-agentic-assessment#readme) to prepare those resources. Existing LangGraph workspaces can use the migration instructions below.

## Quick start

Clone both repositories into the same parent directory:

```bash
git clone https://github.com/VCLogic/vclogic-vc-agentic-assessment.git
git clone https://github.com/VCLogic/vclogic-web-application.git
cd vclogic-web-application
uv sync --extra dev --extra embeddings
cd web/frontend
npm ci
npm run build
cd ../..
```

Expected layout:

```text
workspace/
├── vclogic-web-application/
├── vclogic-vc-agentic-assessment/       # Configuration, inputs, indexes, outputs
└── vclogic-vc-investor-onboarding/     # Optional; automatically discovered
    └── bundles/
```

After preparing the engine workspace, launch from the web repository root:

```bash
uv run --extra embeddings vc-clone-web --pipeline-workspace ../vclogic-vc-agentic-assessment --host 0.0.0.0 --allow-remote --port 8001
```

Open **http://localhost:8001** on the server, or **http://<server-ip>:8001** from another machine. Keep the workspace path on one line. Wait for `Application startup complete`; startup validates investor indexes before accepting requests.

This is a workspace-wide, single-user application without per-user access control. Use the remote binding on a trusted network. For loopback-only use:

```bash
uv run --extra embeddings vc-clone-web --pipeline-workspace ../vclogic-vc-agentic-assessment --port 8001
```

The default grounded configuration uses `OPENROUTER_API_KEY` from the process environment. Configure credentials before launching live assessments; browsing specifications and investor discovery do not call a model provider. The embeddings extra can be omitted when your configuration does not require it.

### Launch configuration

| Option | Default / behavior |
| --- | --- |
| `--pipeline-workspace` | Required path to the assessment workspace. |
| `--config` | `configs/rehearsal-charles-v41-grounded.toml`, relative to the assessment workspace. |
| `--host` | `127.0.0.1`; non-loopback addresses require `--allow-remote`. |
| `--port` | `8000`; the quick start uses `8001`. |
| `--investor-bundles` | Repeatable bundle roots; replaces the default sibling bundle location. |
| `--static-root` | `web/frontend/dist`, relative to the current working directory. |

Run `uv run vc-clone-web --help` for CLI usage. The API exposes `/api/health` and interactive documentation at `/docs`.

The uv configuration installs the sibling engine in editable mode. The application wheel declares an engine dependency; deployments must supply a compatible engine wheel or package source and the built frontend separately. No published engine package is assumed.

## Investor workflow

1. Prepare or onboard an investor in the assessment/onboarding projects.
2. Open **Settings → Investors** and refresh discovery if needed.
3. Enable the investor and select one ready version. A new investor with exactly one ready version is enabled automatically.
4. Open its dossier to explore evidence, or **View selected version specifications** to inspect its configuration.
5. Save a pitch, request an assessment, and start a rehearsal when ready.

The application discovers prepared assets; it does not run onboarding or build missing indexes through the browser. Historical sessions retain their original investor version when you change the active selection.

## Investor discovery and versions

Open **Settings → Investors** (`/settings/investors`) to enable or disable an
investor and choose the version used for new assessments. The gallery and pitch
selectors show enabled, ready versions. Existing profile URLs remain readable
for installed legacy profiles whose indexes need attention.

The application discovers installed profiles from the configured input root and
onboarding receipts under `onboarding/<vc-slug>/bundle.json`. It also discovers
prepared bundles in the sibling `vclogic-vc-investor-onboarding/bundles` directory.
To use different locations, supply one or more explicit roots (these replace the
sibling default):

```bash
uv run vc-clone-web --pipeline-workspace ../vclogic-vc-agentic-assessment \
  --investor-bundles ../vclogic-vc-investor-onboarding/bundles \
  --investor-bundles /path/to/another/bundle-library
```

Each root may contain bundle directories or be a bundle itself. Discovery does
not prepare bundles, download models, rebuild indexes, or call a model provider.
Settings explains incomplete or incompatible versions. Finish onboarding/index
preparation in the source project and refresh to make them ready. Discovery is
cached briefly; open investor/settings pages refresh every 30 seconds, and
**Refresh investors** performs an immediate scan.

- An installed version remains selected on first discovery. A new investor with
  exactly one ready version is enabled automatically; multiple ready versions
  require an explicit choice.
- New versions never replace an existing selection automatically. Explicitly
  disabled investors stay disabled. Choices persist across application restarts.
- Disabling prevents new assessments for that investor. Saved results remain
  readable, and existing rehearsals and rehearsals from saved assessments retain
  the version they started with.
- A version is identified by its asset/configuration fingerprint, not its folder
  name. Duplicate copies of the same bundle do not become separate choices.
- Jobs retain a validated copy of their version before execution. Changing or
  deleting a source bundle cannot replace the inputs of queued work or existing
  version-bound sessions. Missing active sources require a settings choice before
  new work; an older retained version is not silently substituted.

Preferences, version snapshots, and session-version bindings are stored under
`outputs/web-investors` in the assessment workspace. Keep this directory when
backing up projects/rehearsals. Snapshots consume disk space and are retained so
past sessions can resume. Do not modify retained inputs manually. Runtime outputs
continue to use the configured application output location; version-specific
rehearsal checkpoints live alongside each retained version in its runtime folder.

Older assessments without a recorded investor version stay readable and keep
legacy resume behavior. They are not reused as a verified match for new
version-bound work. Historical comparison percentiles are omitted for new
versions because the existing historical score files do not identify their
version.

Settings is workspace-wide in this local, single-user application; it is not a
per-account access-control system.

## Syncing an existing LangGraph workspace

The assessment workspace owns the runtime inputs. Copying the frontend does not
copy the retrieval indexes. Use the scoped migration tool to restore the six
legacy investors from an existing LangGraph workspace (the source is read-only):

```bash
# Preview changes first; stop the web server before applying a migration.
uv run python scripts/migrate_legacy_investors.py \
  --source ../vc-digital-twins/langgraph-vc-clone-framework \
  --target ../vclogic-vc-agentic-assessment

# Copy and validate the runtime assets.
uv run python scripts/migrate_legacy_investors.py \
  --source ../vc-digital-twins/langgraph-vc-clone-framework \
  --target ../vclogic-vc-agentic-assessment --apply
```

The migration preserves unrelated investors, including onboarded versions. It
validates the copied inputs and keeps backups of replaced assets and settings.
Existing assessment/version snapshots remain untouched. Backups and a per-file
migration report are saved under `outputs/legacy-investor-migrations` in the
assessment workspace. Run migrations while the application is stopped; the
script checks for changed settings but does not share a transaction lock with
running application processes.

## Automatic investor portraits

The six existing attributed portraits remain bundled with the frontend. For other
investors, opening a page that displays their portrait automatically resolves a
matching investor profile on The Pitch and downloads the image to
`outputs/web-investors/portraits` in the assessment workspace. This requires
outbound HTTPS access to `www.thepitch.show` and `cdn.sanity.io`, but does not
require a frontend rebuild or model-provider call.

The lookup uses the investor's source URL when available, otherwise their name
in The Pitch's investor directory. Ambiguous matches are left unresolved. Images
are cached locally with source attribution; failed lookups are cached for one
hour. If a portrait is unavailable, the portrait component displays initials and
the investor remains usable. Portrait downloads have host, format, size, and time
limits and do not run during the investor-list request.

## Investor dossier evidence

Runtime indexes make an investor executable; they do not contain the historical
assessments used by the gallery's recurring rationales and the dossier's Decision
Signature. To restore those views from an existing LangGraph workspace:

```bash
uv run python scripts/sync_investor_dossiers.py \
  --source ../vc-digital-twins/langgraph-vc-clone-framework \
  --target ../vclogic-vc-agentic-assessment --apply
```

Omit `--apply` to preview. The tool requires matching source and destination
investor fingerprints and exports exact reference investigations with provenance
and hashes. Existing differing or corrupt exports are backed up before replacement.
The compact files live in `outputs/web-investors/profile-evidence/<slug>/<version>.json`.
The application picks up new or repaired exports without restarting; reload the
dossier page. Selecting another version does not reuse the previous version's data.

These datasets restore descriptive historical profiles, not calibrated predictions
for the active version. Historical executions may have used different inputs; the
exports preserve that limitation. New investors without a historical dataset still
show their full Investment Memory, with an explicit explanation in the Decision
Signature. No historical assessments are invented from wiki excerpts. Onboarded
profiles may fill blank firm/structured role fields from matching declared source
metadata, while explicit registry values and signed inputs remain unchanged.

## Investor configuration specifications

Use **Settings → Investors → View selected version specifications**, or
**View investor specifications** inside a dossier. The read-only page shows the
selected version's identity, declared check tiers, complete configured taxonomy,
capabilities, model/budget defaults, embeddings, retrieval, and rehearsal policy.
Assessment and rehearsal configurations are shown separately. Disabled investors
and incomplete versions can be inspected without activating them.

These are prepared defaults. Live jobs bind their own paths and identities;
rehearsal depth can reduce the question ceiling, and classifier availability is
resolved at execution. Viewing specifications does not create a snapshot, run a
provider, or change settings. Credential values and provider endpoint URLs are
omitted. Source files are checked against the version's recorded hashes before
being displayed. Regenerate prepared bundles through onboarding to change their
configuration, then select the intended ready version in Settings.

## Development and verification

Run backend and frontend checks from this repository:

```bash
uv run --extra dev pytest -q
cd web/frontend
npm test -- --run
npm run build
```

For frontend development, run the API on its default port `8000`, then run `npm run dev` in `web/frontend`. Vite proxies `/api` to `http://127.0.0.1:8000`; adjust `vite.config.ts` if using another backend port.

Browser smoke tests use Playwright with the Chrome channel. With Chrome installed and the frontend built:

```bash
cd web/frontend
npm run test:e2e -- --grep "brand lockup|gallery is portrait|active rehearsal|specifications"
```

Playwright starts or reuses an API at `127.0.0.1:8766` using the sibling assessment workspace. Backend integration tests use the sibling workspace too; set `VCLOGIC_PIPELINE_WORKSPACE` to override it for those tests. Historical session tests skip when archived canary outputs are absent. Tests using mocked providers do not validate real provider credentials or model quality.

After Python changes, restart the application. After frontend changes, rebuild `web/frontend` and refresh the browser.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `Address already in use` | Choose another port with `--port`, or stop the existing application you intend to replace. |
| Cannot load rehearsal configuration | Check the complete `--pipeline-workspace` path and that the selected config exists beneath it. Do not split a path across shell lines. |
| `compiled frontend not found` | Run `npm ci` and `npm run build` in `web/frontend`, then launch from the repository root. |
| Investors missing or unavailable | Check **Settings → Investors**, bundle roots, enabled state, selected version, and index readiness. Run the legacy migration if needed. |
| Dossier has no historical Decision Signature | Restore matching historical dossier evidence; runtime indexes alone do not provide it. New investors may legitimately have no historical dataset. |
| Portrait displays initials | Check access to The Pitch and its image CDN. Failed lookups are cached for one hour. |
| Live assessment fails | Check engine configuration, provider credentials, and embedding/index availability. |

## Repository guide

| Path | Purpose |
| --- | --- |
| `src/vclogic_web/` | FastAPI routes, jobs, investor catalog, version binding, and presentation services. |
| `web/frontend/` | React application, frontend tests, and browser checks. |
| `tests/web/` | Backend API and service tests. |
| `scripts/` | Scoped legacy migration, dossier export, and portrait utilities. |
| `docs/` | Extraction notes, product reference, and implementation records. |

The engine owns execution and investor data; this repository owns the web interface and API integration. Runtime artifacts live in the configured assessment workspace. Back up its project/session outputs together with `outputs/web-investors` to preserve settings, retained versions, and dossier evidence. Secrets, dependencies, build products, and runtime outputs are excluded from Git.

Further context: [extraction notes](docs/EXTRACTION.md), [historical web reference](docs/WEB_REFERENCE.md), [product notes](PRODUCT.md), and [design notes](DESIGN.md). This application was extracted from `vc-digital-twins/langgraph-vc-clone-framework`.
