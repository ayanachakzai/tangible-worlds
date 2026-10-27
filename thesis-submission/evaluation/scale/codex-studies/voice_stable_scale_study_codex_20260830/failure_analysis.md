# Failure analysis

## Candidate A: `size <value>`

Candidate A scored 24 TP, 3 FP, 0 FN, and 121 TN. Precision was 88.9%; recall was 100%; exact intent and generation-meaning accuracy were 97.97%. False positives:

1. `a T-shirt size small`
2. `a costume size large`
3. `a prop label reading size tiny`

These are common label/apparel descriptions, not contrived syntax errors. The parser would strip their final words and alter renderer scale, so A does not qualify.

Synthetic STT recognized 3/4 A phrases. `object two is a car size tiny` became `Object 2 is a car-sized tiny.`, which does not match Candidate A. `small`, `big`, and `huge` retained the marker.

## Candidate B: `size is <value>`

Candidate B scored 24 TP, 6 FP, 0 FN, and 118 TN. Precision was 80%; recall was 100%; exact intent and generation-meaning accuracy were 95.95%. False positives were ordinary sentences ending in `whose size is tiny/miniature/small/big/large/huge`.

Synthetic STT recognized all 4/4 B phrases, but acoustic clarity cannot compensate for semantic ambiguity. B does not qualify.

## Candidate C: current `scale <value>`

Candidate C scored 24 TP, 0 FP, 0 FN, and 124 TN: 100% precision, recall, exact intent, and generation-meaning accuracy. Synthetic STT recognized all 4/4 phrases.

However, Ayan's repeated real speech `object two is a car scale tiny` became `Object 2 is a car scaled tiny`. That is a proven acoustic failure in the actual workflow and outweighs synthetic success for claims about live reliability. Globally accepting `scaled` is still rejected because the previous tolerant study demonstrated semantic false positives.

## Decision consequence

No candidate is both newly voice-proven and semantically perfect. Candidate C remains the least harmful grammar because its failure is visible and recoverable through confirmation/retry, whereas A and B silently corrupt valid meanings.
