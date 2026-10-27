# Proposed integration (unapplied)

Patch: `tolerant_marked_scale_candidate.patch`

SHA-256: `dd8fe119894bdb5aec643bf0a1d9f488ce56372d36ccfa7a60f682f26e3dd713`

## Scope

The follow-up patch changes only the already-applied parser region in current `serve.py`:

1. accepts either comma or whitespace before terminal `scale <supported-size>`;
2. expands the ambiguity guard so earlier no-comma supported markers are rejected;
3. rejects semicolon/colon pseudo-delimiters;
4. adds the required 30 August 2026 project-decision comment and retains the Python `re` reference.

It does not reapply the previous integration. It does not change `index.html`, voice routing, `/api/converse`, assignment fields, target values, generation stripping, cache behavior, relations, movement, dependencies, or Qwen behavior.

## Verification

| Check | Result |
|---|---|
| patch size | 46 lines, one production file |
| `git apply --check` against current tree | pass |
| isolated-copy apply | pass |
| patched `serve.py` compile | pass |
| isolated `git diff --check` | pass |
| unchanged browser module syntax | pass |
| isolated result equals proposed copy | pass |
| proposed parser vs assignment-route cases | 110/110 pass |
| strict comma compatibility | pass |
| no-comma tolerance | pass |
| `scaled` alias remains neutral | pass |
| browser/voice file byte-identical | pass |
| Qwen scale calls added | 0 |

Evidence: `raw/patch_verification.txt` and `raw/proposed_integration_results.json`.

The patch was not applied to production.
