"""
trims leading and trailing quiet from a clip before it reaches moonshine.

phase 6b. finding 7 in the phase 6a diary blames leading dead air for the junk
words ("thank you", "you", "naked") that appear on the front of transcripts.
this module exists so that claim can be tested rather than assumed.

usage as a script prints how much each clip in a folder would lose:
    python trim_silence.py audio_phrasing
"""

import sys
import wave
from pathlib import Path

import numpy as np

FRAME_MS = 20
DROP_DB = 40.0      # project tuning
MARGIN_MS = 50      # project tuning, keeps a little air either side of speech


def read_wav(path):
    """
    reads a 16 bit mono wav into floats in -1..1, the same range moonshine's
    load_wav_file returns so the trimmed and untrimmed paths stay comparable.
    """
    with wave.open(str(path)) as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return audio, rate


def frame_energy(audio, rate, frame_ms=FRAME_MS):
    """
    chops the clip into short frames and gives each one an energy in dB.
    short-time energy is the standard first step for endpoint detection.
    """
    n = int(rate * frame_ms / 1000)
    count = len(audio) // n
    if count == 0:
        return np.array([]), n
    frames = audio[:count * n].reshape(count, n)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    return 20 * np.log10(rms + 1e-9), n


def trim(audio, rate, drop_db=DROP_DB, margin_ms=MARGIN_MS):
    """
    keeps everything between the first and last frame that sits within drop_db
    of the loudest frame, plus a margin.

    the threshold is relative to each clip's own loudest frame rather than a
    fixed dBFS number. i measured the two phase 6a corpora at roughly 25 dB
    apart in level, and a browser mic will be different again, so an absolute
    threshold would not survive moving between recordings.
    """
    db, n = frame_energy(audio, rate)
    if db.size == 0:
        return audio, 0.0, 0.0

    loud = np.where(db > db.max() - drop_db)[0]
    if loud.size == 0:
        return audio, 0.0, 0.0

    margin = int(margin_ms / FRAME_MS)
    first = max(0, loud[0] - margin)
    last = min(len(db) - 1, loud[-1] + margin)

    cut_head = first * n
    cut_tail = len(audio) - (last + 1) * n
    return audio[cut_head:(last + 1) * n], cut_head / rate, max(0.0, cut_tail / rate)


def main():
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "audio")
    print(f"{'clip':36}{'dur':>7}{'head':>7}{'tail':>7}{'kept':>7}")
    for path in sorted(folder.glob("*.wav")):
        audio, rate = read_wav(path)
        kept, head, tail = trim(audio, rate)
        print(f"{path.stem:36}{len(audio)/rate:7.2f}{head:7.2f}{tail:7.2f}"
              f"{len(kept)/rate:7.2f}")


if __name__ == "__main__":
    main()
