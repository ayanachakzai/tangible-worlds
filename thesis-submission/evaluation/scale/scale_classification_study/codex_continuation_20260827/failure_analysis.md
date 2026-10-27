# Failure analysis

This review preserves the frozen acceptable-label score. No expected set was widened after inference.

## Candidate A — 29 mismatches

The direct prompt produced valid and repeatable enums, but unseen coverage was poor.

- Ordinary under-sizing: `wheelbarrow`, `arcade cabinet`, `portable toilet cubicle`, and `ticket booth` all became `handheld`; `sauna cabin` became `body_scale`.
- Built-scale compression: all four infrastructure cases missed; `container port`, `thermal power station`, and `coastal flood barrier` became `building_scale`, while `motorway interchange` became `room_scale`.
- Extreme-scale inconsistency: `metropolis` became `building_scale` and `country` became `ambiguous`.
- Modifier failures: 8/20 missed, including miniature representation, built-reference, landform-reference, and comparison forms.

This is systematic semantic miscalibration, not an enum-format problem.

## Candidate B — 22 mismatches

The structured result was the best candidate, but the observable basis often showed that decomposition had succeeded while class selection still failed.

- `suspension-bridge-sized serpent` produced basis `suspension bridge` but class `building_scale`.
- `mountain-sized robot` produced basis `mountain` but class `colossal_scale`.
- `tree as tall as an office tower` produced basis `office tower height` but class `colossal_scale`.
- `whale as long as a passenger train` produced basis `passenger train length` but class `room_scale`.
- `fortress the size of a garden shed` produced basis `garden shed` but class `building_scale`.
- `miniature model of a space station` discarded the modifier in its basis (`space station`) and returned `building_scale`.

Ordinary performance also remained non-robust: 2/4 body, 2/4 room, and 1/4 infrastructure cases matched. Ambiguity handling regressed to 2/4 because `traffic` and `earthquake` were forced into physical bins.

## Candidate C — 24 mismatches

The parser fixed `mountain-sized robot` and `miniature model of a space station`, but this did not generalise enough to qualify. Modifier accuracy was only 13/20, the same as B and one case better than A.

Several extracted bases were correct but Qwen still mapped them incorrectly:

- `suspension-bridge` -> `room_scale`
- `an office tower` -> `colossal_scale`
- `a passenger train` -> `room_scale`
- `an airport terminal` -> `room_scale`
- `a garden shed` -> `body_scale`

The parser also exposed compressed-bin ambiguity: `bicycle` was classified `vehicle_scale`, so `bicycle-sized elephant` missed the preregistered `body_scale`. Adding noun-specific fixes would violate the study's simplicity and research-integrity constraint.

## True failures versus defensible disagreements

The reported scores count every output outside its preregistered set as a mismatch.

Clear true failures include handheld portable cubicles/booths, room-scale motorway interchanges, body-scale temples, built-scale miniature space-station models, room-scale passenger-train comparisons, and colossal office-tower comparisons.

Some frozen mismatches permit a defensible alternative reading after the fact, but are not rescored:

- `doorway into another dimension -> ambiguous` treats the phrase as a supernatural concept rather than a physical doorway.
- `mobile home -> building_scale` treats it as a settled small building rather than a room/vehicle object.
- `country -> landform_scale` treats geographic territory as a landform-adjacent extent.
- `rabbit as tall as a doorway -> room_scale` is an adjacent body/room boundary choice.
- `mountain-sized robot -> colossal_scale` is an adjacent landform/colossal boundary choice, though it conflicts with the guide's explicit “beyond ordinary landform” distinction.

These cases do not explain the broad failures in ordinary room, infrastructure, and modifier groups.

## Systematic conclusion

Validity and deterministic repeatability are strong. Semantic calibration is not. Structured decomposition and general syntax extraction each moved a small number of cases but did not remove the failure pattern. Further improvement would require increasingly specific scale-anchor examples or noun rules, which would be prompt-set tuning rather than credible unrestricted open-vocabulary classification.
