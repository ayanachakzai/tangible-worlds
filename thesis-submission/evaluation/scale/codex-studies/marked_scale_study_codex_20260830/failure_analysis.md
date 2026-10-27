# Failure analysis

## Observed classification failures

None on the preregistered holdout. Grammar A and B each produced zero false positives, zero false negatives, and zero exact-record mismatches. All 20 malformed/multiple/conflicting/synonym cases per candidate used the preregistered neutral fallback. [RAN]

## Why this differs from unmarked adjective parsing

The previous leading-adjective parser silently reinterpreted ordinary meanings including `Big Ben`, `small talk`, `large language model`, and `miniature painting`. The marked candidates require a reserved terminal control phrase, so those meanings are no longer scale candidates. The parser also rejects multiple markers instead of letting the final word win.

## Remaining failure surfaces

- The comma is contractual. If Moonshine does not emit the comma after a spoken pause, the assignment remains neutral. This is a visible, safe false negative rather than a semantic rewrite, but acoustic recall is not established here.
- The exact terminal suffix is reserved. Literal content ending exactly `, scale tiny` cannot be distinguished from control without an escape mechanism.
- The holdout is adversarial and project-specific, not a universal-language proof.
- `0.35` through `3.00` are visual design values; perceived size still depends on mesh shape, placement, display, and occlusion.
- The proposed code was tested in isolation. It was deliberately not exercised against live production runtime JSON or participant hardware.

Grammar B's natural phrase `make it` overlaps the existing atmosphere idiom more strongly even though the outer assignment route prevents measured errors. This is one reason Grammar A is more defensible when both score equally.
