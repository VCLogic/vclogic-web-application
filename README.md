# VCLogic web application

React frontend and FastAPI API for founder pitch assessment, investor comparison, and rehearsal. The assessment engine is maintained in [vclogic-vc-agentic-assessment](https://github.com/VCLogic/vclogic-vc-agentic-assessment).

## Local setup

Clone both repositories into the same parent directory:

```text
workspace/
  vclogic-vc-agentic-assessment/
  vclogic-web-application/
```

From this repository (Python 3.11–3.13, uv, and Node.js required):

```bash
uv sync --extra dev
cd web/frontend
npm ci
npm run build
cd ../..
uv run vc-clone-web --pipeline-workspace ../vclogic-vc-agentic-assessment
```

Open http://127.0.0.1:8000. Startup validates the installed investor indexes before accepting requests; with a full investor library, wait for `Application startup complete` in the terminal. The API runs locally by default. The default config is `configs/rehearsal-charles-v41-grounded.toml` inside the pipeline workspace. `--config` paths are relative to that workspace; `--static-root` paths are relative to the application checkout. Set provider keys in the environment and prepare the pipeline configuration/indexes before requesting a live assessment; see its README. For grounded semantic retrieval, install the engine's embeddings extra with `uv sync --extra dev --extra embeddings`.

The uv source override installs the sibling pipeline in editable mode. The built application wheel declares `vclogic-vc-agentic-assessment` as a dependency; deployments must supply a compatible engine wheel or configure a package source. No published package is assumed.

## Verify

```bash
uv run pytest -q
cd web/frontend
npm test -- --run
npm run build
# Smoke checks that work without archived project/session data:
npm run test:e2e -- --grep "brand lockup|gallery is portrait|active rehearsal"
```

Web integration tests read investor reference data from the sibling pipeline. Set `VCLOGIC_PIPELINE_WORKSPACE` to use another checkout. Historical session checks require their archived outputs and skip when absent.

## Ownership

- `src/vclogic_web`: API routes, jobs, presentation models, project/session services.
- `web/frontend`: React application and browser tests.
- `tests/web`: API and service checks.
- `scripts/sync_investor_portraits.py`: frontend portrait tooling.

The engine owns assessment/rehearsal execution and investor data. API jobs currently store runtime artifacts beneath the configured pipeline workspace output directory. No process-wide directory change is needed to connect the repositories. Secrets, dependencies, generated assets, and runtime outputs are excluded from Git.

Extracted from the current working files in `vc-digital-twins/langgraph-vc-clone-framework`; the original source remains intact.

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

## Network access

To listen on all network interfaces, choose an unused port and explicitly allow
remote access:

```bash
uv run --extra embeddings vc-clone-web \
  --pipeline-workspace ../vclogic-vc-agentic-assessment \
  --host 0.0.0.0 --allow-remote --port 8001
```

Open `http://<server-ip>:8001`. After changing Python code, restart the server.
After frontend changes, run `npm run build` in `web/frontend` and refresh the
browser.

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
