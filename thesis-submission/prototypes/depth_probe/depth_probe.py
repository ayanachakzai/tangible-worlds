"""
depth_probe.py
--------------
read-only diagnostic (w.r.t. scene data). does NOT write
scene_state.json, does NOT touch track_tabletop.py, does NOT persist
any config.

answers: on my actual table, do the objects i care about rise far
enough above the table plane to be separable from lidar noise?

verified 28 july on the real rig:
    table plane residual std = 1.6mm
    min detectable object height ~5mm
    5 objects on table -> 5 detected (yolo26x detected 1)
    watch reads 15-16mm, 9x the noise floor

usage:
    1. open record3d on iphone, usb streaming on, tap record.
    2. point at the table, objects on it.
    3. python depth_probe.py

    keys (click the preview window first, macos only delivers keys to
    a focused highgui window):
        [ ]  lower/raise height threshold (floor locked to 3x noise)
        q    quit

what it does:
    - unprojects the lidar depth frame to a 3d point cloud
    - ransac-fits the dominant plane on the full frame
    - measures every point's height above that plane
    - thresholds, closes small internal gaps, then connected
      components -> one blob per object
    - skips any blob smaller than MIN_BLOB_AREA_CM2 (noise) or taller
      than HEIGHT_CEILING (furniture, not placed input)
    - prints height (mm) and footprint (cm2) per blob
    - prints a rolling noise floor, always on

known physical limit: transparent objects (drinking glass) return no
lidar signal at all, ir passes straight through. gloss black plastic
absorbs ir and may behave similarly, untested. neither is a threshold
problem. excluded from the physical vocabulary, not tuned around.

known measurement limit: height is stable frame to frame, footprint
area is NOT. at a 10mm threshold the blob contour sits on the object's
slope, so small height noise moves the boundary a lot (a 16mm blob was
observed swinging between 4 and 30 cm2). anything downstream that uses
area needs temporal smoothing first. height can be trusted raw.

known tracking limit: assign_ids() matches on centroid distance only,
no appearance signal. if an object moves farther than MAX_MATCH_DIST
between two captured frames AND a different object appears within
MAX_MATCH_DIST of its vacated spot in that same frame, the tracker
cannot tell them apart and will assign the old id to whichever blob is
now nearer, not necessarily the original object. verified 12 aug with
a synthetic test, not a hypothetical. not a bug: this is the ceiling
on what position-only matching can do without an appearance feature.
in practice a hand-placed object doesn't cross that distance in one
frame at normal capture rates, so this should stay theoretical.
the separate id-churn-from-noise problem (an object at the noise edge
blinking out for a frame and coming back as a new id) is fixed by the
grace period, see PERSIST_SECONDS and assign_ids().

refs:
    record3d intrinsics come as a coeffs struct, not a matrix:
        https://github.com/marek-simonik/record3d/blob/master/demo-main.py
    depth frame is metric float32 metres from arkit scenedepth:
        https://developer.apple.com/documentation/arkit/arframe/3566299-scenedepth
    plane ransac: standard 3-point sample + inlier count, then svd refit
    connectedComponentsWithStats:
        https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html

# ref: 28 july. v1 read intrinsics per-frame unvalidated, bad fx gave
# inf, every fit returned None and the None path hit `continue` before
# imshow so the failure was silent with no window. v2 fixed that. v3
# dropped keypress-gated noise sampling for an always-on rolling window
# (macos focus problem). v4 added an roi crop, on the theory that a
# large blob (~568mm/~620cm2) was off-table surface past the table
# edge stealing the plane fit.
#
# v5, 12 aug: v4 was wrong. that blob, and later ones at 256mm and
# 357mm, were furniture (a shelf unit, a chair) correctly detected as
# objects standing above the floor. the floor is and always was the
# work surface. the plane fit was correct throughout, three rounds of
# debugging were spent chasing a problem that did not exist. furniture
# is a height problem, not a spatial one, so it is excluded by
# HEIGHT_CEILING instead of cropping the frame. roi removed entirely:
# state, persistence, mouse callback, mask, visualization.
#
# v6, 12 aug: two blob-quality bugs found running v5 against real
# objects. (1) noise speckle blobs at 5-8 per frame against 4 real
# objects, because the tuning floor (3x noise) is a statistical
# minimum not a comfortable margin, and MIN_BLOB_PX filtered on raw
# pixel count, which can't distinguish a small real object from noise
# since the same object covers fewer pixels farther from the camera.
# switched to MIN_BLOB_AREA_CM2 on real area. (2) a brush split into
# two blobs: its handle dips below thresh partway along its length,
# which breaks connectivity for connectedComponentsWithStats. added
# MORPH_CLOSE after the existing MORPH_OPEN to bridge small internal
# gaps without merging objects placed genuinely apart.
#
# v7, 12 aug: persistent id tracker. connectedComponentsWithStats
# numbers blobs by raster-scan discovery order, which reshuffles every
# frame and isn't an identity. added assign_ids(): greedy nearest-
# neighbour centroid matching against the previous frame's tracks,
# closest pairs matched first, MAX_MATCH_DIST caps how far a match can
# be so two distinct nearby objects don't get merged into one identity.
# no grace period on a missed frame yet, see the method docstring.
#
# v8, 12 aug: grace period on missed frames. real hardware log (12 aug)
# showed one object's id climb from 31 to 47 over ~90 frames, id churn
# from noise-edge blinking, exactly the flaw v7's own docstring called
# out as untested. assign_ids() now keeps an unmatched track alive for
# PERSIST_SECONDS and reports it as a "ghost" using its last known
# reading, instead of dropping it the instant one frame misses. same
# pattern track_tabletop.py already uses for YOLO (there: 3.0s).
#
# the "divide by zero encountered in matmul" runtimewarning on apple
# silicon is spurious, accelerate's blas raises fp flags on clean data.
# verified: 49152/49152 valid points, results correct.
"""

