#!/usr/bin/env python3
"""Synthetic Pocket-TTS -> Moonshine marker bakeoff.

This is isolated phrase evidence, not a substitute for Ayan's microphone,
voice, room, controller timing, or the observed real-user transcript.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw" / "synthetic_stt"
RAW.mkdir(parents=True, exist_ok=True)
TTS_URL = "http://127.0.0.1:8000/tts"
STT_URL = "http://127.0.0.1:8090/transcribe"

phrases = []
for candidate, marker in (("A", "size"), ("B", "size is"), ("C", "scale")):
    for value in ("tiny", "small", "big", "huge"):
        phrases.append({
            "candidate": candidate,
            "value": value,
            "reference": f"object two is a car {marker} {value}",
        })

results = []
for index, item in enumerate(phrases, start=1):
    stem = f"{index:02d}_{item['candidate'].lower()}_{item['value']}"
    raw_wav = RAW / f"{stem}_24k.wav"
    wav_16k = RAW / f"{stem}_16k.wav"
    record = {**item, "synthetic_voice": "Pocket TTS Alba", "status": "pending"}
    try:
        body = urllib.parse.urlencode({"text": item["reference"], "voice_url": "alba"}).encode()
        start = time.perf_counter()
        with urllib.request.urlopen(urllib.request.Request(TTS_URL, data=body), timeout=20) as response:
            raw_wav.write_bytes(response.read())
        record["tts_s"] = round(time.perf_counter() - start, 3)

        subprocess.run([
            "/opt/homebrew/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(raw_wav), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav_16k),
        ], check=True, capture_output=True, text=True)

        start = time.perf_counter()
        request = urllib.request.Request(
            STT_URL,
            data=wav_16k.read_bytes(),
            headers={"Content-Type": "audio/wav"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
        record["roundtrip_stt_s"] = round(time.perf_counter() - start, 3)
        record["moonshine_stt_s"] = payload.get("stt_s")
        record["heard"] = payload.get("text", "")
        record["exact_casefold"] = record["heard"].strip(" .!?").casefold() == item["reference"].casefold()
        record["status"] = "ok"
    except Exception as exc:
        record["status"] = "error"
        record["error"] = f"{type(exc).__name__}: {exc}"
    results.append(record)
    print(f"{stem}: {record.get('heard', record.get('error'))}")

payload = {
    "evidence_type": "synthetic Pocket TTS Alba audio transcribed by the live local Moonshine service",
    "limitations": "Not equivalent to Ayan's speech, microphone, room, pacing, or repeated live interaction.",
    "phrase_count": len(results),
    "results": results,
}
(RAW / "stt_bakeoff_results.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "ok": sum(r["status"] == "ok" for r in results),
    "errors": sum(r["status"] == "error" for r in results),
    "exact": sum(r.get("exact_casefold", False) for r in results),
}, indent=2))
