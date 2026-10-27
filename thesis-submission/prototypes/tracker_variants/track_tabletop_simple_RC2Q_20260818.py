"""
track_tabletop_simple.py
------------------------
single-file experimental tracker for Tangible Worlds.

current stage
-------------
Record3D RGB + LiDAR depth
-> select tabletop ROI
-> empty-table calibration fits one plane
-> depth connected components detect props
-> separate edge-connected foreground detects hand/body
-> hand/body never enters normal id assignment
-> body-to-last-clean-object-surface distance latches an existing id
-> the latch reserves a known id through a real manipulation episode.
-> live digital movement during the hand episode is NOT wired yet.

why this file exists
--------------------
this is the revert file plus loop instrumentation. it measures where the
frame loop spends its time, because the live preview ran far behind the
real table. identity logic, detection, masks and calibration are all
unchanged from track_tabletop_simple_REVERT_20260817.py.

per-frame terminal printing is replaced by one summary line per second.
python flushes stdout on every print, so a fast loop printing every frame
can be throttled by the terminal rather than by the code.

body episodes are reported, and prop height is now a high percentile of
the component instead of its single tallest pixel. hardware showed one
stationary prop reading 16mm, then 26mm, then 40mm across moves, far past
the re-id height tolerance, so the same prop was read as a new one. a
percentile ignores a few stray tall pixels at the component edge.

both numbers are printed side by side as percentile/max so the difference
can be watched before the percentile is trusted.

this version also prints why a blob failed to match anything already in
memory, before it enters tentative new-object confirmation.

that diagnostic showed the real fault. the body signal drops out for a
frame or two while a hand is still over the table. on those frames the
loop resumed measuring, filed a forearm away as a prop, and measured a
half covered prop at a third of its real height. the stale height then
rejected the prop when it was finally put down.

so the body state is held for a short settle window after the hand appears
to leave. the table must look clear for several frames in a row before
identity is allowed to resume.

height is no longer used to decide identity. it is measured against one
plane fitted once from an empty table, so it drifts with camera pose and
with position across the surface. hardware showed a stationary prop
reading 20, 22, 24, 26 then 28mm, and a moved prop failing a match with
area agreeing to within one percent while height differed by 147 percent.
height is still measured, published and printed, because terrain wants it
and a few millimetres of drift do not matter there. it just does not
decide which prop is which.

identity after a move is now decided by a small nearest-centroid classifier
over shape and colour, learned from the props themselves while they are
being handled. a logged capture of four props showed the outline features
carrying information the stored single snapshot never had: trained on the
first third of each prop and tested on the last third, shape plus colour
scored 99.4 percent against 90.1 percent for the old area, height and
colour snapshot, and 55.9 percent for area alone.

the classifier refuses rather than guesses. if the nearest prop is too far
away, or the runner up is nearly as close, the blob remains unclaimed. a new
unclaimed detection must now persist before receiving a public id.
project decision: measure before changing detection or identity again.

this version adds one missing case: two known props can become one connected
component when they touch. that single component is treated as a merged
measurement, not a new physical object. both original ids stay alive while
merged, and neither id learns from the merged outline. when the component
splits again, the existing learned classifier assigns the two separate blobs
back to the two stored ids.

rc1 changes, 18 august
----------------------
this release-candidate development build treats identity as one explicit session
lifecycle rather than a chain of isolated re-identification fixes. participants
place the complete prop set first, then press l to start a bounded learning phase
and k to lock it. starting learning locks the public object roster. after that no
new semantic id can be invented during movement, merge, split or noise.

classifier memory is built only inside the explicit learning phase and becomes
read-only after lock. learning requires every confirmed prop to be present,
separate and matched by ordinary physical continuity. merged, manipulated,
missing, tentative and ambiguous observations never train an identity.

merge reasoning now runs before the wider ordinary proximity matcher. on the
first clean frame after a hand episode, any component whose footprint plausibly
represents two previous objects is protected from single-object matching while
unchanged objects are resolved. residual two-to-one state can then declare the
merge before one member swallows the combined blob.

debug build
-----------
this file keeps the MERGE detector/classifier evidence, but changes track state
management after the 17 august hardware debug run exposed two separate faults:
(1) a touched known prop could be rejected by appearance after a move even though
interaction had already identified it, and (2) short-lived 4cm2 / 7mm depth
fragments could immediately become public semantic ids.

known objects now have interaction continuity: if a latched id is not still at
its old position after release, that id is reserved and the remaining plausible
released blob inherits it after unchanged objects are matched. classifier evidence
can support this decision but cannot veto a single unambiguous release candidate.

new detections are probationary before they receive a public id. this follows the
track-management principle in SORT: a new track should accumulate evidence before
it is confirmed, specifically to avoid false-positive tracks. tentative detections
are never eligible for manipulation latching and are never written to scene_state.

debug logging stays enabled throughout this experimental state-machine build.

external references
-------------------
FlowPut:
Jan Riemann, Martin Schmitz, Alexander Hendrich, Max Muehlhaeuser,
"FlowPut: Environment-Aware Interactivity for Tangible 3D Objects",
Proc. ACM IMWUT 2(1), Article 31, March 2018.
DOI: 10.1145/3191763
https://doi.org/10.1145/3191763
Relevant sections:
- 4.1.2: table-plane removal / height threshold.
- 4.1.3: cluster above-table points and classify edge-entering clusters
  as body.
- 4.4: compute distance from body-cluster points to tracked object
  surfaces for touch.
- 9.3: documents the edge-entering body heuristic and its limitations.

Record3D official Python demo:
https://github.com/marek-simonik/record3d/blob/master/demo-main.py
Used for Record3DStream, RGB/depth frames and camera intrinsics.

OpenCV official docs:
selectROI:
https://docs.opencv.org/4.x/d7/dfc/group__highgui.html
morphologyEx:
https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html
connectedComponentsWithStats:
https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html
calcHist / compareHist:
https://docs.opencv.org/4.x/d8/dc8/tutorial_histogram_comparison.html

NumPy SVD:
https://numpy.org/doc/stable/reference/generated/numpy.linalg.svd.html

Interactive Perception:
Jeannette Bohg, Karol Hausman, Bharath Sankaran, Oliver Brock,
Danica Kragic, Stefan Schaal, Gaurav S. Sukhatme,
"Interactive Perception: Leveraging Action in Perception and Perception
in Action", IEEE Transactions on Robotics 33(6), 1273-1291, 2017.
DOI: 10.1109/TRO.2017.2721939
https://doi.org/10.1109/TRO.2017.2721939
Used only as the idea that touching an object is itself evidence about
which object it is. no algorithm taken.

Merged measurements:
Joao F. Henriques, Rui Caseiro, Jorge Batista,
"Globally Optimal Solution to Multi-Object Tracking with Merged Measurements",
ICCV 2011, pp. 2470-2477.
DOI: 10.1109/ICCV.2011.6126532
https://www.robots.ox.ac.uk/~joao/publications/henriques_iccv2011.pdf
Relevant sections:
- abstract / section 1: one measurement can represent several objects.
- section 2.2: merges and splits need many-to-one / one-to-many handling.
- section 4: individual identities are recovered across grouped measurements.
this file borrows only that merge-group principle. it does not implement the
paper's global graph optimisation.


Track confirmation / probationary births:
Alex Bewley, Zongyuan Ge, Lionel Ott, Fabio Ramos, Ben Upcroft,
"Simple Online and Realtime Tracking", ICIP 2016.
DOI: 10.1109/ICIP.2016.7533003
https://arxiv.org/abs/1602.00763
Relevant section 3.4: a new tracker undergoes a probationary period and must
accumulate enough detection evidence to prevent false-positive tracks.
This file borrows only that track-management principle. it does not implement
SORT's Kalman filter, IOU association or Hungarian assignment.

Hand-object tracking:
Srinath Sridhar, Franziska Mueller, Michael Zollhoefer, Dan Casas,
Antti Oulasvirta, Christian Theobalt,
"Real-time Joint Tracking of a Hand Manipulating an Object from RGB-D
Input", ECCV 2016.
arXiv: 1610.04889
https://arxiv.org/abs/1610.04889
Used only as the idea that contact and occlusion are constraints. no
hand-pose model taken.

project decisions, not claims from any of the above
---------------------------------------------------
arbitrary everyday props have no pre-scanned model, so where FlowPut
measures body-to-model distance i use the last clean LiDAR surface seen
for each prop.
static edge foreground found during empty-table calibration is remembered
and excluded from later body evidence.
body detection has no 150mm prop ceiling so the arm stays connected to the
workspace edge. prop detection keeps the ceiling.
RGB histogram is supporting re-id evidence only. the durable semantic
handle is the numeric id, never a detector class.
no YOLO, SAM2, neural hand model, carry timer or ghost object is used here.
the tracker has explicit confirmed, manipulated, missing and merged public-id
states. tentative detections are pre-id candidates. starting learning locks the
public roster and locking learning freezes all identity templates.
"""

import cv2, json, math, os, sys, time, warnings
from itertools import combinations, permutations
import numpy as np
from threading import Event
from record3d import Record3DStream

OUT_FILE = "scene_state.json"
WINDOW = "Tangible Worlds - Simple Hybrid Tracker"
DEBUG_ROOT = "tracker_debug"
QUALIFICATION_RESULTS_PATH = os.path.join(DEBUG_ROOT, "qualification_results.txt")
DEBUG_FEATURE_NAMES = ["elongation", "circularity", "hu1", "hu2",
                       "hue_mean", "hue_std", "sat_mean", "val_mean", "val_std"]

CALIBRATION_FRAMES = 30
CALIBRATION_MULT = 5.0
MIN_THRESHOLD_MM = 6.0
MAX_THRESHOLD_MM = 20.0
HEIGHT_CEILING_MM = 150.0
MIN_AREA_CM2 = 3.0
# project decision: report height as this percentile of the component, not
# its maximum. the ceiling test still uses the maximum, so tall things are
# rejected exactly as before.
HEIGHT_PCT = 95.0
ROI_BORDER_PX = 2

# project decisions: identity classifier settings, chosen from a logged
# capture of four real props rather than by hand. the distance threshold
# trades two failures against each other, measured on that capture:
#
#   maxdist   known prop recognised   unseen prop refused
#     0.50          251/329                250/251
#     0.55          259/329                232/251
#     0.60          297/329                179/251
#     0.80          326/329                 20/251
#
# a loose threshold recognises known props well but quietly absorbs a newly
# introduced prop into an existing id, which silently gives two physical
# objects one meaning. a tight threshold refuses more often, which costs a
# spare id number that the conversational layer can repair. 0.55 is chosen
# because the recoverable failure is preferred. no setting gave a wrong
# assignment between learned props.
# CLASS_SCALE is the spread of each feature across that capture. it is fixed
# rather than measured live so a distance means the same thing whether one
# prop has been learned or six. features in order: elongation, circularity,
# hu1, hu2, hue mean, hue spread, saturation mean, value mean, value spread.
# ref: Hu 1962, "Visual pattern recognition by moment invariants",
# IRE Trans. Information Theory 8(2), 179-187, DOI 10.1109/TIT.1962.1057692
# ref: https://docs.opencv.org/4.x/dd/d49/tutorial_py_contour_features.html
CLASS_SCALE = np.array([0.2424, 0.0562, 0.0263, 0.7915,
                        42.9082, 28.6348, 43.0794, 47.3566, 17.4596], np.float32)
CLASS_MIN_SAMPLES = 20
CLASS_MAX_SAMPLES = 200
LEARN_SAMPLE_EVERY = 3
CLASS_MAX_DIST = 0.55
CLASS_MARGIN = 1.4

# project decision: the two hardware merge logs were within about 5 percent
# of the two separate footprint areas added together. 15 percent leaves a
# wider test margin without making ordinary single blobs look like merges.
# MERGE_MIN_ADDED_FRAC also requires the candidate to contain at least half
# of the moved object's old area on top of the stationary object's area.
# both are hardware-test values, not values claimed by the paper below.
# ref: Henriques et al. 2011, ICCV, merged measurements.
# https://www.robots.ox.ac.uk/~joao/publications/henriques_iccv2011.pdf
MERGE_AREA_TOL = 0.15
MERGE_MIN_ADDED_FRAC = 0.50

