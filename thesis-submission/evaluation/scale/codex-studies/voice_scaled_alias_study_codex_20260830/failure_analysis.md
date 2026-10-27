# Failure analysis

## Root production failure

Ayan's spoken `object two is a car scale tiny` repeatedly becomes `object two is a car scaled tiny`. The existing generic parser correctly treats `scaled` as semantic language, so `generation_meaning` becomes `a car scaled tiny`, the cache identity changes, and another car is generated.

The candidate repairs only the accepted voice-assignment payload:

```text
object two is a car scaled tiny
-> outer voice assignment: object 2, meaning a car scaled tiny
-> voice-only alias: a car scale tiny
-> current server parser: generation_meaning a car, target_size 0.35
```

## Unavoidable semantic collision

The candidate cannot infer whether terminal `scaled tiny` was spoken intentionally or produced by STT. All 12 preregistered literal endings are therefore false positives against unrestricted human intent, including `a VFX asset already scaled tiny`, `a source mesh uniformly scaled big`, `a toy car prop scaled miniature`, and `a background house intentionally scaled large`.

Human-intent result: 24 TP, 12 FP, 0 FN, 68 TN; 66.7% precision and 100% recall. This is unacceptable as a global or generic assignment-parser rule, and the patch does not create one.

The qualified contract instead reserves those exact terminal words only in confirmed voice `object <id> is ...` commands. Under that declared grammar boundary, the result is 36 TP, 0 FP, 0 FN, 68 TN. Literal voice meanings with the reserved ending must be rephrased. This is a deliberate expressivity tradeoff, not a claim that the ambiguity has been solved.

## Safe failures

Non-terminal `scaled` language, malformed forms, unsupported synonyms, multiple/conflicting supported controls, semicolon/colon boundaries, atmosphere commands, and non-assignment utterances are not normalized. Existing correct `scale <size>` forms pass unchanged. Typed `a car scaled tiny` never invokes the normalizer and remains semantic, neutral, and byte-for-byte unchanged at the generic parser boundary.

## Test-environment incidents

The first isolated server import failed because system Python lacks `requests`; a process-local placeholder was used because no network path is exercised. No dependency was installed. The first hand-authored patch header had an incorrect unified-diff line count; it was corrected before any apply test passed. Neither incident touched production or altered the frozen results.
