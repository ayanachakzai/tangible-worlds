"""
Tangible Worlds RC6PROPS detector qualification.

Purpose:
- qualify which everyday props the current iPhone LiDAR setup can actually see
- separate foreground fragmentation from downstream filter rejection
- keep identity, learning, merge state and semantics completely out of this test
- make the live preview large enough to inspect the real RGB frame and depth mask

This file keeps the RC4Q physical detector structure:
Record3D RGB + LiDAR depth
-> select tabletop ROI
-> empty-table plane calibration
-> height-above-plane foreground
-> morphology
-> edge-connected body exclusion
-> connected components
-> metric area / height filters

The main diagnostic additions are:
- full-resolution RGB is used for the visual preview instead of first shrinking
  it to the depth grid
- the actual incoming RGB and depth resolutions are printed and saved
- every raw connected component is logged, including rejected components and why
- one-prop, five-position qualification trials can be run from the same window

Keys after calibration:
- p: enter prop-naming mode inside the preview window
- type the prop name, ENTER to confirm, BACKSPACE to edit, ESC to cancel
- 1..5: start a 20 second trial for that table position
- s: save a diagnostic snapshot
- q: quit and write the summary

Project decision:
- prop naming stays inside the OpenCV event loop. A blocking terminal input()
  call froze the live Record3D/OpenCV loop on macOS during the first RC6 test.

Use one physical prop at a time during a qualification trial.

RC6 close9 variant:
- identical to RC6PROPS v2 except the default morphological close is 9x9
- run label defaults to close9
- this isolates component grouping as the only detector variable in this pass

# ref: Record3D official Python demo
# https://github.com/marek-simonik/record3d/blob/master/demo-main.py
# ref: OpenCV ROI, morphology and connected components
# https://docs.opencv.org/4.x/d7/dfc/group__highgui.html
# https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html
# https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html
# ref: Riemann et al. 2018, FlowPut, DOI 10.1145/3191763
"""

import argparse
import csv
import json
import os
import time
import warnings
from collections import deque
from threading import Event

import cv2
import numpy as np
from record3d import Record3DStream


WINDOW = "Tangible Worlds - RC6PROPS Qualification"
DEBUG_ROOT = "tracker_debug"

CALIBRATION_FRAMES = 30
CALIBRATION_MULT = 5.0
MIN_THRESHOLD_MM = 6.0
MAX_THRESHOLD_MM = 20.0
HEIGHT_CEILING_MM = 150.0
MIN_AREA_CM2 = 3.0
HEIGHT_PCT = 95.0
ROI_BORDER_PX = 2

OPEN_KERNEL = np.ones((3, 3), np.uint8)

BODY_EDGE_PX = 2
BODY_MIN_AREA_CM2 = 20.0

TRIAL_SECONDS = 20.0
ROLLING_SECONDS = 5.0
PASS_DETECTION_RATE = 0.95
PASS_SINGLE_RATE = 0.95
PASS_AREA_CV = 0.15

PREVIEW_WIDTH = 1600
PREVIEW_HEIGHT = 920
STATUS_HEIGHT = 180


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--close-kernel",
        type=int,
        default=9,
        choices=(5, 9),
        help="morphological close kernel size. RC4Q baseline is 5; RC6 comparison uses 9.",
    )
    parser.add_argument(
        "--run-label",
        default="close9",
        help="short label saved with the run, e.g. baseline, close9, lower_camera",
    )
    return parser.parse_args()


def fit_plane(points):
    """fit one plane to the table.
    # ref: https://numpy.org/doc/stable/reference/generated/numpy.linalg.svd.html
    # ref: Riemann et al. 2018, FlowPut, section 4.1.2
    """
    if len(points) < 100:
        raise RuntimeError("not enough valid table points")
    centre = points.mean(axis=0)
    _, _, vh = np.linalg.svd(points - centre, full_matrices=False)
    n = vh[-1] / np.linalg.norm(vh[-1])
    c = -float(n.dot(centre))
    if c < 0:
        n, c = -n, -c
    return n.astype(np.float32), c, centre.astype(np.float32)


def plane_axes(n):
    u = np.array([1.0, 0.0, 0.0], np.float32)
    u -= n * float(u.dot(n))
    if np.linalg.norm(u) < 1e-6:
        u = np.array([0.0, 1.0, 0.0], np.float32)
        u -= n * float(u.dot(n))
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    v /= np.linalg.norm(v)
    return u, v


def safe_slug(text):
    out = "".join(ch.lower() if ch.isalnum() else "_" for ch in text.strip())
    out = "_".join(part for part in out.split("_") if part)
    return out[:60] or "unnamed"


def fit_inside(image, max_w, max_h, interpolation=cv2.INTER_AREA):
    h, w = image.shape[:2]
    if h <= 0 or w <= 0:
        return image, 1.0
    scale = min(max_w / w, max_h / h)
    scale = max(scale, 1e-6)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    if nw == w and nh == h:
        return image.copy(), 1.0
    return cv2.resize(image, (nw, nh), interpolation=interpolation), scale


