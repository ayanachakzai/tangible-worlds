# Tangible Worlds explicit participant-authored scale qualification

Study date: 30 August 2026.

## Final decision

**Explicit-size concept is good but current parser/contract does not qualify yet.** [READ][RAN]

Renderer mechanics, caching, typed/voice parity, and generation-adjective separation all passed in isolation. The best deterministic unmarked-language parser did not: precision was 72.7% and recall was 66.7%, with nine false positives that silently changed semantics and scale. No production patch was created or applied. [RAN]

## Current paths and insertion boundary

[READ] Typed assignment and the live-verified voice grammar already converge on `/api/assign`; `make it foggy` remains routed to `/api/converse`. `/api/assign` creates the cached record and starts generation. The renderer polls that record, loads a ready mesh, normalises by longest bounding-box dimension, and later moves the existing group without regenerating.

[READ] If a future parser qualifies, the minimal locations are:

1. parse explicit syntax once inside `/api/assign`;
2. cache original `meaning`, stripped `generation_meaning`, scale intent/source, and target;
3. use `generation_meaning` for generation/cache identity;
4. pass `assignment.target_size` into the existing GLB normalisation call;
5. leave voice routing, atmosphere routing, and movement polling unchanged.

## Exact parser grammar and vocabulary

[RAN] Two designs were frozen. D1 searched anywhere for `tiny|miniature|small|big|large|huge`. D2, the stronger design, used:

```regex
^\s*(?:(a|an)\s+)?(tiny|miniature|small|big|large|huge)\s+(.+?)\s*[.!?]*\s*$
```

Exact mappings:

| supported words | intent | target |
|---|---|---:|
| `tiny`, `miniature` | `very_small` | 0.35 |
| `small` | `small` | 0.65 |
| none | `neutral` | 1.00 |
| `big`, `large` | `large` | 1.80 |
| `huge` | `very_large` | 3.00 |

Matching is case-insensitive and tolerates surrounding whitespace and terminal punctuation. `a`/`an` is preserved when the scale word is stripped: `a small red castle -> a red castle`. These numbers are project-tuned visual values, not universal or metric semantics.

## Unsupported cases

The candidate does not support synonyms (`teeny`, `puny`, `little`, `enormous`, `colossal`), comparatives (`smaller`, `bigger`, `larger`, `a little bigger`), trailing/predicative forms (`castle is huge`), hyphenated `small-scale`, or multiple/conflicting modifiers. It cannot semantically distinguish proper names, lexicalized phrases, non-physical intensifiers, or adjectives attached to local components. [READ][RAN]

## Fresh parser holdout

[RAN] The 60 preregistered cases contain 36 explicit positives and 24 neutral/adversarial negatives.

| design | TP | FP | FN | TN | precision | recall | exact intent |
|---|---:|---:|---:|---:|---:|---:|---:|
| D1 anywhere | 27 | 15 | 9 | 9 | 64.3% | 75.0% | 36/60 |
| D2 leading | 24 | 9 | 12 | 15 | 72.7% | 66.7% | 39/60 |

D2 correctly ignores later words such as `the castle has a small door`, but optional-article/leading syntax still misreads nine phrases: `tiny flag on a castle`, `Big Ben`, `big ben`, `large language model`, `small talk`, `huge fan of castles`, `miniature painting`, `a big wheel inside a clock`, and `a SMALL detail on the tower`. [RAN]

False positives are more serious than unsupported synonyms: each one changes `generation_meaning` and renderer size while appearing deterministic. No case-specific patch was added.

## Exact assignment fields

The smallest tested representation is:

```json
{
  "meaning": "a tiny castle",
  "generation_meaning": "a castle",
  "explicit_scale_intent": "very_small",
  "target_size": 0.35,
  "scale_source": "participant_explicit",
  "status": "generating",
  "rotation": {"x": 0, "y": 0, "z": 0}
}
```

Bare/unsupported language uses `neutral`, `1.00`, and `neutral_default`. Existing status, rotation, and mesh URL fields remain. Old records without a target would require a 1.00 fallback. [READ]

## Generation adjective decision

[RAN] Candidate B is the qualified semantic separation: strip only the recognised leading scale word before generation and preserve the original phrase. The existing production shape rewriter retained the scale word in all five Candidate A trials:

- `tiny toy car -> one low-poly tiny toy car...`
- `miniature castle -> one low-poly miniature castle...`
- `huge mushroom -> one low-poly huge mushroom...`
- `small house -> one low-poly small house...`
- `large bridge -> one low-poly large bridge...`

Keeping the word therefore double-encodes scale into generation and renderer normalization. Stripping preserves non-scale identity (`tiny toy car -> toy car`). Within this candidate contract, `miniature` is reserved as scale; a model identity can remain explicitly as `tiny castle model -> castle model`.

Qwen remains part of the existing shape-framing pipeline, but it is not involved in detecting, selecting, or numerically controlling scale.

## Typed/voice parity

[RAN] Typed object 2 with `a tiny castle` and voice transcript `object two is a tiny castle` resolved to the same five scale/meaning fields. `make it foggy` did not match assignment grammar. This confirms that server-side parsing would preserve the live voice fix and atmosphere route without a second question or spoken menu.

## Renderer, persistence, and movement

[RAN] Real-browser tests loaded castle, car, and irregular umbrella GLBs. Each was cloned at all five targets. All 15 measured longest dimensions exactly matched the target (within 1e-5), grounded at y=0 (within 1e-5), and stayed inside the corrected 10-unit gallery. Parent movement did not change scale or trigger another asset load/normalization. One browser reload reproduced the castle mechanics.

[RAN] The cached assignment fixture preserved target 0.35 and `participant_explicit` after JSON write/read. Twenty simulated movement updates followed one assignment and left the generation-call count at one.

Screenshots: [castle](output/playwright/castle.png), [car](output/playwright/car.png), and [umbrella](output/playwright/umbrella.png).

## Visual limitations

- Longest-dimension normalization does not equalize footprint, mass, or perceived size; the three screenshots make this shape dependency visible.
- A 3.00 object fits the 10-unit plane in the tested bounded placement but can still overhang if a participant moves it near an edge.
- A 0.35 object is visibly ordered in these screenshots but may be hard to inspect on different displays or with low-detail generated geometry.
- Arbitrary participant overlap can occlude any size.
- These are technical/visual checks, not human-subject validation.

## Dissertation explainability

[READ][RAN] The five-value scale mapping, cached assignment fields, adjective stripping, and movement rule are simple enough to explain. The unmarked English parser is not defensible as a reliable open-vocabulary mechanism because its apparent simplicity hides semantic collisions. Claiming that “leading `big` means scale” would incorrectly rewrite legitimate participant meanings.

## Limitations

- The holdout is deliberately adversarial and project-specific; it does not measure universal English.
- Renderer tests used three existing GLBs, not all future generated shapes.
- Persistence/movement were tested in isolated copies and simulations, not by modifying production.
- No STT/TTS model or real physical tracker was altered or requalified.
- No participant study was run.
- Unsupported synonyms must not be claimed to work.

## Exactly one next action

Prototype and fresh-holdout-test a marked one-utterance grammar such as `object two is a castle, scale tiny` before any production integration. It keeps typed/voice parity and avoids a second question, while making scale authorship syntactically explicit. This new grammar was not tested here and must not be treated as qualified yet.
