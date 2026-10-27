"""
compute_scene.py
----------------
Reads scene_state.json (from tracking layer), computes spatial
relationships between objects, and writes scene_description.json
(consumed by rendering layer).

This is the SQ1 mapping layer: translating physical arrangement
into semantic scene structure. The design of this mapping is the
core research contribution.

Usage:
    python compute_scene.py

    Watches scene_state.json for changes and updates
    scene_description.json in real time.

References:
    Spatial grammar design informed by:
        Underkoffler & Ishii (1999) Urp: spatial relationships between
        physical objects drive computational responses.
        https://doi.org/10.1145/302979.303114

        Tangible Diffusion (TEI 2024): physical block positions mapped
        to generative parameters. Our approach extends this from 2D
        image generation to 3D scene composition.

    Euclidean distance for proximity:

    Clustering by distance threshold (simple approach for prototype):
        Objects within NEAR_THRESHOLD are considered "near" and grouped.
        Future work: replace with DBSCAN for robust clustering.
        https://scikit-learn.org/stable/modules/clustering.html#dbscan

    Output format (scene_description.json) consumed by
    phase3-tabletop/rendering/.
"""

import sys
import json
import time
import os
import numpy as np
from itertools import combinations

# ── Settings ──────────────────────────────────────────────

SCENE_STATE = "../tracking/scene_state.json"
SCENE_DESC = "scene_description.json"
POLL_INTERVAL = 0.1   # seconds between checking for updates

# object-move logging, study instrumentation. kept in its own file so it stays
# separate from conversation_log.json, which records words rather than hands.
MOVE_LOG = "../conversation/object_move_log.jsonl"
MOVE_THRESHOLD = 0.02     # project tuning, normalised table units, needs a
                          # live jitter check before the first session

# Proximity thresholds (in normalised 0..1 coordinate space)
# these are design decisions for SQ1, tuned by experiment.
# Record rationale for changes in the design diary.
NEAR_THRESHOLD = 0.15     # objects closer than this are "near"
FAR_THRESHOLD = 0.40      # objects further than this are "far"


# ── Spatial relationship helpers ──────────────────────────

def compute_distance(obj_a, obj_b):
    """Euclidean distance between two objects in normalised coords."""
    return float(np.linalg.norm([
        obj_a["x"] - obj_b["x"],
        obj_a["y"] - obj_b["y"]
    ]))


def classify_proximity(distance):
    """Classify distance as near, medium, or far."""
    if distance < NEAR_THRESHOLD:
        return "near"
    elif distance > FAR_THRESHOLD:
        return "far"
    return "medium"


def compute_direction(obj_a, obj_b):
    """
    What direction is obj_b relative to obj_a?
    Returns a human-readable string like "right and below".

    Coordinate system (top-down camera view):
        x: 0 = left edge, 1 = right edge
        y: 0 = top/far edge, 1 = bottom/near edge
    """
    dx = obj_b["x"] - obj_a["x"]
    dy = obj_b["y"] - obj_a["y"]

    # Horizontal component
    if abs(dx) < 0.05:
        h = ""           # roughly aligned horizontally
    elif dx > 0:
        h = "right"
    else:
        h = "left"

    # Vertical component
    if abs(dy) < 0.05:
        v = ""           # roughly aligned vertically
    elif dy > 0:
        v = "below"
    else:
        v = "above"

    # Combine
    parts = [p for p in [h, v] if p]
    if not parts:
        return "same position"
    return " and ".join(parts)


def compute_pairwise(objects):
    """
    For every pair of objects, compute distance, proximity, and direction.
    Returns a list of relationship dicts.
    """
    relationships = []

    for a, b in combinations(objects, 2):
        dist = compute_distance(a, b)
        relationships.append({
            "from": a["label"],
            "from_id": a["id"],
            "to": b["label"],
            "to_id": b["id"],
            "distance": round(dist, 4),
            "proximity": classify_proximity(dist),
            "direction": compute_direction(a, b),
        })

    return relationships


def find_clusters(objects):
    """
    Group objects that are near each other.
    Simple approach: two objects in the same cluster if distance < NEAR_THRESHOLD.
    Returns a list of clusters, each cluster is a list of object labels.

    this is a basic single-linkage clustering.
    For the prototype this is sufficient. If object count grows,
    switch to scipy or sklearn DBSCAN.
    """
    n = len(objects)
    if n == 0:
        return []

    # Start with each object in its own cluster
    cluster_ids = list(range(n))

    # Merge clusters for objects that are near each other
    for i, j in combinations(range(n), 2):
        if compute_distance(objects[i], objects[j]) < NEAR_THRESHOLD:
            # Union: merge j's cluster into i's cluster
            old_id = cluster_ids[j]
            new_id = cluster_ids[i]
            for k in range(n):
                if cluster_ids[k] == old_id:
                    cluster_ids[k] = new_id

    # Group by cluster ID
    groups = {}
    for idx, cid in enumerate(cluster_ids):
        groups.setdefault(cid, []).append(objects[idx]["label"])

    return list(groups.values())


