# Tangible Worlds tolerant marked-scale qualification

Study date: 30 August 2026.

## Final decision

**Candidate A qualifies: optional comma with explicit terminal scale.** [READ][RAN]

Selected accepted forms:

```text
a car, scale tiny
a car scale tiny
```

`a car scaled tiny` is not accepted. Candidate B's transcript alias improved coverage but failed the semantic false-positive gate.

## Fresh 120-case holdout

The holdout was frozen before parser code and covers every requested syntax, size word, input mode, voice ID form, whitespace/case/punctuation variant, semantic collision family, malformed/conflicting marker, synonym, proper noun, and atmosphere route. [RAN]

| Candidate | TP | FP | FN | TN | Precision | Recall | Exact intent | Generation meaning |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A: optional comma + terminal `scale` | 36 | 0 | 0 | 84 | 100% | 100% | 100% | 100% |
| B: A + terminal `scaled` | 48 | 6 | 0 | 66 | 88.9% | 100% | 95% | 95% |

These are grammar-specific metrics: unsupported `scaled` forms are neutral for A. Across all 48 intended explicit-marker or observed-transcript variants, A covers 36/48 (75%) and B covers 48/48 (100%). B's extra coverage is rejected because it silently rewrites six ordinary meanings.

## False positives and safe fallbacks

Candidate A had no false positives or false negatives. Bare assignments, scale-model language, `large scale map`, `small-scale`, `scaled replica`, unsupported synonyms, non-terminal markers, conflicts, and atmosphere commands remained unchanged and neutral/outside assignment as preregistered. [RAN]

Candidate B falsely detected:

- `a VFX asset already scaled tiny`
- `a forced-perspective castle scaled small`
- `a source mesh uniformly scaled big`
- `a background house intentionally scaled large`
- `a toy car prop scaled miniature`
- `a bridge proxy scaled huge`

Because `scaled` is ordinary descriptive English, there is no deterministic evidence that it came from an STT substitution. B reintroduces semantic ambiguity and does not qualify.

## Voice transcript result

All eight required transcript records matched Candidate A's preregistered result:

| Transcript | Candidate A result |
|---|---|
| `object four is a car, scale tiny` | explicit 0.35 |
| `object four is a car scale tiny` | explicit 0.35 |
| `object four is a car scaled tiny` | neutral 1.00, unchanged |
| `object 4 is a car scale tiny` | explicit 0.35 |
| `object four is a tiny scale model car` | neutral 1.00 |
| `object four is a scale model car` | neutral 1.00 |
| `object four is a large scale map` | neutral 1.00 |
| `object four is a car scaled model` | neutral 1.00 |

The no-comma Moonshine/typed form is therefore fixed by A. The observed `scaled` variant is explicitly evaluated but deliberately not tolerated; it fails safely instead of changing meaning.

## Typed/voice parity and backward compatibility

Typed `a car scale tiny` and voice `object four is a car scale tiny` produced identical semantic assignment fields and `generation_meaning = "a car"`. The existing comma pair also remained identical and produced 0.35. Candidate B's alias pair was internally consistent but rejected for safety, not parity. [RAN]

The proposed parser preserved original `meaning`, stripped only the terminal control marker, retained existing `scale_source`, intent, and target fields, and passed all 110 assignment-route cases in the isolated patched copy.

## Unapplied follow-up patch

`tolerant_marked_scale_candidate.patch` is a 46-line diff affecting only the current `serve.py` parser/comment region. It does not reapply the previous patch. `index.html`—including voice assignment, `/api/converse` routing, cached target rendering, relations, and movement—is byte-identical in the isolated tree. No dependency or Qwen scale logic is added. [READ][RAN]

| Verification | Result |
|---|---|
| Python study scripts compile | pass |
| patched server compiles | pass |
| unchanged module JavaScript parses | pass |
| isolated `git diff --check` | pass |
| `git apply --check` against current tree | pass |
| isolated patch apply | pass |
| isolated/proposed comparison | pass |
| protected before/after hashes | all 33 match |

No production file, runtime JSON, voice file, or authoritative document was modified. No commit, push, restore, clean, or install occurred.

## Preregistration note

Five frozen records contain incorrect expected outer object keys because their voice text uses word IDs other than the constructor's default `4`. The oracle was not edited after evaluation. Scale-output scoring excludes that already-live outer key field and remains 120/120 exact for A; the affected IDs and impact statement are retained in `results.json`. The eight required transcript cases and all scale decisions are unaffected.

## Exactly one next production action

After Ayan approves this decision, apply `tolerant_marked_scale_candidate.patch` once to the current working tree.
