"""
recomputes the refusal-threshold table from the four-prop capture.

this reads features.csv, the 986-row capture logged by
log_features_20260817.py, and scores it with the same nearest-centroid
classifier the tracker uses at runtime, so the reported table has a
reproducible artefact rather than a remembered number.

"""

import sys
import numpy as np
import pandas as pd

# ref: track_tabletop.py DEBUG_FEATURE_NAMES, same order as shape_colour_vector()
FEATURES = ["elongation", "circularity", "hu1", "hu2",
            "hue_mean", "hue_std", "sat_mean", "val_mean", "val_std"]

# ref: track_tabletop.py CLASS_SCALE
CLASS_SCALE = np.array([0.2424, 0.0562, 0.0263, 0.7915,
                        42.9082, 28.6348, 43.0794, 47.3566, 17.4596], np.float32)

CLASS_MARGIN = 1.4          # ref: track_tabletop.py
CENTROID_FRAMES = 135       # first n frames of each learned prop
LEARNED = [1, 2, 3]
UNSEEN = 4
THRESHOLDS = [0.50, 0.55, 0.60, 0.80]


def distance(z, centre):
    """rms of the scaled difference. ref: track_tabletop.py classify()"""
    return float(np.sqrt(np.mean((z - centre) ** 2)))


def main(path):
    d = pd.read_csv(path)
    x = d[FEATURES].to_numpy(np.float32)


    measured = x.std(axis=0, ddof=1)
    print("scale check, shipped vs measured spread of this capture")
    for name, ship, meas in zip(FEATURES, CLASS_SCALE, measured):
        print(f"  {name:<12} {ship:>9.4f}  {meas:>9.4f}")
    print()

    z = x / CLASS_SCALE
    label = d["label"].to_numpy()

    centroids, recognition_idx = {}, []
    for prop in LEARNED:
        rows = np.flatnonzero(label == prop)
        centroids[prop] = z[rows[:CENTROID_FRAMES]].mean(axis=0)
        recognition_idx.extend(rows[CENTROID_FRAMES:])
    recognition_idx = np.array(sorted(recognition_idx))
    refusal_idx = np.flatnonzero(label == UNSEEN)

    print(f"frames per prop: {dict(zip(*np.unique(label, return_counts=True)))}")
    print(f"centroid frames: {len(LEARNED)} x {CENTROID_FRAMES} = "
          f"{len(LEARNED) * CENTROID_FRAMES}")
    print(f"recognition frames: {len(recognition_idx)}")
    print(f"refusal frames:     {len(refusal_idx)}")
    print()

    scored = {}
    for i in np.concatenate([recognition_idx, refusal_idx]):
        ranked = sorted((distance(z[i], centroids[p]), p) for p in LEARNED)
        scored[i] = ranked

    for use_margin in (False, True):
        tag = "with runner-up margin" if use_margin else "distance only"
        print(f"--- {tag} ---")
        print(f"{'maxdist':>8}  {'recognised':>16}  {'refused':>12}  {'misassigned':>11}")
        for t in THRESHOLDS:
            correct = wrong = 0
            for i in recognition_idx:
                ranked = scored[i]
                best, best_id = ranked[0]
                if best > t:
                    continue
                if use_margin and ranked[1][0] <= best * CLASS_MARGIN:
                    continue
                if best_id == label[i]:
                    correct += 1
                else:
                    wrong += 1
            refused = 0
            for i in refusal_idx:
                ranked = scored[i]
                best, _ = ranked[0]
                if best > t or (use_margin and ranked[1][0] <= best * CLASS_MARGIN):
                    refused += 1
            print(f"{t:>8.2f}  {correct:>7}/{len(recognition_idx):<8}"
                  f"  {refused:>5}/{len(refusal_idx):<6}  {wrong:>11}")
        print()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "features.csv")