import cv2
import time
import numpy as np
from threading import Event
from record3d import Record3DStream

# ── settings ──────────────────────────────────────────────
HEIGHT_THRESH = 0.010      # m above table plane to count as "object". tune live with [ ]
HEIGHT_CEILING = 0.150     # m. above this is furniture (shelf, chair, table edge), not placed input
                            # ref: 12 aug. a 568mm blob (shelf) and later 256mm/357mm blobs
                            # (chair, same shelf) were misdiagnosed as off-table surface / wrong
                            # plane lock across three debugging rounds. all were correctly
                            # detected furniture. no participant object comes near 150mm.
MIN_BLOB_AREA_CM2 = 3.0    # ignore specks, filtered by real area not pixel count
                            # ref: 12 aug. pixel count conflates depth: the same real object
                            # covers fewer pixels the farther it is from the camera, so a
                            # pixel-count filter can't tell a genuine small object from noise
                            # near the threshold floor. area_cm2 is already computed per blob,
                            # this just filters on it before appending instead of after.
CLOSE_KERNEL_PX = 5         # ref: 12 aug. bridges small local height dips within one object
                            # (a brush handle narrowing below thresh mid-length was splitting
                            # into two connected components) without merging objects that are
                            # actually placed apart. tuned for ~75cm working distance (median
                            # depth on the rig, 28 july). revisit if working distance changes.
RANSAC_ITERS = 250
RANSAC_TOL = 0.006         # m. inlier band for the table fit
NOISE_SAMPLE_FRAMES = 30   # rolling window length for the noise floor
NOISE_FLOOR_MULT = 3       # live threshold tuning cannot go below this many x measured noise
                            # ref: 12 aug. speckle blobs at 3-4mm were self-inflicted by tuning
                            # threshold down to 2mm while chasing the phantom plane problem.
MAX_MATCH_DIST = 0.06      # normalised frame units, cx/cy distance ceiling for id matching
                            # ref: 12 aug. objects move by hand between frames, they don't
                            # teleport. ~6% of frame width at ~75cm working distance (28 july
                            # median depth) is generous slack for real hand motion, tight enough
                            # to not accidentally match two distinct nearby objects.
PERSIST_SECONDS = 1.0      # ref: 12 aug. an object right at the noise edge can drop out for a
                            # frame or two, not because it moved, just noise. without this, that
                            # single miss reads as "object gone" and it comes back as a brand
                            # new id. same idea track_tabletop.py already uses for YOLO misses
                            # (there: 3.0s). shorter here since this is a sub-second blip, not a
                            # multi-frame yolo miss. see assign_ids().
