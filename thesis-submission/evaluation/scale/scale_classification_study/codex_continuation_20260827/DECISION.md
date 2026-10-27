# Decision

## Selected outcome

**Qwen semantic-scale classification does not qualify for production yet.**

This is exactly the fourth permitted decision outcome. None of the three frozen architectures met the engineering standard.

The best candidate, B structured scale basis, returned a valid contract for 72/72 holdout cases but matched only 50/72 preregistered acceptable labels (69.4%). It matched 28/36 ordinary concrete meanings (77.8%), only 13/20 explicit modifiers (65.0%), and only 2/4 abstractions/events. Its weakest ordinary bins were body (2/4), room (2/4), and infrastructure (1/4). All 12 repeated cases agreed exactly, including two systematic wrong answers.

Candidate A was 43/72 overall and 12/20 on modifiers. Candidate C was 48/72 overall and 13/20 on modifiers. Candidate C's added parser therefore did not provide a material, general improvement worth its extra mechanism.

## Why this resolves the question

The local Qwen3-8B runtime can reliably obey enum or strict JSON syntax, and it is deterministic at temperature zero on the tested repeat subset. It cannot reliably map unrestricted assigned meanings into these project-specific compressed bins. Explicit modifiers remain a systematic problem, and ordinary open-vocabulary room/infrastructure meanings also fail too often. A cached wrong answer is still wrong; caching only prevents reclassification on movement.

No further prompt tuning is justified in this run. Candidate B often extracted the correct physical basis and still selected the wrong class, while Candidate C often passed an exact reference noun and received the wrong bin. Fixing those cases would require more examples, class-boundary patches, or noun rules tuned to observed failures.

## Simplest defensible alternative in the existing stack

Use an explicit assignment-time scale-band selector and cache the participant's selection with the meaning. Do not use Qwen for scale.

Proposed negative-result contract, not applied:

```json
{
  "meaning": "participant's unrestricted phrase",
  "semantic_scale_class": "room_scale",
  "semantic_scale_source": "participant_selected"
}
```

The UI can present human-readable bands—held object, person/furniture, room/shelter, vehicle, building, very large structure/complex, and landscape—plus “not sure”. “Not sure” stores `ambiguous` and renders at the neutral 1.00 fallback. The renderer owns the seven locked numeric targets. Movement changes position only and never changes the cached selection or regenerates the object.

The semantic taxonomy still retains `micro` and `colossal_scale`, but those two choices should not produce invented numeric renderer values. They must remain unavailable for scaled rendering or fall back explicitly to neutral 1.00 until a later isolated visual calibration supplies evidence.

## Exactly one next production action

Add one assignment-time human-readable scale-band selector that saves `semantic_scale_class` and `semantic_scale_source: "participant_selected"` in the assignment record, with `ambiguous -> 1.00`; do not add a Qwen scale-classification call.
