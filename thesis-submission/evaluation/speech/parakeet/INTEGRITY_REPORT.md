# ASR bake-off v2 corpus integrity report

Checked on 2 September 2026 before any ASR evaluation.

## Result

The development corpus is complete and technically valid.

- Expected recordings: 102
- WAV files present: 102
- Recording log entries: 102
- Missing recordings: 0
- Unexpected recordings: 0
- Byte-identical duplicate recordings: 0
- Format: all 16 kHz, mono, 16-bit PCM WAV
- Unreadable or truncated WAV files: 0
- Speech recordings with clipping: 0
- Speech recordings with critically low peak level: 0

## Category counts

| Category | Files |
| --- | ---: |
| Assignment core | 36 |
| Assignment robustness | 12 |
| Atmosphere | 16 |
| Clear confirmation | 20 |
| Ambiguous confirmation | 6 |
| Adversarial non-command audio | 12 |
| Total | 102 |

## Capture observations

`adversarial_silence_t2.wav` contains a single short transient sound. It does not resemble sustained speech in the waveform. It is retained as a realistic accidental-noise test and still has the expected route `empty`.

The cough and prop-noise stress recordings briefly reach the PCM ceiling. The affected points are isolated and occur only in deliberately adversarial non-speech recordings. They do not justify rerecording because rejection of this kind of input is part of the evaluation.

