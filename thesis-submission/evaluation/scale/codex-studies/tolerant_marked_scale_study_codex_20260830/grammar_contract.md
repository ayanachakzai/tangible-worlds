# Tolerant marked-scale grammar contract

## Selected Candidate A

The existing terminal `scale` marker remains mandatory; only the comma becomes optional:

```text
<non-empty meaning> [,] scale <supported-size>
```

Supported terminal size words remain exactly `tiny`, `miniature`, `small`, `big`, `large`, and `huge`. Matching is case-insensitive, permits extra whitespace, and accepts terminal `.`, `!`, or `?`. The marker must be at the end. Internal commas and unrestricted creative meanings are preserved.

| Word | Intent | Target |
|---|---|---:|
| `tiny`, `miniature` | `very_small` | 0.35 |
| `small` | `small` | 0.65 |
| no accepted marker | `neutral` | 1.00 |
| `big`, `large` | `large` | 1.80 |
| `huge` | `very_large` | 3.00 |

## Explicit exclusions

- `scaled <size>` is not accepted. It is too easily an ordinary past-participle description.
- `scaling`, `scales`, `scale it`, `make it`, synonyms, comparatives, and `very large` are not added.
- `scale model`, `large scale map`, `small-scale model`, `scaled replica`, and `scaled model` remain semantic content.
- A non-terminal marker remains content: `a car scale tiny, with red paint` is neutral.
- Multiple or conflicting supported control-looking fragments are neutral; the parser never selects the last one.
- A semicolon or colon before the marker is not treated as the optional delimiter.

The exact terminal `scale <supported-size>` phrase is reserved control syntax whether or not a comma is present. This is the marked-language boundary that prevents a return to unmarked noun/adjective inference.

## Voice boundary

The current outer voice grammar remains `object <id> is <meaning>`. Candidate A is parsed server-side after typed and voice routes converge at `/api/assign`. `object four is a car scale tiny` therefore works, while `object four is a car scaled tiny` safely stays neutral. Atmosphere commands remain outside assignment routing.

No Qwen call, semantic noun scale, dependency, second question, or new voice grammar is introduced.
