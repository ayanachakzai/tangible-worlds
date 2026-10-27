# Frozen parser contract

Frozen before the fresh holdout run on 30 August 2026.

## Shared vocabulary and project-tuned targets

| leading token | intent | renderer target |
|---|---|---:|
| `tiny`, `miniature` | `very_small` | 0.35 |
| `small` | `small` | 0.65 |
| none recognised | `neutral` | 1.00 |
| `big`, `large` | `large` | 1.80 |
| `huge` | `very_large` | 3.00 |

These numeric values are project tuning from the previously accepted same-mesh visual progression. They are not metric or universal scale semantics.

Matching is case-insensitive. Leading/trailing whitespace and terminal `.`, `!`, or `?` do not affect detection. A detected modifier is removed from `generation_meaning`; the exact received phrase remains in `participant_phrase`.

## Design 1 — anywhere-token baseline

Recognise the first vocabulary word anywhere in the phrase:

```regex
\b(tiny|miniature|small|big|large|huge)\b
```

This design is expected to have higher recall but to misread component descriptions such as `the castle has a small door`.

## Design 2 — leading modifier candidate

Recognise exactly one vocabulary word only at the start, optionally after `a` or `an`:

```regex
^\s*(?:(a|an)\s+)?(tiny|miniature|small|big|large|huge)\s+(.+?)\s*[.!?]*\s*$
```

The article is preserved in `generation_meaning`; the size word is removed:

```text
a tiny red castle -> a red castle
huge mountain -> mountain
```

`the` is intentionally not an optional article. This leaves `the Big Ben` as a neutral escape form and keeps the grammar smaller.

## Explicitly unsupported in v1

- synonyms such as `teeny`, `puny`, `little`, `enormous`, and `colossal`
- comparative/morphological forms such as `smaller`, `bigger`, `larger`, `somewhat larger`, and `a little bigger`
- trailing or predicative scale language such as `castle is huge` or `castle, tiny`
- hyphenated `small-scale` / `large-scale`
- multiple or conflicting leading scale words
- semantic disambiguation of proper names or lexicalized phrases such as `Big Ben`, `small talk`, `miniature painting`, and `large language model`
- deciding whether an adjective applies to a local component rather than the whole generated phrase

The parser contains no noun list, no noun-specific exception, no Qwen call, and no external dependency.
