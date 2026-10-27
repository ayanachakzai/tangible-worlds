# Synthetic STT phrase bakeoff

## Evidence status

This is **synthetic**, not a live-user voice test. Pocket TTS Alba generated each phrase; the existing local Moonshine service transcribed a 16 kHz PCM conversion. It does not represent Ayan's voice, microphone, room, speaking rhythm, or browser/controller capture.

Existing real-user evidence: Ayan repeatedly said `object two is a car scale tiny`; Moonshine returned `Object 2 is a car scaled tiny`. This remains Candidate C's authoritative negative acoustic datapoint.

## Results

| Candidate | Value | Moonshine transcript | Marker parsed? |
|---|---|---|---|
| A `size` | tiny | `Object 2 is a car-sized tiny.` | no |
| A `size` | small | `Object 2 is a car size small.` | yes |
| A `size` | big | `Object 2 is a car size big.` | yes |
| A `size` | huge | `Object two is a car size huge.` | yes |
| B `size is` | tiny | `Object 2 is a car size is tiny.` | yes |
| B `size is` | small | `Object 2 is a car size is small` | yes |
| B `size is` | big | `Object 2 is a car size is big` | yes |
| B `size is` | huge | `Object 2 is a car size is huge.` | yes |
| C `scale` | tiny | `Object 2 is a car scale tiny.` | yes |
| C `scale` | small | `Object 2 is a car scale small.` | yes |
| C `scale` | big | `Object 2 is a car scale big.` | yes |
| C `scale` | huge | `Object 2 is a car scale huge.` | yes |

Synthetic marker-contract recognition: A 3/4, B 4/4, C 4/4. All 12 service calls succeeded. Raw evidence SHA-256: `cc88b4768665c9680b413c7e73917f035ccde90f982025f1d0f107112f675407`.

## Interpretation

Candidate B had the strongest synthetic marker retention, but it failed semantic precision. Candidate A was not even uniformly stable in synthetic speech. Candidate C's synthetic result is encouraging but contradicted by the actual repeated user observation; it cannot be described as acoustically qualified.
