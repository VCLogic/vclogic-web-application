# Repository extraction — 2026-09-15

Source: the working files in `/home/dpasch01/vc-digital-twins/langgraph-vc-clone-framework`, based on commit `6cad8c570892d9362d1f2007fec9116a5566ee98` plus local changes. The source checkout was not modified.

The web/API package is now `vclogic_web`. It installs `vclogic-vc-agentic-assessment`, whose Python namespace remains `vc_clone_graph`. The explicit pipeline workspace determines data, configuration, and runtime artifact paths. Frontend assets remain relative to this application checkout.

## Verification

- API/service suite: 83 passed; 3 archived-session checks skipped because the original generated sessions are intentionally absent.
- Frontend unit suite: 89 passed.
- Frontend production build: passed (existing bundle-size advisory remains).
- Browser smoke: 6 passed across desktop/mobile for branding, gallery, and mocked active rehearsal. The complete historical visual suite was not run; some scenarios require saved project/session data.
- Source distribution and wheel builds: passed.
- Isolated installation of both wheels: API health and investor endpoints passed without editable source imports.
- Code review verified package ownership and workspace propagation, including the canonical runner fix in the pipeline.

`VCLOGIC_PIPELINE_WORKSPACE` controls the integration-test data location; the default is the sibling pipeline checkout. Live assessments were not invoked during extraction. Historical recurrence summaries are optional when no archived assessment outputs exist.