DISPLAY_SCALE = 3          # preview is upscaled this much for visibility

# fallback if the device reports unusable intrinsics.
# iphone wide camera is roughly 68 deg horizontal fov.
FALLBACK_HFOV_DEG = 68.0

WINDOW = "depth probe (read-only)"


def fit_plane_ransac(pts, iters=RANSAC_ITERS, tol=RANSAC_TOL):
    """
    ref: 28 july. plain numpy ransac, no open3d/sklearn, keeps deps at
    cv2+numpy+record3d which are all already in use here.
    returns (normal, offset) for plane n.p + c = 0, normal flipped so
    points on the CAMERA side (objects sitting on the table) come out
    positive. expects pts to already be finite.
    """
    n_pts = len(pts)
    if n_pts < 100:
        return None, None

    best_inliers = None
    best_count = 0
    rng = np.random.default_rng(0)

    for _ in range(iters):
        idx = rng.choice(n_pts, 3, replace=False)
        p0, p1, p2 = pts[idx]
        nrm = np.cross(p1 - p0, p2 - p0)
        norm = float(np.linalg.norm(nrm))
        if not np.isfinite(norm) or norm < 1e-9:
            continue
        nrm = nrm / norm
        c = -float(nrm.dot(p0))
        dist = np.abs(pts @ nrm + c)
        inliers = dist < tol
        count = int(inliers.sum())
        if count > best_count:
            best_count = count
            best_inliers = inliers

    if best_inliers is None or best_count < 100:
        return None, None

    # refit on inliers via svd, much more stable than the 3-point sample
    inlier_pts = pts[best_inliers]
    centroid = inlier_pts.mean(axis=0)
    _, _, vh = np.linalg.svd(inlier_pts - centroid, full_matrices=False)
    nrm = vh[2]
    c = -float(nrm.dot(centroid))

    # camera sits at the origin. objects sit between camera and table,
    # so make the origin's signed distance positive.
    if c < 0:
        nrm, c = -nrm, -c

    return nrm, c


