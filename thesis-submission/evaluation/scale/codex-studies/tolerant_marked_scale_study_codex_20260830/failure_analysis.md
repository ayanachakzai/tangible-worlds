# Failure analysis

## Candidate A

Candidate A had no classification failure on its 120-case grammar oracle: 0 false positives and 0 false negatives. Exact scale intent and generation meaning were both 120/120. It retained the strict comma form and accepted the natural no-comma form. [RAN]

Its deliberate usability limit is the observed Moonshine string `a car scaled tiny`: the assignment is preserved unchanged and remains neutral. Across the broader 48 intended marker-or-transcript variants, Candidate A covers 75% because it rejects all 12 `scaled` aliases. This is a safe failure, but it means the STT variant still requires a corrected/retried transcript.

## Candidate B

Candidate B had 48 TP, 6 FP, 0 FN, and 66 TN: 88.9% precision and 100% recall. Exact intent and generation-meaning accuracy were 95%. Its six false positives were:

1. `a VFX asset already scaled tiny`
2. `a forced-perspective castle scaled small`
3. `a source mesh uniformly scaled big`
4. `a background house intentionally scaled large`
5. `a toy car prop scaled miniature`
6. `a bridge proxy scaled huge`

These are ordinary descriptive uses of the past participle `scaled`, especially plausible in creative/VFX language. Candidate B cannot know whether `scaled tiny` came from Moonshine mishearing the explicit marker or was intentionally authored semantic content. It would strip those words and change renderer scale, recreating the silent-rewrite failure class that rejected unmarked adjective parsing. B therefore does not qualify.

## Residual boundary

Candidate A reserves exact terminal `scale <size>` as control. Literal content needing those final words must be rephrased. This is an explicit grammar contract, not inferred semantics. The study tests transcript strings, not acoustic STT accuracy or participant learnability.
