# Method

## Evidence boundary

The study read the current `PROJECT_AUDIT.md`, `RUNBOOK.md`, relevant `DESIGN_DIARY.md` scale/assignment/movement history, working-tree `index.html` and `serve.py`, and the previous explicit-scale study. The current working tree was treated as authoritative and dirty. Production files, runtime JSON, voice files, and documentation were protected. [READ]

## Preregistration

`freeze_holdout.py` created `holdout_cases.json` and refused overwrite. The 90-case oracle was written at `2026-08-30T17:51:03+0100`; `marked_scale_parser.py` was written later at `17:52:40+0100`; results followed at `17:52:45+0100`. Frozen holdout SHA-256: `d6a2a4e2dc6d6acd5a9041a989ba93a686ccbe72ac874e5d8739f34b1f658572`. [RAN]

The holdout contains 20 Grammar A positives, 20 Grammar B positives, 10 bare neutral assignments, 10 semantic collision cases, 8 malformed markers, 6 multiple/conflicting markers, 6 unsupported synonyms, and 10 atmosphere commands. It covers numeric/word IDs, articles, case, spacing, punctuation, internal commas, complex meanings, proper names, all five intents, and both input modes.

## Evaluation

Each grammar was run independently against all 90 cases. The other grammar's valid forms count as neutral because each candidate defines one exact supported syntax. Detection metrics use explicit marked scale as positive. Exact-record accuracy compares route, key, original meaning, generation meaning, intent, numeric target, source, and detection state.

Ancillary checks then tested:

1. the three requested typed/voice pairs;
2. marker stripping and original preservation for castle, toy car, mushroom, bridge, and house under both candidates;
3. JSON write/read persistence plus 20 movement updates with one generation count;
4. all atmosphere cases remaining outside assignment routing;
5. the proposed server parser against all 80 assignment-route holdout cases;
6. generation/cache separation through an isolated `castle.glb` cache fixture;
7. unchanged voice routing, renderer target wiring, and relation use of stripped meaning.

## Patch method

After both candidates qualified, Grammar A was chosen under the brief's simpler/more-defensible rule. Current production `serve.py` and `index.html` were copied under `raw/proposed_tree/`, edited there, and diffed into `marked_scale_candidate.patch`. The patch was checked against the untouched working tree, then applied under `raw/patch_apply_check/`. The isolated result compiled as Python, its extracted module JavaScript passed `node --check`, and it byte-matched the proposed tree. [RAN]

No browser generation, Qwen scale inference, production server write, commit, or push was performed.
