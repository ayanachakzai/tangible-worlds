# Tangible Worlds voice-stable marked size grammar study

Study date: 30 August 2026.

## Final decision

**Current `scale <value>` remains best despite acoustic limitation.** [READ][RAN]

Neither proposed replacement satisfies the critical semantic precision gate. Candidate C remains production's least harmful deterministic grammar; its `scale tiny -> scaled tiny` real-user failure is retained as a known voice limitation, not hidden by synthetic results.

## Fresh 148-case semantic holdout

| Candidate | TP | FP | FN | TN | Precision | Recall | Exact intent | Generation meaning |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A: `size <value>` | 24 | 3 | 0 | 121 | 88.9% | 100% | 97.97% | 97.97% |
| B: `size is <value>` | 24 | 6 | 0 | 118 | 80.0% | 100% | 95.95% | 95.95% |
| C: current `scale <value>` | 24 | 0 | 0 | 124 | 100% | 100% | 100% | 100% |

Candidate A silently reinterprets `a T-shirt size small`, `a costume size large`, and `a prop label reading size tiny`. Candidate B silently reinterprets six ordinary descriptions ending in `whose size is <supported-value>`. These are exactly the high-impact false positives the project rejects. [RAN]

Candidate C correctly preserved life/full-size language, comparison charts, size labels, `scale model`, `scaled mesh`, `large scale map`, malformed/conflicting markers, synonyms, bare assignments, proper nouns, and atmosphere commands.

## STT evidence

The live local Pocket TTS/Moonshine synthetic bakeoff completed all 12 phrases. Marker recognition was:

- A `size <value>`: 3/4; `size tiny` became `car-sized tiny`.
- B `size is <value>`: 4/4.
- C `scale <value>`: 4/4.

This is synthetic evidence only. It does not reproduce Ayan's speech or capture conditions. The repeated actual observation—`object two is a car scale tiny` becoming `Object 2 is a car scaled tiny`—is therefore the decisive acoustic limitation for C. Synthetic success cannot override it. [RAN]

B's stronger synthetic performance does not rescue it from 80% semantic precision. A is both semantically unsafe and not uniformly stable even under synthetic speech. No new candidate qualifies.

## Typed/voice, generation, cache, renderer, and movement

For valid parsed text, all candidates passed typed/voice parity. The retained current contract passed every requested field/invariant: original `meaning` preserved, `generation_meaning` stripped to `a car`, `very_small` intent, target 0.35, unchanged `participant_marked` source, generation/cache identity based on stripped meaning, renderer use of `target_size`, and movement without regeneration. [READ][RAN]

The current safe rejection of `scaled tiny` preserves the full phrase and neutral 1.00. Its downside is a second generation/cache identity for the whole phrase, as observed live; accepting it globally would create worse silent semantic errors.

## Production boundary

No follow-up patch was produced. That omission is deliberate: A and B failed qualification, while C is already present in the current working tree. Production `index.html`, `serve.py`, tracker, mapping, and conversation files remained unchanged. No runtime JSON, docs, dependencies, commits, or remote state were touched.

Current server syntax was compile-checked from an isolated copy. The 444-row parser regression suite passed its expected metrics. Before/after hashes for all five protected files match. [RAN]

## Limitation and recovery

No tested grammar is both newly voice-proven and semantically perfect. Current `scale <value>` remains best because its error is visible in the confirmation and can be rejected; A/B errors would be silent after acceptance.

## Exactly one next production action

Add one facilitator instruction to the participant protocol: if confirmation says `scaled <value>`, answer no and repeat `scale <value>`.
