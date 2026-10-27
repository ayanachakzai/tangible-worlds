# Codex run notes

## Chronology

1. [READ] Read the complete 30 August qualification brief.
2. [READ] Loaded the Three.js fundamentals/loaders and Playwright instructions because the task required an isolated real-browser GLB test.
3. [RAN] Captured protected hashes and dirty-tree status before study writes.
4. [READ] Audited current typed assignment, live voice assignment, atmosphere fallback, `/api/assign`, assignment cache, generation functions, GLB normalization, and movement update paths.
5. [RAN] Froze two parser designs and a 60-case holdout before execution.
6. [RAN] Ran 120 parser records; D1 scored 64.3% precision/75.0% recall, D2 72.7%/66.7%.
7. [RAN] Compared five original/stripped meanings with the current production shape prompt; all original inputs retained their scale adjective.
8. [RAN] Confirmed typed/voice contract equality, atmosphere non-interference, one generation call across 20 moves, and JSON persistence.
9. [RAN] Served the isolated renderer on temporary port 8765 and tested castle, car, and umbrella in Playwright Chromium.
10. [RAN] Captured three screenshots, checked exact dimensions/grounding/movement/bounds, reloaded once, then closed the browser and stopped the temporary server.
11. [READ] Reviewed every false positive/negative without widening ground truth or adding exceptions.

## Decision discipline

[READ][RAN] Only two parser designs were tested. Qwen was used only through the existing generation-shaping prompt for A/B evidence, never for scale interpretation. No third parser, synonym expansion, noun exception, production patch, integration document, commit, or push was created.

## Final outcome

[READ][RAN] Explicit-size concept is good but current parser/contract does not qualify yet. The one next action is the marked single-utterance grammar holdout described in `DECISION.md`.
