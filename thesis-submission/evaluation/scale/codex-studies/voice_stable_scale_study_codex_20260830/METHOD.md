# Method

## Current-tree evidence

The dirty working tree, not HEAD, was treated as authoritative. It contains the live voice assignment route, participant-authored scale fields, renderer target wiring, stripped generation/cache identity, and optional-comma `scale <value>` parser. The current project audit, runbook, design diary, production files, and prior scale studies were read first. [READ]

Five protected production files and complete Git status were captured before any study artifact was created.

## Frozen semantic holdout

`holdout_cases.json` was frozen at `2026-08-30T23:57:36+0100`; candidate parser code was written later at `23:59:49+0100`, and results followed at `23:59:56+0100`. Holdout SHA-256: `e8ad2c2447ed4178c7599c159c5399e1648b8886e970389a157b3a74933155ba`. [RAN]

The 148 cases include 24 valid forms for each candidate; all six size words; typed/voice input; articles; case, punctuation, spacing; word/numeric IDs; internal commas; long VFX meanings; 20 semantic `size` phrases; 12 semantic `scale/scaled` phrases; 10 bare assignments; 10 atmosphere commands; 10 malformed markers; 8 conflicts; and 6 unsupported synonyms.

Each candidate was evaluated independently against its declared syntax. TP/FP/FN/TN, exact intent, and generation-meaning accuracy were computed from the frozen oracle.

## Synthetic STT bakeoff

Both existing local services were available: Pocket TTS Alba on port 8000 and Moonshine on port 8090. Twelve phrases were generated without installing or changing anything: Candidates A, B, and C for `tiny`, `small`, `big`, and `huge`. Pocket TTS's 24 kHz mono WAV was converted to 16 kHz PCM with the already-installed `ffmpeg`, then posted to the live Moonshine endpoint. Raw WAVs and JSON are under `raw/synthetic_stt/`. [RAN]

This is synthetic evidence. It does not reproduce Ayan's voice, microphone, room, pacing, or controller capture. The repeated real-user observation in the brief is retained as the stronger negative datapoint for Candidate C's `tiny` phrase.

## Contract verification

Typed/voice parity passed for one valid phrase under every candidate. For retained Candidate C, the isolated contract check confirmed original preservation, marker stripping, intent 0.35, unchanged `participant_marked` source, generation-based cache identity, renderer target use, and movement without regeneration. Already-proven GLB renderer tests were not repeated.

No production request, generation, runtime JSON write, install, patch application, commit, push, restore, or clean was performed.
