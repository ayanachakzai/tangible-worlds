"""
Tangible Worlds RC5RGB detector diagnostic, 19 Aug 2026.

Purpose:
- diagnose shallow-prop segmentation only
- no ids, no learning, no merge state, no semantics
- compare local LiDAR background subtraction against static RGB background
  subtraction and an RGB-assisted hybrid on the same Record3D frame

Live preview:
LOCAL DEPTH | RGB CHANGE | HYBRID
with the three masks directly underneath.

The hybrid does not replace LiDAR geometry. RGB is allowed to repair or
supply a foreground silhouette while depth remains available for metric
measurements whenever the sensor provides it.

# ref: Record3D official Python demo,
# https://github.com/marek-simonik/record3d/blob/master/demo-main.py
# ref: OpenCV colour conversion, morphology and connected components,
# https://docs.opencv.org/4.x/d8/d01/group__imgproc__color__conversions.html
# https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html
# https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html
# ref: Riemann et al. 2018, FlowPut, DOI 10.1145/3191763
"""

import csv
import json
import os
import time
import warnings
from threading import Event

import cv2
import numpy as np
from record3d import Record3DStream

WINDOW = "Tangible Worlds - RC5RGB Detector Diagnostic"
DEBUG_ROOT = "tracker_debug"

BUILD_FRAMES = 40
VALIDATE_FRAMES = 20
PLANE_CALIBRATION_MULT = 5.0
PLANE_MIN_THRESHOLD_MM = 6.0
PLANE_MAX_THRESHOLD_MM = 20.0
HEIGHT_CEILING_MM = 150.0
LOCAL_MIN_AREA_CM2 = 3.0
RGB_MIN_AREA_CM2 = 2.0
MAX_RGB_AREA_CM2 = 260.0
HEIGHT_PCT = 95.0
ROI_BORDER_PX = 2

LOCAL_FLOOR_CANDIDATES_MM = (2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0)
LOCAL_NOISE_MULT = 5.0
LOCAL_MIN_VALID_FRAC = 0.70

# Static RGB background is calibrated on the same empty-table frames.
# The L channel is downweighted because body movement can alter exposure and
# cast broad shadows. a/b chroma still contributes fully.
RGB_FLOOR_CANDIDATES = (5.0, 7.0, 9.0, 12.0, 15.0, 20.0, 25.0)
RGB_NOISE_MULT = 5.0
RGB_L_WEIGHT = 0.55
RGB_MAX_GLOBAL_L_SHIFT = 28.0

PLANE_OPEN = np.ones((3, 3), np.uint8)
PLANE_CLOSE = np.ones((5, 5), np.uint8)
LOCAL_CLOSE = np.ones((5, 5), np.uint8)
RGB_CLOSE = np.ones((5, 5), np.uint8)
HYBRID_CLOSE = np.ones((5, 5), np.uint8)
BODY_BACKGROUND_DILATE = np.ones((5, 5), np.uint8)
BODY_EDGE_PX = 2
BODY_MIN_AREA_CM2 = 20.0


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


