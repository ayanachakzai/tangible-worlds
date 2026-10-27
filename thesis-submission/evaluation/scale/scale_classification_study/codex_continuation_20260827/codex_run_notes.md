# Codex run notes

## Evidence chronology

1. [READ] Read the autonomous continuation brief and inspected the launcher only as a wrapper.
2. [READ] Audited authoritative docs, production boundaries, saved study artifacts, and the prior renderer-scale result.
3. [RAN] Captured protected SHA-256 hashes and Git status before study writes.
4. [RAN] Reproduced seven anchors: 7/7 valid, 7/7 acceptable.
5. [RAN] Froze `candidate_contracts.md`, `holdout_cases.json`, and `evaluate_candidates.py` before holdout inference.
6. [RAN] Verified 72 cases, 20 modifiers, 12 repeats, and zero exact development-phrase duplicates.
7. [RAN] Ran a development-only Candidate B schema check (`wooden chair`) before the holdout; strict JSON parsed successfully.
8. [RAN] Ran A, B, and C without changing prompts or expected labels: 96 calls each, 288 total.
9. [READ] Audited every mismatch and structured scale basis.
10. [RAN] Confirmed 288 per-call raw JSON files plus aggregate JSON/CSV.

## Frozen-result summary

- A: 72/72 valid, 43/72 acceptable, 12/20 modifiers, 12/12 repeated cases in exact agreement.
- B: 72/72 valid, 50/72 acceptable, 13/20 modifiers, 12/12 repeated cases in exact agreement.
- C: 72/72 valid, 48/72 acceptable, 13/20 modifiers, 12/12 repeated cases in exact agreement.

## Safety notes

[READ] The working tree was dirty before this run. No cleaning, commit, push, runtime-state edit, package installation, model switch, LM Studio configuration change, or process termination was performed.

[READ] No production integration was applied. No `PROPOSED_INTEGRATION.md` is produced because the brief required it only when an automatic architecture qualifies.

## Decision

[READ][RAN] Qwen semantic-scale classification does not qualify for production yet. The one recommended next action is the participant-selected cached scale-band control described in `DECISION.md`.
