# Restore complete investor dossiers

**Scope:** Correct the missing VC dossier content reported by the user. Preserve version-specific execution and restore descriptive historical model evidence from the source project.

## Findings

- CatalogProfiles disabled historical evidence for all ready versions, removing recurring rationale summaries and graphs.
- Canonical historical outputs were not migrated with runtime indexes. Six original graphs have 35–42 rationales and 80 displayed edges each.
- All 12 chapters for each legacy VC are present and match source. Mac has 14 complete chapters but no historical assessment dataset in the source project.
- Mac's bundle registry omits firm metadata that exists in its declared source profile.

## Implementation and verification

- [x] Export six compact reference-history datasets after source/target runtime fingerprint comparison; preserve exact source payloads and provenance.
- [x] Bind imported evidence to slug/version, validate payload integrity, invalidate profile caches when imports change, and suppress unbound history for unready profiles too.
- [x] Restore gallery recurrence and Decision Signature through the original aggregation code.
- [x] Explain missing/invalid/imported reference history in the UI without implying calibrated current-model performance.
- [x] Fill blank identity metadata from matching declared bundle source records without mutating signed inputs.
- [x] Run full backend/frontend tests, production build, exact source graph parity checks, and live browser dossier checks.

## Provenance and review

Imported 301 reference assessments: Charles86, Cyan21, Elizabeth53, Jesse27, Jillian59, Phil55. 283 historical run manifest hashes differ from their current manifests; 18 match. Current source/target input equality authorizes attaching the source project's descriptive record, not a claim that historical runs used today's inputs. The UI and export metadata state this limitation. Assessment calibration and historical score reuse remain unchanged.

Read-only review identified corrupt-export recovery and unready-profile unbound-history fallback. Both fixed with regression coverage. No model providers called and no assessment results fabricated.


## Final verification

- Backend: 155 passed; 3 archived-canary checks skipped.
- Frontend: 97 passed across 25 files; production build passed with the existing chunk-size advisory.
- Browser: 12 passed, 4 viewport-specific checks skipped. Desktop/mobile dossier, gallery, brand, settings, and rehearsal checks pass.
- Live API equality against the original source: all six legacy VCs match exact graph node/edge payloads, chapter payloads, and positive/negative/unresolved recurrence counts. Rationale counts: Charles42, Cyan35, Elizabeth39, Jesse40, Jillian41, Phil36; 80 displayed edges each.
- Live browser confirms Charles's complete 42-rationale inventory, zero mobile horizontal overflow, and Mac's 14 chapters plus RareBreed Ventures identity. Screenshots inspected at `/tmp/vclogic-restored-charles-desktop.png` and `/tmp/vclogic-restored-charles-mobile.png`.
- The added historical-evidence note initially exceeded the existing desktop page-height contract by four pixels. Shortened the note while retaining its reference/calibration distinction; existing browser assertions now pass unchanged.
- Existing user server processes were preserved. Restart the running application once to load the new Python dossier reader; subsequent sidecar imports refresh by file signature.