class DetectorDiagnostic:
    def __init__(self):
        self.event = Event()
        self.session = None
        self.intr = None
        self.roi = None
        self.n = None
        self.c = None
        self.origin = None
        self.plane_threshold_m = PLANE_MIN_THRESHOLD_MM / 1000.0

        self.bg_height = None
        self.bg_valid = None
        self.bg_noise_mm = None
        self.local_threshold_mm = None
        self.local_floor_mm = None
        self.baseline_depth = None

        self.bg_lab = None
        self.rgb_noise = None
        self.rgb_threshold = None
        self.rgb_floor = None

        self.body_background = None
        self.debug_dir = None
        self.csv_path = None
        self.frame_count = 0
        self.last_save_frame = -1000000

    def on_new_frame(self):
        self.event.set()

    def on_stream_stopped(self):
        print("\n[!] Record3D stream stopped")

    def setup_debug(self):
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.debug_dir = os.path.join(DEBUG_ROOT, f"rc5rgb_{stamp}")
        os.makedirs(self.debug_dir, exist_ok=True)
        self.csv_path = os.path.join(self.debug_dir, "detector_metrics.csv")
        with open(self.csv_path, "w", newline="") as f:
            csv.writer(f).writerow([
                "time", "frame",
                "local_count", "local_areas_cm2",
                "rgb_count", "rgb_areas_cm2",
                "hybrid_count", "hybrid_areas_cm2",
                "rgb_global_l_shift",
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

    def small_bgr(self, rgb, depth):
        dh, dw = depth.shape
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        return cv2.resize(bgr, (dw, dh), interpolation=cv2.INTER_AREA)

    def lab_frame(self, bgr):
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)

    def roi_mask(self, shape):
        mask = np.zeros(shape, dtype=bool)
        x, y, w, h = self.roi
        mask[y:y + h, x:x + w] = True
        return mask

    def select_roi(self):
        print("[*] select ONLY the usable tabletop, then press ENTER")
        while True:
            rgb, depth = self.frame()
            if depth is None:
                continue
            if self.intr is None:
                self.intr = self.resolve_intrinsics(depth, rgb)
                print("[*] depth intrinsics:", *[f"{v:.1f}" for v in self.intr])
            preview = self.small_bgr(rgb, depth)
            x, y, w, h = cv2.selectROI(WINDOW, preview, True, False)
            if w >= 40 and h >= 40:
                self.roi = (int(x), int(y), int(w), int(h))
                print(f"[*] work area: x={x} y={y} w={w} h={h}")
                return
            print("[!] selection cancelled or too small")

    def height_from_depth(self, depth):
        pts, valid = self.unproject(depth)
        height = pts @ self.n + self.c
        return pts, valid, height

    def local_mask(self, height, valid):
        roi = self.roi_mask(height.shape)
        trustworthy = valid & self.bg_valid & roi
        delta_mm = (height - self.bg_height) * 1000.0
        mask = (
            trustworthy
            & (delta_mm > self.local_threshold_mm)
            & (delta_mm < HEIGHT_CEILING_MM)
        ).astype(np.uint8)
        return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, LOCAL_CLOSE)

    def body_mask(self, height, valid):
        roi = self.roi_mask(height.shape)
        mask = (valid & roi & (height > self.plane_threshold_m)).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, PLANE_OPEN)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, PLANE_CLOSE)
        return mask

    def body_pixels(self, height, valid, depth):
        current = self.body_mask(height, valid)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(current, 8)
        fx, fy, _, _ = self.intr
        pixel_area = (depth ** 2) / (fx * fy)
        rx, ry, rw, rh = self.roi
        combined = np.zeros_like(current, dtype=bool)
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
            novel = (labels == i) & valid & (self.body_background == 0)
            if not np.any(novel):
                continue
            area = float(pixel_area[novel].sum() * 10000.0)
            if np.isfinite(area) and area >= BODY_MIN_AREA_CM2:
                combined |= novel
        return combined if np.any(combined) else None

    def rgb_score(self, lab):
        roi = self.roi_mask(lab.shape[:2])
        # project decision, 19 aug 2026: remove the global median luminance
        # shift before per-pixel comparison. this makes the diagnostic less
        # sensitive to camera exposure changes caused by a participant leaning
        # into the frame while preserving local object contrast.
        dl_raw = lab[..., 0] - self.bg_lab[..., 0]
        samples = dl_raw[roi & np.isfinite(dl_raw)]
        shift = float(np.median(samples)) if samples.size else 0.0
        shift = float(np.clip(shift, -RGB_MAX_GLOBAL_L_SHIFT, RGB_MAX_GLOBAL_L_SHIFT))
        dl = (lab[..., 0] - shift) - self.bg_lab[..., 0]
        da = lab[..., 1] - self.bg_lab[..., 1]
        db = lab[..., 2] - self.bg_lab[..., 2]
        score = np.sqrt((RGB_L_WEIGHT * dl) ** 2 + da ** 2 + db ** 2)
        return score.astype(np.float32), shift

    def rgb_mask(self, lab):
        score, shift = self.rgb_score(lab)
        roi = self.roi_mask(score.shape)
        mask = (roi & np.isfinite(score) & (score > self.rgb_threshold)).astype(np.uint8)
        # no opening here. opening can erase the thin stem we are explicitly
        # testing. component area filtering handles isolated RGB speckle.
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, RGB_CLOSE)
        return mask, score, shift

    def approx_pixel_area(self, depth):
        fx, fy, _, _ = self.intr
        z = np.where(
            np.isfinite(depth) & (depth > 0.05) & (depth < 5.0),
            depth,
            self.baseline_depth,
        )
        return (z ** 2) / (fx * fy)

    def filter_rgb_components(self, mask, depth):
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        pixel_area = self.approx_pixel_area(depth)
        rx, ry, rw, rh = self.roi
        kept = np.zeros_like(mask, dtype=np.uint8)
        for i in range(1, count):
            x = int(stats[i, cv2.CC_STAT_LEFT])
            y = int(stats[i, cv2.CC_STAT_TOP])
            w = int(stats[i, cv2.CC_STAT_WIDTH])
            h = int(stats[i, cv2.CC_STAT_HEIGHT])
            if (
                x <= rx + ROI_BORDER_PX
                or y <= ry + ROI_BORDER_PX
                or x + w >= rx + rw - ROI_BORDER_PX
                or y + h >= ry + rh - ROI_BORDER_PX
            ):
                continue
            sel = labels == i
            area = float(pixel_area[sel].sum() * 10000.0)
            if not np.isfinite(area):
                continue
            if RGB_MIN_AREA_CM2 <= area <= MAX_RGB_AREA_CM2:
                kept[sel] = 1
        return kept

    def component_blobs(self, mask, depth, height=None, min_area=LOCAL_MIN_AREA_CM2):
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        pixel_area = self.approx_pixel_area(depth)
        rx, ry, rw, rh = self.roi
        valid = np.isfinite(depth) & (depth > 0.05) & (depth < 5.0)
        blobs = []
        for i in range(1, count):
            x = int(stats[i, cv2.CC_STAT_LEFT])
            y = int(stats[i, cv2.CC_STAT_TOP])
            w = int(stats[i, cv2.CC_STAT_WIDTH])
            h = int(stats[i, cv2.CC_STAT_HEIGHT])
            if (
                x <= rx + ROI_BORDER_PX
                or y <= ry + ROI_BORDER_PX
                or x + w >= rx + rw - ROI_BORDER_PX
                or y + h >= ry + rh - ROI_BORDER_PX
            ):
                continue
            sel = labels == i
            area = float(pixel_area[sel].sum() * 10000.0)
            if not np.isfinite(area) or area < min_area:
                continue
            height_mm = None
            if height is not None:
                hs = sel & valid
                vals = height[hs] * 1000.0
                vals = vals[np.isfinite(vals)]
                if vals.size:
                    height_mm = float(np.percentile(vals, HEIGHT_PCT))
            blobs.append({
                "bbox": (x, y, w, h),
                "area": area,
                "height": height_mm,
            })
        return blobs

    def false_rgb_count(self, mask, depth):
        return len(self.component_blobs(self.filter_rgb_components(mask, depth), depth, None, RGB_MIN_AREA_CM2))

    def calibrate(self):
        total = BUILD_FRAMES + VALIDATE_FRAMES
        print(f"[*] empty table for {total} frames; keep hands and props out")
        depths = []
        bgrs = []
        while len(depths) < total:
            rgb, depth = self.frame()
            if depth is None:
                continue
            depths.append(depth.copy())
            bgrs.append(self.small_bgr(rgb, depth))
            print(f"\rcalibrating {len(depths)}/{total}", end="", flush=True)

        build = np.stack(depths[:BUILD_FRAMES])
        safe = np.where(np.isfinite(build), build, np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            self.baseline_depth = np.nanmedian(safe, axis=0).astype(np.float32)

        pts, valid = self.unproject(self.baseline_depth)
        use = valid & self.roi_mask(self.baseline_depth.shape)
        self.n, self.c, self.origin = fit_plane(pts[use])

        plane_noise = []
        for depth in depths[:BUILD_FRAMES]:
            pts_i, valid_i = self.unproject(depth)
            use_i = valid_i & self.roi_mask(depth.shape)
            residual = (pts_i @ self.n + self.c)[use_i]
            residual = residual[np.abs(residual) < 0.02]
            if residual.size:
                plane_noise.append(float(np.std(residual) * 1000.0))
        if not plane_noise:
            raise RuntimeError("could not measure table noise")
        plane_noise_mm = float(np.median(plane_noise))
        plane_threshold_mm = float(np.clip(
            plane_noise_mm * PLANE_CALIBRATION_MULT,
            PLANE_MIN_THRESHOLD_MM,
            PLANE_MAX_THRESHOLD_MM,
        ))
        self.plane_threshold_m = plane_threshold_mm / 1000.0

        height_frames = []
        valid_frames = []
        for depth in depths[:BUILD_FRAMES]:
            _, valid_i, height_i = self.height_from_depth(depth)
            height_frames.append(np.where(valid_i, height_i, np.nan))
            valid_frames.append(valid_i)
        hstack = np.stack(height_frames)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            self.bg_height = np.nanmedian(hstack, axis=0).astype(np.float32)
            abs_dev = np.abs(hstack - self.bg_height[None, :, :])
            mad = np.nanmedian(abs_dev, axis=0)
        valid_count = np.sum(np.stack(valid_frames), axis=0)
        self.bg_valid = (
            (valid_count >= int(np.ceil(BUILD_FRAMES * LOCAL_MIN_VALID_FRAC)))
            & np.isfinite(self.bg_height)
        )
        self.bg_noise_mm = (1.4826 * mad * 1000.0).astype(np.float32)
        self.bg_noise_mm[~np.isfinite(self.bg_noise_mm)] = np.inf

        selected_local = None
        local_validation = []
        for floor_mm in LOCAL_FLOOR_CANDIDATES_MM:
            threshold_map = np.maximum(floor_mm, self.bg_noise_mm * LOCAL_NOISE_MULT)
            false_frames = 0
            max_count = 0
            for depth in depths[BUILD_FRAMES:]:
                _, valid_i, height_i = self.height_from_depth(depth)
                roi = self.roi_mask(depth.shape)
                delta_mm = (height_i - self.bg_height) * 1000.0
                mask = (
                    valid_i & self.bg_valid & roi
                    & (delta_mm > threshold_map)
                    & (delta_mm < HEIGHT_CEILING_MM)
                ).astype(np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, LOCAL_CLOSE)
                nfalse = len(self.component_blobs(mask, depth, height_i))
                if nfalse:
                    false_frames += 1
                    max_count = max(max_count, nfalse)
            local_validation.append((floor_mm, false_frames, max_count))
            if false_frames == 0 and selected_local is None:
                selected_local = floor_mm
        if selected_local is None:
            selected_local = float(LOCAL_FLOOR_CANDIDATES_MM[-1])
        self.local_floor_mm = float(selected_local)
        self.local_threshold_mm = np.maximum(
            self.local_floor_mm,
            self.bg_noise_mm * LOCAL_NOISE_MULT,
        ).astype(np.float32)

        # Static RGB background model at depth resolution.
        labs = np.stack([self.lab_frame(b) for b in bgrs[:BUILD_FRAMES]])
        self.bg_lab = np.median(labs, axis=0).astype(np.float32)
        roi = self.roi_mask(self.baseline_depth.shape)
        rgb_scores = []
        for lab in labs:
            score, _ = self.rgb_score(lab)
            rgb_scores.append(score)
        rgb_stack = np.stack(rgb_scores)
        self.rgb_noise = np.median(rgb_stack, axis=0).astype(np.float32)

        selected_rgb = None
        rgb_validation = []
        for floor in RGB_FLOOR_CANDIDATES:
            threshold_map = np.maximum(floor, self.rgb_noise * RGB_NOISE_MULT)
            false_frames = 0
            max_count = 0
            for bgr, depth in zip(bgrs[BUILD_FRAMES:], depths[BUILD_FRAMES:]):
                lab = self.lab_frame(bgr)
                score, _ = self.rgb_score(lab)
                mask = (roi & (score > threshold_map)).astype(np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, RGB_CLOSE)
                nfalse = self.false_rgb_count(mask, depth)
                if nfalse:
                    false_frames += 1
                    max_count = max(max_count, nfalse)
            rgb_validation.append((floor, false_frames, max_count))
            if false_frames == 0 and selected_rgb is None:
                selected_rgb = floor
        if selected_rgb is None:
            selected_rgb = float(RGB_FLOOR_CANDIDATES[-1])
        self.rgb_floor = float(selected_rgb)
        self.rgb_threshold = np.maximum(
            self.rgb_floor,
            self.rgb_noise * RGB_NOISE_MULT,
        ).astype(np.float32)

        baseline_height = pts @ self.n + self.c
        self.body_background = self.body_mask(baseline_height, valid)
        self.body_background = cv2.dilate(
            self.body_background,
            BODY_BACKGROUND_DILATE,
            iterations=1,
        )

        usable_noise = self.bg_noise_mm[self.bg_valid & roi]
        local_noise_med = float(np.median(usable_noise)) if usable_noise.size else float("nan")
        local_noise_p95 = float(np.percentile(usable_noise, 95)) if usable_noise.size else float("nan")
        rgb_noise_roi = self.rgb_noise[roi]
        rgb_noise_med = float(np.median(rgb_noise_roi)) if rgb_noise_roi.size else float("nan")
        rgb_noise_p95 = float(np.percentile(rgb_noise_roi, 95)) if rgb_noise_roi.size else float("nan")

        print(f"\n[*] plane/body threshold: {plane_threshold_mm:.1f}mm")
        print(f"[*] local depth floor: {self.local_floor_mm:.1f}mm")
        print(f"[*] local pixel noise median/p95: {local_noise_med:.2f}/{local_noise_p95:.2f}mm")
        print(f"[*] rgb change floor: {self.rgb_floor:.1f}")
        print(f"[*] rgb background noise median/p95: {rgb_noise_med:.2f}/{rgb_noise_p95:.2f}")
        print("[*] empty-table RGB validation:")
        for floor, false_frames, max_count in rgb_validation:
            mark = " <- selected" if abs(floor - self.rgb_floor) < 1e-6 else ""
            print(f"    {floor:>4.1f}: false frames={false_frames}/{VALIDATE_FRAMES} max_components={max_count}{mark}")

        with open(os.path.join(self.debug_dir, "calibration.json"), "w") as f:
            json.dump({
                "roi": [int(v) for v in self.roi],
                "intrinsics": [float(v) for v in self.intr],
                "plane_noise_mm": plane_noise_mm,
                "plane_threshold_mm": plane_threshold_mm,
                "local_floor_mm": self.local_floor_mm,
                "local_noise_median_mm": local_noise_med,
                "local_noise_p95_mm": local_noise_p95,
                "rgb_floor": self.rgb_floor,
                "rgb_noise_median": rgb_noise_med,
                "rgb_noise_p95": rgb_noise_p95,
                "rgb_l_weight": RGB_L_WEIGHT,
                "local_validation": [
                    {"floor_mm": float(a), "false_frames": int(b), "max_components": int(c)}
                    for a, b, c in local_validation
                ],
                "rgb_validation": [
                    {"floor": float(a), "false_frames": int(b), "max_components": int(c)}
                    for a, b, c in rgb_validation
                ],
            }, f, indent=2)

        np.savez_compressed(
            os.path.join(self.debug_dir, "background_model.npz"),
            bg_height=self.bg_height,
            bg_valid=self.bg_valid.astype(np.uint8),
            bg_noise_mm=self.bg_noise_mm,
            local_threshold_mm=self.local_threshold_mm,
            baseline_depth=self.baseline_depth,
            bg_lab=self.bg_lab,
            rgb_noise=self.rgb_noise,
            rgb_threshold=self.rgb_threshold,
        )

    def masks(self, bgr, depth):
        _, valid, height = self.height_from_depth(depth)
        local = self.local_mask(height, valid)
        lab = self.lab_frame(bgr)
        rgb_raw, rgb_score, global_l_shift = self.rgb_mask(lab)
        rgb = self.filter_rgb_components(rgb_raw, depth)

        body = self.body_pixels(height, valid, depth)
        if body is not None:
            local[body] = 0
            rgb[body] = 0

        # diagnostic hybrid: keep every clean local-depth pixel and allow a
        # stable interior RGB foreground component to repair missing silhouette.
        # We are testing whether RGB contains the information before deciding
        # the final production gating rule.
        hybrid = ((local > 0) | (rgb > 0)).astype(np.uint8)
        hybrid = cv2.morphologyEx(hybrid, cv2.MORPH_CLOSE, HYBRID_CLOSE)
        if body is not None:
            hybrid[body] = 0
        return height, local, rgb, hybrid, rgb_score, global_l_shift

    def annotate(self, bgr, blobs, title):
        out = bgr.copy()
        cv2.putText(out, title, (5, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        for idx, b in enumerate(blobs, 1):
            x, y, w, h = b["bbox"]
            cv2.rectangle(out, (x, y), (x + w, y + h), (255, 255, 255), 1)
            if b["height"] is None:
                text = f"{idx}:{b['area']:.0f}cm2"
            else:
                text = f"{idx}:{b['area']:.0f}cm2 {b['height']:.0f}mm"
            cv2.putText(out, text, (x, max(12, y - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
        return out

    def mask_view(self, mask, title):
        out = cv2.cvtColor(mask * 255, cv2.COLOR_GRAY2BGR)
        cv2.putText(out, title, (5, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        return out

    def composite(self, bgr, local, rgb, hybrid, lblobs, rblobs, hblobs, shift):
        top = np.hstack([
            self.annotate(bgr, lblobs, f"LOCAL DEPTH n={len(lblobs)}"),
            self.annotate(bgr, rblobs, f"RGB CHANGE n={len(rblobs)} Lshift={shift:+.1f}"),
            self.annotate(bgr, hblobs, f"HYBRID n={len(hblobs)}"),
        ])
        bottom = np.hstack([
            self.mask_view(local, "local depth mask"),
            self.mask_view(rgb, "rgb change mask"),
            self.mask_view(hybrid, "hybrid mask"),
        ])
        return np.vstack([top, bottom])

    def write_metrics(self, lblobs, rblobs, hblobs, shift):
        def areas(blobs):
            return ";".join(f"{b['area']:.2f}" for b in blobs)
        with open(self.csv_path, "a", newline="") as f:
            csv.writer(f).writerow([
                f"{time.time():.6f}", self.frame_count,
                len(lblobs), areas(lblobs),
                len(rblobs), areas(rblobs),
                len(hblobs), areas(hblobs),
                f"{shift:.3f}",
            ])

    def save_snapshot(self, composite, bgr, depth, height, local, rgb, hybrid, score, reason):
        stamp = f"{self.frame_count:06d}_{reason}"
        cv2.imwrite(os.path.join(self.debug_dir, stamp + ".png"), composite)
        np.savez_compressed(
            os.path.join(self.debug_dir, stamp + ".npz"),
            bgr=bgr,
            depth=depth,
            height=height,
            local=local,
            rgb=rgb,
            hybrid=hybrid,
            rgb_score=score,
        )
        print(f"[d] saved {stamp}")

    def run(self):
        self.setup_debug()
        self.connect()
        self.select_roi()
        self.calibrate()

        print("[*] RGB-assisted detector diagnostic running")
        print("[*] no ids, no learning, no merge logic")
        print("[*] preview: LOCAL DEPTH | RGB CHANGE | HYBRID")
        print("[*] test phone, stem, card/wood cover in several tabletop positions")
        print("[*] q = quit, s = save snapshot")

        last_print = time.time()
        try:
            while True:
                rgb_full, depth = self.frame()
                if depth is None:
                    continue
                self.frame_count += 1
                bgr = self.small_bgr(rgb_full, depth)
                height, local, rgb, hybrid, score, shift = self.masks(bgr, depth)
                lblobs = self.component_blobs(local, depth, height)
                rblobs = self.component_blobs(rgb, depth, None, RGB_MIN_AREA_CM2)
                hblobs = self.component_blobs(hybrid, depth, height, RGB_MIN_AREA_CM2)
                composite = self.composite(bgr, local, rgb, hybrid, lblobs, rblobs, hblobs, shift)
                self.write_metrics(lblobs, rblobs, hblobs, shift)

                now = time.time()
                if now - last_print >= 1.0:
                    def fmt(blobs):
                        return "[" + ",".join(f"{b['area']:.0f}" for b in blobs) + "]"
                    print(
                        f"[t] local={len(lblobs)}{fmt(lblobs)} "
                        f"rgb={len(rblobs)}{fmt(rblobs)} "
                        f"hybrid={len(hblobs)}{fmt(hblobs)} "
                        f"Lshift={shift:+.1f}"
                    )
                    last_print = now

                if (
                    (len(lblobs) != len(rblobs) or len(rblobs) != len(hblobs))
                    and self.frame_count - self.last_save_frame >= 90
                ):
                    self.save_snapshot(composite, bgr, depth, height, local, rgb, hybrid, score, "disagree")
                    self.last_save_frame = self.frame_count

                cv2.imshow(WINDOW, composite)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("s"):
                    self.save_snapshot(composite, bgr, depth, height, local, rgb, hybrid, score, "manual")
        finally:
            cv2.destroyAllWindows()
            print(f"[*] metrics: {self.csv_path}")
            print("[*] stopped")


if __name__ == "__main__":
    DetectorDiagnostic().run()
