# Tangible Worlds final voice-only STT normalization qualification

Study date: 30 August 2026.

## Final decision

**Reserve terminal `scaled <size>` as a voice-only scale-control alias and qualify it.** [READ][RAN]

This is a narrow project grammar decision. It does not claim that literal descriptive `scaled` language can be distinguished from Moonshine's observed substitution. Production remains unchanged; the qualified one-file patch is unapplied.

## Fresh 104-case voice-transcript holdout

| Interpretation | TP | FP | FN | TN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| Unrestricted human intent | 24 | 12 | 0 | 68 | 66.7% | 100% |
| Reserved voice grammar | 36 | 0 | 0 | 68 | 100% | 100% |

All 24 intended STT aliases were normalized. All 12 literal semantic endings were also normalized, proving that the mechanism cannot safely operate as a general semantic repair. The project grammar qualifies only because the exact ending is explicitly reserved after the confirmed voice-assignment route has matched. The complete outer-route and assignment oracle passed 104/104; all 10 atmosphere/non-assignment cases remained on the conversation route.

**Limitation:** voice meanings literally ending in `scaled <tiny|miniature|small|big|large|huge>` are reserved control syntax and must be rephrased.

## Typed and existing grammar protection

The candidate is absent from the typed path and the generic server parser. The actual current parser returned the following in isolation:

```text
typed a car scaled tiny
-> generation_meaning: a car scaled tiny
-> target_size: 1.0
-> scale_source: neutral_default

existing a car scale tiny
-> generation_meaning: a car
-> target_size: 0.35
-> scale_source: participant_marked
```

All 12 existing correct voice `scale <size>` holdout forms remained unchanged and explicit. Confirmation still occurs before accepted-command routing, and atmosphere fallback is unchanged.

## Mandatory cache regression

The actual current `serve.py` parser was loaded from an isolated copy with production SHA-256 `22089f1f43568a344206a3ab3ee05cb62bea79eaf828be6ffd965491967cc523`. The existing 1,047,760-byte `phase3-tabletop/rendering/generated_meshes/a-car.glb` was copied into an isolated fixture.

```text
voice original:       a car scaled tiny
normalized payload:  a car scale tiny
correct-form payload: a car scale tiny
generation meaning:  a car (both)
cache slug:           a-car (both)
target size:          0.35 (both)
generator calls:      0
final status:         ready
```

An already assigned same-object correct payload is also an exact server no-op because the normalized strings are equal. The test altered no production cache or assignment file.

## Unapplied patch

`voice_scaled_alias_candidate.patch` changes only the accepted voice-assignment route in `index.html`: 29 insertions and one deletion. It adds no dependency and leaves `/api/assign` and `serve.py` untouched.

| Verification | Result |
|---|---|
| Frozen full contract | 104/104 pass |
| Patched assignment normalization | 94/94 pass |
| Typed protection | pass |
| Atmosphere routing | 10/10 pass |
| Existing cache reuse | pass, zero generation |
| Patched module syntax | pass |
| `git diff --check` | pass |
| `git apply --check` | pass |
| Isolated-copy apply | pass |
| Protected production hashes | all five unchanged |

No production file, runtime JSON, dependency, commit, remote, or dirty-tree entry outside this study was changed.

## Exactly one next production action

After Ayan approves this reserved grammar, apply `voice_scaled_alias_candidate.patch` once to the current working tree.
