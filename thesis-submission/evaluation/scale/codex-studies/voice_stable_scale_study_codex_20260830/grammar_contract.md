# Retained voice/typed scale grammar

## Recommended grammar

Retain the current deterministic terminal marker:

```text
<meaning> [,] scale <tiny|miniature|small|big|large|huge>
```

The comma remains optional. The marker is case-insensitive, terminal, and accepts terminal `.`, `!`, or `?`. Internal meaning remains unrestricted. Exact targets remain:

| Word | Intent | Target |
|---|---|---:|
| `tiny`, `miniature` | `very_small` | 0.35 |
| `small` | `small` | 0.65 |
| no accepted marker | `neutral` | 1.00 |
| `big`, `large` | `large` | 1.80 |
| `huge` | `very_large` | 3.00 |

## Rejected alternatives

`size <value>` is rejected because terminal phrases such as `a T-shirt size small`, `a costume size large`, and `a prop label reading size tiny` are ordinary semantic content indistinguishable from the proposed marker.

`size is <value>` is rejected because phrases such as `a house whose size is tiny` and `a VFX proxy whose size is small` naturally end in the exact proposed marker.

`scaled <value>` remains rejected. It is ordinary descriptive English and previously caused six semantic false positives.

No synonyms, comparative language, noun inference, Qwen scale decision, second scale question, or dependency is added.

## Acoustic limitation

The current grammar is not voice-stable for Ayan's observed `scale tiny` pronunciation: Moonshine repeatedly returned `scaled tiny`. That transcript remains neutral and preserves the full meaning. The existing visible/spoken confirmation loop is therefore the safe recovery mechanism; it must not be silently repaired into semantic scale.
