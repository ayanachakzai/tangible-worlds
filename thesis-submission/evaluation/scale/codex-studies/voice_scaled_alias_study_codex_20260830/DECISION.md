# Decision

**Reserve terminal `scaled <size>` as a voice-only scale-control alias and qualify it.** [READ][RAN]

The alias is qualified as reserved project grammar, not as an accurate classifier of unrestricted English. It runs only after an accepted transcript has matched the existing `object <id> is <meaning>` voice-assignment route. It rewrites the exact terminal words to the already-qualified `scale <size>` control before `/api/assign`; the generic server parser and typed route remain unchanged.

The 104-case holdout produced 24 TP, 12 FP, 0 FN, and 68 TN against unrestricted human semantic intent: 66.7% precision and 100% recall. The 12 false positives prove that no deterministic text rule can distinguish the observed STT substitution from a literal voice description with the same ending. Under the explicitly reserved voice grammar, all 36 reserved aliases and all 68 non-aliases were exact: 100% precision and recall.

**Limitation:** voice meanings literally ending in `scaled <tiny|miniature|small|big|large|huge>` are reserved control syntax and must be rephrased.

The candidate solves the repeated real transcript failure, protects typed `a car scaled tiny`, preserves atmosphere and confirmation routing, and hits the existing `a-car.glb` cache with zero generator calls in the isolated regression. Production remains unchanged; the one-file patch is unapplied.

Exactly one next production action: after Ayan approves this reserved grammar, apply `voice_scaled_alias_candidate.patch` once to the current working tree.
