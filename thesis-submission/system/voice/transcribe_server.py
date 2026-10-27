"""
turns the browser's posted wav into text using local parakeet tdt 0.6b v3.

run:
    cd ~/Documents/UAL/tangible-worlds/phase6-voice
    source .venv/bin/activate
    python transcribe_server.py

this file keeps the same browser contract as the old moonshine server:
the browser posts a 16 khz mono pcm16 wav to port 8090 and receives
{ok, text, stt_s}. parakeet itself runs privately on port 8091.

the nemo-speech child process is started and stopped by this file, so the
facilitator still runs one command for speech recognition.

references:
- nemo-speech.cpp local server and /ready endpoint:
  https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/server.md
- nemo-speech.cpp asr configuration:
  https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/asr/configuration.md
- parakeet tdt 0.6b v3 model:
  https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
"""

import io
import json
import subprocess
import time
import urllib.error
import urllib.request
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


PORT = 8090
PARAKEET_PORT = 8091
PARAKEET_URL = f"http://127.0.0.1:{PARAKEET_PORT}"
TRANSCRIBE_URL = f"{PARAKEET_URL}/v1/audio/transcriptions"
READY_URL = f"{PARAKEET_URL}/ready"

# exact local runtime qualified in the 1 sep 2026 asr bake-off.
NEMO_SPEECH = Path.home() / ".local/bin/nemo-speech"
MODEL_FILE = (
    Path.home()
    / "Downloads/asr_bakeoff_v2/models/parakeet-tdt-0.6b-v3.q8_0.gguf"
)

# project decision, 1 sep 2026:
# plain parakeet is the production profile. no speech-context boosting is sent.
# nemo-speech.cpp documents that parakeet tdt ignores word boosting anyway.
# ref: https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/asr/configuration.md


def start_parakeet():
    if not NEMO_SPEECH.is_file():
        raise RuntimeError(f"nemo-speech not found: {NEMO_SPEECH}")
    if not MODEL_FILE.is_file():
        raise RuntimeError(f"parakeet model not found: {MODEL_FILE}")

    process = subprocess.Popen([
        str(NEMO_SPEECH),
        "serve",
        "--asr-model", str(MODEL_FILE),
        "--host", "127.0.0.1",
        "--port", str(PARAKEET_PORT),
        "--threads", "1",
        "--no-ui",
    ])

    # nemo-speech.cpp documents /ready as the server readiness endpoint.
    # do not expose port 8090 until the model reports that it is actually ready.
    # ref: https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/server.md
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"parakeet stopped during startup with code {process.returncode}"
            )

        try:
            with urllib.request.urlopen(READY_URL, timeout=1.0) as response:
                if response.status == 200:
                    return process
        except (urllib.error.URLError, TimeoutError):
            pass

        time.sleep(0.2)

    process.terminate()
    process.wait(timeout=5)
    raise RuntimeError("parakeet did not become ready within 60 seconds")


def multipart_body(wav_bytes):
    # the local nemo-speech server exposes an openai-compatible subset at
    # /v1/audio/transcriptions. i use urllib so this adapter adds no new
    # python dependency to the phase6 voice environment.
    # ref: https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/server.md
    boundary = f"----tangible-worlds-{time.time_ns()}"
    body = bytearray()

    def field(name, value):
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        )
        body.extend(str(value).encode())
        body.extend(b"\r\n")

    field("model", "parakeet-tdt-0.6b-v3")
    field("language", "en")
    field("response_format", "json")
    field("automatic_punctuation", "false")

    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        b'Content-Disposition: form-data; name="file"; filename="voice.wav"\r\n'
    )
    body.extend(b"Content-Type: audio/wav\r\n\r\n")
    body.extend(wav_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    return boundary, bytes(body)


def transcribe(wav_bytes):
    boundary, body = multipart_body(wav_bytes)
    request = urllib.request.Request(
        TRANSCRIBE_URL,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"parakeet http {error.code}: {detail}"
        ) from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"parakeet unavailable: {error}") from error

    took = time.perf_counter() - start
    return str(payload.get("text", "")).strip(), took


class Handler(BaseHTTPRequestHandler):

    def reply(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        # index.html runs on 8080 and this server runs on 8090, so the browser
        # sends a cors preflight before posting audio.
        # ref: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS#preflighted_requests
        self.reply(200, {"ok": True})

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))

        try:
            with wave.open(io.BytesIO(raw)) as wav:
                rate = wav.getframerate()
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
        except (wave.Error, EOFError) as error:
            return self.reply(
                400, {"ok": False, "error": f"bad wav: {error}"}
            )

        # this is the existing browser transport contract, not a parakeet limit.
        if rate != 16000:
            return self.reply(
                400, {"ok": False, "error": f"need 16000 hz, got {rate}"}
            )
        if channels != 1:
            return self.reply(
                400,
                {
                    "ok": False,
                    "error": f"need mono audio, got {channels} channels",
                },
            )
        if sample_width != 2:
            return self.reply(
                400,
                {
                    "ok": False,
                    "error": f"need 16-bit pcm, got {sample_width * 8}-bit",
                },
            )

        try:
            text, took = transcribe(raw)
        except RuntimeError as error:
            print(f"[stt] failed  {error}")
            return self.reply(502, {"ok": False, "error": str(error)})

        print(f"[stt] {took:.3f}s  {text!r}")
        self.reply(
            200,
            {"ok": True, "text": text, "stt_s": round(took, 3)},
        )

    def log_message(self, format, *args):
        pass


def main():
    parakeet = None
    try:
        print("starting parakeet...")
        parakeet = start_parakeet()
        print(
            f"parakeet ready, listening on port {PORT} "
            f"(private backend {PARAKEET_PORT})"
        )
        HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nstopping speech server...")
    finally:
        if parakeet is not None and parakeet.poll() is None:
            parakeet.terminate()
            try:
                parakeet.wait(timeout=5)
            except subprocess.TimeoutExpired:
                parakeet.kill()
                parakeet.wait()


if __name__ == "__main__":
    main()
