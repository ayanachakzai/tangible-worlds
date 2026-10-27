# Tangible Worlds Semantic Relative-Scale Study

Study date: 27 August 2026

## Executive conclusion

Do not lock the current manual ladder unchanged.

The best tested mapping is `C_compact`:

| class | target size |
|---|---:|
| handheld | 0.35 |
| body_scale | 0.65 |
| room_scale | 1.00 |
| vehicle_scale | 1.35 |
| building_scale | 1.80 |
| infrastructure_scale | 2.35 |
| landform_scale | 3.00 |

This ladder retained an immediately visible ordinal hierarchy in the production, near top-down, and lower-oblique views. It was also better than the current proposal on every measured boundedness tradeoff that mattered: lower total footprint, less large-object dominance, less edge overhang, and better visibility for the two smallest tested classes. The current ladder is defensible in direction but unnecessarily aggressive at the top and slightly too small at the bottom.

The evidence is strong enough to lock these seven visually tested values for this MSc prototype. It is not evidence for universal semantic scale ratios, and it does not validate `micro` or `colossal_scale`.

## What was actually tested

### Files and renderer paths

- [READ] `phase3-tabletop/PROJECT_AUDIT.md`, `phase3-tabletop/RUNBOOK.md`, and relevant current scale, rendering, tracking, and study-history sections in `design-diary/DESIGN_DIARY.md`.
- [READ] Full active scale and positioning paths in `phase3-tabletop/rendering/index.html` and the active server boundary in `phase3-tabletop/rendering/serve.py`.
- [READ] `phase3-tabletop/rendering/scale_test.html` and `scale_test_before_sliders.html`.
- [RAN] The isolated [study harness](study_harness.html) in an existing Chrome installation through the already installed Playwright CLI.
- [RAN] The [evidence gallery](preview.html), [machine-readable results](results.json), and 60 raw JSON records in `logs/raw_data/`.

### Calibration stimuli

Seven existing GLBs were loaded successfully in every rendered condition:

| stimulus | test class | bytes | SHA-256 |
|---|---|---:|---|
| coffee-mug.glb | handheld | 1,913,764 | `a1a1075f13bb270d0ba4a017347ccafc3ccce5b5301c32e25d0e2716c496edd4` |
| wooden-chair.glb | body_scale | 947,868 | `ce596f444c1c5552e9c8a034b999bffa809b95459ec8957c365cf25318f4ed82` |
| a-tent.glb | room_scale | 1,542,988 | `5f66ce8111abaecb5e226a09bb18b4d53d3650718a278225fd48dc6210196689` |
| a-car.glb | vehicle_scale | 1,047,760 | `d23bb955cf4e1d34b3d412f1a71d03eb7993965effd56bf2bc0133527e92bb33` |
| a-house.glb | building_scale | 2,212,300 | `8a6b003411b7f0d7a9b3b58878eeb60014f3e5654ded7c27dd0ab8ca954376ad` |
| a-castle.glb | infrastructure_scale | 2,563,340 | `8c297214bdf6727824080045d65f9e1fb0926628865a3cf72149e8ab2791ec21` |
| a-mountain.glb | landform_scale | 1,524,456 | `2752845b34b0aa2d7b19b326ce11902f684cccd29dccb9bfeb80b5441a4bb45f` |

### Ladders

| id | hypothesis | values |
|---|---|---|
| A_baseline | Common size should erase hierarchy. | 0.90, 0.90, 0.90, 0.90, 0.90, 0.90, 0.90 |
| B_current | Current manual spacing should make all ranks legible. | 0.30, 0.60, 1.00, 1.40, 2.00, 2.70, 3.40 |
| C_compact | Smaller upper classes may reduce crowding while preserving lower and middle separation. | 0.35, 0.65, 1.00, 1.35, 1.80, 2.35, 3.00 |
| D_expanded | Stronger middle and upper separation may improve rank reading but risk domination. | 0.25, 0.55, 1.00, 1.55, 2.20, 3.00, 3.80 |
| E_balanced | A bounded interpolation may preserve current anchors while lowering the upper maximum. | 0.32, 0.62, 1.00, 1.42, 1.95, 2.50, 3.10 |

### Compositions and cameras

Four deterministic compositions were rendered: one-per-class reference, crowding stress, mixed adjacency, and edge stress. Every composition was rendered from the production camera `(0, 12, 5)`, a near top-down camera `(0, 14, 0.01)`, and a lower-oblique camera `(8, 7, 8)`, all looking at the table center with a 50 degree perspective field of view.

