// Port of phase3-tabletop/mapping/compute_scene.py. Thresholds and rules are
// unchanged: 2D Euclidean distance in normalised table units, three proximity
// bands, a ±0.05 direction dead zone, single-linkage clusters on "near", and
// layout centre / spread.
export const NEAR_THRESHOLD = 0.15;
export const FAR_THRESHOLD = 0.40;

export const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

export function proximity(d) {
  if (d < NEAR_THRESHOLD) return 'near';
  if (d > FAR_THRESHOLD) return 'far';
  return 'medium';
}

export function direction(a, b) {
  const dx = b.x - a.x, dy = b.y - a.y;
  const h = Math.abs(dx) < 0.05 ? '' : dx > 0 ? 'right' : 'left';
  const v = Math.abs(dy) < 0.05 ? '' : dy > 0 ? 'below' : 'above';
  const parts = [h, v].filter(Boolean);
  return parts.length ? parts.join(' and ') : 'same position';
}

export function pairwise(objects) {
  const out = [];
  for (let i = 0; i < objects.length; i++) {
    for (let j = i + 1; j < objects.length; j++) {
      const a = objects[i], b = objects[j];
      const d = distance(a, b);
      out.push({ from_id: a.id, to_id: b.id, distance: Math.round(d * 1e4) / 1e4, proximity: proximity(d), direction: direction(a, b) });
    }
  }
  return out;
}

export function clusters(objects) {
  const ids = objects.map((_, i) => i);
  for (let i = 0; i < objects.length; i++) {
    for (let j = i + 1; j < objects.length; j++) {
      if (distance(objects[i], objects[j]) < NEAR_THRESHOLD) {
        const oldId = ids[j], newId = ids[i];
        for (let k = 0; k < ids.length; k++) if (ids[k] === oldId) ids[k] = newId;
      }
    }
  }
  const groups = new Map();
  ids.forEach((cid, idx) => { if (!groups.has(cid)) groups.set(cid, []); groups.get(cid).push(objects[idx].id); });
  return [...groups.values()];
}

export function layout(objects) {
  if (!objects.length) return { centre_x: 0.5, centre_y: 0.5, spread: 0, count: 0 };
  const cx = objects.reduce((s, o) => s + o.x, 0) / objects.length;
  const cy = objects.reduce((s, o) => s + o.y, 0) / objects.length;
  const spread = objects.reduce((s, o) => s + Math.hypot(o.x - cx, o.y - cy), 0) / objects.length;
  const r = (v) => Math.round(v * 1e4) / 1e4;
  return { centre_x: r(cx), centre_y: r(cy), spread: r(spread), count: objects.length };
}

// index.html normalizedToWorld()
export const toWorld = (nx, ny, size = 10) => [(nx - 0.5) * size, (ny - 0.5) * size];
