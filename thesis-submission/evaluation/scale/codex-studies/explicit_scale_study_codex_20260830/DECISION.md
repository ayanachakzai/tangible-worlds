# Decision

## Selected outcome

**Explicit-size concept is good but current parser/contract does not qualify yet.**

This is exactly the second permitted outcome.

## Basis

The technically deterministic parts passed:

- typed and current voice assignment converge on an identical cached contract;
- normal atmosphere language remains outside the assignment route;
- the original phrase and stripped generation meaning can coexist cleanly;
- stripping the recognised scale adjective avoids double encoding in generation and renderer size;
- 0.35, 0.65, 1.00, 1.80, and 3.00 apply exactly to castle, car, and umbrella GLBs;
- grounding, JSON persistence, browser reload reconstruction, and movement independence passed in isolation;
- Qwen is unnecessary for scale interpretation.

The natural-language detection layer failed the safety standard. The best of two designs achieved 24/33 precision (72.7%) and 24/36 recall (66.7%). Nine neutral phrases were silently reinterpreted as explicit scale, including `Big Ben`, `large language model`, `small talk`, `miniature painting`, and local component descriptions. Those failures would change both the generated asset phrase and renderer target.

Regular expressions cannot distinguish those meanings without semantic inference. Adding noun exceptions would be brittle; asking Qwen would reopen a rejected architecture. The current parser therefore must not be integrated.

## Qualified design decisions retained for a future mechanism

- Five intents and targets remain: `very_small=0.35`, `small=0.65`, `neutral=1.00`, `large=1.80`, `very_large=3.00`.
- Supported vocabulary remains the candidate set: `tiny`, `miniature`, `small`, `big`, `large`, `huge`.
- If a future explicit syntax detects one of them, strip only that scale token from `generation_meaning` and preserve the original phrase in `meaning`.
- Cache `explicit_scale_intent`, `target_size`, and `scale_source` once at assignment.
- Movement changes position only.
- Qwen does not control scale.

## Exactly one next action

Prototype and fresh-holdout-test one marked, single-utterance grammar such as `object two is a castle, scale tiny` (typed equivalent: `castle, scale tiny`) before making any production change. The explicit `scale` marker is intended to preserve open vocabulary while avoiding the semantic collisions found here; it was not evaluated in this run and is not yet a production recommendation.