Five ladders multiplied by four compositions multiplied by three cameras produced 60 screenshots. All 60 completed with seven of seven GLBs loaded where the composition contained all seven instances, or the intended six instances in edge stress. No capture failed.

## Verified renderer facts

- [READ] Production defines `TABLE_SIZE = 10` and renders a `PlaneGeometry(10, 10)`.
- [READ] Production uses a 50 degree `PerspectiveCamera` at `(0, 12, 5)` looking at `(0, 0, 0)`.
- [READ] `normalizeAndAddModel()` measures a `Box3`, takes `max(size.x, size.y, size.z)`, and applies one scalar scale.
- [READ] The ordinary-object fallback is `targetSize = targetSize || 0.9`.
- [READ] `applyRotationAndRest()` resets child `y`, applies rotation, measures the box again, and subtracts `box.min.y`.
- [READ] Ready-object groups are initially placed at `y = OBJECT_HEIGHT / 2`, which is `0.3`, while the generated child is grounded inside the group. This means the production group offset can leave the final generated child 0.3 units above the table. The isolated scale harness intentionally set the group to `y = 0` so this unrelated positioning issue did not contaminate scale comparison.
- [READ] The current isolated `scale_test.html` uses the same table and camera, resets object scale, normalizes by longest box dimension, and grounds the child at table level.
- [RAN] All study instances reported `grounded: true` after normalization.
- [RAN] All seven GLBs were readable, hashable, and renderable.

## Research findings

