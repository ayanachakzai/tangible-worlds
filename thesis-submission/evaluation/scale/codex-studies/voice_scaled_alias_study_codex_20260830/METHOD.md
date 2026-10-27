# Method

Study date: 30 August 2026. Execution completed just after midnight local time on 31 August; the requested study name and study date are retained.

## Baseline and boundary

Before creating the study, `git status --short --branch` and SHA-256 hashes were captured for the five protected production files. The current working-tree versions of the audit, runbook, design diary, renderer, server, and prior marked/tolerant/voice-stable scale studies were inspected. Production was never edited.

The candidate boundary was preregistered from the request:

1. The accepted transcript must first match `object <id> is <meaning>`.
2. Only that voice assignment's semantic text may be considered.
3. An unambiguous standalone terminal `scaled <supported-size>` may be rewritten to `scale <same-size>`.
4. Earlier supported `scale`/`scaled` fragments and semicolon/colon boundaries fail safely.
5. Typed input never invokes the normalizer; `/api/assign` remains unchanged.

## Frozen holdout

`freeze_holdout.py` contains case construction and expected outcomes only—no candidate normalizer. Before candidate code existed, the final 104-case oracle was frozen to `holdout_cases.json`, SHA-256 `f2776d8648dc40254842abee66d5848795615d32c2835b46ba57b36ae0a39488`.

Two lexical defects were caught and corrected before candidate implementation: hyphenated `pre-scaled` was replaced with standalone `previously scaled`, and two proper-name examples were made non-terminal. The final hash above is the evaluated preregistration.

The holdout contains 24 intended STT aliases, 12 existing correct `scale` forms, 12 literal terminal semantic collisions, 10 non-terminal `scaled` meanings, 10 malformed aliases, 8 unsupported synonyms, 8 multiple/conflicting endings, 10 atmosphere/non-assignment commands, and 10 ordinary assignments. It covers all six supported size words plus word/digit/`number` IDs, articles, casing, spacing, punctuation, VFX language, proper nouns, and malformed syntax.

The oracle deliberately records both `human_intended_alias` and `reserved_grammar_alias`. This prevents the project decision from hiding semantic collisions: the same 12 records are false positives under unrestricted intent and valid controls only if the voice grammar reserves them.

## Evaluation

`candidate_normalizer.mjs` implements the isolated candidate. `run_qualification.mjs` uses the current outer voice grammar and an exact JavaScript mirror of the current server scale parser to evaluate every frozen case, typed protection, atmosphere routing, exact assignment fields, and both confusion matrices. `results.json` and `results.csv` contain the full outputs.

`verify_cache_regression.py` executes the actual current `serve.py` parser from an isolated temporary directory. Because system Python lacks `requests` and no network path is tested, that import alone is replaced with a process-local empty module; no dependency was installed. The test copies the existing 1,047,760-byte `generated_meshes/a-car.glb` into an isolated cache, invokes the actual local cache path, and fails if generation is called.

## Patch verification

Only after qualification was `voice_scaled_alias_candidate.patch` created against the current `index.html`. It changes only the voice assignment route. Verification covers:

- `node --check` on the isolated patched module script;
- `git diff --check` on the isolated current/patched comparison;
- `git apply --check` against the current working tree;
- isolated-copy application;
- 94/94 patched assignment-route normalization cases;
- the full 104/104 route and assignment contract;
- protected production hashes before/after.

No commit, push, install, runtime JSON change, production apply, clean, or restore occurred.