class PropsQualification:
    def __init__(self, args):
        self.args = args
        self.close_kernel = np.ones((args.close_kernel, args.close_kernel), np.uint8)
        self.event = Event()
        self.session = None
        self.intr = None
        self.roi = None
        self.n = None
        self.c = None
        self.origin = None
        self.u = None
        self.v = None
        self.threshold_m = MIN_THRESHOLD_MM / 1000.0
        self.body_background = None
        self._current_pts = None

        self.debug_dir = None
        self.components_csv = None
        self.frames_csv = None
        self.frame_count = 0
        self.stream_shape_logged = False
        self.rgb_shape = None
        self.depth_shape = None
        self.calibration_info = {}

        self.current_prop = None
        self.naming_mode = False
        self.name_buffer = ""
        self.active_trial = None
        self.trial_results = []
        self.rolling = deque()
        self.latest_summary = "no trial yet"
        self.last_preview = None
        self.last_depth = None
        self.last_height = None
        self.last_mask = None
        self.last_records = []

    def on_new_frame(self):
        self.event.set()

    def on_stream_stopped(self):
        print("\n[!] Record3D stream stopped")

    def setup_debug(self):
        stamp = time.strftime("%Y%m%d_%H%M%S")
        label = safe_slug(self.args.run_label)
        self.debug_dir = os.path.join(DEBUG_ROOT, f"rc6props_{label}_{stamp}")
        os.makedirs(self.debug_dir, exist_ok=True)

        self.components_csv = os.path.join(self.debug_dir, "components.csv")
        with open(self.components_csv, "w", newline="") as f:
            csv.writer(f).writerow([
                "time", "frame", "prop", "trial_position", "trial_active",
                "component_index", "accepted", "reason",
                "area_cm2", "height_p95_mm", "height_max_mm",
                "x_norm", "y_norm", "tx_cm", "ty_cm",
                "bbox_x", "bbox_y", "bbox_w", "bbox_h",
            ])

        self.frames_csv = os.path.join(self.debug_dir, "frames.csv")
        with open(self.frames_csv, "w", newline="") as f:
            csv.writer(f).writerow([
                "time", "frame", "prop", "trial_position", "trial_active",
                "raw_components", "accepted_components", "rejected_components",
                "rolling_any_detection_rate", "rolling_single_component_rate",
            ])
        print(f"[d] debug folder: {self.debug_dir}")

    def connect(self):
        """# ref: Record3D official Python demo."""
        devices = Record3DStream.get_connected_devices()
        print(f"[*] found {len(devices)} Record3D device(s)")
        if not devices:
            raise SystemExit("no Record3D device found")
        self.session = Record3DStream()
        self.session.on_new_frame = self.on_new_frame
        self.session.on_stream_stopped = self.on_stream_stopped
        self.session.connect(devices[0])
        print("[*] connected")

    def frame(self):
        """# ref: Record3D official Python demo."""
        self.event.wait()
        self.event.clear()
        rgb = np.asarray(self.session.get_rgb_frame())
        depth = np.asarray(self.session.get_depth_frame(), dtype=np.float32)
        if rgb.size == 0 or depth.ndim != 2 or depth.size == 0:
            return None, None
        if not self.stream_shape_logged:
            rh, rw = rgb.shape[:2]
            dh, dw = depth.shape
            self.rgb_shape = (rh, rw)
            self.depth_shape = (dh, dw)
            print(f"[*] live stream resolution: RGB={rw}x{rh} depth={dw}x{dh}")
            print("[*] RC6 preview uses the incoming RGB frame directly; detection remains on the depth grid")
            self.stream_shape_logged = True
        return rgb, depth

    def raw_intrinsics(self):
        k = self.session.get_intrinsic_mat()
        if hasattr(k, "fx"):
            return float(k.fx), float(k.fy), float(k.tx), float(k.ty)
        a = np.asarray(k, dtype=np.float64)
        if a.shape == (3, 3):
            return float(a[0, 0]), float(a[1, 1]), float(a[0, 2]), float(a[1, 2])
        raise RuntimeError(f"unrecognised Record3D intrinsics: {type(k)}")

    def resolve_intrinsics(self, depth, rgb):
        # Same scaling assumption as RC4Q: Record3D intrinsics arrive in RGB units.
        dh, dw = depth.shape
        rh, rw = rgb.shape[:2]
        fx, fy, cx, cy = self.raw_intrinsics()
        return fx * dw / rw, fy * dh / rh, cx * dw / rw, cy * dh / rh

    def unproject(self, depth):
        """pinhole X=(u-cx)Z/fx, Y=(v-cy)Z/fy.
        # ref: Record3D official Python demo.
        """
        fx, fy, cx, cy = self.intr
        dh, dw = depth.shape
        px, py = np.meshgrid(
            np.arange(dw, dtype=np.float32),
            np.arange(dh, dtype=np.float32),
        )
        valid = np.isfinite(depth) & (depth > 0.05) & (depth < 5.0)
        x = np.zeros_like(depth)
        y = np.zeros_like(depth)
        x[valid] = (px[valid] - cx) * depth[valid] / fx
        y[valid] = (py[valid] - cy) * depth[valid] / fy
        return np.stack([x, y, depth], axis=-1), valid

    def roi_mask(self, shape):
        mask = np.zeros(shape, dtype=bool)
        x, y, w, h = self.roi
        mask[y:y + h, x:x + w] = True
        return mask

    def depth_box_to_rgb(self, box, rgb_shape, depth_shape):
        x, y, w, h = box
        rh, rw = rgb_shape[:2]
        dh, dw = depth_shape
        sx = rw / float(dw)
        sy = rh / float(dh)
        return (
            int(round(x * sx)),
            int(round(y * sy)),
            int(round(w * sx)),
            int(round(h * sy)),
        )

    def depth_roi_to_rgb(self, rgb_shape, depth_shape):
        return self.depth_box_to_rgb(self.roi, rgb_shape, depth_shape)

    def select_roi(self):
        print("[*] select ONLY the usable tabletop, then press ENTER")
        print("[*] ROI selection is shown from the clearer RGB frame, then mapped back to the depth grid")
        while True:
            rgb, depth = self.frame()
            if depth is None:
                continue
            if self.intr is None:
                self.intr = self.resolve_intrinsics(depth, rgb)
                print("[*] depth intrinsics:", *[f"{v:.1f}" for v in self.intr])

            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            selection, scale = fit_inside(bgr, 1300, 800)
            x, y, w, h = cv2.selectROI(WINDOW, selection, True, False)
            if w < 40 or h < 40:
                print("[!] selection cancelled or too small")
                continue

            rgb_x = x / scale
            rgb_y = y / scale
            rgb_w = w / scale
            rgb_h = h / scale
            rh, rw = rgb.shape[:2]
            dh, dw = depth.shape
            dx = int(round(rgb_x * dw / rw))
            dy = int(round(rgb_y * dh / rh))
            dw_roi = int(round(rgb_w * dw / rw))
            dh_roi = int(round(rgb_h * dh / rh))

            dx = max(0, min(dx, dw - 1))
            dy = max(0, min(dy, dh - 1))
            dw_roi = max(1, min(dw_roi, dw - dx))
            dh_roi = max(1, min(dh_roi, dh - dy))
            if dw_roi <= 10 or dh_roi <= 10:
                print("[!] mapped depth ROI is too small")
                continue

            self.roi = (dx, dy, dw_roi, dh_roi)
            print(f"[*] depth work area: x={dx} y={dy} w={dw_roi} h={dh_roi}")
            return

    def body_mask(self, height, valid):
        """above-table mask for body reasoning. no prop ceiling here.
        # ref: Riemann et al. 2018, FlowPut, sections 4.1.2 and 4.1.3
        # ref: https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html
        """
        mask = (
            valid
            & self.roi_mask(height.shape)
            & (height > self.threshold_m)
        ).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, OPEN_KERNEL)
        return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.close_kernel)

    def calibrate(self):
        """RC4Q table-plane calibration, without identity-state resets."""
        print(f"[*] empty table for {CALIBRATION_FRAMES} frames; keep hands and props out")
        depths = []
        while len(depths) < CALIBRATION_FRAMES:
            _, depth = self.frame()
            if depth is None:
                continue
            depths.append(depth.copy())
            print(f"\rcalibrating {len(depths)}/{CALIBRATION_FRAMES}", end="", flush=True)

        stack = np.stack(depths)
        safe = np.where(np.isfinite(stack), stack, np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            baseline = np.nanmedian(safe, axis=0).astype(np.float32)

        pts, valid = self.unproject(baseline)
        use = valid & self.roi_mask(baseline.shape)
        self.n, self.c, self.origin = fit_plane(pts[use])
        self.u, self.v = plane_axes(self.n)

        noise = []
        for depth in depths:
            frame_pts, frame_valid = self.unproject(depth)
            frame_use = frame_valid & self.roi_mask(depth.shape)
            residual = (frame_pts @ self.n + self.c)[frame_use]
            residual = residual[np.abs(residual) < 0.02]
            if residual.size:
                noise.append(float(np.std(residual) * 1000.0))
        if not noise:
            raise RuntimeError("could not measure table noise")

        noise_mm = float(np.median(noise))
        threshold_mm = float(np.clip(
            noise_mm * CALIBRATION_MULT,
            MIN_THRESHOLD_MM,
            MAX_THRESHOLD_MM,
        ))
        self.threshold_m = threshold_mm / 1000.0

        baseline_pts, baseline_valid = self.unproject(baseline)
        baseline_height = baseline_pts @ self.n + self.c
        self.body_background = self.body_mask(baseline_height, baseline_valid)
        self.body_background = cv2.dilate(
            self.body_background,
            self.close_kernel,
            iterations=1,
        )

        self.calibration_info = {
            "noise_mm": noise_mm,
            "threshold_mm": threshold_mm,
            "roi_depth": [int(v) for v in self.roi],
            "intrinsics_depth": [float(v) for v in self.intr],
            "rgb_resolution": None if self.rgb_shape is None else [int(self.rgb_shape[1]), int(self.rgb_shape[0])],
            "depth_resolution": None if self.depth_shape is None else [int(self.depth_shape[1]), int(self.depth_shape[0])],
            "close_kernel": int(self.args.close_kernel),
            "run_label": self.args.run_label,
        }
        with open(os.path.join(self.debug_dir, "calibration.json"), "w") as f:
            json.dump(self.calibration_info, f, indent=2)

        print(f"\n[*] calibrated: noise={noise_mm:.1f}mm threshold={threshold_mm:.1f}mm close={self.args.close_kernel}x{self.args.close_kernel}")
        if noise_mm > 2.5:
            print(f"[!] noise {noise_mm:.1f}mm is high. quit, pick a flatter ROI, calibrate again")

    def body_present(self, height, valid, depth):
        """return all qualifying edge-entering body components.
        # ref: Riemann et al. 2018, FlowPut, sections 4.1.3 and 9.3
        """
        current = self.body_mask(height, valid)
        count, labels, stats, cents = cv2.connectedComponentsWithStats(current, 8)
        fx, fy, _, _ = self.intr
        pixel_area = (depth ** 2) / (fx * fy)
        rx, ry, rw, rh = self.roi
        background = self.body_background
        if background is None:
            background = np.zeros_like(current)
        combined = np.zeros_like(current, dtype=bool)
        body_records = []

        for i in range(1, count):
            x = int(stats[i, cv2.CC_STAT_LEFT])
            y = int(stats[i, cv2.CC_STAT_TOP])
            w = int(stats[i, cv2.CC_STAT_WIDTH])
            h = int(stats[i, cv2.CC_STAT_HEIGHT])
            touches_edge = (
                x <= rx + BODY_EDGE_PX
                or y <= ry + BODY_EDGE_PX
                or x + w >= rx + rw - BODY_EDGE_PX
                or y + h >= ry + rh - BODY_EDGE_PX
            )
            if not touches_edge:
                continue
            novel = (labels == i) & valid & (background == 0)
            if not np.any(novel):
                continue
            area = float(pixel_area[novel].sum() * 10000.0)
            if not np.isfinite(area) or area < BODY_MIN_AREA_CM2:
                continue

            combined |= novel
            heights_mm = height[novel] * 1000.0
            centre = np.median(self._current_pts[novel], axis=0)
            cx, cy = cents[i]
            record = {
                "index": int(i),
                "bbox": (x, y, w, h),
                "accepted": False,
                "reason": "body_exclusion",
                "area": area,
                "height": float(np.percentile(heights_mm, HEIGHT_PCT)) if heights_mm.size else float("nan"),
                "max_height": float(heights_mm.max()) if heights_mm.size else float("nan"),
                "x": float((cx - rx) / rw),
                "y": float((cy - ry) / rh),
                "tx": float("nan"),
                "ty": float("nan"),
            }
            if np.all(np.isfinite(centre)):
                rel = centre - self.origin
                record["tx"] = float(rel.dot(self.u) * 100.0)
                record["ty"] = float(rel.dot(self.v) * 100.0)
            body_records.append(record)

        if body_records:
            return True, combined, body_records
        return False, None, []

    def inspect_components(self, rgb, depth):
        """Run the RC4Q detector and retain every raw component and rejection reason."""
        pts, valid = self.unproject(depth)
        self._current_pts = pts
        height = pts @ self.n + self.c
        body, body_pixels, body_records = self.body_present(height, valid, depth)

        mask = (
            valid
            & self.roi_mask(depth.shape)
            & (height > self.threshold_m)
            & (height < HEIGHT_CEILING_MM / 1000.0)
        ).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, OPEN_KERNEL)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.close_kernel)
        if body_pixels is not None:
            mask[body_pixels] = 0

        count, labels, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
        fx, fy, _, _ = self.intr
        pixel_area = (depth ** 2) / (fx * fy)
        rx, ry, rw, rh = self.roi
        records = []

        for i in range(1, count):
            x = int(stats[i, cv2.CC_STAT_LEFT])
            y = int(stats[i, cv2.CC_STAT_TOP])
            w = int(stats[i, cv2.CC_STAT_WIDTH])
            h = int(stats[i, cv2.CC_STAT_HEIGHT])
            cx, cy = cents[i]
            record = {
                "index": int(i),
                "bbox": (x, y, w, h),
                "accepted": False,
                "reason": "",
                "area": float("nan"),
                "height": float("nan"),
                "max_height": float("nan"),
                "x": float((cx - rx) / rw),
                "y": float((cy - ry) / rh),
                "tx": float("nan"),
                "ty": float("nan"),
            }

            if (
                x <= rx + ROI_BORDER_PX
                or y <= ry + ROI_BORDER_PX
                or x + w >= rx + rw - ROI_BORDER_PX
                or y + h >= ry + rh - ROI_BORDER_PX
            ):
                record["reason"] = "roi_edge"
                records.append(record)
                continue

            sel = (labels == i) & valid
            if not np.any(sel):
                record["reason"] = "no_valid_depth_pixels"
                records.append(record)
                continue

            area = float(pixel_area[sel].sum() * 10000.0)
            heights_mm = height[sel] * 1000.0
            if heights_mm.size == 0:
                record["reason"] = "no_height_pixels"
                records.append(record)
                continue

            height_mm = float(np.percentile(heights_mm, HEIGHT_PCT))
            max_mm = float(heights_mm.max())
            centre = np.median(pts[sel], axis=0)
            record["area"] = area
            record["height"] = height_mm
            record["max_height"] = max_mm

            if not np.isfinite(area) or not np.isfinite(height_mm) or not np.isfinite(max_mm):
                record["reason"] = "nonfinite_measurement"
                records.append(record)
                continue
            if not np.all(np.isfinite(centre)):
                record["reason"] = "nonfinite_centre"
                records.append(record)
                continue
            if area < MIN_AREA_CM2:
                record["reason"] = "below_min_area"
                records.append(record)
                continue
            if max_mm > HEIGHT_CEILING_MM:
                record["reason"] = "above_height_ceiling"
                records.append(record)
                continue

            rel = centre - self.origin
            record["tx"] = float(rel.dot(self.u) * 100.0)
            record["ty"] = float(rel.dot(self.v) * 100.0)
            record["accepted"] = True
            record["reason"] = "accepted"
            records.append(record)

        records.extend(body_records)
        return records, mask, height, body

    def trial_position(self):
        if self.active_trial is None:
            return ""
        return str(self.active_trial["position"])

    def write_component_rows(self, records, now):
        prop = self.current_prop or ""
        position = self.trial_position()
        active = int(self.active_trial is not None)
        with open(self.components_csv, "a", newline="") as f:
            writer = csv.writer(f)
            for r in records:
                x, y, w, h = r["bbox"]
                writer.writerow([
                    f"{now:.6f}", self.frame_count, prop, position, active,
                    r["index"], int(r["accepted"]), r["reason"],
                    self.csv_num(r["area"]), self.csv_num(r["height"]), self.csv_num(r["max_height"]),
                    self.csv_num(r["x"]), self.csv_num(r["y"]), self.csv_num(r["tx"]), self.csv_num(r["ty"]),
                    x, y, w, h,
                ])

    @staticmethod
    def csv_num(value):
        return "" if not np.isfinite(value) else f"{float(value):.6f}"

    def rolling_rates(self, now, accepted_count):
        self.rolling.append((now, accepted_count))
        while self.rolling and now - self.rolling[0][0] > ROLLING_SECONDS:
            self.rolling.popleft()
        if not self.rolling:
            return 0.0, 0.0
        any_rate = sum(1 for _, n in self.rolling if n >= 1) / len(self.rolling)
        single_rate = sum(1 for _, n in self.rolling if n == 1) / len(self.rolling)
        return any_rate, single_rate

    def write_frame_row(self, records, now, any_rate, single_rate):
        accepted = sum(1 for r in records if r["accepted"])
        rejected = len(records) - accepted
        with open(self.frames_csv, "a", newline="") as f:
            csv.writer(f).writerow([
                f"{now:.6f}", self.frame_count, self.current_prop or "",
                self.trial_position(), int(self.active_trial is not None),
                len(records), accepted, rejected,
                f"{any_rate:.6f}", f"{single_rate:.6f}",
            ])

    def begin_prop_entry(self):
        # Keep naming inside cv2.waitKey. Blocking on terminal input() stops
        # the live OpenCV/Record3D event loop on macOS.
        if self.active_trial is not None:
            print("[!] finish the active trial before changing prop")
            return
        self.naming_mode = True
        self.name_buffer = self.current_prop or ""
        self.latest_summary = "NAME PROP: type in this window, ENTER confirm, ESC cancel"
        print("\n[*] prop naming mode: type in the preview, ENTER confirm, ESC cancel")

    def handle_prop_entry_key(self, key):
        if not self.naming_mode:
            return False

        if key in (10, 13):
            name = self.name_buffer.strip()
            if name:
                self.current_prop = name
                self.latest_summary = f"prop set: {name}. press 1..5 to run a 20s position trial"
                print(f"[*] current prop: {name}")
            else:
                self.latest_summary = "prop name unchanged"
                print("[!] prop name unchanged")
            self.naming_mode = False
            self.name_buffer = ""
            return True

        if key == 27:
            self.naming_mode = False
            self.name_buffer = ""
            self.latest_summary = f"prop: {self.current_prop or 'none'}"
            print("[*] prop naming cancelled")
            return True

        if key in (8, 127):
            self.name_buffer = self.name_buffer[:-1]
            return True

        if 32 <= key <= 126 and len(self.name_buffer) < 48:
            self.name_buffer += chr(key)
            return True

        return True

    def start_trial(self, position):
        if self.current_prop is None:
            print("[!] press p and name the prop first")
            return
        if self.active_trial is not None:
            print("[!] a trial is already running")
            return

        self.active_trial = {
            "prop": self.current_prop,
            "position": int(position),
            "start": time.time(),
            "frames": 0,
            "any_frames": 0,
            "single_frames": 0,
            "areas": [],
            "raw_counts": [],
            "rejection_counts": {},
        }
        self.rolling.clear()
        self.latest_summary = f"trial running: {self.current_prop} position {position}"
        print(f"[*] started {TRIAL_SECONDS:.0f}s trial: {self.current_prop}, position {position}")

    def update_trial(self, records, now):
        if self.active_trial is None:
            return
        t = self.active_trial
        accepted = [r for r in records if r["accepted"]]
        t["frames"] += 1
        t["raw_counts"].append(len(records))
        if len(accepted) >= 1:
            t["any_frames"] += 1
        if len(accepted) == 1:
            t["single_frames"] += 1
            if np.isfinite(accepted[0]["area"]):
                t["areas"].append(float(accepted[0]["area"]))
        for r in records:
            if r["accepted"]:
                continue
            reason = r["reason"]
            t["rejection_counts"][reason] = t["rejection_counts"].get(reason, 0) + 1

        if now - t["start"] >= TRIAL_SECONDS:
            self.finish_trial(now)

    def finish_trial(self, now):
        t = self.active_trial
        if t is None:
            return
        frames = max(1, t["frames"])
        any_rate = t["any_frames"] / frames
        single_rate = t["single_frames"] / frames
        areas = np.asarray(t["areas"], dtype=np.float64)
        area_mean = float(np.mean(areas)) if areas.size else float("nan")
        area_std = float(np.std(areas)) if areas.size else float("nan")
        area_cv = area_std / area_mean if areas.size and area_mean > 0 else float("inf")
        passed = (
            any_rate >= PASS_DETECTION_RATE
            and single_rate >= PASS_SINGLE_RATE
            and area_cv <= PASS_AREA_CV
        )
        result = {
            "prop": t["prop"],
            "position": t["position"],
            "start_time": t["start"],
            "end_time": now,
            "frames": t["frames"],
            "any_detection_rate": any_rate,
            "single_component_rate": single_rate,
            "area_mean_cm2": None if not np.isfinite(area_mean) else area_mean,
            "area_std_cm2": None if not np.isfinite(area_std) else area_std,
            "area_cv": None if not np.isfinite(area_cv) else area_cv,
            "rejection_counts": t["rejection_counts"],
            "pass": bool(passed),
        }
        self.trial_results.append(result)
        verdict = "PASS" if passed else "FAIL"
        cv_text = "n/a" if not np.isfinite(area_cv) else f"{area_cv * 100:.1f}%"
        self.latest_summary = (
            f"{verdict} {t['prop']} pos {t['position']}: "
            f"detect {any_rate * 100:.1f}% single {single_rate * 100:.1f}% area cv {cv_text}"
        )
        print("\n[trial] " + self.latest_summary)
        self.active_trial = None
        self.rolling.clear()
        self.save_summary()

    def prop_summary(self, prop):
        all_rows = [r for r in self.trial_results if r["prop"] == prop]
        latest = {}
        for row in all_rows:
            latest[row["position"]] = row
        rows = [latest[pos] for pos in sorted(latest)]
        positions = sorted(latest)
        complete = all(pos in latest for pos in range(1, 6))
        all_pass = complete and all(latest[pos]["pass"] for pos in range(1, 6))
        return rows, complete, all_pass

    def save_summary(self):
        props = {}
        for prop in sorted({r["prop"] for r in self.trial_results}):
            rows, complete, all_pass = self.prop_summary(prop)
            props[prop] = {
                "positions_completed": sorted({r["position"] for r in rows}),
                "complete_five_positions": complete,
                "overall_pass": all_pass,
            }
        payload = {
            "run_label": self.args.run_label,
            "close_kernel": self.args.close_kernel,
            "criteria": {
                "trial_seconds": TRIAL_SECONDS,
                "detection_rate_min": PASS_DETECTION_RATE,
                "single_component_rate_min": PASS_SINGLE_RATE,
                "area_cv_max": PASS_AREA_CV,
                "positions_required": 5,
            },
            "calibration": self.calibration_info,
            "trials": self.trial_results,
            "props": props,
        }
        with open(os.path.join(self.debug_dir, "qualification_summary.json"), "w") as f:
            json.dump(payload, f, indent=2)

    def rgb_overlay(self, rgb, depth, records):
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        roi_rgb = self.depth_roi_to_rgb(bgr.shape, depth.shape)
        rx, ry, rw, rh = roi_rgb
        cv2.rectangle(bgr, (rx, ry), (rx + rw, ry + rh), (255, 255, 255), 2)
        cv2.putText(
            bgr, "full RGB preview", (20, 34), cv2.FONT_HERSHEY_SIMPLEX,
            0.9, (255, 255, 255), 2, cv2.LINE_AA,
        )

        for r in records:
            x, y, w, h = self.depth_box_to_rgb(r["bbox"], bgr.shape, depth.shape)
            colour = (80, 220, 80) if r["accepted"] else (60, 80, 235)
            cv2.rectangle(bgr, (x, y), (x + w, y + h), colour, 2)
            if r["accepted"]:
                label = f"c{r['index']} {r['area']:.1f}cm2 {r['height']:.0f}mm"
            else:
                area = "?" if not np.isfinite(r["area"]) else f"{r['area']:.1f}cm2"
                label = f"c{r['index']} reject:{r['reason']} {area}"
            cv2.putText(
                bgr, label, (x, max(24, y - 7)), cv2.FONT_HERSHEY_SIMPLEX,
                0.55, colour, 2, cv2.LINE_AA,
            )
        return bgr

    def mask_overlay(self, mask, records):
        canvas = np.zeros((mask.shape[0], mask.shape[1], 3), dtype=np.uint8)
        canvas[mask > 0] = (55, 55, 55)
        for r in records:
            x, y, w, h = r["bbox"]
            colour = (80, 220, 80) if r["accepted"] else (60, 80, 235)
            cv2.rectangle(canvas, (x, y), (x + w, y + h), colour, 1)
            cv2.putText(
                canvas, str(r["index"]), (x, min(mask.shape[0] - 4, y + 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, colour, 1, cv2.LINE_AA,
            )
        rx, ry, rw, rh = self.roi
        cv2.rectangle(canvas, (rx, ry), (rx + rw, ry + rh), (255, 255, 255), 1)
        cv2.putText(
            canvas, "depth component mask", (5, 15), cv2.FONT_HERSHEY_SIMPLEX,
            0.42, (255, 255, 255), 1, cv2.LINE_AA,
        )
        return canvas

    def status_panel(self, width, now, records, any_rate, single_rate, fps):
        panel = np.zeros((STATUS_HEIGHT, width, 3), dtype=np.uint8)
        accepted = sum(1 for r in records if r["accepted"])
        rejected = len(records) - accepted
        rgb_text = "?" if self.rgb_shape is None else f"{self.rgb_shape[1]}x{self.rgb_shape[0]}"
        depth_text = "?" if self.depth_shape is None else f"{self.depth_shape[1]}x{self.depth_shape[0]}"

        prop_line = f"prop: {self.current_prop or 'none'} | keys: p=name prop, 1..5=start 20s position trial, s=snapshot, q=quit"
        summary_line = self.latest_summary
        if self.naming_mode:
            shown = self.name_buffer if self.name_buffer else "_"
            prop_line = "NAMING PROP: type here | ENTER confirm | BACKSPACE edit | ESC cancel"
            summary_line = f"> {shown}_"

        lines = [
            f"RGB {rgb_text} | depth {depth_text} | close {self.args.close_kernel}x{self.args.close_kernel} | threshold {self.threshold_m * 1000:.1f}mm | fps {fps:.1f}",
            f"raw components {len(records)} | accepted {accepted} | rejected {rejected} | rolling 5s detect {any_rate * 100:.1f}% | single {single_rate * 100:.1f}%",
            prop_line,
            summary_line,
        ]
        if self.active_trial is not None:
            elapsed = now - self.active_trial["start"]
            remain = max(0.0, TRIAL_SECONDS - elapsed)
            lines[3] = f"TRIAL {self.active_trial['prop']} position {self.active_trial['position']} | {remain:.1f}s remaining"

        y = 32
        for i, text in enumerate(lines):
            scale = 0.66 if i < 3 else 0.72
            colour = (255, 255, 255) if i < 3 else (100, 230, 255)
            cv2.putText(panel, text, (18, y), cv2.FONT_HERSHEY_SIMPLEX, scale, colour, 1, cv2.LINE_AA)
            y += 38
        return panel

    def composite(self, rgb, depth, mask, records, any_rate, single_rate, fps, now):
        rgb_view = self.rgb_overlay(rgb, depth, records)
        mask_view = self.mask_overlay(mask, records)

        body_h = PREVIEW_HEIGHT - STATUS_HEIGHT
        left_w = int(PREVIEW_WIDTH * 0.67)
        right_w = PREVIEW_WIDTH - left_w

        rgb_fit, _ = fit_inside(rgb_view, left_w, body_h, cv2.INTER_AREA)
        mask_fit, _ = fit_inside(mask_view, right_w, body_h, cv2.INTER_NEAREST)

        body = np.zeros((body_h, PREVIEW_WIDTH, 3), dtype=np.uint8)
        ry = (body_h - rgb_fit.shape[0]) // 2
        rx = (left_w - rgb_fit.shape[1]) // 2
        body[ry:ry + rgb_fit.shape[0], rx:rx + rgb_fit.shape[1]] = rgb_fit

        my = (body_h - mask_fit.shape[0]) // 2
        mx = left_w + (right_w - mask_fit.shape[1]) // 2
        body[my:my + mask_fit.shape[0], mx:mx + mask_fit.shape[1]] = mask_fit
        cv2.line(body, (left_w, 0), (left_w, body_h), (100, 100, 100), 1)

        status = self.status_panel(PREVIEW_WIDTH, now, records, any_rate, single_rate, fps)
        return np.vstack([body, status])

    def save_snapshot(self, rgb, depth, height, mask, records, composite, reason):
        stamp = f"{self.frame_count:06d}_{safe_slug(reason)}"
        bgr_full = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        cv2.imwrite(os.path.join(self.debug_dir, stamp + "_rgb.png"), bgr_full)
        cv2.imwrite(os.path.join(self.debug_dir, stamp + "_preview.png"), composite)
        cv2.imwrite(os.path.join(self.debug_dir, stamp + "_mask.png"), mask * 255)
        np.savez_compressed(
            os.path.join(self.debug_dir, stamp + ".npz"),
            depth=depth,
            height=height,
            mask=mask,
        )
        with open(os.path.join(self.debug_dir, stamp + "_components.json"), "w") as f:
            serial = []
            for r in records:
                row = dict(r)
                row["bbox"] = list(row["bbox"])
                for key in ("area", "height", "max_height", "x", "y", "tx", "ty"):
                    if not np.isfinite(row[key]):
                        row[key] = None
                serial.append(row)
            json.dump(serial, f, indent=2)
        print(f"[d] saved {stamp}")

    def print_final_card(self):
        if not self.trial_results:
            print("[*] no qualification trials were completed")
            return
        print("\n===== RC6PROPS QUALIFICATION =====")
        props = sorted({r["prop"] for r in self.trial_results})
        for prop in props:
            rows, complete, overall_pass = self.prop_summary(prop)
            verdict = "PASS" if overall_pass else ("INCOMPLETE" if not complete else "FAIL")
            positions = sorted({r["position"] for r in rows})
            print(f"{prop}: {verdict} positions={positions}")
            for r in sorted(rows, key=lambda x: x["position"]):
                cv = r["area_cv"]
                cv_text = "n/a" if cv is None else f"{cv * 100:.1f}%"
                mark = "PASS" if r["pass"] else "FAIL"
                print(
                    f"  pos {r['position']}: {mark} "
                    f"detect={r['any_detection_rate'] * 100:.1f}% "
                    f"single={r['single_component_rate'] * 100:.1f}% "
                    f"area_cv={cv_text}"
                )
        print("==================================")

    def run(self):
        self.setup_debug()
        self.connect()
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW, PREVIEW_WIDTH, PREVIEW_HEIGHT)
        self.select_roi()
        self.calibrate()

        print("[*] RC6PROPS running")
        print("[*] this is detector qualification only: no ids, no learning, no merge logic")
        print("[*] preview: full RGB on the left, enlarged depth component mask on the right")
        print("[*] use ONE physical prop at a time for a timed qualification trial")
        print("[*] p = name prop, 1..5 = start position trial, s = snapshot, q = quit")

        last_loop = time.time()
        fps_smooth = 0.0
        try:
            while True:
                rgb, depth = self.frame()
                if depth is None:
                    continue
                now = time.time()
                dt = max(now - last_loop, 1e-6)
                inst_fps = 1.0 / dt
                fps_smooth = inst_fps if fps_smooth <= 0 else 0.9 * fps_smooth + 0.1 * inst_fps
                last_loop = now
                self.frame_count += 1

                records, mask, height, body = self.inspect_components(rgb, depth)
                accepted_count = sum(1 for r in records if r["accepted"])
                any_rate, single_rate = self.rolling_rates(now, accepted_count)
                self.write_component_rows(records, now)
                self.write_frame_row(records, now, any_rate, single_rate)
                self.update_trial(records, now)

                composite = self.composite(
                    rgb, depth, mask, records, any_rate, single_rate, fps_smooth, now
                )
                self.last_preview = composite
                self.last_depth = depth
                self.last_height = height
                self.last_mask = mask
                self.last_records = records

                cv2.imshow(WINDOW, composite)
                key = cv2.waitKey(1) & 0xFF

                if self.naming_mode:
                    if key != 255:
                        self.handle_prop_entry_key(key)
                    continue

                if key == ord("q"):
                    break
                if key == ord("p"):
                    self.begin_prop_entry()
                if key in (ord("1"), ord("2"), ord("3"), ord("4"), ord("5")):
                    self.start_trial(int(chr(key)))
                if key == ord("s"):
                    self.save_snapshot(rgb, depth, height, mask, records, composite, "manual")
        finally:
            if self.active_trial is not None:
                print("[!] active trial was interrupted and is not scored")
                self.active_trial = None
            self.save_summary()
            self.print_final_card()
            cv2.destroyAllWindows()
            print(f"[*] components log: {self.components_csv}")
            print(f"[*] frame log: {self.frames_csv}")
            print(f"[*] summary: {os.path.join(self.debug_dir, 'qualification_summary.json')}")
            print("[*] stopped")


if __name__ == "__main__":
    PropsQualification(parse_args()).run()
