# ASR bake-off v2, step 1

This recorder creates the new development corpus through the same browser
AudioWorklet, 16 kHz mono PCM path, and DualSense touchpad trigger used by the
production voice condition. It does not run a transcriber and does not modify
the production server, renderer, tracker, or existing Phase 6A corpus.

The development corpus contains 102 independent recordings:

- 36 core object assignments from three fresh takes of twelve phrases
- 12 assignment robustness recordings with fillers, pauses and delivery changes
- 20 clear yes or no confirmation recordings
- 6 deliberately ambiguous confirmation recordings
- 16 atmosphere commands
- 12 adversarial silence, prop noise, aborted speech and human non-speech clips

The order is shuffled with a fixed seed. Existing clips are skipped when the
page is reopened. The locked holdout corpus will be created only after model
settings are frozen.

## Run

From this directory:

```bash
python3 capture_server.py
```

Open:

```text
http://127.0.0.1:8091
```

Use the same Opera or Chromium browser and the same DualSense touchpad button
used by the production system. Spacebar is available only as a fallback.

Keep normal variation. Redo only when the wrong words were spoken, the displayed
instruction was not followed, or capture technically failed. Do not listen for
accent quality and do not run any transcription during recording.

Outputs:

```text
audio_dev/*.wav
recording_log_dev.json
```

The server refuses to overwrite an existing clip. To intentionally replace one,
stop the server and remove only that exact WAV and its matching log entry.
