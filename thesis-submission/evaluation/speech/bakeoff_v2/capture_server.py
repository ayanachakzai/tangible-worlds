"""
Serves the isolated ASR bake-off recorder and saves its 16 kHz WAV files.

This does not import or modify the production voice server.

Usage: python3 capture_server.py
"""

import io
import json
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
CORPUS_PATH = ROOT / "corpus_dev.json"
AUDIO_DIR = ROOT / "audio_dev"
LOG_PATH = ROOT / "recording_log_dev.json"
PORT = 8091
MAX_WAV_BYTES = 8 * 1024 * 1024


def expanded_corpus():
    data = json.loads(CORPUS_PATH.read_text())
    items = []
    for template in data["templates"]:
        takes = int(template.get("takes", 1))
        for take in range(1, takes + 1):
            item = dict(template)
            item["template_id"] = template["id"]
            item["take"] = take
            item["id"] = template["id"] if takes == 1 else f"{template['id']}_t{take}"
            items.append(item)
    return items


CORPUS = expanded_corpus()
CORPUS_BY_ID = {item["id"]: item for item in CORPUS}


def read_log():
    try:
        return json.loads(LOG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_log(log):
    temporary = LOG_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(log, indent=2))
    temporary.replace(LOG_PATH)


def inspect_wav(raw):
    with wave.open(io.BytesIO(raw), "rb") as wav_file:
        channels = wav_file.getnchannels()
        width = wav_file.getsampwidth()
        rate = wav_file.getframerate()
        frames = wav_file.getnframes()
    if channels != 1 or width != 2 or rate != 16000:
        raise ValueError(
            f"need 16 kHz mono 16-bit PCM, got {rate} Hz, "
            f"{channels} channel(s), {width * 8}-bit"
        )
    return frames, frames / rate


class Handler(BaseHTTPRequestHandler):

    def send_bytes(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, code, payload):
        self.send_bytes(
            code,
            json.dumps(payload).encode(),
            "application/json; charset=utf-8",
        )

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self.send_bytes(
                200,
                (ROOT / "capture.html").read_bytes(),
                "text/html; charset=utf-8",
            )
        if path == "/voice_capture_worklet.js":
            return self.send_bytes(
                200,
                (ROOT / "voice_capture_worklet.js").read_bytes(),
                "text/javascript; charset=utf-8",
            )
        if path == "/corpus":
            recorded = sorted(path.stem for path in AUDIO_DIR.glob("*.wav"))
            return self.send_json(
                200,
                {"items": CORPUS, "recorded": recorded, "total": len(CORPUS)},
            )
        return self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/save":
            return self.send_json(404, {"ok": False, "error": "not found"})

        clip_id = parse_qs(parsed.query).get("id", [""])[0]
        if clip_id not in CORPUS_BY_ID:
            return self.send_json(400, {"ok": False, "error": "unknown clip id"})

        length = int(self.headers.get("Content-Length", "0"))
        if length <= 44 or length > MAX_WAV_BYTES:
            return self.send_json(400, {"ok": False, "error": "invalid WAV size"})

        AUDIO_DIR.mkdir(exist_ok=True)
        target = AUDIO_DIR / f"{clip_id}.wav"
        if target.exists():
            return self.send_json(409, {"ok": False, "error": "clip already exists"})

        raw = self.rfile.read(length)
        try:
            frames, duration = inspect_wav(raw)
        except (wave.Error, EOFError, ValueError) as error:
            return self.send_json(400, {"ok": False, "error": f"bad WAV: {error}"})

        temporary = AUDIO_DIR / f".{clip_id}.tmp"
        temporary.write_bytes(raw)
        temporary.replace(target)

        log = read_log()
        log[clip_id] = {
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "duration_s": round(duration, 3),
            "frames": frames,
            "sample_rate": 16000,
            "peak": self.headers.get("X-Clip-Peak"),
            "browser_duration_s": self.headers.get("X-Clip-Duration"),
            "microphone": self.headers.get("X-Microphone"),
            "reference": CORPUS_BY_ID[clip_id]["reference"],
            "category": CORPUS_BY_ID[clip_id]["category"],
            "file": str(target.relative_to(ROOT)),
        }
        write_log(log)

        print(f"saved {clip_id}: {duration:.2f}s")
        self.send_json(200, {"ok": True, "id": clip_id, "duration_s": duration})


print(f"ASR bake-off recorder: http://127.0.0.1:{PORT}")
print(f"development clips: {len(CORPUS)}")
ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
