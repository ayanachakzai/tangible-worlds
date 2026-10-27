"""
Tangible Worlds RC5D detector diagnostic, 19 Aug 2026.

Purpose:
- diagnose shallow-prop segmentation only
- no ids, no learning, no merge state, no semantics
- compare the current plane-height detector against a per-pixel empty-table
  background model on the same Record3D frame

Pipeline:
Record3D RGB + LiDAR depth
-> select tabletop ROI
-> empty-table calibration
-> fit one table plane
-> learn per-pixel empty-table height baseline and temporal noise
-> compare three masks live:
   1. current plane detector
   2. local background detector
   3. fused detector

# ref: Record3D official Python demo,
# https://github.com/marek-simonik/record3d/blob/master/demo-main.py
# ref: OpenCV morphology and connected components,
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

WINDOW = "Tangible Worlds - RC5D Detector Diagnostic"
DEBUG_ROOT = "tracker_debug"

BUILD_FRAMES = 40
VALIDATE_FRAMES = 20
PLANE_CALIBRATION_MULT = 5.0
PLANE_MIN_THRESHOLD_MM = 6.0
PLANE_MAX_THRESHOLD_MM = 20.0
HEIGHT_CEILING_MM = 150.0
MIN_AREA_CM2 = 3.0
HEIGHT_PCT = 95.0
ROI_BORDER_PX = 2

# local-background threshold candidates are selected only from empty-table
# validation frames. the real hardware test still decides whether the method
# is useful for actual shallow props.
LOCAL_FLOOR_CANDIDATES_MM = (2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0)
LOCAL_NOISE_MULT = 5.0
LOCAL_MIN_VALID_FRAC = 0.70

PLANE_OPEN = np.ones((3, 3), np.uint8)
PLANE_CLOSE = np.ones((5, 5), np.uint8)
LOCAL_CLOSE = np.ones((5, 5), np.uint8)
FUSED_CLOSE = np.ones((3, 3), np.uint8)

# keep the proven multi-body exclusion geometry from RC4Q. this diagnostic
# does not test identity, but using the same exclusion rule keeps the detector
# comparison close to the intended final pipeline.
BODY_EDGE_PX = 2
BODY_MIN_AREA_CM2 = 20.0
BODY_BACKGROUND_DILATE = np.ones((5, 5), np.uint8)


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
        self.debug_dir = os.path.join(DEBUG_ROOT, f"rc5d_{stamp}")
        os.makedirs(self.debug_dir, exist_ok=True)
        self.csv_path = os.path.join(self.debug_dir, "detector_metrics.csv")
        with open(self.csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "time", "frame",
                "plane_count", "plane_areas_cm2",
                "local_count", "local_areas_cm2",
                "fused_count", "fused_areas_cm2",
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

    def plane_mask(self, height, valid):
        roi = self.roi_mask(height.shape)
        mask = (
            valid
            & roi
            & (height > self.plane_threshold_m)
            & (height < HEIGHT_CEILING_MM / 1000.0)
        ).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, PLANE_OPEN)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, PLANE_CLOSE)
        return mask

    def local_mask(self, height, valid):
        roi = self.roi_mask(height.shape)
        trustworthy = valid & self.bg_valid & roi
        delta_mm = (height - self.bg_height) * 1000.0
        mask = (
            trustworthy
            & (delta_mm > self.local_threshold_mm)
            & (delta_mm < HEIGHT_CEILING_MM)
        ).astype(np.uint8)
        # project decision, 19 aug 2026: local-background diagnostic closes
        # small holes but does not run the current 3x3 opening first. the goal
        # is to test whether opening contributes to shallow-object breakup.
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, LOCAL_CLOSE)
        return mask

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
        background = self.body_background
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
            novel = (labels == i) & valid & (background == 0)
            if not np.any(novel):
                continue
            area = float(pixel_area[novel].sum() * 10000.0)
            if np.isfinite(area) and area >= BODY_MIN_AREA_CM2:
                combined |= novel
        return combined if np.any(combined) else None

    def component_blobs(self, mask, depth, height):
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        fx, fy, _, _ = self.intr
        pixel_area = (depth ** 2) / (fx * fy)
        valid = np.isfinite(depth) & (depth > 0.05) & (depth < 5.0)
        rx, ry, rw, rh = self.roi
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
            sel = (labels == i) & valid
            if not np.any(sel):
                continue
            area = float(pixel_area[sel].sum() * 10000.0)
            heights_mm = height[sel] * 1000.0
            if heights_mm.size == 0:
                continue
            height_mm = float(np.percentile(heights_mm, HEIGHT_PCT))
            max_mm = float(np.max(heights_mm))
            if not np.isfinite(area) or not np.isfinite(height_mm) or not np.isfinite(max_mm):
                continue
            if area < MIN_AREA_CM2 or max_mm > HEIGHT_CEILING_MM:
                continue
            blobs.append({
                "bbox": (x, y, w, h),
                "area": area,
                "height": height_mm,
            })
        return blobs

    def false_prop_count(self, mask, depth, height):
        return len(self.component_blobs(mask, depth, height))

    def calibrate(self):
        total = BUILD_FRAMES + VALIDATE_FRAMES
        print(f"[*] empty table for {total} frames; keep hands and props out")
        depths = []
        rgbs = []
        while len(depths) < total:
            rgb, depth = self.frame()
            if depth is None:
                continue
            depths.append(depth.copy())
            rgbs.append(rgb)
            print(f"\rcalibrating {len(depths)}/{total}", end="", flush=True)

        build = np.stack(depths[:BUILD_FRAMES])
        safe = np.where(np.isfinite(build), build, np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            baseline_depth = np.nanmedian(safe, axis=0).astype(np.float32)

        pts, valid = self.unproject(baseline_depth)
        use = valid & self.roi_mask(baseline_depth.shape)
        self.n, self.c, self.origin = fit_plane(pts[use])

        # keep RC4's plane threshold so the comparison is honest.
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

        # project decision, 19 aug 2026: store the empty table in plane-height
        # coordinates rather than raw depth. this keeps the measurement in the
        # same physical direction used by the existing tracker while removing
        # fixed per-pixel residual bias from one global fitted plane.
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

        # validate several floors on held-out empty-table frames and keep the
        # lowest one producing no prop-sized false component in the holdout.
        selected = None
        validation_summary = []
        for floor_mm in LOCAL_FLOOR_CANDIDATES_MM:
            threshold_map = np.maximum(floor_mm, self.bg_noise_mm * LOCAL_NOISE_MULT)
            false_frames = 0
            max_count = 0
            for depth in depths[BUILD_FRAMES:]:
                _, valid_i, height_i = self.height_from_depth(depth)
                roi = self.roi_mask(depth.shape)
                delta_mm = (height_i - self.bg_height) * 1000.0
                mask = (
                    valid_i
                    & self.bg_valid
                    & roi
                    & (delta_mm > threshold_map)
                    & (delta_mm < HEIGHT_CEILING_MM)
                ).astype(np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, LOCAL_CLOSE)
                nfalse = self.false_prop_count(mask, depth, height_i)
                if nfalse:
                    false_frames += 1
                    max_count = max(max_count, nfalse)
            validation_summary.append((floor_mm, false_frames, max_count))
            if false_frames == 0 and selected is None:
                selected = floor_mm

        if selected is None:
            selected = float(LOCAL_FLOOR_CANDIDATES_MM[-1])
        self.local_floor_mm = float(selected)
        self.local_threshold_mm = np.maximum(
            self.local_floor_mm,
            self.bg_noise_mm * LOCAL_NOISE_MULT,
        ).astype(np.float32)

        # same static edge-clutter memory used by RC4 body exclusion.
        baseline_height = pts @ self.n + self.c
        self.body_background = self.body_mask(baseline_height, valid)
        self.body_background = cv2.dilate(
            self.body_background,
            BODY_BACKGROUND_DILATE,
            iterations=1,
        )

        usable_noise = self.bg_noise_mm[self.bg_valid & self.roi_mask(self.bg_noise_mm.shape)]
        local_noise_med = float(np.median(usable_noise)) if usable_noise.size else float("nan")
        local_noise_p95 = float(np.percentile(usable_noise, 95)) if usable_noise.size else float("nan")

        print(f"\n[*] plane detector threshold: {plane_threshold_mm:.1f}mm")
        print(f"[*] local background floor: {self.local_floor_mm:.1f}mm")
        print(f"[*] local pixel noise median/p95: {local_noise_med:.2f}/{local_noise_p95:.2f}mm")
        print("[*] empty-table local validation:")
        for floor_mm, false_frames, max_count in validation_summary:
            mark = " <- selected" if abs(floor_mm - self.local_floor_mm) < 1e-6 else ""
            print(f"    {floor_mm:>3.1f}mm: false frames={false_frames}/{VALIDATE_FRAMES} max_components={max_count}{mark}")

        with open(os.path.join(self.debug_dir, "calibration.json"), "w") as f:
            json.dump({
                "roi": [int(v) for v in self.roi],
                "intrinsics": [float(v) for v in self.intr],
                "plane_noise_mm": plane_noise_mm,
                "plane_threshold_mm": plane_threshold_mm,
                "local_floor_mm": self.local_floor_mm,
                "local_noise_median_mm": local_noise_med,
                "local_noise_p95_mm": local_noise_p95,
                "validation": [
                    {"floor_mm": float(a), "false_frames": int(b), "max_components": int(c)}
                    for a, b, c in validation_summary
                ],
            }, f, indent=2)

        np.savez_compressed(
            os.path.join(self.debug_dir, "background_model.npz"),
            bg_height=self.bg_height,
            bg_valid=self.bg_valid.astype(np.uint8),
            bg_noise_mm=self.bg_noise_mm,
            local_threshold_mm=self.local_threshold_mm,
            baseline_depth=baseline_depth,
        )

    def masks(self, depth):
        _, valid, height = self.height_from_depth(depth)
        plane = self.plane_mask(height, valid)
        local = self.local_mask(height, valid)

        body = self.body_pixels(height, valid, depth)
        if body is not None:
            plane[body] = 0
            local[body] = 0

        # fused detector keeps the stable current detector for tall props and
        # lets the local-background detector fill shallow regions it misses.
        fused = ((plane > 0) | (local > 0)).astype(np.uint8)
        fused = cv2.morphologyEx(fused, cv2.MORPH_CLOSE, FUSED_CLOSE)
        if body is not None:
            fused[body] = 0
        return height, plane, local, fused

    def annotate(self, bgr, blobs, title):
        out = bgr.copy()
        cv2.putText(out, title, (5, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        for idx, b in enumerate(blobs, 1):
            x, y, w, h = b["bbox"]
            cv2.rectangle(out, (x, y), (x + w, y + h), (255, 255, 255), 1)
            text = f"{idx}:{b['area']:.0f}cm2 {b['height']:.0f}mm"
            cv2.putText(out, text, (x, max(12, y - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
        return out

    def mask_view(self, mask, title):
        out = cv2.cvtColor(mask * 255, cv2.COLOR_GRAY2BGR)
        cv2.putText(out, title, (5, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        return out

    def composite(self, bgr, plane, local, fused, pblobs, lblobs, fblobs):
        top = np.hstack([
            self.annotate(bgr, pblobs, f"plane current n={len(pblobs)}"),
            self.annotate(bgr, lblobs, f"local background n={len(lblobs)}"),
            self.annotate(bgr, fblobs, f"fused n={len(fblobs)}"),
        ])
        bottom = np.hstack([
            self.mask_view(plane, "plane mask"),
            self.mask_view(local, "local mask"),
            self.mask_view(fused, "fused mask"),
        ])
        return np.vstack([top, bottom])

    def write_metrics(self, pblobs, lblobs, fblobs):
        def areas(blobs):
            return ";".join(f"{b['area']:.2f}" for b in blobs)
        with open(self.csv_path, "a", newline="") as f:
            csv.writer(f).writerow([
                f"{time.time():.6f}", self.frame_count,
                len(pblobs), areas(pblobs),
                len(lblobs), areas(lblobs),
                len(fblobs), areas(fblobs),
            ])

    def save_snapshot(self, composite, depth, height, plane, local, fused, reason):
        stamp = f"{self.frame_count:06d}_{reason}"
        cv2.imwrite(os.path.join(self.debug_dir, stamp + ".png"), composite)
        np.savez_compressed(
            os.path.join(self.debug_dir, stamp + ".npz"),
            depth=depth,
            height=height,
            plane=plane,
            local=local,
            fused=fused,
        )
        print(f"[d] saved {stamp}")

    def run(self):
        self.setup_debug()
        self.connect()
        self.select_roi()
        self.calibrate()

        print("[*] detector diagnostic running")
        print("[*] no ids, no learning, no merge logic")
        print("[*] test the shallow props in several tabletop positions")
        print("[*] q = quit, s = save snapshot")

        last_print = time.time()
        try:
            while True:
                rgb, depth = self.frame()
                if depth is None:
                    continue
                self.frame_count += 1
                height, plane, local, fused = self.masks(depth)
                bgr = self.small_bgr(rgb, depth)
                pblobs = self.component_blobs(plane, depth, height)
                lblobs = self.component_blobs(local, depth, height)
                fblobs = self.component_blobs(fused, depth, height)
                composite = self.composite(bgr, plane, local, fused, pblobs, lblobs, fblobs)
                self.write_metrics(pblobs, lblobs, fblobs)

                now = time.time()
                if now - last_print >= 1.0:
                    def fmt(blobs):
                        return "[" + ",".join(f"{b['area']:.0f}" for b in blobs) + "]"
                    print(
                        f"[t] plane={len(pblobs)}{fmt(pblobs)} "
                        f"local={len(lblobs)}{fmt(lblobs)} "
                        f"fused={len(fblobs)}{fmt(fblobs)}"
                    )
                    last_print = now

                # save occasional disagreement frames automatically. this is
                # diagnostic only and does not affect detection.
                if (
                    (len(pblobs) != len(lblobs) or len(local.nonzero()[0]) != len(plane.nonzero()[0]))
                    and self.frame_count - self.last_save_frame >= 90
                ):
                    self.save_snapshot(composite, depth, height, plane, local, fused, "disagree")
                    self.last_save_frame = self.frame_count

                cv2.imshow(WINDOW, composite)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("s"):
                    self.save_snapshot(composite, depth, height, plane, local, fused, "manual")
        finally:
            cv2.destroyAllWindows()
            print(f"[*] metrics: {self.csv_path}")
            print("[*] stopped")


if __name__ == "__main__":
    DetectorDiagnostic().run()
