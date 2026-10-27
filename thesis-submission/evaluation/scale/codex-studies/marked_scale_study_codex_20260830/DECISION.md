# Decision

**Grammar A qualifies for production.** [READ][RAN]

Selected syntax:

```text
<meaning>, scale <tiny|miniature|small|big|large|huge>
```

Grammar A and Grammar B each achieved 20 TP, 0 FP, 0 FN, and 70 TN on the same preregistered 90-case holdout: 100% precision, 100% recall, and 100% exact intent accuracy. Grammar A is selected because `scale` explicitly names the control dimension, is shorter than `make it`, and is easier to distinguish from an ordinary scene imperative. Grammar B is resolved as technically qualified but not selected. [RAN]

No production file was modified. The proposed integration remains solely in `marked_scale_candidate.patch`. [RAN]

Exactly one next production action: after Ayan approves this decision, apply `marked_scale_candidate.patch` once to the current working tree.
