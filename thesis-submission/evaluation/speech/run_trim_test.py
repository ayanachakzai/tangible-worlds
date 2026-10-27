"""
tests whether trimming leading and trailing quiet removes the junk words that
appear on the front of moonshine transcripts (phase 6a finding 7).

runs both corpora through moonshine once with no trim and once per trim
setting, then reports how many clips still start with a word that is not in
the reference.

usage: python run_trim_test.py
"""

import json
import time
from pathlib import Path

import moonshine_voice as mv
from moonshine_voice.transcriber import Transcriber

from run_moonshine import KEYTERMS, transcript_text
from trim_silence import read_wav, trim

AUDIO_DIR = Path("audio")
PHRASING_DIR = Path("audio_phrasing")
REF_PATH = Path("references.json")
OUT_PATH = Path("trim_results.json")

# sweeping the threshold because i do not know the right value. 40 leaves a
# short transient at the very start of most clips untouched, 30 removes it.
# project tuning, not a cited value.
DROPS = [None, 40.0, 30.0, 25.0]


def load_clips():
    """
    both corpora in one list. the phrasing clips have no references file, so
    the phrase comes from the filename, which is how they were recorded.
    written from scratch, no external source, this is just path handling.
    """
    clips = []

    refs = json.loads(REF_PATH.read_text())
    for cid in sorted(refs):
        path = AUDIO_DIR / f"{cid}.wav"
        if path.exists():
            clips.append(("corpus", cid, path, refs[cid]["reference"]))

    for path in sorted(PHRASING_DIR.glob("*.wav")):
        phrase = path.stem.rsplit("_t", 1)[0].replace("_", " ")
        clips.append(("phrasing", path.stem, path, phrase))

    return clips


def leading_junk(heard, reference):
    """
    finding 7 predicts a filler token stuck on the front. so the test is
    simply whether the first word of the transcript appears anywhere in the
    reference. "Thank you Add lightning" fails, "Add lightning" passes.
    empty reference clips are skipped, any output there is a different bug.
    written from scratch, no external source.
    """
    words = heard.lower().strip(" .,!?").split()
    if not words or not reference:
        return False
    return words[0].strip(".,!?") not in reference.lower().split()


def critical_tokens_kept(heard, reference):
    """
    exact match is the wrong measure, what matters is whether the words that
    drive the twelve schema fields survive. so this checks every reference
    word longer than three letters is present somewhere in the transcript.
    # ref: metric correction recorded in the phase 6a design diary entry
    # ref: written from scratch, no external source
    """
    if not reference:
        return True
    heard_words = set(heard.lower().replace(".", " ").replace(",", " ").split())
    for w in reference.lower().split():
        if len(w) > 3 and w not in heard_words:
            return False
    return True


def main():
    clips = load_clips()
    print(f"{len(clips)} clips")

    model_path, model_arch = mv.get_model_for_language("en")
    transcriber = Transcriber(model_path=model_path, model_arch=model_arch)
    transcriber.set_keyterms(KEYTERMS)
    print(f"arch {model_arch}")

    results = {}
    for drop in DROPS:
        name = "baseline" if drop is None else f"trim{int(drop)}"
        print(f"\n-- {name}")
        run = {}
        for group, cid, path, reference in clips:
            audio, rate = read_wav(path)
            head = 0.0
            if drop is not None:
                audio, head, _ = trim(audio, rate, drop_db=drop)

            start = time.perf_counter()
            heard = transcript_text(
                transcriber.transcribe_without_streaming(
                    list(audio), sample_rate=rate))
            elapsed = time.perf_counter() - start

            run[cid] = {
                "group": group,
                "heard": heard,
                "reference": reference,
                "head_trimmed_s": round(head, 2),
                "stt_s": round(elapsed, 3),
                "leading_junk": leading_junk(heard, reference),
                "critical_ok": critical_tokens_kept(heard, reference),
            }
            flag = "JUNK" if run[cid]["leading_junk"] else "    "
            print(f"   {flag} {cid:34} {heard[:44]}")

        results[name] = run
        OUT_PATH.write_text(json.dumps(results, indent=2))

    transcriber.close()

    print(f"\n{'run':10}{'junk':>8}{'critical ok':>14}")
    for name, run in results.items():
        junk = sum(1 for r in run.values() if r["leading_junk"])
        ok = sum(1 for r in run.values() if r["critical_ok"])
        print(f"{name:10}{junk:8}{ok:>10}/{len(run)}")

    print(f"\nwritten to {OUT_PATH}")


if __name__ == "__main__":
    main()
