"""
runs every shortlisted faster-whisper checkpoint over the recorded corpus and
saves what each one heard, plus how long it took. no scoring here, that lives
in score.py so a scoring bug doesn't cost me a whole rerun.

usage: python run_bakeoff.py
"""

import gc
import json
import time
from pathlib import Path

from faster_whisper import WhisperModel

AUDIO_DIR = Path("audio")
REF_PATH = Path("references.json")
RESULTS_PATH = Path("bakeoff_results.json")

COMPUTE_TYPE = "int8"
DEVICE = "cpu"

# ordered small to large on purpose. the first few download in seconds and give
# me working results early, so if something is broken i find out before waiting
# on the 3gb large-v3 download.
# ".en" checkpoints are english-only and trained on narrower english. the
# same-size multilingual checkpoint is included beside each one because that is
# the actual hypothesis being tested: my accent may be failing on the variant,
# not on whisper.
# ref: https://arxiv.org/abs/2212.04356 (radford et al, whisper, sec 3.9 on
#      english-only vs multilingual model performance)
# ref: https://github.com/SYSTRAN/faster-whisper#usage
CHECKPOINTS = [
    "tiny.en",
    "base.en",
    "distil-small.en",
    "small.en",
    "small",
    "medium.en",
    "medium",
    "large-v3-turbo",
    "large-v3",
]

# the twelve-field atmosphere schema in serve.py is driven by a closed, known
# vocabulary. faster-whisper can bias the decoder toward supplied words, which
# is a legitimate accuracy win aimed exactly at the words that break my system.
# tested on and off as a second axis because if biasing lets a small checkpoint
# match a large one, that is the difference between 1.5gb and 3gb resident.
# ref: https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py
HOTWORDS = ("brighter dimmer warmer cooler misty foggy hazy dusk dawn overcast "
            "stormy lightning rain golden hour moonlight spooky midday horizon")


def load_corpus():
    refs = json.loads(REF_PATH.read_text())
    clips = []
    for cid in sorted(refs):
        path = AUDIO_DIR / f"{cid}.wav"
        if not path.exists():
            print(f"  missing audio for {cid}, skipping")
            continue
        clips.append((cid, str(path), refs[cid]["reference"]))
    return clips


def transcribe(model, path, hotwords):
    """
    one clip through one model, timed. faster-whisper returns a generator, so
    the list() is what actually forces the work to happen and has to sit inside
    the timer.
    condition_on_previous_text is off because these are independent short
    utterances with no shared context, and carrying context between them is a
    known trigger for repetition loops on short audio.
    ref: https://arxiv.org/abs/2212.04356 (radford et al, whisper, sec 4.5 on
         repetition looping in long-form decoding)
    ref: https://github.com/SYSTRAN/faster-whisper#usage
    """
    start = time.perf_counter()
    segments, info = model.transcribe(
        path,
        language="en",
        beam_size=5,
        condition_on_previous_text=False,
        vad_filter=False,
        hotwords=hotwords,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    elapsed = time.perf_counter() - start
    return text, elapsed


def main():
    clips = load_corpus()
    if not clips:
        print("no clips found. run record_corpus.py first.")
        return

    print(f"{len(clips)} clips, {len(CHECKPOINTS)} checkpoints, hotwords on and off")
    print(f"{len(clips) * len(CHECKPOINTS) * 2} transcriptions total\n")

    try:
        results = json.loads(RESULTS_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        results = {}

    for checkpoint in CHECKPOINTS:
        for use_hotwords in (False, True):
            run_id = f"{checkpoint}|hotwords={use_hotwords}"
            if run_id in results:
                print(f"[{run_id}] already done, skipping")
                continue

            print(f"\n── {run_id}")
            try:
                t0 = time.perf_counter()
                model = WhisperModel(checkpoint, device=DEVICE,
                                     compute_type=COMPUTE_TYPE)
                load_s = time.perf_counter() - t0
                print(f"   loaded in {load_s:.1f}s")
            except Exception as e:
                # a checkpoint that fails to download or convert should not
                # kill a run that has already spent twenty minutes.
                print(f"   FAILED to load: {e}")
                results[run_id] = {"error": str(e)}
                RESULTS_PATH.write_text(json.dumps(results, indent=2))
                continue

            run = {"load_s": round(load_s, 2), "clips": {}}
            for cid, path, reference in clips:
                try:
                    text, elapsed = transcribe(
                        model, path, HOTWORDS if use_hotwords else None)
                except Exception as e:
                    text, elapsed = f"<error: {e}>", 0.0
                run["clips"][cid] = {
                    "heard": text,
                    "reference": reference,
                    "stt_s": round(elapsed, 3),
                }
                print(f"   {cid}  {elapsed:5.2f}s  {text[:60]}")

            results[run_id] = run
            RESULTS_PATH.write_text(json.dumps(results, indent=2))

            # drop the model before loading the next one, otherwise two
            # checkpoints sit in memory at once on a 16gb machine.
            del model
            gc.collect()

    print(f"\ndone. results in {RESULTS_PATH}")


if __name__ == "__main__":
    main()
