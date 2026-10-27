# Marked scale grammar contract

## Selected grammar

Grammar A reserves one terminal suffix:

```text
<unrestricted non-empty meaning>, scale <modifier>
```

Voice keeps the already-live outer route:

```text
object <numeric-or-one-to-ten-id> is <meaning>, scale <modifier>
```

Typed input supplies the same meaning suffix directly. The delimiter comma, the word `scale`, one supported modifier, and end-of-meaning position are required. Matching is case-insensitive; spaces around the comma and within the marker may vary; terminal `.`, `!`, or `?` is accepted. Commas inside the preceding meaning are retained because only the terminal suffix is parsed. [RAN]

## Frozen mapping

| Modifier | Intent | Target |
|---|---|---:|
| `tiny`, `miniature` | `very_small` | 0.35 |
| `small` | `small` | 0.65 |
| no accepted suffix | `neutral` | 1.00 |
| `big`, `large` | `large` | 1.80 |
| `huge` | `very_large` | 3.00 |

These are project-tuned visual targets, not metric or universal semantic sizes.

## Safe-failure rules

- Unsupported synonyms, comparatives, malformed markers, missing commas, and non-terminal markers remain neutral and unchanged.
- Any earlier control-looking `scale ...` or `make it ...` fragment before a valid terminal marker makes the whole meaning neutral. The parser never chooses between multiple or conflicting markers.
- Ordinary phrases such as `Big Ben`, `small-scale model`, `large scale map`, `scale model`, `miniature painting`, and `a note saying make it tiny` stay neutral.
- An utterance that does not match `object <id> is <meaning>` remains outside assignment routing and continues to `/api/converse`.
- The exact reserved suffix is control syntax. A participant who literally needs those terminal words as object content must rephrase; no escape grammar is proposed.

## Boundary and limitation

The contract qualifies deterministic parsing of accepted transcripts, not Moonshine acoustic recognition. A missing transcript comma produces a safe neutral false negative (`castle scale tiny`), not a scale change. A short spoken-corpus regression of the selected phrase is therefore part of the one post-approval production regression, not evidence claimed by this study.

No Qwen call, noun inference, new dependency, second question, or follow-up menu is part of this grammar.
