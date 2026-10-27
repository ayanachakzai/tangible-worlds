# Method

## Baseline

The current dirty working tree—not HEAD—was authoritative. It already contained the live voice assignment route and the previously applied strict marked-scale integration. The current `PROJECT_AUDIT.md`, `RUNBOOK.md`, relevant `DESIGN_DIARY.md` history, `index.html`, `serve.py`, and both prior scale studies were read before candidate work. Production and runtime files were protected. [READ]

## Frozen holdout

`freeze_holdout.py` wrote and locked 120 cases at `2026-08-30T18:32:54+0100`. Candidate parser code was written later at `18:34:14+0100`; first result output followed at `18:34:55+0100`. Holdout SHA-256: `cc3681cea6f41879eedf8868b73c195e190feca3cce10dce70da6c57569c6c62`. [RAN]

The oracle contains 36 common comma/no-comma positives, 12 intended `scaled` transcript aliases for B, 12 bare assignments, 10 atmosphere commands, 14 semantic `scale` phrases, 12 semantic `scaled` phrases, 10 malformed markers, 8 conflicts, and 6 unsupported synonyms. It covers all six size words, five intents, typed/voice input, word/numeric IDs, case, punctuation, extra spacing, internal commas, proper nouns, and long VFX-like meanings.

Candidate-specific detection metrics measure each grammar's declared syntax. A separate cross-candidate coverage measure reports the practical tradeoff across all 48 intended marker/transcript forms: A covers 36/48 (75%), while B covers 48/48 (100%). False positives remain the qualification gate.

## Preregistration audit

The frozen scale oracle was not edited after evaluation. Five generic-constructor records retained default object key `4` despite voice text saying `five`, `six`, `eight`, or `nine`: `C07`, `D04`, `D06`, `M09`, and `S14`. Object-number routing is an already-live outer parser and is outside the requested scale comparison. Results therefore score the preregistered route, original meaning, generation meaning, intent, target, source, and explicit detection; the five object-key annotation mismatches are preserved and disclosed in `results.json`. They have no effect on TP/FP/FN/TN, intent, generation meaning, transcript cases, parity, or the decision. [RAN]

## Additional checks

- All eight required voice transcript strings were evaluated for both candidates.
- Typed/voice parity was checked for selected no-comma and backward-compatible comma syntax; the B alias was also checked diagnostically.
- The proposed server parser was executed against all 110 assignment-route cases in an isolated patched tree.
- The current browser file was copied byte-for-byte and its module JavaScript passed `node --check`; no browser change is proposed.
- The follow-up patch passed Python compile, `git diff --check`, `git apply --check`, isolated apply, and isolated/proposed comparison.

No production request, generation, runtime reset, install, commit, push, restore, or cleanup was performed.
