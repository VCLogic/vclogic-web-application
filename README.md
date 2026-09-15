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

Open http://127.0.0.1:8000. The API runs locally by default. The default config is `configs/rehearsal-charles-v41-grounded.toml` inside the pipeline workspace. `--config` paths are relative to that workspace; `--static-root` paths are relative to the application checkout. Set provider keys in the environment and prepare the pipeline configuration/indexes before requesting a live assessment; see its README. For grounded semantic retrieval, install the engine's embeddings extra with `uv sync --extra dev --extra embeddings`.

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
