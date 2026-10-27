# Frozen candidate contracts

Frozen before fresh holdout inference on 27 August 2026.

All candidates use the already-qualified local `qwen/qwen3-8b` model through LM Studio at `http://127.0.0.1:1234/v1/chat/completions`, `temperature: 0.0`, `stream: false`, `/no_think`, and `chat_template_kwargs: {"enable_thinking": false}`. No holdout phrase or expected answer appears in a prompt.

## Shared taxonomy and decision guide

The following text is shared by all candidates:

```text
You classify an assigned meaning for Tangible Worlds into one semantic relative-scale class.

The physical tabletop prop is only a handle. Ignore the prop's physical size.
Classify the REAL-WORLD OR INTENDED REPRESENTED SCALE of the assigned meaning.
The classes are compressed visual ordering bins for a miniature 3D environment, not literal metre measurements and not object-category labels.

Classes:
- micro: clearly much smaller than normal handheld objects.
- handheld: normally held or carried in the hands.
- body_scale: roughly person, animal, or furniture scale.
- room_scale: roughly room or small shelter scale.
- vehicle_scale: ordinary mobile vehicle or vessel scale.
- building_scale: one substantial building or building-like structure.
- infrastructure_scale: a very large built structure or complex beyond one ordinary building.
- landform_scale: a geographic terrain or natural landform feature.
- colossal_scale: city, continent, astronomical, or similarly enormous extent beyond an ordinary landform.
- ambiguous: no stable physical scale can be inferred, or the meaning is abstract, non-physical, an event, or too underspecified.

Decision rules:
- classify typical physical extent, not the noun's category.
- honour explicit size and comparison language over the subject noun's ordinary size.
- choose the nearest single class for a concrete physical meaning.
- use ambiguous conservatively when physical extent is genuinely unstable.
```

## Candidate A — direct enum baseline

Architecture: one Qwen call, no preprocessing.

System suffix:

```text
Return ONLY one exact class name:
micro
handheld
body_scale
room_scale
vehicle_scale
building_scale
infrastructure_scale
landform_scale
colossal_scale
ambiguous

Do not explain. Do not output punctuation, JSON, markdown, or any other text.
```

User turn:

```text
Assigned semantic meaning: "<meaning>"
Classify the intended represented real-world scale. /no_think
```

Output contract: one exact enum string. `max_tokens: 20`.

## Candidate B — one-call structured scale basis

Architecture: one Qwen call, no preprocessing. The observable `scale_basis` field forces the explicit scale reference to be represented alongside the final class. It is not a request for reasoning.

System suffix:

```text
Return ONLY one JSON object with exactly these keys:
{"scale_basis":"<short observable physical size reference>","semantic_scale_class":"<class>"}

scale_basis must be a short noun phrase naming the physical extent or explicit comparison that controls the class. It is not an explanation or private reasoning.
semantic_scale_class must be exactly one of: micro, handheld, body_scale, room_scale, vehicle_scale, building_scale, infrastructure_scale, landform_scale, colossal_scale, ambiguous.
No markdown or extra keys.
```

User turn:

```text
Assigned semantic meaning: "<meaning>"
Identify the observable scale basis and classify the intended represented real-world scale. /no_think
```

Output contract: strict two-key JSON object. `max_tokens: 80`. The request uses LM Studio's OpenAI-compatible JSON-schema response format; the local parser still rejects missing, extra, or invalid fields.

## Candidate C — minimal deterministic modifier basis plus enum

Architecture: a standard-library regular-expression pass extracts only these general grammatical relationships, then exactly one Qwen enum call classifies the extracted scale basis:

1. `<subject> as tall/wide/long/large/big as <reference>` -> `<reference>`
2. `<subject> the size of <reference>` -> `<reference>`
3. `<reference>-sized <subject>` -> `<reference>`
4. `life-size(d)`, `full-size(d)`, or `full-scale` `model/replica of <referent>` -> ordinary full-size `<referent>`
5. `miniature` or `toy` `model/replica/version of <referent>` -> a small portable model

The parser contains no noun-specific class rules. It normalises only `hand`, `palm`, and `pocket` references to a generic one-hand/pocket physical extent. If no pattern matches, the original meaning is the scale basis.

System suffix: identical enum-only suffix to Candidate A.

User turn:

```text
Assigned semantic meaning: "<meaning>"
Deterministically extracted intended scale basis: "<basis>"
Classify the physical extent expressed by the scale basis. /no_think
```

Output contract: one exact enum string. `max_tokens: 20`.

## Frozen repeatability plan

Run each candidate once on all 72 holdout cases. For the 12 cases marked `repeat: true`, run two additional calls, giving three outputs per repeated case. The repeat subset contains eight modifier cases and four non-modifier controls. Report contract validity, preregistered acceptability, group results, modifier results, and exact three-run agreement separately.