class DepthProbe:
    def __init__(self):
        self.event = Event()
        self.session = None
        self.thresh = HEIGHT_THRESH
        self.noise_samples = []   # rolling, always on. no keypress needed.
        self.noise_mean_mm = 0.0  # last rolling noise mean, mm. floors self.thresh in the key handler
        self.intr = None          # cached (fx, fy, tx, ty) for the depth frame
        self.dumped = False

        # persistent id tracking. connectedComponentsWithStats numbers
        # blobs by discovery order (raster-scan position of the first
        # pixel), which reshuffles every frame and means nothing as an
        # object identity. tracks: persistent_id -> last known centroid.
        self.tracks = {}
        self.next_id = 1

    # -- persistent id tracking --

    def assign_ids(self, blobs):
        """
        match this frame's blobs to persistent ids from the previous
        frame via greedy nearest-neighbour centroid matching, closest
        pairs first. replaces connectedComponentsWithStats' discovery-
        order numbering, which carries no identity across frames.

        ref: 12 aug. greedy over hungarian: object count here is single
        digits (dev rig scale), no need for the assignment-optimality
        guarantee scipy's linear_sum_assignment would give, and scipy
        is a new dependency this doesn't need.

        ref: 12 aug, v8. grace period added, this is the actual fix for
        the id-churn bug seen on real hardware (one object at the noise
        edge printed ids 31 through 47 in ~90 frames). a track that
        isn't matched THIS frame is no longer dropped immediately, it's
        kept for PERSIST_SECONDS and returned as a "ghost" blob using
        its last known reading, same pattern track_tabletop.py already
        uses for YOLO misses (there: 3.0s buffer). only a track that
        stays unmatched past PERSIST_SECONDS is actually dropped. a
        real object turning up later than that gets a fresh id, it
        does not "come back" as its old self, there's no way to know
        it's the same object once the grace window has closed.
        """
        now = time.time()
        live_tracks = {tid: tr for tid, tr in self.tracks.items()
                       if now - tr["last_seen"] <= PERSIST_SECONDS}

        candidates = []
        for tid, tr in live_tracks.items():
            for bi, b in enumerate(blobs):
                d = ((tr["cx"] - b["cx"]) ** 2 + (tr["cy"] - b["cy"]) ** 2) ** 0.5
                if d <= MAX_MATCH_DIST:
                    candidates.append((d, tid, bi))
        candidates.sort(key=lambda c: c[0])

        id_for_blob = {}
        used_tracks = set()
        for d, tid, bi in candidates:
            if tid in used_tracks or bi in id_for_blob:
                continue
            used_tracks.add(tid)
            id_for_blob[bi] = tid

        for bi in range(len(blobs)):
            if bi not in id_for_blob:
                id_for_blob[bi] = self.next_id
                self.next_id += 1

        for bi, b in enumerate(blobs):
            b["n"] = id_for_blob[bi]
            b["ghost"] = False

        # carry forward any live track NOT matched this frame as a
        # ghost, using its last known reading. this is the part that
        # actually stops the churn: the object stays "seen" through a
        # brief blip instead of vanishing and coming back as new.
        matched_ids = set(id_for_blob.values())
        for tid, tr in live_tracks.items():
            if tid in matched_ids:
                continue
            ghost = dict(tr["blob"])
            ghost["n"] = tid
            ghost["ghost"] = True
            blobs.append(ghost)

        # rebuild tracks. every blob in this frame's output (real or
        # ghost) refreshes its position, but only a REAL detection
        # refreshes last_seen. a ghost keeps the original timestamp so
        # its grace clock keeps counting down instead of resetting,
        # an object that's genuinely gone still gets dropped on time.
        new_tracks = {}
        for b in blobs:
            tid = b["n"]
            last_seen = live_tracks[tid]["last_seen"] if b["ghost"] else now
            new_tracks[tid] = {"cx": b["cx"], "cy": b["cy"],
                                "last_seen": last_seen, "blob": b}
        self.tracks = new_tracks

        return blobs

    # -- stream --

    def on_new_frame(self):
        self.event.set()

    def on_stream_stopped(self):
        print("\n[!] record3d stream stopped.")

    def connect(self):
        devs = Record3DStream.get_connected_devices()
        print(f"[*] found {len(devs)} device(s)")
        if len(devs) == 0:
            raise SystemExit("no device. is record3d open with usb streaming on?")
        self.session = Record3DStream()
        self.session.on_new_frame = self.on_new_frame
        self.session.on_stream_stopped = self.on_stream_stopped
        self.session.connect(devs[0])

    # -- intrinsics --

    def _raw_coeffs(self):
        """
        record3d has returned intrinsics as a coeffs struct in some
        versions and a 3x3 ndarray in others. handle both.
        """
        try:
            k = self.session.get_intrinsic_mat()
        except Exception as e:
            print(f"[!] get_intrinsic_mat failed: {e}")
            return None

        if hasattr(k, "fx"):
            return float(k.fx), float(k.fy), float(k.tx), float(k.ty)

        arr = np.asarray(k, dtype=np.float64)
        if arr.shape == (3, 3):
            return float(arr[0, 0]), float(arr[1, 1]), float(arr[0, 2]), float(arr[1, 2])

        print(f"[!] unrecognised intrinsics type: {type(k)}")
        return None

    def resolve_intrinsics(self, dw, dh, rgb_shape):
        """
        intrinsics are reported for the RGB frame (1920x1440), depth is
        256x192, so scale by the resolution ratio. verified 28 july:
        1358.38 * (192/1440) = 181.1, matches.
        """
        coeffs = self._raw_coeffs()
        fx = fy = tx = ty = None

        if coeffs is not None and len(rgb_shape) >= 2:
            rh, rw = rgb_shape[0], rgb_shape[1]
            if rw > 0 and rh > 0:
                sx, sy = dw / rw, dh / rh
                fx, fy = coeffs[0] * sx, coeffs[1] * sy
                tx, ty = coeffs[2] * sx, coeffs[3] * sy

        vals = (fx, fy, tx, ty)
        ok = all(v is not None and np.isfinite(v) for v in vals)
        if ok:
            ok = fx > 1.0 and fy > 1.0

        if not ok:
            f = dw / (2.0 * np.tan(np.radians(FALLBACK_HFOV_DEG) / 2.0))
            fx = fy = float(f)
            tx, ty = dw / 2.0, dh / 2.0
            print(f"[!] intrinsics unusable, falling back to {FALLBACK_HFOV_DEG} deg "
                  f"fov estimate: fx={fx:.1f}")

        return float(fx), float(fy), float(tx), float(ty)

    def unproject(self, depth, fx, fy, tx, ty):
        """depth pixel grid -> (H,W,3) camera-space points, plus valid mask."""
        dh, dw = depth.shape[:2]
        us, vs = np.meshgrid(np.arange(dw, dtype=np.float32),
                             np.arange(dh, dtype=np.float32))
        z = depth
        valid = (z > 0.05) & (z < 5.0) & np.isfinite(z)

        with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
            x = (us - tx) * z / fx
            y = (vs - ty) * z / fy

        pts = np.stack([x, y, z], axis=-1)
        finite = np.isfinite(pts).all(axis=-1)
        valid = valid & finite
        pts = np.nan_to_num(pts, nan=0.0, posinf=0.0, neginf=0.0)
        return pts, valid

    def run(self):
        self.connect()
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        print("[*] connected.")
        print("[*] keys: [ ]=threshold down/up (floor 3x noise), q=quit")

        while True:
            self.event.wait()
            self.event.clear()

            depth = np.asarray(self.session.get_depth_frame(), dtype=np.float32)
            rgb = np.asarray(self.session.get_rgb_frame())
            if depth.ndim != 2 or depth.size == 0:
                continue
            dh, dw = depth.shape[:2]

            if self.intr is None:
                self.intr = self.resolve_intrinsics(dw, dh, rgb.shape)
            fx, fy, tx, ty = self.intr

            pts, valid = self.unproject(depth, fx, fy, tx, ty)
            flat = pts[valid]

            # one-shot diagnostic dump
            if not self.dumped:
                self.dumped = True
                dv = depth[np.isfinite(depth) & (depth > 0)]
                print("\n--- device dump ---")
                print(f"depth frame : {depth.shape} {depth.dtype}")
                print(f"rgb frame   : {rgb.shape}")
                print(f"raw coeffs  : {self._raw_coeffs()}")
                print(f"depth intr  : fx={fx:.1f} fy={fy:.1f} tx={tx:.1f} ty={ty:.1f}")
                if len(dv):
                    print(f"depth range : {dv.min():.3f} to {dv.max():.3f} m "
                          f"(median {np.median(dv):.3f})")
                else:
                    print("depth range : NO VALID DEPTH VALUES")
                print(f"valid pts   : {int(valid.sum())} / {depth.size}")
                print("---\n")

            nrm = c = None
            if len(flat) >= 500:
                nrm, c = fit_plane_ransac(flat)

            blobs = []
            noise_std_mm = 0.0
            mask = np.zeros((dh, dw), np.uint8)
            height = np.zeros((dh, dw), np.float32)

            if nrm is not None:
                height = (pts @ nrm + c).astype(np.float32)
                height[~valid] = 0.0

                resid = height[valid]
                table_resid = resid[np.abs(resid) < RANSAC_TOL]
                noise_std_mm = float(table_resid.std() * 1000) if len(table_resid) else 0.0

                mask = ((height > self.thresh) & valid).astype(np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
                # ref: 12 aug. close after open: bridges a local height dip
                # (brush handle) back into one component. open still runs
                # first to drop single-pixel speckle before closing has a
                # chance to bridge speckle into something bigger.
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                                        np.ones((CLOSE_KERNEL_PX, CLOSE_KERNEL_PX), np.uint8))
                n_lab, labels, stats, cents = cv2.connectedComponentsWithStats(mask, 8)

                # per-pixel ground area at depth z is z^2/(fx*fy)
                # ref: 28 july. real cm2 footprint, not a pixel count.
                # NOTE: noisy frame to frame, see header. smooth before use.
                px_area = (depth ** 2) / (fx * fy)

                for i in range(1, n_lab):
                    sel = labels == i
                    area_cm2 = float(px_area[sel].sum() * 10000)
                    # ref: 12 aug. was stats[i, cv2.CC_STAT_AREA] < MIN_BLOB_PX
                    # (raw pixel count). switched to real area: pixel count for
                    # the same physical object shrinks with distance, so it
                    # can't distinguish a small real object from noise.
                    if area_cm2 < MIN_BLOB_AREA_CM2:
                        continue
                    hs = height[sel]
                    max_m = float(hs.max())
                    # ref: 12 aug. furniture stands above the floor same as a
                    # placed object. exclude by height, not by cropping the
                    # frame. see HEIGHT_CEILING above.
                    if max_m > HEIGHT_CEILING:
                        continue
                    blobs.append({
                        "max_mm": max_m * 1000,
                        "mean_mm": float(hs.mean() * 1000),
                        "area_cm2": area_cm2,
                        "cx": float(cents[i][0] / dw),
                        "cy": float(cents[i][1] / dh),
                    })

                blobs = self.assign_ids(blobs)

            # rolling noise floor, always on. keypress-gated version was
            # unreliable, macos only delivers keys to a focused window.
            if nrm is not None:
                self.noise_samples.append(noise_std_mm)
                self.noise_samples = self.noise_samples[-NOISE_SAMPLE_FRAMES:]
                self.noise_mean_mm = float(np.mean(self.noise_samples))

            # console readout
            if nrm is None:
                line = "PLANE FIT FAILED (no dominant plane in frame)"
            else:
                line = (f"thresh={self.thresh*1000:.0f}mm "
                        f"noise={self.noise_mean_mm:.1f}mm (need >{self.noise_mean_mm*3:.0f}mm)  ")
                line += "  ".join(
                    f"[{b['n']}]{'~' if b.get('ghost') else ''} {b['max_mm']:.0f}mm {b['area_cm2']:.0f}cm2"
                    for b in blobs
                ) if blobs else "no blobs"
            print(f"\r{line}" + " " * 20, end="", flush=True)

            # visual. always drawn, even on fit failure.
            if nrm is not None:
                vis_src = np.clip(height / 0.15, 0, 1)
            else:
                dvalid = np.isfinite(depth) & (depth > 0)
                dmax = float(depth[dvalid].max()) if dvalid.any() else 1.0
                vis_src = np.clip(depth / max(dmax, 1e-6), 0, 1)

            vis = (np.nan_to_num(vis_src) * 255).astype(np.uint8)
            vis = cv2.applyColorMap(vis, cv2.COLORMAP_TURBO)
            vis[~(np.isfinite(depth) & (depth > 0))] = 0

            for b in blobs:
                px, py = int(b["cx"] * dw), int(b["cy"] * dh)
                # ref: 12 aug. orange = held (ghost, not seen this exact
                # frame, riding out its grace period). white = actually
                # detected right now. lets you SEE the fix working
                # instead of just trusting the console text.
                color = (0, 165, 255) if b.get("ghost") else (255, 255, 255)
                cv2.circle(vis, (px, py), 4, color, -1)
                cv2.putText(vis, f"{b['n']}:{b['max_mm']:.0f}mm" + ("~" if b.get("ghost") else ""),
                            (px + 6, py - 6), cv2.FONT_HERSHEY_SIMPLEX,
                            0.35, color, 1)

            if mask.any():
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                               cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(vis, contours, -1, (255, 255, 255), 1)

            if nrm is None:
                cv2.putText(vis, "PLANE FIT FAILED", (6, 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            else:
                cv2.putText(vis,
                            f"noise {self.noise_mean_mm:.1f}mm  min obj {self.noise_mean_mm*3:.0f}mm",
                            (6, dh - 6), cv2.FONT_HERSHEY_SIMPLEX,
                            0.35, (255, 255, 255), 1)

            vis = cv2.resize(vis, (dw * DISPLAY_SCALE, dh * DISPLAY_SCALE),
                             interpolation=cv2.INTER_NEAREST)
            cv2.imshow(WINDOW, vis)

            k = cv2.waitKey(1) & 0xFF
            if k == ord("q"):
                break
            elif k == ord("["):
                floor = max(0.002, (self.noise_mean_mm * NOISE_FLOOR_MULT) / 1000.0)
                self.thresh = max(floor, self.thresh - 0.002)
            elif k == ord("]"):
                self.thresh = min(0.100, self.thresh + 0.002)

        cv2.destroyAllWindows()
        print("\n[*] done.")


if __name__ == "__main__":
    DepthProbe().run()