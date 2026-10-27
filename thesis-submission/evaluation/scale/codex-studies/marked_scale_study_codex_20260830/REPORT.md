# Tangible Worlds marked single-utterance scale qualification

Study date: 30 August 2026.

## Final decision

**Grammar A qualifies for production.** [READ][RAN]

Selected form: `castle, scale tiny` / `object two is a castle, scale tiny`.

Both marked candidates technically qualified on the same fresh holdout. Grammar A is selected because the shorter word `scale` explicitly names the controlled dimension and is less confusable with the project's ordinary `make it ...` atmosphere idiom. There is one decision and one proposed patch; Grammar B is not left open.

## Frozen grammar

```text
<meaning>, scale <tiny|miniature|small|big|large|huge>
```

| Words | Intent | Renderer target |
|---|---|---:|
| `tiny`, `miniature` | `very_small` | 0.35 |
| `small` | `small` | 0.65 |
| no accepted marker | `neutral` | 1.00 |
| `big`, `large` | `large` | 1.80 |
| `huge` | `very_large` | 3.00 |

The suffix is case-insensitive, terminal, and tolerant of spacing and terminal punctuation. The comma is required. Unsupported or ambiguous wording preserves the entire original meaning and receives neutral 1.00. Qwen does not detect or select scale.

## Fresh 90-case holdout

The oracle was frozen before parser code and includes valid A/B syntax, all five intents, numeric/word IDs, typed/voice forms, articles, case/whitespace/punctuation, complex meanings and internal commas, Big Ben, semantic `scale`/`make it` uses, malformed/multiple/conflicting markers, synonyms, bare assignments, and atmosphere commands. [RAN]

| Grammar | TP | FP | FN | TN | Precision | Recall | Exact intent | Exact records |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A: `, scale tiny` | 20 | 0 | 0 | 70 | 100% | 100% | 100% | 90/90 |
| B: `, make it tiny` | 20 | 0 | 0 | 70 | 100% | 100% | 100% | 90/90 |

There were no semantic false positives. Each candidate safely handled all 20 malformed, multiple/conflicting, and unsupported-synonym cases. All 10 normal atmosphere commands remained outside assignment routing for both candidates. [RAN]

## Typed/voice parity

All three requested pairs passed the shared semantic assignment contract: route, object key, intent, target, source, detection state, and subject identity agreed. [RAN]

- A: typed `castle, scale tiny` and voice `object two is a castle, scale tiny` -> `very_small`, 0.35.
- B: typed `castle, make it huge` and voice `object two is a castle, make it huge` -> `very_large`, 3.00.
- Bare: typed `castle` and voice `object two is a castle` -> `neutral`, 1.00.

The supplied voice strings contain an article (`a`) that the typed strings do not. The contract correctly preserves that participant wording, so the original/generation strings are not byte-identical; the scale contract and subject identity are. The live voice parsing/routing block is byte-identical in the isolated patched copy.

## Generation semantics

Castle, toy car, mushroom, bridge, and house passed under both grammars: 10/10 checks removed only the terminal control suffix from `generation_meaning` and separately preserved the original phrase. [RAN]

For selected Grammar A, the isolated proposed cache check stored `meaning = "castle, scale tiny"`, used `generation_meaning = "castle"`, hit `castle.glb`, preserved target 0.35, and completed the existing status update. Relations and rotation caching also use stripped meaning with backward-compatible fallback. Qwen remains available for the existing shape rewriter, but it receives the stripped meaning and performs no scale inference.

## Persistence, renderer, and movement

The isolated assignment survived JSON write/read with target 0.35, original meaning, stripped generation meaning, and source intact. Twenty position updates left the assignment unchanged and generation count at one. [RAN]

The unapplied browser patch passes cached `target_size` into the existing longest-dimension normalizer; old records fall back to neutral 1.00. The current movement branch continues updating only the existing group's position, so scale persists and movement does not reload or regenerate. Renderer mechanics themselves were already qualified across real castle, car, and irregular umbrella GLBs in the immediately preceding study; this run did not duplicate production generation or modify the renderer.

## Unapplied production patch

`marked_scale_candidate.patch` is a minimal current-tree diff for `serve.py` and `index.html`. It preserves the current voice assignment route, `/api/converse`, generation caching, movement behavior, relations, rotation, labels, and existing references/style; it adds no dependency. [READ][RAN]

| Verification | Result |
|---|---|
| Python study scripts compile | pass |
| patched `serve.py` compiles | pass |
| patched module JavaScript parses | pass |
| `git apply --check` against untouched current tree | pass |
| isolated-copy patch apply | pass |
| isolated result equals proposed tree | pass |
| proposed parser assignment cases | 80/80 pass |
| production protected hashes | all 33 match before/after |

No protected production file, runtime JSON, voice file, or authoritative doc changed; no commit or push occurred.

## Limits

- This qualifies deterministic transcript parsing, not Moonshine acoustic recognition. If a spoken pause is transcribed without the contractual comma, scale safely remains neutral. A small selected-phrase voice regression is required after approval.
- The exact terminal phrase is reserved control syntax; literal content ending with it requires rephrasing.
- The holdout is project-specific, and the numeric targets remain visual design values rather than physical units.
- The patch is verified but unapplied, as required.

## Exactly one next production action

After Ayan approves this decision, apply `marked_scale_candidate.patch` once to the current working tree.