Stoakley, Conway, and Pausch introduced the World in Miniature as a second viewport that improves context and enables work at a scale different from the represented world. They also state that sufficiently small scale makes selection and manipulation difficult. This supports a compressed overview with a legibility floor. It does not supply a target-size sequence. Source: [author-hosted paper](https://www.cs.cmu.edu/~stage3/publications/95/conferences/chi/paper.html), DOI [10.1145/223904.223938](https://doi.org/10.1145/223904.223938).

Danyluk et al. distinguish representation size, represented scope, and scale in their World-in-Miniature design space. Their review shows broad variation and treats abstraction and geometry as separate design dimensions. This supports a bounded miniature representation whose scope can span more than its literal display size. It does not imply that a planet and mug should use real metre ratios. Source: [author-hosted PDF](https://barrettens.github.io/files/Danyluk_2021_WorldsInMiniature.pdf), DOI [10.1145/3411764.3445098](https://doi.org/10.1145/3411764.3445098).

Macaranas, Antle, and Riecke distinguish attribute properties such as big-small from spatial properties such as near-far. Their 20-participant study found several big-small mappings were readily identified, including more-less. This supports monotonic size as a potentially readable semantic attribute. It does not validate these nouns, class boundaries, or ratios. Source: [author-hosted PDF](https://antle.iat.sfu.ca/wp-content/uploads/2018/02/MacaranasAntleRiecke_TEI12_Metaphors.pdf), DOI [10.1145/2148131.2148166](https://doi.org/10.1145/2148131.2148166).

No verified source in this pass justified linear, geometric, or any other fixed numeric progression for Tangible Worlds. The chosen values are project-specific empirical tuning.

## Visual results

### A_baseline

The baseline proves that common-size normalization is unsuitable for semantic relative scale. The mug, chair, car, house, castle, and mountain all read as similarly sized props. Mesh shape supplies most of the remaining apparent variation, so the intended class ordering is absent. See [reference production](screenshots/A_baseline__reference__production.png) and [reference top-down](screenshots/A_baseline__reference__topdown.png).

### B_current

The current ladder creates a strong hierarchy from all three cameras. Its lower and middle classes remain distinguishable, so the earlier manual work was directionally sound. Its weakness is unnecessary upper-class dominance. Two mountains and two large built forms consume too much attention even before any bounding overlap occurs. See [reference production](screenshots/B_current__reference__production.png), [crowding production](screenshots/B_current__crowding__production.png), and [edge production](screenshots/B_current__edge__production.png).

### C_compact

The compact ladder is the best tradeoff. The mug remains visible, the chair remains taller and distinct, and tent, car, house, castle, and mountain form a readable sequence. The ranking survives top-down and lower-oblique inspection. Two mountains can coexist without becoming the entire scene, although they remain intentionally prominent. See [reference production](screenshots/C_compact__reference__production.png), [reference top-down](screenshots/C_compact__reference__topdown.png), [reference lower oblique](screenshots/C_compact__reference__low_oblique.png), and [crowding production](screenshots/C_compact__crowding__production.png).

### D_expanded

The expanded ladder fails the bounded-composition test. It makes the mug and chair least legible, produces the highest crowding footprint, adds a third overlap in mixed adjacency, and gives landform geometry excessive screen dominance. See [reference production](screenshots/D_expanded__reference__production.png), [crowding production](screenshots/D_expanded__crowding__production.png), and [adjacency production](screenshots/D_expanded__adjacency__production.png).

### E_balanced

The Codex-derived balanced ladder is competent but does not beat `C_compact`. It uses more footprint, makes the mug smaller, and overhangs the edge farther. Its slightly stronger vehicle and building steps were visually unnecessary because `C_compact` already preserved those distinctions. See [reference production](screenshots/E_balanced__reference__production.png), [crowding production](screenshots/E_balanced__crowding__production.png), and [edge lower oblique](screenshots/E_balanced__edge__low_oblique.png).

## Quantitative results

### Composition descriptors

Metrics below use the production camera record. World-space footprint is camera-independent. Percent means summed axis-aligned x-z footprint area divided by the 10 by 10 plane area. It double-counts overlap by design and is not a perceptual model.

| ladder | reference footprint % | crowding footprint % | adjacency overlaps | edge out-of-bounds instances |
|---|---:|---:|---:|---:|
| A_baseline | 4.66 | 4.34 | 0 | 0 |
| B_current | 20.23 | 25.89 | 2 | 1 |
| C_compact | 16.35 | 20.54 | 2 | 1 |
| D_expanded | 24.61 | 31.92 | 3 | 1 |
| E_balanced | 18.05 | 22.59 | 2 | 1 |

Relative to `B_current`, `C_compact` reduced summed reference footprint by 19.2% and crowding footprint by 20.6%. Relative to `D_expanded`, it reduced crowding footprint by 35.6%.

The edge-stress mountain centered at `x = 4.15` crossed the right table boundary in every semantic ladder. Overhang was 0.842 units for `B_current`, 0.643 for `C_compact`, 1.041 for `D_expanded`, and 0.693 for `E_balanced`. `C_compact` did not eliminate the boundary issue, but it produced the least overhang among the semantic candidates.

### Recommended ladder dimensions at the reference composition

| class | target | resulting x | resulting y | resulting z | footprint % | production projected box, px |
|---|---:|---:|---:|---:|---:|---:|
| handheld | 0.35 | 0.350 | 0.330 | 0.291 | 0.102 | 34.9 by 33.3 |
| body_scale | 0.65 | 0.468 | 0.650 | 0.491 | 0.230 | 37.6 by 61.0 |
| room_scale | 1.00 | 0.973 | 0.527 | 1.000 | 0.973 | 92.1 by 89.2 |
| vehicle_scale | 1.35 | 1.350 | 0.678 | 1.302 | 1.758 | 141.5 by 125.1 |
| building_scale | 1.80 | 1.737 | 1.759 | 1.800 | 3.126 | 171.6 by 208.4 |
| infrastructure_scale | 2.35 | 2.350 | 2.069 | 2.128 | 5.001 | 280.6 by 249.6 |
| landform_scale | 3.00 | 3.000 | 2.886 | 1.721 | 5.163 | 366.2 by 232.4 |

The recommended adjacent target-size ratios are 1.857, 1.538, 1.350, 1.333, 1.306, and 1.277. The decreasing ratios are a project compression choice, not a published perceptual formula.

### Longest-dimension normalization challenge

At the common 0.9 target, footprint area ranged from 0.440% for the chair to 0.788% for the tent, a 1.79 times difference even though requested targets were identical. The mountain footprint was 0.465%, while the castle was 0.733%. Under `B_current`, castle and mountain footprints were nearly equal at 6.601% and 6.632% despite target sizes 2.7 and 3.4. Shape therefore changes footprint and apparent mass substantially.

Conclusion: longest-dimension normalization is adequate with a documented limitation for this MSc study. It reliably bounds the maximum dimension and remains simple enough to explain. It does not equalize footprint or volume, and SPAR3D aspect-ratio variation may amplify the discrepancy. The tested ordinal gaps remained visually readable despite this effect, so a separate normalization redesign is not required before Qwen integration.

## Adversarial findings

- The smallest tested class remained visible in all one-per-class and crowding views. In `C_compact`, its production projected box was about 35 by 33 pixels. This is better than about 30 by 28 pixels in `B_current` and about 25 by 24 pixels in `D_expanded`.
- The middle classes remained distinguishable under `C_compact` from production, top-down, and lower-oblique cameras.
- Multiple large classes coexisted with no axis-aligned overlap in the fixed crowding composition, but the two mountains still dominated the upper part of the production frame.
- Every semantic ladder failed the deliberate edge-boundary test for the mountain. `C_compact` minimized rather than solved the failure.
- Mixed adjacency caused two footprint overlaps in `B_current`, `C_compact`, and `E_balanced`, and three in `D_expanded`. The mug beside the mountain can become fully occluded even from near top-down because their footprints overlap. Static semantic size alone cannot guarantee visibility under arbitrary participant placement.
- Ranking survived near top-down inspection, but mesh shape altered apparent footprint strongly. The mountain and castle can occupy similar x-z area even with different target sizes.
- A viewer can read a broad hierarchy without seeing the numbers in `C_compact`, but exact adjacent class labels, especially room versus vehicle, still depend partly on knowing the object identities.
- Seven visually convenient calibration meshes cannot establish performance for open vocabulary or all SPAR3D outputs.

The preferred ladder survived the attempt to falsify its hierarchy, crowding, and camera robustness. It did not survive arbitrary-overlap or edge-placement challenges. Those failures are explicitly outside what a static scale ladder alone can solve.

## Recommendation

Lock the seven tested classes to `0.35, 0.65, 1.00, 1.35, 1.80, 2.35, 3.00` in the class order handheld through landform_scale.

Leave `micro` unresolved because no suitable micro stimulus was tested. Leave `colossal_scale` unresolved because no suitable colossal stimulus was tested. Assigning values below 0.35 or above 3.00 without assets would manufacture certainty precisely where visibility and crowding are already the limiting constraints.

Retain the approved taxonomy for now. The class sequence is useful as a renderer contract, but `room_scale`, `infrastructure_scale`, and `landform_scale` are semantic design bins, not claims of physical measurement.

## Qwen integration implications

The simplest later contract is one cached enum per assigned meaning:

```json
{
  "semantic_scale_class": "building_scale",
  "semantic_scale_version": "scale-ladder-v1"
}
```

Qwen should return only the approved enum. The assignment record should cache it once when the meaning is created. The renderer should own the enum-to-target lookup and should never accept a free numeric size from Qwen. Movement should update position only.

For `ambiguous`, retain the class label and use a neutral project fallback of `1.00` rather than pretending that the concept has a physical class. The fallback is an interface default, not a semantic judgment. If a participant reassigns the meaning, create a new classification for the new assignment; do not reclassify ordinary movement.

## Limitations

- Open vocabulary can contain nouns, phrases, events, emotions, and abstractions with no stable physical size.
- The seven calibration meshes create a serious overfitting risk because each tested class has only one shape and visual style.
- SPAR3D geometry can vary in orientation, aspect ratio, empty bounds, detail density, and generated scale.
- Longest-box-dimension normalization does not equalize x-z footprint, volume, or perceived mass.
- Camera and composition matter. The same object occupies different projected area from production, top-down, and lower-oblique views.
- Axis-aligned footprint overlap does not equal visible occlusion, but it correctly flags placements where occlusion is possible.
- The production ready-group `y = 0.3` offset was excluded to isolate scale. Production screenshots may therefore differ in grounding and shadows until that separate issue is handled.
- `micro`, `colossal_scale`, and ambiguous concepts did not have suitable visual calibration stimuli.
- No participant study was run. Visual legibility judgments here are technical and design judgments by one evaluator, supported by deterministic evidence rather than human-subject data.

## Next action

Implement one cached `semantic_scale_class` field in the assignment record and map only the seven validated enum values to the locked `C_compact` targets in the renderer, leaving `micro` and `colossal_scale` explicitly unimplemented until suitable stimuli are tested.

## Final verification

The verification record is in `codex_run_notes.md`, `file_hashes_before.txt`, and `file_hashes_after.txt`. The gallery and every report screenshot link were checked against the files on disk.
