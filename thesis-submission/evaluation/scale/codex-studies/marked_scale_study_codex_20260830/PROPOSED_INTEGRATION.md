# Proposed integration (unapplied)

Patch: `marked_scale_candidate.patch`

Patch SHA-256: `d9161f1bfdfd4a42445e8fad09955a97382dd65252b3900860d0073d7ece0b07`

## Minimal insertion boundary

The proposed server change adds one deterministic Grammar A parser beside the assignment store, caches five scale fields when `/api/assign` receives a new meaning, and passes the stripped `generation_meaning` through existing local/pod/cache and relation paths. `_mark()` still keys status writes against the original participant meaning. Rotation cache identity moves to the stripped generation slug. No new dependency or model call is added.

The proposed browser change passes cached `target_size` to the existing longest-dimension normalizer, falling back to locked neutral 1.00 for old records. Relation lookup uses `generation_meaning` with an old-record fallback. Labels still show the original phrase. Existing voice assignment and `/api/converse` blocks are untouched.

## Verification

| Check | Result |
|---|---|
| `git apply --check` against current working tree | pass |
| apply in isolated copied tree | pass |
| patched `serve.py` compile | pass |
| extracted module JavaScript `node --check` | pass |
| isolated applied files match proposed files | pass |
| proposed server parser vs 80 assignment-route cases | 80/80 pass |
| isolated marked assignment uses `castle.glb`, not marker slug | pass |
| original phrase/status matching preserved | pass |
| voice route byte-identical | pass |
| Qwen scale calls | 0 |

Evidence is in `raw/patch_verification.txt` and `raw/proposed_integration_results.json`.

## Deliberate non-actions

The patch was not applied. Production `index.html`, `serve.py`, tracker, mapping, conversation, voice, JSON, and docs were not edited. No commit or push was made.