def compute_scene_layout(objects):
    """
    Overall scene properties: centre of mass, spread, object count.
    Gives the rendering layer a sense of the overall composition.
    """
    if not objects:
        return {"centre_x": 0.5, "centre_y": 0.5, "spread": 0, "count": 0}

    xs = [o["x"] for o in objects]
    ys = [o["y"] for o in objects]

    # Centre of mass (average position)
    cx = float(np.mean(xs))
    cy = float(np.mean(ys))

    # Spread: average distance from centre (how spread out the arrangement is)
    spread = float(np.mean([
        np.linalg.norm([x - cx, y - cy]) for x, y in zip(xs, ys)
    ]))

    return {
        "centre_x": round(cx, 4),
        "centre_y": round(cy, 4),
        "spread": round(spread, 4),
        "count": len(objects),
    }

# ── Object-move logging ───────────────────────────────────

def log_object_moves(objects, last_seen, participant_id):
    """
    Write one line per hand action: an object appearing, moving far enough to
    count, or leaving the table. Words are already logged in
    conversation_log.json, so this is the other half of SQ3, which asks how
    creators divide labour between hands and voice.

    Only changes are written. The loop runs at 10 Hz, so logging every frame
    would produce tens of thousands of near-identical rows per session.

    last_seen is updated in place and carries positions between calls.

    # ref: Hilbert & Redmiles, ACM Computing Surveys 32(4), 2000,
    #      DOI 10.1145/371578.371593, on capturing interaction events
    # ref: https://jsonlines.org/ , one json object per line so events can be
    #      appended without rewriting the file
    """
    events = []
    now = time.time()
    current = {obj["id"]: obj for obj in objects}

    for oid, obj in current.items():
        previous = last_seen.get(oid)
        if previous is None:
            events.append({"event": "appear", "x": obj["x"], "y": obj["y"]})
        else:
            moved = compute_distance(obj, previous)
            if moved < MOVE_THRESHOLD:
                continue
            events.append({"event": "move", "x": obj["x"], "y": obj["y"],
                           "from_x": previous["x"], "from_y": previous["y"],
                           "distance": round(moved, 4)})
        last_seen[oid] = {"x": obj["x"], "y": obj["y"],
                          "label": obj.get("label")}
        events[-1].update({"timestamp": now, "object_id": oid,
                           "label": obj.get("label"),
                           "participant_id": participant_id})

    for oid in [i for i in last_seen if i not in current]:
        gone = last_seen.pop(oid)
        events.append({"timestamp": now, "event": "disappear",
                       "object_id": oid, "label": gone.get("label"),
                       "x": gone["x"], "y": gone["y"],
                       "participant_id": participant_id})

    if not events:
        return 0

    try:
        with open(MOVE_LOG, "a") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
    except OSError:
        return 0
    return len(events)

# ── Main loop ─────────────────────────────────────────────

def process_scene(state):
    """
    Take a scene state dict and produce a full scene description.
    This is the core mapping function.
    """
    objects = state.get("objects", [])

    return {
        "timestamp": state.get("timestamp", time.time()),
        "objects": objects,
        "relationships": compute_pairwise(objects),
        "clusters": find_clusters(objects),
        "layout": compute_scene_layout(objects),
    }


def main():
    # facilitator passes the participant id: python compute_scene.py P01
    # this is argument handling.
    participant_id = sys.argv[1] if len(sys.argv) > 1 else None
    last_seen = {}

    print("[*] Mapping layer started. Watching for scene changes...")
    print(f"[*] Reading: {SCENE_STATE}")
    print(f"[*] Writing: {SCENE_DESC}")
    print(f"[*] Proximity thresholds: near < {NEAR_THRESHOLD}, far > {FAR_THRESHOLD}")
    print(f"[*] Object-move log: {MOVE_LOG}  participant: {participant_id}")
    print("[*] Press Ctrl+C to stop.\n")

    last_timestamp = None

    while True:
        try:
            # Read the tracking output
            if not os.path.exists(SCENE_STATE):
                time.sleep(POLL_INTERVAL)
                continue

            with open(SCENE_STATE, "r") as f:
                state = json.load(f)

            # Skip if nothing changed
            ts = state.get("timestamp")
            if ts == last_timestamp:
                time.sleep(POLL_INTERVAL)
                continue
            last_timestamp = ts

            # Compute the scene description
            description = process_scene(state)

            # Write it out
            with open(SCENE_DESC, "w") as f:
                json.dump(description, f, indent=2)

            # study instrumentation, hands half of SQ3
            moves = log_object_moves(state.get("objects", []), last_seen,
                                     participant_id)

            # Console readout
            rels = description["relationships"]
            clusters = description["clusters"]
            layout = description["layout"]

            print(f"Objects: {layout['count']}  "
                  f"Spread: {layout['spread']:.3f}  "
                  f"Clusters: {len(clusters)}  "
                  f"Moves logged: {moves}")

            for r in rels:
                print(f"  {r['from']} -> {r['to']}: "
                      f"{r['proximity']} ({r['distance']:.3f}), "
                      f"{r['direction']}")

            print()

        except json.JSONDecodeError:
            # scene_state.json being written to, skip this cycle
            pass
        except KeyboardInterrupt:
            print("\n[*] Mapping layer stopped.")
            break

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()