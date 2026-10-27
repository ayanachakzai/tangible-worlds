"""
log_features_20260817.py
------------------------
feature logger for Tangible Worlds. no learning, no decisions.

purpose
-------
area, height and colour have each failed in turn as identity evidence.
before writing any classifier, measure whether the props actually separate,
and on which features. this script records measurements while a prop is
handled, and writes one csv row per frame.

it reuses the tracker file unchanged. nothing here can affect tracking.

how to use
----------
one prop on the table at a time.
press a digit 1 to 9 to start recording under that label.
move the prop around, turn it over, slide it to different parts of the
table for about ten seconds.
press 0 to stop.
swap the prop, press the next digit, repeat.
press q to write the csv and quit.

external references
-------------------

Hu moments are the standard rotation and scale invariant shape descriptor:
Ming-Kuei Hu, "Visual pattern recognition by moment invariants",
IRE Transactions on Information Theory 8(2), 179-187, 1962.
DOI: 10.1109/TIT.1962.1057692
https://doi.org/10.1109/TIT.1962.1057692

interactive machine learning framing, for the classifier that may follow:
Rebecca Fiebrink and Perry R. Cook, "The Wekinator: a system for real-time,
interactive machine learning in music", ISMIR 2010.
https://www.wekinator.org
this file implements no part of Wekinator. it only gathers the small
user-provided example set that such an approach depends on.

project decisions
-----------------
recording only runs when exactly one prop is visible and no body is
present, so every row is unambiguously about the labelled prop.
shape features are computed from the same mask the tracker builds, rebuilt
here rather than added to the tracker, so the tracker file stays untouched.
"""

import csv, importlib.util, math, os, sys, time
import cv2
import numpy as np

TRACKER_FILE = "track_tabletop_simple_NOHEIGHT_20260817.py"
OUT_CSV = "features.csv"
WINDOW = "Tangible Worlds - Feature Logger"