# project decisions from the 17 august hardware debug run. new detections are
# tentative first. a detection that appears on the first clean frame after a
# hand episode can confirm quickly; spontaneous detections need longer evidence.
# ref: Bewley et al. 2016, SORT, section 3.4, DOI 10.1109/ICIP.2016.7533003
NEW_CONFIRM_RELEASE_FRAMES = 6
NEW_CONFIRM_BACKGROUND_FRAMES = 30
NEW_CANDIDATE_DIST_CM = 3.0
NEW_CANDIDATE_AREA_MIN = 0.50
NEW_CANDIDATE_AREA_MAX = 2.00
NEW_CANDIDATE_MAX_MISSES = 2

# project decision: interaction continuity owns a normal one-object move. the
# area gate is deliberately loose. it only rejects an obviously implausible
# leftover blob before giving the latched id back by exclusion.
RELEASE_AREA_MIN = 0.35
RELEASE_AREA_MAX = 1.70

# project decision from 18 aug hardware debug. between clean frames, a
# confirmed prop that is still essentially in the same tabletop place keeps
# its id from geometry alone. rgb is supporting evidence and cannot veto
# near-zero physical continuity. this is deliberately much tighter than the
# ordinary 10cm proximity matcher, so it cannot bridge a real hand move.
CONTINUITY_MATCH_CM = 2.0
CONTINUITY_AREA_MIN = 0.60
CONTINUITY_AREA_MAX = 1.60

# project decision, 18 aug 2026: learning is an explicit bounded session phase.
# all intended props must already be confirmed and separate before it starts.
# start-learning locks the public roster; stop-learning freezes every learned
# template for the rest of the run. no runtime dependency or external model.
LEARN_AREA_MIN = 0.70
LEARN_AREA_MAX = 1.30
UNKNOWN_ANOMALY_COOLDOWN_FRAMES = 60

# project decision, 18 aug 2026 RC2: after learning lock, the roster is a
# closed set. an unmatched known id stays missing rather than disappearing.
# exclusion recovery is deliberately loose on appearance but still requires
# a physically plausible footprint. with several missing ids it refuses an
# ambiguous global permutation rather than silently swapping meanings.
ROSTER_AREA_MIN = 0.45
ROSTER_AREA_MAX = 1.75
ROSTER_GLOBAL_MARGIN = 1.18
SPLIT_AREA_MIN = 0.45
SPLIT_AREA_MAX = 1.75

# project decisions: tolerances tuned by hand on this table, no source.
VISIBLE_MATCH_CM = 10.0
ACTIVE_MAX_AREA_GROWTH = 2.0
ACTIVE_HIST_MIN = 0.20
BODY_EDGE_PX = 2
BODY_MIN_AREA_CM2 = 20.0
# project decision: consecutive clear frames required before the body state
# is released. a one frame dropout while a hand is still over the table used
# to let a forearm become a prop and let a covered prop be remeasured.
BODY_CLEAR_FRAMES = 5
TOUCH_DISTANCE_CM = 3.0
MAX_BODY_POINTS = 900
MAX_SURFACE_POINTS = 600
DISTANCE_BLOCK = 96

OPEN_KERNEL = np.ones((3, 3), np.uint8)
CLOSE_KERNEL = np.ones((5, 5), np.uint8)


def fit_plane(points):
    """fit one plane to the table.
    # ref: https://numpy.org/doc/stable/reference/generated/numpy.linalg.svd.html
    # ref: Riemann et al. 2018, FlowPut, DOI 10.1145/3191763, section 4.1.2"""
    if len(points) < 100: raise RuntimeError("not enough valid table points")
    centre = points.mean(axis=0)
    _, _, vh = np.linalg.svd(points - centre, full_matrices=False)
    n = vh[-1] / np.linalg.norm(vh[-1]); c = -float(n.dot(centre))
    if c < 0: n, c = -n, -c  # project decision: keep the plane normal pointing up.
    return n.astype(np.float32), c, centre.astype(np.float32)


def plane_axes(n):
    u = np.array([1., 0., 0.], np.float32); u -= n * float(u.dot(n))
    if np.linalg.norm(u) < 1e-6:
        u = np.array([0., 1., 0.], np.float32); u -= n * float(u.dot(n))
    u /= np.linalg.norm(u); v = np.cross(n, u); v /= np.linalg.norm(v)
    return u, v


