# Method

Study date: 30 August 2026.

## Boundary and safety

[READ] Production working-tree files were treated as authoritative, including the uncommitted live-verified voice assignment route in `index.html`. All writes were confined to `explicit_scale_study_codex_20260830/`. No runtime JSON, production code, model setting, package, service, commit, or remote was changed.

[RAN] SHA-256 hashes and Git status were captured before study creation. Final hashes are compared separately.

## Pass 1 — current path audit

[READ] Typed assignment posts `{object_key, meaning}` to `/api/assign`. The live voice route parses `object <id> is <meaning>` and posts the same body to the same endpoint; non-assignment speech still calls `/api/converse`.

[READ] `/api/assign` stores one record in `assignments.json`, then invokes the existing local/fake/pod generation path. Generated meshes are cached by a meaning-derived slug. The browser polls assignments and loads a ready GLB through `loadGeneratedMesh` and `normalizeAndAddModel`. Movement polling updates the existing group's x/z position and does not call generation.

[READ] The smallest potential insertion points are therefore server-side parsing in `/api/assign`, generation use of a separate `generation_meaning`, and renderer use of cached `target_size`. The voice parser itself should not change.

## Pass 2 — two frozen parser designs

[RAN] Froze `parser_contract.md`, `holdout_cases.json`, and both implementations before the holdout run.

- D1 recognises the first vocabulary token anywhere.
- D2 recognises one leading vocabulary token, optionally after `a`/`an`.

No third parser was created. Neither implementation contains a noun rule, exception list, external dependency, or Qwen call.

## Pass 3 — assignment contract

[RAN] Built and serialised the minimal record in `assignment_contract.md`: original `meaning`, separate `generation_meaning`, `explicit_scale_intent`, `target_size`, and `scale_source`, alongside existing status/rotation/mesh fields.

[RAN] A saved assignment fixture survived JSON write/read with `target_size=0.35` and `scale_source=participant_explicit` unchanged.

## Pass 4 — generation semantics

[RAN] Reused the exact current production `SHAPE_SYSTEM_PROMPT` for five A/B comparisons. Candidate A retained the explicit scale adjective in every shaped generation prompt. Candidate B removed only the scale token. No prompt was tuned and no new asset generation was required.

## Pass 5 — renderer mechanics

[RAN] Created an isolated Three.js page using existing castle, car, and irregular umbrella GLBs. Each asset was loaded once and cloned at 0.35, 0.65, 1.00, 1.80, and 3.00. Browser measurements checked longest-dimension target, ground contact, 10-unit-plane boundedness, and invariance under parent movement.

[RAN] All 15 instances matched their target within 1e-5, grounded at y=0 within 1e-5, stayed inside the corrected gallery bounds, and retained scale through parent movement. One browser reload reproduced the castle result. Screenshots are under `output/playwright/`.

## Pass 6 — typed/voice parity

[RAN] Reproduced the current voice grammar in isolation. Typed `{object_key: 2, meaning: "a tiny castle"}` and transcript `object two is a tiny castle` produced identical cached contracts. `make it foggy` did not match assignment grammar.

[RAN] A movement simulation applied 20 positions after one assignment and retained exactly one generation call and the same target size.

## Pass 7 — fresh adversarial holdout

[RAN] The frozen holdout contains 60 phrases: 24 supported leading forms, 12 real but intentionally unsupported explicit forms, and 24 neutral/adversarial forms. It covers articles, casing, punctuation, whitespace, synonyms, comparatives, trailing language, proper names, lexicalized uses, component descriptions, and prefix collisions.

[RAN] Precision and recall treat any non-neutral ground-truth phrase as positive. False positives are neutral phrases that the parser silently scales; false negatives are explicit scale phrases it conservatively leaves neutral.

## Pass 8 — patch gate

[READ][RAN] The mechanism did not qualify because D2 precision was 72.7% with nine high-impact false positives. Under the brief's gate, no `PROPOSED_INTEGRATION.md` and no production patch were created. Consequently `git apply --check` and isolated patch application were not applicable.

## Pass 9 — decision

[READ][RAN] Selected exactly: **explicit-size concept is good but current parser/contract does not qualify yet**. The contract and renderer mechanics are viable; the blocker is semantic ambiguity in unmarked natural-language adjectives.
