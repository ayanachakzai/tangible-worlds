# Decision

**Candidate A qualifies: optional comma with explicit terminal scale.** [READ][RAN]

Accepted forms:

```text
<meaning>, scale <tiny|miniature|small|big|large|huge>
<meaning> scale <tiny|miniature|small|big|large|huge>
```

Candidate A produced 36 TP, 0 FP, 0 FN, and 84 TN: 100% precision and 100% grammar-specific recall. Candidate B recognized all 12 preregistered `scaled` transcript aliases but also produced six semantic false positives on ordinary VFX descriptions. Because a silent semantic rewrite is more serious than safely leaving one STT variant neutral, `scaled <size>` is rejected. [RAN]

No production file was modified. The 46-line follow-up diff remains unapplied as `tolerant_marked_scale_candidate.patch`.

Exactly one next production action: after Ayan approves this decision, apply `tolerant_marked_scale_candidate.patch` once to the current working tree.