def shape_colour_vector(sel, bbox, hsv):
    """nine numbers describing a prop: four about its outline, five about its
    colour. the outline numbers barely move when a prop is turned over, which
    is why they hold where height and colour alone did not.
    # ref: https://docs.opencv.org/4.x/dd/d49/tutorial_py_contour_features.html
    # ref: https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html
    # ref: Hu 1962, DOI 10.1109/TIT.1962.1057692"""
    x, y, w, h = bbox
    patch = sel[y:y+h, x:x+w].astype(np.uint8)
    contours, _ = cv2.findContours(patch, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return None
    c = max(contours, key=cv2.contourArea)
    px_area = float(cv2.contourArea(c))
    perimeter = float(cv2.arcLength(c, True))
    if px_area <= 0 or perimeter <= 0: return None
    (_, _), (rw, rh), _ = cv2.minAreaRect(c)
    short, long = sorted((float(rw), float(rh)))
    elongation = long / max(short, 1e-6)
    circularity = 4.*math.pi*px_area / (perimeter*perimeter)
    hu = cv2.HuMoments(cv2.moments(c)).flatten()[:2]
    hu = [float(-math.copysign(1., v)*math.log10(abs(v))) if abs(v) > 1e-30 else 0. for v in hu]
    out = [elongation, circularity, hu[0], hu[1]]
    hue = hsv[:, :, 0][sel].astype(np.float32)
    sat = hsv[:, :, 1][sel].astype(np.float32)
    val = hsv[:, :, 2][sel].astype(np.float32)
    if hue.size == 0: return None
    out += [float(hue.mean()), float(hue.std()), float(sat.mean()),
            float(val.mean()), float(val.std())]
    vector = np.array(out, np.float32)
    return vector if np.all(np.isfinite(vector)) else None


def bounded_points(points, limit):
    """project decision: cap point counts so distance maths stays cheap."""
    if len(points) <= limit: return points.copy()
    idx = np.linspace(0, len(points)-1, limit).astype(np.int32)
    return points[idx].copy()


class SimpleHybridTracker:
    def __init__(self):
        self.event = Event(); self.session = None; self.intr = None; self.roi = None
        self.n = self.c = self.origin = self.u = self.v = None
        self.threshold_m = MIN_THRESHOLD_MM / 1000.; self.body_background = None
        self.active = {}; self.memory = {}; self.next_id = 1
        # ref: Riemann et al. 2018, FlowPut, DOI 10.1145/3191763, section 4.4
        self.manipulated_id = None
        # ref: Henriques et al. 2011, ICCV, merged measurements.
        # project adaptation: only one pair is held as merged at a time.
        self.merged_pair = None
        # instrumentation only. counted here, printed once a second in run().
        self.n_restored = 0; self.n_new = 0; self.n_body = 0; self.diag = "none"
        self.frame_count = 0
        # project diagnostic: these fields never feed identity decisions.
        # they only record enough state to replay a failure after hardware use.
        self.debug_dir = None
        self.debug_log_path = None
        self.debug_event = 0
        self.debug_last_frame = None
        # tentative detections have no semantic id and cannot be manipulated.
        # ref: Bewley et al. 2016, SORT, section 3.4.
        self.pending_new = {}
        self.next_pending = 1
        # project decision, 18 aug 2026: explicit learning owns the identity
        # template. once learning starts the participant's prop roster is closed.
        self.learning_mode = False
        self.learning_locked = False
        self.roster_locked = False
        self.learning_buffers = {}
        self.learning_frames = 0
        self.track_state = {}
        self.unknown_last_saved_frame = -10**9
        # project decision, 18 aug 2026 RC2: active means visible now;
        # last_known is the durable state of every locked roster member.
        self.last_known = {}
        # multiple hands may touch multiple props in the same episode. the
        # set is supporting evidence only; global roster recovery owns release.
        self.manipulated_ids = set()

    def on_new_frame(self): self.event.set()
    def on_stream_stopped(self): print("\n[!] Record3D stream stopped")

    def setup_debug(self):
        """make one folder per hardware run. diagnostic only."""
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.debug_dir = os.path.join(DEBUG_ROOT, f"run_{stamp}")
        os.makedirs(self.debug_dir, exist_ok=True)
        self.debug_log_path = os.path.join(self.debug_dir, "events.jsonl")
        self.debug_write("run_start", {
            "source": "track_tabletop_simple_RC2Q_20260818.py",
            "class_max_dist": CLASS_MAX_DIST,
            "class_margin": CLASS_MARGIN,
            "visible_match_cm": VISIBLE_MATCH_CM,
            "active_hist_min": ACTIVE_HIST_MIN,
            "active_max_area_growth": ACTIVE_MAX_AREA_GROWTH,
            "merge_area_tol": MERGE_AREA_TOL,
            "learn_sample_every": LEARN_SAMPLE_EVERY,
            "learn_min_samples": CLASS_MIN_SAMPLES,
            "roster_locks_on_learning_start": True,
        })
        print(f"[d] debug folder: {self.debug_dir}")

    def debug_write(self, event, data=None):
        """append one JSON record. this function has no effect on tracking."""
        if self.debug_log_path is None: return
        record = {"time": time.time(), "frame": self.frame_count, "event": event}
        if data: record.update(data)
        with open(self.debug_log_path, "a") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")

    def debug_blob(self, b):
        feat = b.get("feat")
        return {
            "tx": float(b["tx"]), "ty": float(b["ty"]),
            "area": float(b["area"]), "height": float(b["height"]),
            "max_height": float(b["max_height"]), "depth": float(b["depth"]),
            "bbox": [int(v) for v in b["bbox"]],
            "feat": None if feat is None else [float(v) for v in feat],
        }

    def debug_active_state(self):
        out = {}
        for object_id, old in self.active.items():
            out[str(object_id)] = {
                "tx": float(old["tx"]), "ty": float(old["ty"]),
                "area": float(old.get("area", self.memory[object_id]["area"])),
                "height": float(old.get("height", self.memory[object_id]["height"])),
                "samples": len(self.memory[object_id]["samples"]),
                "state": self.track_state.get(object_id, "confirmed"),
            }
        return out

    def debug_feature_breakdown(self, feat, object_id):
        """show which learned features contribute to one class distance."""
        if feat is None or object_id not in self.memory: return None
        samples = self.memory[object_id]["samples"]
        if len(samples) < CLASS_MIN_SAMPLES: return None
        centre = np.array(samples).mean(axis=0)
        scaled = np.abs((feat - centre) / CLASS_SCALE)
        order = np.argsort(scaled)[::-1]
        return {
            "distance": self.class_distance(feat, object_id),
            "blob": [float(v) for v in feat],
            "centre": [float(v) for v in centre],
            "scaled_abs_delta": [float(v) for v in scaled],
            "largest": [
                {"feature": DEBUG_FEATURE_NAMES[int(i)], "scaled_delta": float(scaled[i])}
                for i in order[:4]
            ],
        }

    def debug_matrix(self, blobs):
        """all old-id/blob evidence used by proximity and classifier passes."""
        rows = []
        for object_id, old in self.reference_tracks().items():
            ref = self.memory[object_id]
            for bi, b in enumerate(blobs):
                d = float(np.hypot(b["tx"]-old["tx"], b["ty"]-old["ty"]))
                rgb = float(cv2.compareHist(b["hist"], ref["hist"], cv2.HISTCMP_CORREL))
                area_growth = float(b["area"] / max(ref["area"], 1e-6))
                rows.append({
                    "id": int(object_id), "blob": int(bi),
                    "position_cm": d, "hist_corr": rgb,
                    "area_growth_vs_memory": area_growth,
                    "proximity_candidate": bool(
                        d <= VISIBLE_MATCH_CM and
                        b["area"] <= ref["area"]*ACTIVE_MAX_AREA_GROWTH and
                        rgb >= ACTIVE_HIST_MIN
                    ),
                    "class_distance": self.class_distance(b.get("feat"), object_id),
                })
        return rows

    def debug_release_frame(self, blobs, body_frames, raw_frames):
        """log the first clean frame after a hand/body episode."""
        moved = self.manipulated_id
        data = {
            "manipulated_id": moved,
            "body_frames": int(body_frames), "raw_body_frames": int(raw_frames),
            "active": self.debug_active_state(),
            "blobs": [self.debug_blob(b) for b in blobs],
            "matrix": self.debug_matrix(blobs),
            "merged_ids": None if self.merged_pair is None else list(self.merged_pair["ids"]),
        }
        self.debug_write("release_first_clean", data)
        refs = self.reference_tracks()
        if moved is None or moved not in refs:
            print(f"[d] release frame: latch=none visible={len(self.active)} roster={len(refs)} blobs={len(blobs)}")
            return
        old = refs[moved]
        print(f"[d] release frame for #{moved}: old=({old['tx']:.1f},{old['ty']:.1f})cm "
              f"area={old['area']:.0f} blobs={len(blobs)}")
        for bi, b in enumerate(blobs):
            pos = float(np.hypot(b["tx"]-old["tx"], b["ty"]-old["ty"]))
            rgb = float(cv2.compareHist(b["hist"], self.memory[moved]["hist"], cv2.HISTCMP_CORREL))
            cd = self.class_distance(b.get("feat"), moved)
            print(f"[d]   b{bi}: pos={pos:.1f}cm area={b['area']:.0f} hist={rgb:.2f} class#{moved}={cd:.2f}")

    def debug_save_anomaly(self, reason, blobs, extra=None):
        """save exact detector/classifier state only when something suspicious happens."""
        if self.debug_dir is None: return
        self.debug_event += 1
        stem = f"anomaly_{self.debug_event:03d}_{reason}"
        data = {
            "reason": reason,
            "manipulated_id": self.manipulated_id,
            "active": self.debug_active_state(),
            "blobs": [self.debug_blob(b) for b in blobs],
            "matrix": self.debug_matrix(blobs),
            "merged_ids": None if self.merged_pair is None else list(self.merged_pair["ids"]),
        }
        if extra: data.update(extra)
        json_path = os.path.join(self.debug_dir, stem + ".json")
        with open(json_path, "w") as f: json.dump(data, f, indent=2)

        arrays = {}
        frame = self.debug_last_frame
        if frame is not None:
            arrays["depth"] = frame["depth"]
            arrays["height"] = frame["height"]
            arrays["valid"] = frame["valid"]
            arrays["mask"] = frame["mask"]
            arrays["preview"] = frame["preview"]
            cv2.imwrite(os.path.join(self.debug_dir, stem + "_preview.png"), frame["preview"])
            cv2.imwrite(os.path.join(self.debug_dir, stem + "_mask.png"), frame["mask"] * 255)
        for object_id, mem in self.memory.items():
            arrays[f"samples_id{object_id}"] = np.array(mem["samples"], np.float32)
            arrays[f"hist_id{object_id}"] = mem["hist"]
            if object_id in self.active:
                arrays[f"surface_id{object_id}"] = self.active[object_id]["surface"]
        if arrays:
            # ref: https://numpy.org/doc/stable/reference/generated/numpy.savez_compressed.html
            np.savez_compressed(os.path.join(self.debug_dir, stem + ".npz"), **arrays)
        self.debug_write("anomaly_saved", {"reason": reason, "stem": stem})
        print(f"[d] saved anomaly: {os.path.join(self.debug_dir, stem)}")

    def connect(self):
        """# ref: https://github.com/marek-simonik/record3d/blob/master/demo-main.py"""
        devices = Record3DStream.get_connected_devices(); print(f"[*] found {len(devices)} Record3D device(s)")
        if not devices: raise SystemExit("no Record3D device found")
        self.session = Record3DStream(); self.session.on_new_frame = self.on_new_frame
        self.session.on_stream_stopped = self.on_stream_stopped; self.session.connect(devices[0]); print("[*] connected")

    def frame(self):
        """# ref: https://github.com/marek-simonik/record3d/blob/master/demo-main.py"""
        self.event.wait(); self.event.clear()
        rgb = np.asarray(self.session.get_rgb_frame())
        depth = np.asarray(self.session.get_depth_frame(), dtype=np.float32)
        if rgb.size == 0 or depth.ndim != 2 or depth.size == 0: return None, None
        return rgb, depth

    def raw_intrinsics(self):
        """# ref: https://github.com/marek-simonik/record3d/blob/master/demo-main.py"""
        k = self.session.get_intrinsic_mat()
        if hasattr(k, "fx"): return float(k.fx), float(k.fy), float(k.tx), float(k.ty)
        a = np.asarray(k, dtype=np.float64)
        if a.shape == (3, 3): return float(a[0,0]), float(a[1,1]), float(a[0,2]), float(a[1,2])
        raise RuntimeError(f"unrecognised Record3D intrinsics: {type(k)}")

    def resolve_intrinsics(self, depth, rgb):
        """project decision: record3d gives RGB-sized intrinsics, so scale them
        to the depth grid before unprojecting."""
        dh, dw = depth.shape; rh, rw = rgb.shape[:2]; fx, fy, cx, cy = self.raw_intrinsics()
        return fx*dw/rw, fy*dh/rh, cx*dw/rw, cy*dh/rh

    def unproject(self, depth):
        """pinhole X=(u-cx)Z/fx, Y=(v-cy)Z/fy
        # ref: https://github.com/marek-simonik/record3d/blob/master/demo-main.py"""
        fx, fy, cx, cy = self.intr; dh, dw = depth.shape
        px, py = np.meshgrid(np.arange(dw, dtype=np.float32), np.arange(dh, dtype=np.float32))
        valid = np.isfinite(depth) & (depth > .05) & (depth < 5.)
        x = np.zeros_like(depth); y = np.zeros_like(depth)
        x[valid] = (px[valid]-cx)*depth[valid]/fx; y[valid] = (py[valid]-cy)*depth[valid]/fy
        return np.stack([x, y, depth], axis=-1), valid

    def small_bgr(self, rgb, depth):
        """project decision: resize RGB down to the depth grid so one mask
        indexes both. cheap, and good enough for a colour histogram."""
        dh, dw = depth.shape; bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        return cv2.resize(bgr, (dw, dh), interpolation=cv2.INTER_AREA)

    def roi_mask(self, shape):
        mask = np.zeros(shape, bool); x, y, w, h = self.roi; mask[y:y+h, x:x+w] = True; return mask

    def select_roi(self):
        """# ref: https://docs.opencv.org/4.x/d7/dfc/group__highgui.html"""
        print("[*] select ONLY the usable tabletop, then press ENTER")
        while True:
            rgb, depth = self.frame()
            if depth is None: continue
            if self.intr is None:
                self.intr = self.resolve_intrinsics(depth, rgb)
                print("[*] depth intrinsics: " + " ".join(f"{v:.1f}" for v in self.intr))
            x, y, w, h = cv2.selectROI(WINDOW, self.small_bgr(rgb, depth), True, False)
            if w > 10 and h > 10:
                self.roi = int(x), int(y), int(w), int(h); print(f"[*] work area: x={x} y={y} w={w} h={h}"); return
            print("[!] selection cancelled or too small")

    def body_mask(self, height, valid):
        """above-table mask for body reasoning. no prop ceiling here.
        # ref: Riemann et al. 2018, FlowPut, DOI 10.1145/3191763, sections 4.1.2 and 4.1.3
        # ref: https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html"""
        mask = (valid & self.roi_mask(height.shape) & (height > self.threshold_m)).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, OPEN_KERNEL)
        return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, CLOSE_KERNEL)

    def calibrate(self):
        """fit the table, set a height threshold, learn static edge clutter.
        # ref: Riemann et al. 2018, FlowPut, DOI 10.1145/3191763, section 4.1.2
        the static edge-clutter memory below is a project decision."""
        print(f"[*] empty table for {CALIBRATION_FRAMES} frames; keep hands out"); depths = []
        while len(depths) < CALIBRATION_FRAMES:
            _, depth = self.frame()
            if depth is None: continue
            depths.append(depth.copy()); print(f"\rcalibrating {len(depths)}/{CALIBRATION_FRAMES}", end="", flush=True)

        stack = np.stack(depths); safe = np.where(np.isfinite(stack), stack, np.nan)
        # project decision: some pixels are invalid in every frame, so the
        # all-NaN warning here is expected and only that warning is muted.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning); baseline = np.nanmedian(safe, axis=0).astype(np.float32)

        pts, valid = self.unproject(baseline); use = valid & self.roi_mask(baseline.shape)
        self.n, self.c, self.origin = fit_plane(pts[use]); self.u, self.v = plane_axes(self.n)
        noise = []
        for depth in depths:
            pts, valid = self.unproject(depth); use = valid & self.roi_mask(depth.shape)
            residual = (pts @ self.n + self.c)[use]; residual = residual[np.abs(residual) < .02]
            if residual.size: noise.append(float(np.std(residual) * 1000.))
        if not noise: raise RuntimeError("could not measure table noise")
        noise_mm = float(np.median(noise)); threshold_mm = float(np.clip(noise_mm*CALIBRATION_MULT, MIN_THRESHOLD_MM, MAX_THRESHOLD_MM))
        self.threshold_m = threshold_mm / 1000.

        # project decision: remember foreground that already touched the ROI
        # edge on an empty table, so furniture is not read as a body later.
        baseline_pts, baseline_valid = self.unproject(baseline); baseline_height = baseline_pts @ self.n + self.c
        self.body_background = self.body_mask(baseline_height, baseline_valid)
        # ref: https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html
        self.body_background = cv2.dilate(self.body_background, CLOSE_KERNEL, iterations=1)
        self.active = {}; self.memory = {}; self.next_id = 1; self.manipulated_id = None
        self.manipulated_ids = set(); self.last_known = {}
        self.merged_pair = None; self.pending_new = {}; self.next_pending = 1
        self.learning_mode = False; self.learning_locked = False; self.roster_locked = False
        self.learning_buffers = {}; self.learning_frames = 0; self.track_state = {}
        self.unknown_last_saved_frame = -10**9
        print(f"\n[*] calibrated: noise={noise_mm:.1f}mm threshold={threshold_mm:.1f}mm")
        self.debug_write("calibration", {
            "noise_mm":float(noise_mm),
            "threshold_mm":float(threshold_mm),
            "roi":[int(v) for v in self.roi],
            "intrinsics":[float(v) for v in self.intr],
        })
        # project decision: print-only warning, changes no behaviour. noise here
        # is the spatial spread of the table around its own fitted plane, not
        # sensor jitter, so a high number means the chosen ROI is not flat.
        if noise_mm > 2.5:
            print(f"[!] noise {noise_mm:.1f}mm is high. quit, pick a flatter ROI, calibrate again")

    def appearance(self, hsv, sel):
        """# ref: https://docs.opencv.org/4.x/d8/dc8/tutorial_histogram_comparison.html"""
        hist = cv2.calcHist([hsv], [0,1], sel.astype(np.uint8)*255, [16,16], [0,180,0,256])
        cv2.normalize(hist, hist, alpha=1., norm_type=cv2.NORM_L1); return hist.astype(np.float32)

    def body_present(self, height, valid, depth):
        """return all qualifying edge-entering body components, not just one.
        two arms, a hand plus forearm, or other participant body foreground may
        coexist. all are exclusion evidence; none is allowed to become a prop.
        # ref: Riemann et al. 2018, FlowPut, DOI 10.1145/3191763, sections 4.1.3 and 9.3
        """
        current = self.body_mask(height, valid)
        # ref: https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html
        count, labels, stats, _ = cv2.connectedComponentsWithStats(current, 8)
        fx, fy, _, _ = self.intr; pixel_area = (depth**2)/(fx*fy); rx, ry, rw, rh = self.roi
        background = self.body_background if self.body_background is not None else np.zeros_like(current)
        combined = np.zeros_like(current, dtype=bool)
        n_components = 0
        for i in range(1, count):
            x = int(stats[i, cv2.CC_STAT_LEFT]); y = int(stats[i, cv2.CC_STAT_TOP])
            w = int(stats[i, cv2.CC_STAT_WIDTH]); h = int(stats[i, cv2.CC_STAT_HEIGHT])
            touches_edge = x <= rx+BODY_EDGE_PX or y <= ry+BODY_EDGE_PX or x+w >= rx+rw-BODY_EDGE_PX or y+h >= ry+rh-BODY_EDGE_PX
            if not touches_edge: continue
            novel = (labels == i) & valid & (background == 0)
            if not np.any(novel): continue
            area = float(pixel_area[novel].sum()*10000.)
            if np.isfinite(area) and area >= BODY_MIN_AREA_CM2:
                combined |= novel
                n_components += 1
        if n_components:
            return True, combined
        return False, None

    def detect(self, rgb, depth):
        pts, valid = self.unproject(depth); height = pts @ self.n + self.c
        body, body_pixels = self.body_present(height, valid, depth)
        body_points = bounded_points(pts[body_pixels], MAX_BODY_POINTS) if body and body_pixels is not None else None

        mask = (valid & self.roi_mask(depth.shape) & (height > self.threshold_m) & (height < HEIGHT_CEILING_MM/1000.)).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, OPEN_KERNEL); mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, CLOSE_KERNEL)
        # project decision, 18 aug 2026 RC2: body is an exclusion mask, not a
        # reason to stop understanding the whole table. this supports two arms
        # and persistent head/body visibility. a prop physically connected to a
        # hand may disappear temporarily, but its learned id remains durable.
        if body_pixels is not None:
            mask[body_pixels] = 0
        # ref: https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html
        count, labels, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
        fx, fy, _, _ = self.intr; pixel_area = (depth**2)/(fx*fy)
        bgr = self.small_bgr(rgb, depth); hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV); rx, ry, rw, rh = self.roi; blobs = []

        for i in range(1, count):
            x = int(stats[i, cv2.CC_STAT_LEFT]); y = int(stats[i, cv2.CC_STAT_TOP])
            w = int(stats[i, cv2.CC_STAT_WIDTH]); h = int(stats[i, cv2.CC_STAT_HEIGHT])
            # project decision: components touching the ROI edge are not props.
            if x <= rx+ROI_BORDER_PX or y <= ry+ROI_BORDER_PX or x+w >= rx+rw-ROI_BORDER_PX or y+h >= ry+rh-ROI_BORDER_PX: continue
            # project decision: morphology can spread a component onto invalid
            # depth, so measure using valid pixels only.
            sel = (labels == i) & valid
            if not np.any(sel): continue
            area = float(pixel_area[sel].sum()*10000.)
            heights_mm = height[sel]*1000.
            height_mm = float(np.percentile(heights_mm, HEIGHT_PCT))
            max_mm = float(heights_mm.max())
            centre = np.median(pts[sel], axis=0)
            if not np.isfinite(area) or not np.isfinite(height_mm) or not np.isfinite(max_mm): continue
            if not np.all(np.isfinite(centre)): continue
            if area < MIN_AREA_CM2 or max_mm > HEIGHT_CEILING_MM: continue
            rel = centre - self.origin; cx, cy = cents[i]
            blobs.append({"x":float((cx-rx)/rw), "y":float((cy-ry)/rh), "tx":float(rel.dot(self.u)*100.), "ty":float(rel.dot(self.v)*100.),
                          "area":area, "height":height_mm, "max_height":max_mm,
                          "depth":float(np.median(depth[sel])), "bbox":(x,y,w,h),
                          "hist":self.appearance(hsv, sel), "surface":bounded_points(pts[sel], MAX_SURFACE_POINTS),
                          "feat":shape_colour_vector(sel, (x,y,w,h), hsv)})
        # project diagnostic: keep references to this exact frame until the
        # next detect() call. anomaly saving happens before then.
        self.debug_last_frame = {
            "depth":depth, "height":height, "valid":valid.astype(np.uint8),
            "mask":mask, "preview":bgr,
        }
        return blobs, bgr, body, body_points

    def classify(self, feat, taken):
        """nearest centroid over the learned samples. refuses when unsure.
        this is the whole model: mean of each prop's examples, in units of
        the pooled spread. no library, no training loop."""
        if feat is None: return None, []
        ids = [i for i in self.memory
               if i not in taken and len(self.memory[i]["samples"]) >= CLASS_MIN_SAMPLES]
        if not ids: return None, []
        z = feat / CLASS_SCALE
        scored = []
        for i in ids:
            centre = np.array(self.memory[i]["samples"]).mean(axis=0) / CLASS_SCALE
            scored.append((float(np.sqrt(np.mean((z - centre)**2))), i))
        scored.sort()
        best, best_id = scored[0]
        if best > CLASS_MAX_DIST: return None, scored
        if len(scored) > 1 and scored[1][0] <= best*CLASS_MARGIN: return None, scored
        return best_id, scored

    def learn(self, object_id, feat):
        """add one example to a prop, from a frame we are confident about."""
        if feat is None: return
        samples = self.memory[object_id]["samples"]
        samples.append(feat)
        if len(samples) > CLASS_MAX_SAMPLES: samples.pop(0)

    def explain_new(self, b, used):
        """print why the classifier refused. diagnostic only."""
        if b.get("feat") is None:
            print("[?] no outline features for this blob, cannot classify")
            return
        _, scored = self.classify(b.get("feat"), used)
        print(f"[?] no match for {b['area']:.0f}cm2 {b['height']:.0f}mm")
        if not scored:
            print(f"[?]   nothing learned yet, or under {CLASS_MIN_SAMPLES} samples each")
            return
        for distance, object_id in scored[:3]:
            n = len(self.memory[object_id]["samples"])
            note = "too far" if distance > CLASS_MAX_DIST else "runner up too close"
            print(f"[?]   vs id{object_id}: distance={distance:.2f} samples={n} {note}")
            detail = self.debug_feature_breakdown(b.get("feat"), object_id)
            if detail is not None:
                top = ", ".join(f"{v['feature']}={v['scaled_delta']:.2f}" for v in detail["largest"][:3])
                print(f"[d]      largest feature changes: {top}")

    def class_distance(self, feat, object_id):
        """distance from one blob feature vector to one learned object."""
        if feat is None: return np.inf
        samples = self.memory[object_id]["samples"]
        if len(samples) < CLASS_MIN_SAMPLES: return np.inf
        z = feat / CLASS_SCALE
        centre = np.array(samples).mean(axis=0) / CLASS_SCALE
        return float(np.sqrt(np.mean((z - centre)**2)))

    def merge_area_error(self, area, expected):
        """fractional difference from the expected combined footprint area."""
        return abs(area - expected) / max(expected, 1e-6)

    def reference_tracks(self):
        """durable identity state after lock, visible-only state before lock."""
        return self.last_known if self.roster_locked and self.last_known else self.active

    def remember_observation(self, object_id, b):
        """update last clean individual observation for one roster member."""
        if not self.roster_locked: return
        self.last_known[object_id] = {
            "tx":b["tx"], "ty":b["ty"], "area":b["area"],
            "height":b["height"], "max_height":b["max_height"],
            "surface":b["surface"].copy(),
        }

    def declare_merge(self, blobs, bi, ids, why):
        """record one connected component as two already-known ids."""
        ids = tuple(sorted(ids))
        blob = blobs[bi]
        members = {}
        refs = self.reference_tracks()
        if any(object_id not in refs for object_id in ids): return None
        for object_id in ids:
            old = refs[object_id]
            members[object_id] = {
                "area": old["area"],
                "height": old["height"],
                "max_height": old["max_height"],
            }
        self.merged_pair = {
            "ids": ids,
            "members": members,
            "blob": blob.copy(),
            "unclear": False,
        }
        for object_id in ids: self.set_track_state(object_id, "merged", "merge declared")
        print(f"[m] merge #{ids[0]} + #{ids[1]} -> one {blob['area']:.0f}cm2 blob; "
              f"keeping both ids ({why})")
        self.debug_write("merge_start", {
            "pair":[int(ids[0]), int(ids[1])], "blob_index":int(bi),
            "area":float(blob["area"]), "why":why,
        })
        return bi

    def find_residual_merge(self, blobs, assigned, used):
        """find one grouped measurement among whatever roster ids remain.

        RC2 deliberately does not require a perfect N -> N-1 component count.
        another learned object may already be missing. unchanged ids are removed
        first, then every remaining id pair is compared with every remaining blob.
        the best physically plausible pair wins only when it is clearly better.

        # ref: Henriques et al. 2011, ICCV, merged measurements.
        # https://www.robots.ox.ac.uk/~joao/publications/henriques_iccv2011.pdf
        """
        if self.merged_pair is not None: return None
        refs = self.reference_tracks()
        old_left = [i for i in refs if i not in used]
        blob_left = [bi for bi in range(len(blobs)) if bi not in assigned]
        if len(old_left) < 2 or not blob_left: return None
        options = []
        for a, c in combinations(old_left, 2):
            expected = refs[a]["area"] + refs[c]["area"]
            for bi in blob_left:
                error = self.merge_area_error(blobs[bi]["area"], expected)
                if error > MERGE_AREA_TOL: continue
                near = np.inf
                for object_id in (a, c):
                    surface = refs[object_id].get("surface")
                    if surface is None or len(surface) == 0: continue
                    near = min(near, self.surface_distance_cm(blobs[bi]["surface"], surface))
                # at least one member should still physically overlap its last
                # clean surface. this prevents a currently missing unrelated id
                # with a similar area sum from stealing the merge pair.
                if near > TOUCH_DISTANCE_CM: continue
                options.append((error, near, bi, a, c))
        if not options: return None
        options.sort(key=lambda x:(x[0], x[1]))
        best = options[0]
        if len(options) > 1 and options[1][0] <= best[0] * ROSTER_GLOBAL_MARGIN and options[1][2:] != best[2:]:
            return None
        error, _, bi, a, c = best
        return self.declare_merge(blobs, bi, (a, c), f"residual roster area error={error:.2f}")

    def find_new_merge(self, blobs, assigned=None, used=None, allowed_blobs=None):
        """latch-supported merge fallback after roster/continuity reasoning."""
        assigned = assigned or {}; used = used or set()
        refs = self.reference_tracks()
        moved = self.manipulated_id
        if moved is None or moved not in refs or moved in used: return None
        if len(self.memory[moved]["samples"]) < CLASS_MIN_SAMPLES: return None
        allowed = set(range(len(blobs))) if allowed_blobs is None else set(allowed_blobs)
        best = None
        for other, old in refs.items():
            if other == moved or other in used: continue
            if len(self.memory[other]["samples"]) < CLASS_MIN_SAMPLES: continue
            moved_area = refs[moved]["area"]; expected = moved_area + old["area"]
            for bi, b in enumerate(blobs):
                if bi in assigned or bi not in allowed: continue
                error = self.merge_area_error(b["area"], expected)
                if error > MERGE_AREA_TOL: continue
                if b["area"] < old["area"] + moved_area*MERGE_MIN_ADDED_FRAC: continue
                surface = old.get("surface")
                if surface is None or len(surface) == 0: continue
                d = self.surface_distance_cm(b["surface"], surface)
                if d > TOUCH_DISTANCE_CM: continue
                if best is None or error < best[0]: best = (error, bi, other)
        if best is None: return None
        _, bi, other = best
        return self.declare_merge(blobs, bi, tuple(sorted((moved, other))), "remaining latch + stationary surface")

    def find_merged_blob(self, blobs):
        """find the continuing single measurement for an active merge pair."""
        if self.merged_pair is None: return None
        expected = sum(v["area"] for v in self.merged_pair["members"].values())
        best = None
        for bi, b in enumerate(blobs):
            error = self.merge_area_error(b["area"], expected)
            if error > MERGE_AREA_TOL: continue
            if best is None or error < best[0]: best = (error, bi)
        return None if best is None else best[1]

    def merged_copies(self, blob, remember=True):
        """publish two ids from one measurement without learning its outline."""
        ids = self.merged_pair["ids"]
        out = []
        for object_id in ids:
            b = blob.copy()
            member = self.merged_pair["members"][object_id]
            b["id"] = object_id
            b["area"] = member["area"]
            b["height"] = member["height"]
            b["max_height"] = member["max_height"]
            b["merged_ids"] = ids
            out.append(b)
        if remember:
            self.merged_pair["blob"] = blob.copy()
            self.merged_pair["unclear"] = False
        return out

    def try_split_pair(self, blobs, available):
        """choose the best two children even when unrelated blobs also exist."""
        if self.merged_pair is None or len(available) < 2: return None
        ids = self.merged_pair["ids"]; members = self.merged_pair["members"]
        ranked = []
        for b0, b1 in combinations(available, 2):
            for mapping in ({b0:ids[0], b1:ids[1]}, {b0:ids[1], b1:ids[0]}):
                parts = []; area_cost = 0.; area_ok = True
                for bi, object_id in mapping.items():
                    ref_area = max(float(members[object_id]["area"]), 1e-6)
                    ratio = float(blobs[bi]["area"]) / ref_area
                    if not (SPLIT_AREA_MIN <= ratio <= SPLIT_AREA_MAX): area_ok = False; break
                    area_cost += abs(ratio - 1.)
                    parts.append(self.class_distance(blobs[bi].get("feat"), object_id))
                if not area_ok: continue
                strong = sum(d <= CLASS_MAX_DIST for d in parts)
                class_cost = sum(d if np.isfinite(d) else 3. for d in parts)
                ranked.append((strong, class_cost + .35*area_cost, mapping))
        if not ranked: return None
        ranked.sort(key=lambda x:(-x[0], x[1]))
        best_strong, best_total, best_map = ranked[0]
        if best_strong == 0: return None
        if len(ranked) == 1: return best_map
        other_strong, other_total, _ = ranked[1]
        if best_strong > other_strong: return best_map
        if best_strong == 2 and other_total > best_total * ROSTER_GLOBAL_MARGIN: return best_map
        return None

    def release_area_ok(self, object_id, blob):
        """very loose physical gate before release continuity claims a blob."""
        refs = self.reference_tracks()
        if object_id not in refs: return False
        old_area = max(float(refs[object_id]["area"]), 1e-6)
        ratio = float(blob["area"]) / old_area
        return RELEASE_AREA_MIN <= ratio <= RELEASE_AREA_MAX

    def choose_release_blob(self, blobs, available, object_id):
        """choose the released observation for one latched known id.

        interaction already tells us which semantic id was moved. unchanged
        objects are matched first. if one physically plausible blob remains,
        it belongs to the latched id by exclusion. if several remain, only a
        uniquely plausible footprint is accepted; otherwise identity is held
        rather than guessed.

        # ref: Bohg et al. 2017, Interactive Perception,
        # DOI 10.1109/TRO.2017.2721939
        """
        plausible = [bi for bi in available if self.release_area_ok(object_id, blobs[bi])]
        if len(plausible) == 1: return plausible[0]
        return None

    def roster_pair_cost(self, object_id, blob):
        """cost for assigning one unmatched blob to one locked roster id."""
        ref_area = max(float(self.memory[object_id]["area"]), 1e-6)
        ratio = float(blob["area"]) / ref_area
        if not (ROSTER_AREA_MIN <= ratio <= ROSTER_AREA_MAX): return None
        d = self.class_distance(blob.get("feat"), object_id)
        class_cost = d if np.isfinite(d) else 3.
        area_cost = abs(ratio - 1.)
        return class_cost + .35*area_cost

    def recover_roster_by_exclusion(self, blobs, assigned, used, blocked):
        """recover missing learned ids without inventing a new identity.

        one missing id plus one plausible leftover blob is deterministic roster
        exclusion and does not depend on the hand latch. with several ids/blobs,
        solve the small global assignment and refuse if two solutions are close.
        """
        if not self.roster_locked: return 0
        pair_ids = set(self.merged_pair["ids"]) if self.merged_pair else set()
        missing = [i for i in sorted(self.memory) if i not in used and i not in pair_ids]
        available = [bi for bi in range(len(blobs)) if bi not in assigned and bi not in blocked]
        if not missing or not available: return 0
        restored = 0

        # deterministic single-id exclusion is the exact RC1Q hardware failure.
        if len(missing) == 1:
            object_id = missing[0]
            plausible = [(self.roster_pair_cost(object_id, blobs[bi]), bi) for bi in available]
            plausible = [(c,bi) for c,bi in plausible if c is not None]
            plausible.sort()
            if len(plausible) == 1 or (len(plausible) > 1 and plausible[1][0] > plausible[0][0] * ROSTER_GLOBAL_MARGIN):
                _, bi = plausible[0]
                assigned[bi] = object_id; used.add(object_id); restored += 1
                self.n_restored += 1
                print(f"[g] restored missing #{object_id} by locked-roster exclusion")
                self.debug_write("roster_exclusion_restore", {"id":int(object_id), "blob_index":int(bi)})
            return restored

        # first take any pair that is uniquely possible in both directions.
        changed = True
        while changed:
            changed = False
            missing_now = [i for i in missing if i not in used]
            available_now = [bi for bi in available if bi not in assigned]
            if not missing_now or not available_now: break
            by_id = {i:[bi for bi in available_now if self.roster_pair_cost(i, blobs[bi]) is not None] for i in missing_now}
            by_blob = {bi:[i for i in missing_now if self.roster_pair_cost(i, blobs[bi]) is not None] for bi in available_now}
            singles = [(i, xs[0]) for i,xs in by_id.items() if len(xs)==1 and len(by_blob[xs[0]])==1]
            for object_id, bi in singles:
                if object_id in used or bi in assigned: continue
                assigned[bi]=object_id; used.add(object_id); restored += 1; self.n_restored += 1; changed=True
                print(f"[g] restored missing #{object_id} by unique roster constraint")
                self.debug_write("roster_constraint_restore", {"id":int(object_id), "blob_index":int(bi)})

        missing_now = [i for i in missing if i not in used]
        available_now = [bi for bi in available if bi not in assigned]
        if not missing_now or len(missing_now) != len(available_now) or len(missing_now) > 4:
            return restored

        ranked = []
        for perm in permutations(available_now, len(missing_now)):
            total = 0.; mapping = {}; ok = True
            for object_id, bi in zip(missing_now, perm):
                cost = self.roster_pair_cost(object_id, blobs[bi])
                if cost is None: ok=False; break
                total += cost; mapping[bi]=object_id
            if ok: ranked.append((total,mapping))
        if not ranked: return restored
        ranked.sort(key=lambda x:x[0]); best_total,best_map=ranked[0]
        if len(ranked)>1 and ranked[1][0] <= best_total*ROSTER_GLOBAL_MARGIN:
            self.debug_write("roster_global_ambiguous", {"ids":[int(i) for i in missing_now], "blobs":[int(i) for i in available_now]})
            return restored
        for bi,object_id in best_map.items():
            assigned[bi]=object_id; used.add(object_id); restored+=1; self.n_restored+=1
        print("[g] global roster recovery: " + " ".join(f"#{oid}<-b{bi}" for bi,oid in sorted(best_map.items())))
        self.debug_write("roster_global_restore", {"mapping":{str(bi):int(oid) for bi,oid in best_map.items()}})
        return restored

    def clear_pending_new(self, why):
        """discard unconfirmed detections when a hand episode begins."""
        if not self.pending_new: return
        ids = sorted(self.pending_new)
        print(f"[c] cleared tentative detections {ids}: {why}")
        self.debug_write("candidate_clear", {"candidates":ids, "why":why})
        self.pending_new = {}

    def pending_match(self, candidate, blob):
        d = float(np.hypot(blob["tx"]-candidate["tx"], blob["ty"]-candidate["ty"]))
        ratio = float(blob["area"]) / max(float(candidate["area"]), 1e-6)
        return d <= NEW_CANDIDATE_DIST_CM and NEW_CANDIDATE_AREA_MIN <= ratio <= NEW_CANDIDATE_AREA_MAX

    def update_pending_new(self, blobs, available, fast_birth):
        """hold unmatched detections as tentative tracks before public ids.

        # ref: Bewley et al. 2016, SORT, section 3.4,
        # DOI 10.1109/ICIP.2016.7533003
        """
        promotions = {}
        matched_blobs = set(); matched_candidates = set(); current_for_candidate = {}
        pairs = []
        for cid, cand in self.pending_new.items():
            for bi in available:
                if self.pending_match(cand, blobs[bi]):
                    d = float(np.hypot(blobs[bi]["tx"]-cand["tx"], blobs[bi]["ty"]-cand["ty"]))
                    pairs.append((d, cid, bi))
        for _, cid, bi in sorted(pairs):
            if cid in matched_candidates or bi in matched_blobs: continue
            cand = self.pending_new[cid]; b = blobs[bi]
            cand["tx"] = b["tx"]; cand["ty"] = b["ty"]; cand["area"] = b["area"]
            cand["hits"] += 1; cand["misses"] = 0
            if fast_birth: cand["release_seen"] = True
            if b.get("feat") is not None: cand["samples"].append(b["feat"].copy())
            cand["hist"] = b["hist"].copy(); cand["blob"] = b.copy()
            matched_candidates.add(cid); matched_blobs.add(bi); current_for_candidate[cid] = bi

        for cid in list(self.pending_new):
            if cid not in matched_candidates:
                self.pending_new[cid]["misses"] += 1
                if self.pending_new[cid]["misses"] > NEW_CANDIDATE_MAX_MISSES:
                    print(f"[c] dropped tentative p{cid}: disappeared before confirmation")
                    self.debug_write("candidate_drop", {"candidate":cid, "why":"misses"})
                    del self.pending_new[cid]

        for bi in available:
            if bi in matched_blobs: continue
            b = blobs[bi]; cid = self.next_pending; self.next_pending += 1
            self.pending_new[cid] = {
                "tx":b["tx"], "ty":b["ty"], "area":b["area"],
                "hits":1, "misses":0, "release_seen":bool(fast_birth),
                "samples":[] if b.get("feat") is None else [b["feat"].copy()],
                "hist":b["hist"].copy(), "blob":b.copy(),
            }
            required = NEW_CONFIRM_RELEASE_FRAMES if fast_birth else NEW_CONFIRM_BACKGROUND_FRAMES
            print(f"[c] tentative p{cid} area={b['area']:.1f}cm2; need {required} clean frames")
            self.debug_save_anomaly("candidate_start", blobs, {
                "candidate":int(cid), "blob_index":int(bi), "required":int(required),
            })
            matched_candidates.add(cid); matched_blobs.add(bi); current_for_candidate[cid] = bi

        # A promoted candidate becomes a real semantic id only after persistence.
        for cid in list(self.pending_new):
            cand = self.pending_new[cid]
            required = NEW_CONFIRM_RELEASE_FRAMES if cand["release_seen"] else NEW_CONFIRM_BACKGROUND_FRAMES
            if cand["hits"] < required: continue
            # promote only the blob actually matched to this candidate this frame.
            bi = current_for_candidate.get(cid)
            if bi is None or bi in promotions: continue
            b = blobs[bi]
            object_id = self.next_id; self.next_id += 1
            # candidate persistence confirms existence only. appearance
            # examples are deliberately discarded here; identity learning begins
            # only when the user explicitly starts the bounded learning phase.
            self.memory[object_id] = {
                "area":b["area"], "height":b["height"],
                "hist":b["hist"].copy(), "samples":[],
            }
            self.set_track_state(object_id, "confirmed", "candidate promoted")
            promotions[bi] = object_id
            self.n_new += 1
            print(f"[+] confirmed id {object_id} from p{cid} after {cand['hits']} frames "
                  f"area={b['area']:.1f}cm2 height={b['height']:.0f}mm")
            self.debug_write("candidate_promote", {
                "candidate":int(cid), "id":int(object_id), "hits":int(cand["hits"]),
                "area":float(b["area"]),
            })
            del self.pending_new[cid]
        return promotions

    def set_track_state(self, object_id, state, why):
        """record public-id lifecycle transitions. state is diagnostic plus policy."""
        old = self.track_state.get(object_id)
        if old == state: return
        self.track_state[object_id] = state
        self.debug_write("track_state", {
            "id":int(object_id), "from":old, "to":state, "why":why,
        })

    def learning_counts(self):
        return {object_id:len(buf["feat"]) for object_id, buf in self.learning_buffers.items()}

    def start_learning(self):
        """lock the prop roster and begin a bounded clean-example capture."""
        if self.learning_locked:
            print("[l] learning is already locked; restart the tracker to relearn the roster")
            return False
        if self.learning_mode:
            print("[l] learning is already running; press k when every id has enough samples")
            return False
        if self.merged_pair is not None or self.manipulated_id is not None or self.manipulated_ids:
            print("[l] cannot start while an object is manipulated or merged")
            return False
        if self.pending_new:
            print(f"[l] wait: tentative detections {sorted(self.pending_new)} are not confirmed yet")
            return False
        if not self.memory:
            print("[l] wait: no confirmed objects yet")
            return False
        if set(self.active) != set(self.memory):
            missing = sorted(set(self.memory) - set(self.active))
            print(f"[l] wait: every confirmed object must be visible and separate; missing={missing}")
            return False

        self.roster_locked = True
        self.learning_mode = True
        self.learning_frames = 0
        self.learning_buffers = {}
        for object_id in sorted(self.memory):
            # project decision: throw away pre-learning candidate examples so
            # the classifier is trained only inside the explicit user-controlled phase.
            self.memory[object_id]["samples"] = []
            self.learning_buffers[object_id] = {"feat":[], "area":[], "height":[], "hist":[]}
            self.set_track_state(object_id, "confirmed", "learning started")
        self.clear_pending_new("roster locked for learning")
        print(f"[l] LEARNING STARTED for ids {sorted(self.memory)}")
        print(f"[l] keep hands out and objects separate; need at least {CLASS_MIN_SAMPLES} samples each; press k to lock")
        self.debug_write("learning_start", {"ids":[int(i) for i in sorted(self.memory)]})
        return True

    def lock_learning(self):
        """freeze classifier and physical templates for the rest of this run."""
        if not self.learning_mode:
            if self.learning_locked: print("[l] learning is already locked")
            else: print("[l] learning has not started; press l after all props are confirmed")
            return False
        counts = self.learning_counts()
        short = {i:n for i,n in counts.items() if n < CLASS_MIN_SAMPLES}
        if short:
            print("[l] not enough clean samples yet: " + " ".join(f"#{i}={n}" for i,n in sorted(short.items())))
            return False

        locked = {}
        for object_id, buf in self.learning_buffers.items():
            samples = [v.copy() for v in buf["feat"][-CLASS_MAX_SAMPLES:]]
            self.memory[object_id]["samples"] = samples
            self.memory[object_id]["area"] = float(np.median(buf["area"]))
            self.memory[object_id]["height"] = float(np.median(buf["height"]))
            hist = np.mean(np.stack(buf["hist"], axis=0), axis=0).astype(np.float32)
            total = float(hist.sum())
            if total > 0: hist /= total
            self.memory[object_id]["hist"] = hist
            locked[object_id] = {
                "samples":len(samples), "area":self.memory[object_id]["area"],
                "height":self.memory[object_id]["height"],
            }

        self.learning_mode = False
        self.learning_locked = True
        # every learned id now has a durable last-known track. future frames may
        # mark it missing, but cannot delete its identity or physical template.
        self.last_known = {}
        for object_id in sorted(self.memory):
            if object_id in self.active:
                old = self.active[object_id]
                self.last_known[object_id] = {
                    "tx":old["tx"], "ty":old["ty"], "area":old["area"],
                    "height":old["height"], "max_height":old["max_height"],
                    "surface":old["surface"].copy(),
                }
        print("[l] LEARNING LOCKED: " + " ".join(f"#{i}={v['samples']}" for i,v in sorted(locked.items())))
        print("[l] object roster and classifier memory are now read-only for this run")
        self.debug_write("learning_lock", {"objects":{str(i):v for i,v in locked.items()}})
        return True

    def capture_learning_batch(self, blobs, assigned, proximity, merged_bi, held_split, protected):
        """collect one clean batch only when every roster object is separately visible."""
        if not self.learning_mode: return
        self.learning_frames += 1
        if self.frame_count % LEARN_SAMPLE_EVERY != 0: return
        ids = set(self.memory)
        assigned_ids = set(assigned.values())
        clean = (merged_bi is None and not held_split and not protected and
                 assigned_ids == ids and len(assigned) == len(ids) and
                 all(bi in proximity for bi in assigned))
        if not clean:
            self.debug_write("learning_skip", {
                "assigned":[int(i) for i in sorted(assigned_ids)],
                "expected":[int(i) for i in sorted(ids)],
                "merged":bool(merged_bi is not None), "protected":sorted(int(i) for i in protected),
            })
            return

        for bi, object_id in assigned.items():
            b = blobs[bi]; feat = b.get("feat")
            if feat is None: return
            base = max(float(self.memory[object_id]["area"]), 1e-6)
            ratio = float(b["area"]) / base
            if not (LEARN_AREA_MIN <= ratio <= LEARN_AREA_MAX):
                self.debug_write("learning_skip", {"id":int(object_id), "why":"area", "area_ratio":ratio})
                return

        for bi, object_id in assigned.items():
            b = blobs[bi]; buf = self.learning_buffers[object_id]
            buf["feat"].append(b["feat"].copy())
            buf["area"].append(float(b["area"]))
            buf["height"].append(float(b["height"]))
            buf["hist"].append(b["hist"].copy())
        counts = self.learning_counts()
        if min(counts.values()) in (1, 5, 10, CLASS_MIN_SAMPLES) or min(counts.values()) % 20 == 0:
            print("[l] samples " + " ".join(f"#{i}={n}" for i,n in sorted(counts.items())))
        self.debug_write("learning_sample", {"counts":{str(i):int(n) for i,n in counts.items()}})

    def potential_merge_blobs(self, blobs, first_clean):
        """protect any plausible two-roster combined measurement on release."""
        if not first_clean or self.merged_pair is not None: return {}
        refs = self.reference_tracks()
        if len(refs) < 2: return {}
        ids = sorted(refs); out = {}
        for bi,b in enumerate(blobs):
            options=[]
            for a,c in combinations(ids,2):
                expected=refs[a]["area"]+refs[c]["area"]
                error=self.merge_area_error(b["area"],expected)
                if error>MERGE_AREA_TOL: continue
                near=np.inf
                for object_id in (a,c):
                    surface=refs[object_id].get("surface")
                    if surface is None or len(surface)==0: continue
                    near=min(near,self.surface_distance_cm(b["surface"],surface))
                if near<=TOUCH_DISTANCE_CM: options.append((error,a,c,near))
            if options:
                options.sort(); out[bi]=options
        if out:
            self.debug_write("merge_candidates", {"blobs":{str(bi):[{"pair":[int(a),int(c)],"area_error":float(e),"surface_cm":float(d)} for e,a,c,d in opts] for bi,opts in out.items()}})
        return out

    def sync_track_states(self, output):
        visible = {int(b["id"]) for b in output}
        merged = set(self.merged_pair["ids"]) if self.merged_pair is not None else set()
        for object_id in self.memory:
            if object_id in merged:
                self.set_track_state(object_id, "merged", "combined measurement")
            elif object_id in visible:
                self.set_track_state(object_id, "confirmed", "visible clean observation")
            else:
                self.set_track_state(object_id, "missing", "no clean observation")

    def assign_ids(self, blobs, first_clean=False):
        """clean frame: group measurements first, then preserve public identity."""
        assigned = {}; used = set(); candidates = []; output = []
        held_split = set()
        refs = self.reference_tracks()

        pair_ids = set(self.merged_pair["ids"]) if self.merged_pair else set()
        had_merge = self.merged_pair is not None
        merged_bi = self.find_merged_blob(blobs) if self.merged_pair else None
        new_merge_started = False
        if merged_bi is not None: used.update(pair_ids)

        # New merges are NOT guessed from the hand latch yet. First protect
        # plausible grouped measurements and match objects that clearly stayed
        # separate. This prevents a wrong latch from selecting the wrong pair.

        # Protect any plausible combined measurement before a single id can
        # consume it. This protection is only active on the first clean frame
        # after a hand episode with one fewer component than public ids.
        merge_candidates = self.potential_merge_blobs(blobs, first_clean)
        protected_merge_blobs = set(merge_candidates)
        if merged_bi is not None: protected_merge_blobs.discard(merged_bi)

        # pass 1a: very tight physical continuity for clearly single blobs.
        continuity = []
        for object_id, old in refs.items():
            if object_id in pair_ids: continue
            old_area = max(float(old["area"]), 1e-6)
            for bi, b in enumerate(blobs):
                if bi == merged_bi or bi in protected_merge_blobs: continue
                d = float(np.hypot(b["tx"]-old["tx"], b["ty"]-old["ty"]))
                ratio = float(b["area"]) / old_area
                if d <= CONTINUITY_MATCH_CM and CONTINUITY_AREA_MIN <= ratio <= CONTINUITY_AREA_MAX:
                    continuity.append((d, object_id, bi))
        proximity = set()
        for _, object_id, bi in sorted(continuity):
            if object_id not in used and bi not in assigned:
                assigned[bi] = object_id; used.add(object_id); proximity.add(bi)

        # pass 1b: residual merge now runs BEFORE wider ordinary matching.
        # unchanged objects have been removed, so two old ids plus one protected
        # combined blob can resolve without the hand latch being correct.
        if merged_bi is None and self.merged_pair is None and first_clean:
            residual_bi = self.find_residual_merge(blobs, assigned, used)
            if residual_bi is not None:
                merged_bi = residual_bi
                pair_ids = set(self.merged_pair["ids"])
                used.update(pair_ids)
                protected_merge_blobs.discard(merged_bi)
                new_merge_started = True

        # If residual state is not sufficient, the manipulation latch gets a
        # second chance, but only among ids and blobs that remain unmatched.
        if merged_bi is None and self.merged_pair is None and first_clean:
            allowed = protected_merge_blobs or {
                bi for bi in range(len(blobs)) if bi not in assigned
            }
            latch_bi = self.find_new_merge(blobs, assigned=assigned, used=used,
                                           allowed_blobs=allowed)
            if latch_bi is not None:
                merged_bi = latch_bi
                pair_ids = set(self.merged_pair["ids"])
                used.update(pair_ids)
                protected_merge_blobs.discard(merged_bi)
                new_merge_started = True

        # pass 1c: wider ordinary proximity only after merge reasoning.
        # protected combined blobs remain unavailable to a single id if the
        # merge itself was ambiguous, which is safer than semantic corruption.
        for object_id, old in refs.items():
            if object_id in pair_ids or object_id in used: continue
            ref = self.memory[object_id]
            for bi, b in enumerate(blobs):
                if bi == merged_bi or bi in assigned or bi in protected_merge_blobs: continue
                d = float(np.hypot(b["tx"]-old["tx"], b["ty"]-old["ty"]))
                rgb = float(cv2.compareHist(b["hist"], ref["hist"], cv2.HISTCMP_CORREL))
                plausible = b["area"] <= ref["area"]*ACTIVE_MAX_AREA_GROWTH and rgb >= ACTIVE_HIST_MIN
                if d <= VISIBLE_MATCH_CM and plausible: candidates.append((d, object_id, bi))
        for _, object_id, bi in sorted(candidates):
            if object_id not in used and bi not in assigned:
                assigned[bi] = object_id; used.add(object_id); proximity.add(bi)

        # pass 1d: solve a known pair that has split again.
        if self.merged_pair is not None and merged_bi is None:
            available = [bi for bi in range(len(blobs)) if bi not in assigned and bi not in protected_merge_blobs]
            split = self.try_split_pair(blobs, available)
            if split is not None:
                ids = self.merged_pair["ids"]
                for bi, object_id in split.items():
                    assigned[bi] = object_id; used.add(object_id)
                    self.n_restored += 1
                print(f"[m] split #{ids[0]} + #{ids[1]} -> two blobs; ids restored")
                self.debug_write("merge_split", {"pair":[int(ids[0]),int(ids[1])]})
                self.merged_pair = None; pair_ids = set()
            else:
                held_split.update(available); used.update(pair_ids)
                if not self.merged_pair.get("unclear"):
                    ids = self.merged_pair["ids"]
                    print(f"[m] split unclear for #{ids[0]} + #{ids[1]}; holding both ids, no new ids")
                    self.debug_save_anomaly("split_unclear", blobs, {"pair":[int(ids[0]), int(ids[1])]})
                    self.merged_pair["unclear"] = True

        # pass 2: interaction continuity owns one normal moved object.
        release_id = None
        fast_birth = bool(first_clean and not new_merge_started and not self.roster_locked)
        moved = self.manipulated_id
        if first_clean and moved is not None and moved in refs and moved not in pair_ids:
            if moved in used:
                print(f"[r] latch #{moved} stayed at its old position; treating episode as no move")
                self.debug_write("release_stationary", {"id":int(moved)})
            else:
                release_id = moved; used.add(moved); fast_birth = False
                print(f"[r] reserving #{moved} through release")
                self.debug_write("release_reserved", {"id":int(moved)})

        if release_id is not None:
            available = [bi for bi in range(len(blobs))
                         if bi not in assigned and bi != merged_bi and bi not in held_split
                         and bi not in protected_merge_blobs]
            release_bi = self.choose_release_blob(blobs, available, release_id)
            if release_bi is not None:
                assigned[release_bi] = release_id
                self.n_restored += 1
                ratio = blobs[release_bi]["area"] / max(refs[release_id]["area"], 1e-6)
                print(f"[r] restored #{release_id} by interaction continuity area_ratio={ratio:.2f}")
                self.debug_write("release_restored", {
                    "id":int(release_id), "blob_index":int(release_bi), "area_ratio":float(ratio),
                })
                release_id = None

        # pass 3: frozen learned classifier for remaining ordinary blobs.
        for bi, b in enumerate(blobs):
            if bi in assigned or bi == merged_bi or bi in held_split or bi in protected_merge_blobs: continue
            object_id, _ = self.classify(b.get("feat"), used)
            if object_id is not None:
                assigned[bi] = object_id; used.add(object_id)
                self.n_restored += 1

        if release_id is not None:
            available = [bi for bi in range(len(blobs))
                         if bi not in assigned and bi != merged_bi and bi not in held_split
                         and bi not in protected_merge_blobs]
            release_bi = self.choose_release_blob(blobs, available, release_id)
            if release_bi is not None:
                assigned[release_bi] = release_id
                self.n_restored += 1
                ratio = blobs[release_bi]["area"] / max(refs[release_id]["area"], 1e-6)
                print(f"[r] restored #{release_id} after other ids matched area_ratio={ratio:.2f}")
                self.debug_write("release_restored_late", {
                    "id":int(release_id), "blob_index":int(release_bi), "area_ratio":float(ratio),
                })
                release_id = None
            elif not available:
                print(f"[r] #{release_id} has no released blob; keeping identity in memory as missing")
                self.debug_write("release_missing", {"id":int(release_id)})
                release_id = None
            else:
                print(f"[r] release of #{release_id} is ambiguous across {len(available)} blobs; refusing to guess")
                self.debug_save_anomaly("release_ambiguous", blobs, {
                    "id":int(release_id), "available":[int(i) for i in available],
                })

        # pass 3b: the learned roster itself is evidence. a known id that
        # failed ordinary matching remains missing and can be recovered from the
        # remaining physical measurements without trusting a single hand latch.
        blocked = set(held_split) | set(protected_merge_blobs)
        if merged_bi is not None: blocked.add(merged_bi)
        self.recover_roster_by_exclusion(blobs, assigned, used, blocked)

        # pass 4: before learning starts, unmatched detections can become
        # tentative public-object candidates. once learning starts the roster
        # is closed permanently for this run, so unmatched blobs cannot mint ids.
        available = [bi for bi in range(len(blobs))
                     if bi not in assigned and bi != merged_bi and bi not in held_split
                     and bi not in protected_merge_blobs]
        if self.roster_locked:
            if available and self.frame_count - self.unknown_last_saved_frame >= UNKNOWN_ANOMALY_COOLDOWN_FRAMES:
                print(f"[u] {len(available)} unmatched blob(s) ignored after roster lock; no new semantic ids")
                self.debug_save_anomaly("unmatched_after_roster_lock", blobs, {
                    "available":[int(i) for i in available],
                })
                self.unknown_last_saved_frame = self.frame_count
            promotions = {}
        else:
            promotions = self.update_pending_new(blobs, available, fast_birth)
            for bi, object_id in promotions.items():
                if bi in assigned: continue
                assigned[bi] = object_id; used.add(object_id)

        if protected_merge_blobs and merged_bi is None:
            self.debug_save_anomaly("merge_candidate_unresolved", blobs, {
                "protected":[int(i) for i in sorted(protected_merge_blobs)],
            })

        # The only learning path in RC1 is this explicit bounded phase.
        self.frame_count += 1
        self.capture_learning_batch(blobs, assigned, proximity, merged_bi, held_split, protected_merge_blobs)

        self.active = {}
        for bi, b in enumerate(blobs):
            if bi == merged_bi or bi in held_split or bi not in assigned: continue
            b["id"] = assigned[bi]
            self.active[b["id"]] = {
                "tx":b["tx"], "ty":b["ty"], "area":b["area"],
                "height":b["height"], "max_height":b["max_height"],
                "surface":b["surface"].copy(),
            }
            self.remember_observation(b["id"], b)
            output.append(b)

        if merged_bi is not None and self.merged_pair is not None:
            merged = self.merged_copies(blobs[merged_bi])
            for b in merged:
                self.active[b["id"]] = {
                    "tx":b["tx"], "ty":b["ty"], "area":b["area"],
                    "height":b["height"], "max_height":b["max_height"],
                    "surface":b["surface"].copy(),
                }
            output.extend(merged)
        elif held_split and self.merged_pair is not None:
            merged = self.merged_copies(self.merged_pair["blob"], remember=False)
            for b in merged:
                self.active[b["id"]] = {
                    "tx":b["tx"], "ty":b["ty"], "area":b["area"],
                    "height":b["height"], "max_height":b["max_height"],
                    "surface":b["surface"].copy(),
                }
            output.extend(merged)

        self.sync_track_states(output)
        return output

    def surface_distance_cm(self, body_points, surface):
        """nearest distance from body points to a stored prop surface.
        # ref: Riemann et al. 2018, FlowPut, DOI 10.1145/3191763, section 4.4
        using the last clean LiDAR surface instead of a known model is a
        project decision, since our props are not scanned in advance."""
        best = np.inf
        for start in range(0, len(body_points), DISTANCE_BLOCK):
            block = body_points[start:start+DISTANCE_BLOCK]; delta = block[:,None,:] - surface[None,:,:]
            best = min(best, float(np.min(np.sum(delta*delta, axis=2))))
        return float(np.sqrt(best)*100.)

    def manipulation_targets(self, body_points):
        """all known prop surfaces touched by any detected body component."""
        if body_points is None or len(body_points) == 0: return set()
        refs = self.reference_tracks(); out=set()
        for object_id, old in refs.items():
            surface=old.get("surface")
            if surface is None or len(surface)==0: continue
            if self.surface_distance_cm(body_points, surface) <= TOUCH_DISTANCE_CM:
                out.add(object_id)
        return out

    def manipulation_target(self, body_points):
        """legacy single-target view used only as optional merge evidence."""
        targets=sorted(self.manipulation_targets(body_points))
        return targets[0] if targets else None

    def write_scene(self, blobs):
        objects = [{"id":b["id"], "label":"object", "x":round(float(np.clip(b["x"],0,1)),4), "y":round(float(np.clip(b["y"],0,1)),4),
                    "depth_m":round(b["depth"],3), "area_cm2":round(b["area"],1), "height_mm":round(b["height"],1),
                    "table_x_cm":round(b["tx"],1), "table_y_cm":round(b["ty"],1)} for b in blobs]
        with open(OUT_FILE, "w") as f: json.dump({"timestamp":time.time(), "objects":objects}, f, indent=2)
        return objects

    def draw(self, frame, blobs):
        rx, ry, rw, rh = self.roi; cv2.rectangle(frame, (rx,ry), (rx+rw,ry+rh), (0,255,255), 1)
        drawn_merges = set()
        for b in blobs:
            group = b.get("merged_ids")
            if group is not None:
                if group in drawn_merges: continue
                drawn_merges.add(group)
                label = "+".join(str(i) for i in group)
            else:
                label = str(b["id"])
            x,y,w,h = b["bbox"]; cv2.rectangle(frame,(x,y),(x+w,y+h),(255,255,255),1)
            cv2.putText(frame,label,(x,max(14,y-4)),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1)
        cv2.putText(frame,f"objects={len(blobs)} threshold={self.threshold_m*1000:.0f}mm",(6,14),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,255,0),1)
        self.draw_learning_state(frame, 34)

    def draw_learning_state(self, frame, y):
        if self.learning_mode:
            counts = self.learning_counts()
            text = "LEARNING " + " ".join(f"#{i}:{n}" for i,n in sorted(counts.items())) + "  K=lock"
        elif self.learning_locked:
            text = "LEARNING LOCKED / ROSTER LOCKED"
        else:
            text = "SETUP: place all props, wait for ids, L=start learning"
        cv2.putText(frame,text,(6,y),cv2.FONT_HERSHEY_SIMPLEX,.38,(255,255,255),1)

    def draw_body_state(self, frame):
        cv2.putText(frame,"BODY/HAND",(6,34),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),2)
        ids=sorted(self.manipulated_ids)
        if ids:
            text="MANIPULATING " + "+".join(f"#{i}" for i in ids)
            cv2.putText(frame,text,(6,54),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),2)

    def handle_key(self, key, body):
        if key == ord("q"): return True
        if key == ord("l"):
            if body: print("[l] keep hands out before starting learning")
            else: self.start_learning()
        elif key == ord("k"):
            if body: print("[l] keep hands out before locking learning")
            else: self.lock_learning()
        return False

    def id_list(self, objects):
        """short list of ids for the instrumentation lines."""
        return " ".join(f"#{o['id']}" for o in objects) or "none"

    def blob_list(self, blobs):
        """per-object measurements for the timing line, percentile/max height."""
        parts = []; seen_merges = set()
        for b in blobs:
            group = b.get("merged_ids")
            if group is not None:
                if group in seen_merges: continue
                seen_merges.add(group)
                raw_area = self.merged_pair["blob"]["area"] if self.merged_pair else 0.
                parts.append(f"#{group[0]}+#{group[1]}=MERGED {raw_area:.0f}cm2")
                continue
            parts.append(f"#{b['id']}={b['area']:.0f}cm2 {b['height']:.0f}mm "
                         f"learned={len(self.memory[b['id']]['samples'])}")
        return " ".join(parts) or "none"

    def report(self, frames, t_wait, t_detect, t_assign, t_draw, objects):
        """print one timing line per second instead of printing every frame."""
        # project decision: instrumentation only, no effect on tracking.
        ms = lambda total: (total / max(frames, 1)) * 1000.
        body_pct = 100. * self.n_body / max(frames, 1)
        print(f"[t] fps={frames} wait={ms(t_wait):.0f}ms detect={ms(t_detect):.0f}ms "
              f"assign={ms(t_assign):.0f}ms draw={ms(t_draw):.0f}ms body={body_pct:.0f}% "
              f"restored={self.n_restored} new={self.n_new} objects={self.diag}")
        self.n_restored = 0; self.n_new = 0; self.n_body = 0

    def qualification_events(self):
        """read this run's diagnostic event stream. reporting only."""
        if self.debug_log_path is None or not os.path.exists(self.debug_log_path):
            return []
        events = []
        try:
            with open(self.debug_log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try: events.append(json.loads(line))
                    except json.JSONDecodeError: continue
        except OSError:
            return []
        return events

    def qualification_report(self):
        """build one pasteable hardware-qualification summary from debug events.

        project decision, 18 aug 2026: qualification reporting must not feed
        tracking. it reads events only after the run, so a reporting bug cannot
        alter object assignment, learning, merge, or split decisions.
        """
        events = self.qualification_events()
        if not events:
            return "TANGIBLE WORLDS TRACKER QUALIFICATION REPORT\nno diagnostic events available\n"

        start = events[0].get("time", time.time())
        end = time.time()
        calibration = next((e for e in events if e.get("event") == "calibration"), None)
        learning_start = next((e for e in events if e.get("event") == "learning_start"), None)
        learning_lock = next((e for e in events if e.get("event") == "learning_lock"), None)
        lock_time = learning_lock.get("time") if learning_lock else None

        def after_lock(e):
            return lock_time is not None and e.get("time", 0) >= lock_time

        def count(name, post_lock=False):
            return sum(1 for e in events if e.get("event") == name and (not post_lock or after_lock(e)))

        anomalies = [e for e in events if e.get("event") == "anomaly_saved"]
        anomaly_counts = {}
        for e in anomalies:
            reason = e.get("reason", "unknown")
            anomaly_counts[reason] = anomaly_counts.get(reason, 0) + 1

        post_lock_anomalies = {}
        for e in anomalies:
            if not after_lock(e): continue
            reason = e.get("reason", "unknown")
            post_lock_anomalies[reason] = post_lock_anomalies.get(reason, 0) + 1

        promotions = [e for e in events if e.get("event") == "candidate_promote"]
        post_lock_promotions = [e for e in promotions if after_lock(e)]
        semantic_ids = sorted({int(e["id"]) for e in promotions if "id" in e})
        final_ids = sorted(int(i) for i in self.memory)
        final_active = sorted(int(i) for i in self.active)

        locked_objects = {}
        if learning_lock:
            for k, v in learning_lock.get("objects", {}).items():
                locked_objects[int(k)] = v
        learning_counts = {i:int(v.get("samples", 0)) for i,v in locked_objects.items()}

        merge_events = [e for e in events if e.get("event") == "merge_start" and after_lock(e)]
        split_events = [e for e in events if e.get("event") == "merge_split" and after_lock(e)]
        restore_events = [e for e in events if e.get("event") in ("release_restored", "release_restored_late") and after_lock(e)]
        stationary_events = [e for e in events if e.get("event") == "release_stationary" and after_lock(e)]
        missing_events = [e for e in events if e.get("event") == "release_missing" and after_lock(e)]
        body_off_events = [e for e in events if e.get("event") == "body_off_assigned" and after_lock(e)]
        latch_events = [e for e in events if e.get("event") == "manipulation_latched" and after_lock(e)]
        roster_restore_events = [e for e in events if e.get("event") in ("roster_exclusion_restore", "roster_constraint_restore", "roster_global_restore") and after_lock(e)]
        multi_touch_events = [e for e in events if e.get("event") == "multi_manipulation_latched" and after_lock(e)]

        calibration_ok = calibration is not None and float(calibration.get("noise_mm", 999)) <= 2.5
        samples_ok = bool(learning_counts) and min(learning_counts.values()) >= CLASS_MIN_SAMPLES
        no_births = learning_lock is not None and len(post_lock_promotions) == 0
        no_release_ambiguity = post_lock_anomalies.get("release_ambiguous", 0) == 0
        no_unresolved_split = post_lock_anomalies.get("split_unclear", 0) == 0
        final_not_merged = self.merged_pair is None
        roster_intact = learning_lock is not None and set(final_ids) == set(learning_counts)
        roster_resolved = learning_lock is not None and set(final_active) == set(final_ids)

        checks = [
            ("calibration_noise_le_2.5mm", calibration_ok),
            ("learning_locked", learning_lock is not None),
            ("learning_min_samples_met", samples_ok),
            ("zero_post_lock_id_births", no_births),
            ("roster_memory_intact_at_shutdown", roster_intact),
            ("all_roster_ids_resolved_at_shutdown", roster_resolved),
            ("zero_release_ambiguity", no_release_ambiguity),
            ("zero_split_unclear", no_unresolved_split),
            ("not_stopped_while_merged", final_not_merged),
        ]

        lines = []
        lines.append("=" * 72)
        lines.append("TANGIBLE WORLDS TRACKER QUALIFICATION REPORT")
        lines.append("=" * 72)
        lines.append(f"run_folder: {self.debug_dir}")
        lines.append(f"source: track_tabletop_simple_RC2Q_20260818.py")
        lines.append(f"started_unix: {start:.3f}")
        lines.append(f"duration_s: {end-start:.1f}")
        if calibration:
            lines.append(f"calibration_noise_mm: {float(calibration.get('noise_mm', 0)):.3f}")
            lines.append(f"calibration_threshold_mm: {float(calibration.get('threshold_mm', 0)):.3f}")
            lines.append(f"roi: {calibration.get('roi')}")
        else:
            lines.append("calibration: MISSING")

        lines.append("")
        lines.append("ROSTER / LEARNING")
        lines.append(f"semantic_ids_created_before_lock: {semantic_ids}")
        lines.append(f"learning_started: {learning_start is not None}")
        lines.append(f"learning_locked: {learning_lock is not None}")
        lines.append(f"learning_samples: {learning_counts}")
        lines.append(f"final_memory_ids: {final_ids}")
        lines.append(f"final_active_ids: {final_active}")
        lines.append(f"post_lock_new_ids: {[int(e['id']) for e in post_lock_promotions if 'id' in e]}")

        lines.append("")
        lines.append("POST-LOCK INTERACTION COUNTS")
        lines.append(f"body_release_episodes: {len(body_off_events)}")
        lines.append(f"manipulation_latches: {len(latch_events)}")
        lines.append(f"interaction_restores: {len(restore_events)}")
        lines.append(f"stationary_false_latches: {len(stationary_events)}")
        lines.append(f"release_missing: {len(missing_events)}")
        lines.append(f"merges: {len(merge_events)}")
        lines.append(f"splits: {len(split_events)}")
        lines.append(f"roster_recovery_events: {len(roster_restore_events)}")
        lines.append(f"multi_object_touch_episodes: {len(multi_touch_events)}")
        lines.append(f"unmatched_after_roster_lock: {post_lock_anomalies.get('unmatched_after_roster_lock', 0)}")
        lines.append(f"release_ambiguous: {post_lock_anomalies.get('release_ambiguous', 0)}")
        lines.append(f"split_unclear: {post_lock_anomalies.get('split_unclear', 0)}")

        lines.append("")
        lines.append("MERGE / SPLIT TIMELINE")
        if merge_events or split_events:
            timeline = sorted(merge_events + split_events, key=lambda e:e.get("time", 0))
            for e in timeline:
                rel = e.get("time", start) - start
                pair = e.get("pair", [])
                if e.get("event") == "merge_start":
                    lines.append(f"+{rel:7.1f}s MERGE {pair} area={e.get('area', 0):.1f} why={e.get('why', '')}")
                else:
                    lines.append(f"+{rel:7.1f}s SPLIT {pair}")
        else:
            lines.append("none")

        lines.append("")
        lines.append("RESTORE TIMELINE")
        if restore_events:
            for e in restore_events:
                rel = e.get("time", start) - start
                lines.append(f"+{rel:7.1f}s RESTORE id={e.get('id')} area_ratio={float(e.get('area_ratio', 0)):.3f}")
        else:
            lines.append("none")

        lines.append("")
        lines.append("POST-LOCK ANOMALIES")
        if post_lock_anomalies:
            for reason, n in sorted(post_lock_anomalies.items()):
                lines.append(f"{reason}: {n}")
        else:
            lines.append("none")

        lines.append("")
        lines.append("AUTOMATIC CHECKS")
        for name, ok in checks:
            lines.append(f"{'PASS' if ok else 'ATTENTION'}  {name}")

        # These are machine-observable checks only. A human must still report
        # any visible silent id swap because software cannot know physical
        # ground-truth identity without an external label.
        lines.append("")
        lines.append("MANUAL OBSERVATION REQUIRED")
        lines.append("Report any visible silent ID swap, missed physical merge, or wrong split.")
        lines.append("The automatic report cannot infer physical ground truth by itself.")
        lines.append("=" * 72)
        return "\n".join(lines) + "\n"

    def save_qualification_report(self):
        """append this run to one cumulative pasteable file."""
        report = self.qualification_report()
        try:
            os.makedirs(DEBUG_ROOT, exist_ok=True)
            with open(QUALIFICATION_RESULTS_PATH, "a") as f:
                f.write(report + "\n")
            print(f"[q] qualification results appended: {QUALIFICATION_RESULTS_PATH}")
        except OSError as e:
            print(f"[q] could not save qualification report: {e}")

    def shutdown(self):
        """detach the record3d callbacks before leaving.
        project decision: the stream calls back from its own thread, and if
        that lands while python is tearing down the interpreter it aborts
        with a fatal TSS error. dropping the callbacks and exiting hard
        avoids that race."""
        self.save_qualification_report()
        self.session.on_new_frame = lambda: None
        self.session.on_stream_stopped = lambda: None
        cv2.destroyAllWindows(); cv2.waitKey(1)
        print("[*] stopped"); sys.stdout.flush(); os._exit(0)

    def run(self):
        self.setup_debug()
        self.connect(); cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL); self.select_roi(); self.calibrate()
        print("[*] tracking; q = quit")
        print("[*] rc2q mode: persistent learned roster + multi-body exclusion + global recovery")
        print(f"[*] qualification output: {QUALIFICATION_RESULTS_PATH}")
        print("[*] workflow: place every prop -> wait for confirmed ids -> press L -> wait for samples -> press K -> move/merge")
        print("[*] hands, arms and other body foreground may be visible; only object-touch episodes pause assignment")
        print("[*] timing mode: one line per second. wait = time spent waiting on record3d")

        report_at = time.perf_counter() + 1.
        frames = 0; t_wait = t_detect = t_assign = t_draw = 0.
        objects = []
        was_interaction = False; body_frames = 0; clear_frames = BODY_CLEAR_FRAMES; raw_frames = 0

        while True:
            t0 = time.perf_counter(); rgb, depth = self.frame(); t1 = time.perf_counter(); t_wait += t1-t0
            if depth is None: continue
            blobs, preview, body_now, body_points = self.detect(rgb, depth)
            t2 = time.perf_counter(); t_detect += t2-t1

            targets_now = self.manipulation_targets(body_points) if body_now else set()
            if targets_now:
                clear_frames = 0
                self.manipulated_ids.update(targets_now)
                if self.manipulated_id is None and len(self.manipulated_ids)==1:
                    self.manipulated_id = next(iter(self.manipulated_ids))
            else:
                clear_frames += 1
            interaction = bool(self.manipulated_ids) and clear_frames < BODY_CLEAR_FRAMES

            if interaction and not was_interaction:
                body_frames=0; raw_frames=0
                self.clear_pending_new("body touched known object before confirmation")
                ids=sorted(self.manipulated_ids)
                print("[b] interaction ON. touched = " + " ".join(f"#{i}" for i in ids))
                self.debug_write("body_on", {"objects_before":self.id_list(objects), "touched":[int(i) for i in ids], "active":self.debug_active_state()})
                for target in ids:
                    self.debug_write("manipulation_latched", {"id":int(target), "multi":bool(len(ids)>1)})
                if len(ids)>1:
                    self.debug_write("multi_manipulation_latched", {"ids":[int(i) for i in ids]})
            if interaction:
                body_frames += 1; self.n_body += 1
                if body_now: raw_frames += 1
                for target in self.manipulated_ids:
                    self.set_track_state(target,"manipulated","body contact evidence")
                self.draw_body_state(preview); cv2.imshow(WINDOW, preview)
                key=cv2.waitKey(1)&0xFF; stop=self.handle_key(key,body=True)
                t3=time.perf_counter(); t_assign += t3-t2; t_draw += time.perf_counter()-t3; frames+=1
                if time.perf_counter()>=report_at:
                    self.report(frames,t_wait,t_detect,t_assign,t_draw,objects); report_at=time.perf_counter()+1.
                    frames=0; t_wait=t_detect=t_assign=t_draw=0.
                was_interaction=True
                if stop: self.shutdown()
                continue

            # Body/head may still be visible here, but if it is not touching a
            # known prop its pixels have already been removed from the prop mask.
            # Normal table understanding therefore continues.
            first_clean = was_interaction
            if first_clean:
                ids=sorted(self.manipulated_ids)
                if len(ids)==1:
                    self.manipulated_id=ids[0]
                    print(f"[*] manipulation released: id {ids[0]}")
                else:
                    self.manipulated_id=None
                    print("[*] multiple-object manipulation released: " + " ".join(f"#{i}" for i in ids))
                self.debug_release_frame(blobs,body_frames,raw_frames)
            was_interaction=False
            was_new=self.n_new; was_restored=self.n_restored

            blobs=self.assign_ids(blobs,first_clean=first_clean)
            self.manipulated_id=None
            if first_clean: self.manipulated_ids.clear()
            objects=self.write_scene(blobs); self.diag=self.blob_list(blobs)

            if first_clean:
                print(f"[b] interaction OFF after {body_frames} frames. objects after = {self.id_list(objects)} new={self.n_new-was_new} restored={self.n_restored-was_restored}")
                self.debug_write("body_off_assigned", {"objects_after":self.id_list(objects), "new":int(self.n_new-was_new), "restored":int(self.n_restored-was_restored)})
            t3=time.perf_counter(); t_assign += t3-t2

            self.draw(preview,blobs); cv2.imshow(WINDOW,preview)
            key=cv2.waitKey(1)&0xFF; stop=self.handle_key(key,body=False)
            t_draw += time.perf_counter()-t3; frames+=1
            if time.perf_counter()>=report_at:
                self.report(frames,t_wait,t_detect,t_assign,t_draw,objects); report_at=time.perf_counter()+1.
                frames=0; t_wait=t_detect=t_assign=t_draw=0.
            if stop: break
        self.shutdown()


if __name__ == "__main__": SimpleHybridTracker().run()
