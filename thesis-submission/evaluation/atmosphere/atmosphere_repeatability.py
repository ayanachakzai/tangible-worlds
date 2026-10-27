"""
checks whether the atmosphere layer is deterministic.

five commands were each run three times from the same starting state and a
frame saved each time. this compares the three runs of each command pixel by
pixel and reports how many pixels differ and where they sit vertically, so the
determinism claim in the report has a reproducible artefact.

a pixel counts as different if any of its channels differs at all. no
tolerance is applied, because the claim being tested is exact repeatability,
not approximate similarity.

run:
    python atmosphere_repeatability.py <folder of frames>
"""

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image


def group_runs(folder):
    """collect the frames, grouped by which command produced them.

    handles both layouts: one subfolder per command, or flat files named like
    001_repeat_sunset_run_01.png. for flat files the leading counter and the
    trailing run number are both stripped, because the counter increments
    across the whole battery while the run number increments within one
    command. what is left is the command name, which is the group.
    """
    folder = Path(folder)
    groups = defaultdict(list)

    subdirs = [p for p in sorted(folder.iterdir()) if p.is_dir()]
    if subdirs:
        for d in subdirs:
            frames = sorted(p for p in d.iterdir() if p.suffix.lower() == ".png")
            if frames:
                groups[d.name] = frames
        return groups

    for p in sorted(folder.iterdir()):
        if p.suffix.lower() != ".png":
            continue
        parts = p.stem.split("_")
        if parts and parts[0].isdigit():        # leading battery counter
            parts = parts[1:]
        if parts and parts[-1].isdigit():       # trailing run number
            parts = parts[:-1]
        if parts and parts[-1] == "run":        # the word "run" itself
            parts = parts[:-1]
        key = "_".join(parts) or p.stem
        groups[key].append(p)
    return groups


def compare(frames):
    """compare every run against the first one. returns a dict of results."""
    images = [np.array(Image.open(f).convert("RGB"), dtype=np.int16) for f in frames]
    shapes = {im.shape for im in images}
    if len(shapes) > 1:
        return {"error": f"frame sizes differ: {shapes}"}

    h, w, _ = images[0].shape
    differing = np.zeros((h, w), dtype=bool)
    for other in images[1:]:
        differing |= (images[0] != other).any(axis=2)

    rows = np.flatnonzero(differing.any(axis=1))
    return {
        "frames": len(images),
        "size": (w, h),
        "total_pixels": w * h,
        "differing": int(differing.sum()),
        "row_span": (int(rows.min()), int(rows.max())) if rows.size else None,
        "row_count": int(rows.size),
    }


def main(folder):
    groups = group_runs(folder)
    if not groups:
        print(f"no png frames found under {folder}")
        return

    grand_diff = grand_total = 0
    spans = []

    for name, frames in sorted(groups.items()):
        r = compare(frames)
        print(f"{name}")
        if "error" in r:
            print(f"  {r['error']}\n")
            continue
        w, h = r["size"]
        print(f"  {r['frames']} runs, {w}x{h} = {r['total_pixels']:,} pixels")
        print(f"  differing pixels: {r['differing']}")
        if r["row_span"]:
            top, bottom = r["row_span"]
            print(f"  confined to rows {top}-{bottom} "
                  f"({r['row_count']} rows of {h})")
            spans.append((top, bottom))
        else:
            print("  frames are pixel-identical")
        print()
        grand_diff += r["differing"]
        grand_total += r["total_pixels"]

    print("-" * 50)
    print(f"across {len(groups)} commands: {grand_diff} differing pixels "
          f"of {grand_total:,} compared")
    if spans:
        print(f"all differences sit between rows {min(t for t, _ in spans)} "
              f"and {max(b for _, b in spans)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")