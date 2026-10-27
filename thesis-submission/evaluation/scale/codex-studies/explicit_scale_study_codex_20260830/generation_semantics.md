# Generation adjective decision

## Decision

Choose Candidate B: remove exactly the recognised leading scale adjective from `generation_meaning`, while preserving the original phrase in `meaning` and caching its explicit scale fields.

## Evidence

[RAN] The current production `SHAPE_SYSTEM_PROMPT` was loaded verbatim from `serve.py` and used without tuning for five Candidate A/B comparisons through the existing local Qwen runtime. This was generation-shaping evidence, not Qwen scale classification.

| participant phrase | Candidate A input/output retained scale word? | Candidate B generation input |
|---|---|---|
| `tiny toy car` | yes: `one low-poly tiny toy car...` | `toy car` |
| `miniature castle` | yes: `one low-poly miniature castle...` | `castle` |
| `huge mushroom` | yes: `one low-poly huge mushroom...` | `mushroom` |
| `small house` | yes: `one low-poly small house...` | `house` |
| `large bridge` | yes: `one low-poly large bridge...` | `bridge` |

Raw request/result records are in `raw/generation_semantics/` and `generation_semantics_results.json`.

Candidate A therefore sends the scale intent into both generation and renderer normalization. Even though framing requests occupy roughly the same image fraction, tokens such as `miniature` and `huge` can influence object styling, proportions, or model-like appearance. That creates the confound the study was designed to avoid.

Candidate B keeps non-scale identity words. `tiny toy car` becomes `toy car`, not `car`. For the supported grammar, `miniature` is explicitly reserved as scale authorship; a participant who wants model identity can retain it separately, for example `tiny castle model -> castle model`. The original `miniature castle` phrase remains in assignment metadata and display.

No new image or mesh generation was needed: the production shape rewriter directly demonstrated that Candidate A propagates every tested scale token, while the renderer tests used existing GLBs to isolate scale mechanics.