def load_tracker(path):
    """import the tracker file by name so this script adds no new dependency."""
    if not os.path.exists(path):
        raise SystemExit(f"tracker file not found next to this script: {path}")
    spec = importlib.util.spec_from_file_location("tracker", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T = load_tracker(TRACKER_FILE)

COLUMNS = ["label", "t", "area_cm2", "height_p95_mm", "height_max_mm", "depth_m",
           "bbox_w_px", "bbox_h_px", "elongation", "extent", "solidity",
           "perimeter_px", "circularity",
           "hu1", "hu2", "hu3", "hu4", "hu5", "hu6", "hu7",
           "hue_mean", "hue_std", "sat_mean", "sat_std", "val_mean", "val_std"]


class FeatureLogger(T.SimpleHybridTracker):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.label = None

    def prop_mask(self, height, valid):
        """rebuild the tracker's prop mask so shape is measured on the same pixels."""
        mask = (valid & self.roi_mask(height.shape) &
                (height > self.threshold_m) &
                (height < T.HEIGHT_CEILING_MM / 1000.)).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, T.OPEN_KERNEL)
        return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, T.CLOSE_KERNEL)

    def shape_features(self, mask, bbox):
        """shape descriptors from the prop outline. all rotation tolerant."""
        x, y, w, h = bbox
        patch = mask[y:y+h, x:x+w]
        contours, _ = cv2.findContours(patch, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        c = max(contours, key=cv2.contourArea)
        px_area = float(cv2.contourArea(c))
        if px_area <= 0:
            return None

        (_, _), (rw, rh), _ = cv2.minAreaRect(c)
        short, long = sorted((float(rw), float(rh)))
        elongation = long / max(short, 1e-6)
        extent = px_area / max(float(w*h), 1e-6)
        hull_area = float(cv2.contourArea(cv2.convexHull(c)))
        solidity = px_area / max(hull_area, 1e-6)
        perimeter = float(cv2.arcLength(c, True))
        circularity = 4.*math.pi*px_area / max(perimeter*perimeter, 1e-6)

        # log scale keeps the seven Hu values in a comparable range.
        hu = cv2.HuMoments(cv2.moments(c)).flatten()
        hu = [float(-math.copysign(1., v) * math.log10(abs(v))) if abs(v) > 1e-30 else 0. for v in hu]
        return [elongation, extent, solidity, perimeter, circularity] + hu

    def colour_features(self, hsv, sel):
        """plain colour statistics. the tracker uses a histogram; these are
        easier to inspect in a spreadsheet and carry the same information."""
        out = []
        for channel in range(3):
            values = hsv[:, :, channel][sel].astype(np.float32)
            out.append(float(values.mean()) if values.size else 0.)
            out.append(float(values.std()) if values.size else 0.)
        return out

    def capture(self, rgb, depth, blobs, mask):
        """one csv row, only when a single prop is on the table."""
        if self.label is None or len(blobs) != 1:
            return
        b = blobs[0]
        shape = self.shape_features(mask, b["bbox"])
        if shape is None:
            return
        bgr = self.small_bgr(rgb, depth)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        x, y, w, h = b["bbox"]
        sel = np.zeros(mask.shape, bool)
        sel[y:y+h, x:x+w] = mask[y:y+h, x:x+w] > 0
        colour = self.colour_features(hsv, sel)
        self.rows.append([self.label, round(time.time(), 3),
                          round(b["area"], 2), round(b["height"], 2), round(b["max_height"], 2),
                          round(b["depth"], 3), w, h]
                         + [round(v, 5) for v in shape]
                         + [round(v, 2) for v in colour])

    def overlay(self, frame, blobs, body):
        state = f"recording label {self.label}" if self.label is not None else "idle, press 1-9"
        if body:
            state = "body present, not recording"
        elif self.label is not None and len(blobs) != 1:
            state = f"paused, {len(blobs)} props visible, need exactly 1"
        counts = {}
        for row in self.rows:
            counts[row[0]] = counts.get(row[0], 0) + 1
        tally = "  ".join(f"{k}:{v}" for k, v in sorted(counts.items())) or "no samples yet"
        cv2.putText(frame, state, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1)
        cv2.putText(frame, tally, (6, 34), cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 255, 0), 1)

    def write_csv(self):
        if not self.rows:
            print("[!] no samples recorded, nothing written")
            return
        with open(OUT_CSV, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(COLUMNS)
            writer.writerows(self.rows)
        counts = {}
        for row in self.rows:
            counts[row[0]] = counts.get(row[0], 0) + 1
        print(f"[*] wrote {len(self.rows)} rows to {OUT_CSV}")
        for label in sorted(counts):
            print(f"    label {label}: {counts[label]} samples")

    def run(self):
        self.connect(); cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        self.select_roi(); self.calibrate()
        print("[*] one prop at a time. digit 1-9 starts recording, 0 stops, q quits")

        while True:
            rgb, depth = self.frame()
            if depth is None: continue
            blobs, preview, body, _ = self.detect(rgb, depth)

            if not body:
                pts, valid = self.unproject(depth)
                height = pts @ self.n + self.c
                mask = self.prop_mask(height, valid)
                self.capture(rgb, depth, blobs, mask)

            for b in blobs:
                x, y, w, h = b["bbox"]
                cv2.rectangle(preview, (x, y), (x+w, y+h), (255, 255, 255), 1)
            self.overlay(preview, blobs, body)
            cv2.imshow(WINDOW, preview)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if ord("1") <= key <= ord("9"):
                self.label = chr(key)
                print(f"[*] recording label {self.label}")
            if key == ord("0") and self.label is not None:
                print(f"[*] stopped label {self.label}")
                self.label = None

        self.write_csv()
        self.session.on_new_frame = lambda: None
        self.session.on_stream_stopped = lambda: None
        cv2.destroyAllWindows(); cv2.waitKey(1)
        print("[*] stopped"); sys.stdout.flush(); os._exit(0)


if __name__ == "__main__": FeatureLogger().run()
