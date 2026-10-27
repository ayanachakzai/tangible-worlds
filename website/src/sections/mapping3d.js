// Chapter 03 generated-world view. The recorded session's cached GLBs, placed
// with the production mapping x = (n − 0.5) × 10, z = (n − 0.5) × 10, on the
// production renderer's table and neutral default atmosphere. Moving a prop
// only translates its mesh; nothing is reloaded or regenerated.
import * as THREE from 'three';
import { Atmosphere, TABLE_SIZE } from '../lib/atmosphere.js';
import { loadGLB, normalise } from '../lib/meshes.js';
import { toWorld, NEAR_THRESHOLD } from '../lib/grammar.js';

const ACCENT = 0xf2c230;
const GLIDE = 0.14; // seconds: a short glide so the eye can follow the move

export async function init(host, { reduced, getState, subscribe, select, label }) {
  const canvas = host.querySelector('.scene3d__canvas');
  const labelLayer = host.querySelector('.scene3d__labels');
  const status = host.querySelector('.js-scene3d-status');

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const scene = new THREE.Scene();

  // The production camera's orientation (from +z, above the table). Its distance
  // is fitted to the frame's aspect so the whole table and the tallest model stay
  // in view, square on desktop and wide on phones.
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 1000);
  const target = new THREE.Vector3(0, 0.5, 0.2);
  const viewDir = new THREE.Vector3();
  const half = TABLE_SIZE / 2 + 0.2;
  const corners = [];
  for (const x of [-half, half]) for (const y of [0, 1.6]) for (const z of [-half, half]) corners.push(new THREE.Vector3(x, y, z));
  const pv = new THREE.Vector3();
  function fitCamera(aspect) {
    // steeper over the near-square desktop frame, closer to the tabletop's top-down
    // view; the production angle (about 48°) on wide phone frames
    const elev = THREE.MathUtils.degToRad(aspect < 1.5 ? 58 : 48);
    viewDir.set(0, Math.sin(elev), Math.cos(elev));
    camera.aspect = aspect;
    camera.updateProjectionMatrix();
    let lo = 4, hi = 60;
    for (let i = 0; i < 24; i++) {
      const d = (lo + hi) / 2;
      camera.position.copy(target).addScaledVector(viewDir, d);
      camera.lookAt(target);
      camera.updateMatrixWorld();
      const fits = corners.every((c) => { pv.copy(c).project(camera); return Math.abs(pv.x) < 0.97 && Math.abs(pv.y) < 0.95; });
      if (fits) hi = d; else lo = d;
    }
    camera.position.copy(target).addScaledVector(viewDir, hi);
    camera.lookAt(target);
  }

  const table = new THREE.Mesh(new THREE.PlaneGeometry(TABLE_SIZE, TABLE_SIZE), new THREE.MeshStandardMaterial({ color: 0x777777, roughness: 0.8 }));
  table.rotation.x = -Math.PI / 2;
  table.receiveShadow = true;
  scene.add(table);
  const grid = new THREE.GridHelper(TABLE_SIZE, 10, 0x46515a, 0x364049);
  grid.position.y = 0.012;
  scene.add(grid);
  const atmo = new Atmosphere(renderer, scene); // neutral default state
  atmo.update(0);

  // the selected model: an accent ring and a faint disc on the table beneath it
  const sel = new THREE.Group();
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.84, 1, 64), new THREE.MeshBasicMaterial({ color: ACCENT, toneMapped: false, side: THREE.DoubleSide }));
  const disc = new THREE.Mesh(new THREE.CircleGeometry(0.84, 64), new THREE.MeshBasicMaterial({ color: ACCENT, toneMapped: false, transparent: true, opacity: 0.22, depthWrite: false }));
  ring.rotation.x = disc.rotation.x = -Math.PI / 2;
  sel.add(disc, ring);
  sel.position.y = 0.02;
  scene.add(sel);
  // the comparison object's near zone (0.15 of the table = 1.5 world units), as on the tabletop
  const zone = new THREE.Mesh(new THREE.RingGeometry(NEAR_THRESHOLD * TABLE_SIZE - 0.04, NEAR_THRESHOLD * TABLE_SIZE, 96), new THREE.MeshBasicMaterial({ color: 0xf3ebd9, toneMapped: false, transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false }));
  zone.rotation.x = -Math.PI / 2;
  zone.position.y = 0.018;
  scene.add(zone);
  // the active relation, dashed while far as on the tabletop
  const relGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
  const relLine = new THREE.Line(relGeo, new THREE.LineDashedMaterial({ color: ACCENT, toneMapped: false, dashSize: 0.25, gapSize: 0.2 }));
  scene.add(relLine);

  const { objs } = getState();
  const groups = new Map();
  const labels = new Map();
  objs.forEach((o) => {
    const g = new THREE.Group();
    g.userData.id = o.id;
    g.userData.goal = new THREE.Vector3();
    scene.add(g);
    groups.set(o.id, g);
    const l = document.createElement('span');
    l.className = 'scene3d__label';
    l.textContent = label(o);
    labelLayer.appendChild(l);
    labels.set(o.id, l);
  });

  let raf = 0, visible = false, last = 0, settled = true;
  const v = new THREE.Vector3();
  let aspect = 0;
  function frame(now) {
    raf = 0;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    if (canvas.width !== Math.round(w * renderer.getPixelRatio()) || canvas.height !== Math.round(h * renderer.getPixelRatio())) renderer.setSize(w, h, false);
    if (Math.abs(aspect - w / h) > 1e-3) { aspect = w / h; fitCamera(aspect); }

    // glide every model towards its table position
    const dt = last ? Math.min(0.1, (now - last) / 1000) : 1;
    last = now;
    const k = reduced ? 1 : 1 - Math.exp(-dt / (GLIDE / 3));
    settled = true;
    groups.forEach((g) => {
      g.position.lerp(g.userData.goal, k);
      if (g.position.distanceToSquared(g.userData.goal) > 1e-6) settled = false; else g.position.copy(g.userData.goal);
    });
    placeMarks();
    renderer.render(scene, camera);

    const { active, ref } = getState();
    const placed = [];
    // on a narrow frame only the selected model and its comparison are labelled, so
    // the tags do not cover the models; the tabletop names all four
    const few = w < 480;
    // the selected label first, then nearest the camera first
    [...groups].sort((a, b) => (b[0] === active.id) - (a[0] === active.id) || b[1].position.z - a[1].position.z).forEach(([id, g]) => {
      const top = g.userData.height || 0.6;
      v.set(g.position.x, top + 0.15, g.position.z).project(camera);
      const l = labels.get(id);
      l.classList.toggle('is-active', id === active.id);
      l.hidden = few && id !== active.id && id !== ref.id;
      if (l.hidden) return;
      const lw = l.offsetWidth, lh = l.offsetHeight;
      // keep every label inside the frame, and lift it clear of labels already placed
      const lx = Math.min(w - lw / 2 - 4, Math.max(lw / 2 + 4, (v.x * 0.5 + 0.5) * w));
      let ly = Math.min(h - 4, Math.max(lh + 4, (-v.y * 0.5 + 0.5) * h));
      for (let n = 0; n < placed.length * 2; n++) {
        const hit = placed.find((p) => Math.abs(p.x - lx) < (p.w + lw) / 2 + 2 && Math.abs(p.y - ly) < lh + 2);
        if (!hit) break;
        ly = hit.y - lh - 2 >= lh + 4 ? hit.y - lh - 2 : hit.y + lh + 2;
      }
      placed.push({ x: lx, y: ly, w: lw });
      l.style.transform = `translate(${lx}px, ${ly}px) translate(-50%, -100%)`;
    });
    labelLayer.dataset.ready = '';
    if (!settled) request();
  }
  const request = () => { if (visible && !raf) raf = requestAnimationFrame(frame); };

  function placeMarks() {
    const { active, ref, prox } = getState();
    const ga = groups.get(active.id), gb = groups.get(ref.id);
    sel.scale.setScalar(Math.max(0.6, (ga.userData.footprint || 1) * 0.62));
    sel.position.set(ga.position.x, 0.02, ga.position.z);
    zone.position.set(gb.position.x, 0.018, gb.position.z);
    const p = relGeo.attributes.position;
    p.setXYZ(0, ga.position.x, 0.04, ga.position.z);
    p.setXYZ(1, gb.position.x, 0.04, gb.position.z);
    p.needsUpdate = true;
    relGeo.computeBoundingSphere();
    relLine.computeLineDistances();
    relLine.material.gapSize = prox === 'far' ? 0.2 : 0;
  }

  function update({ objs: list }) {
    list.forEach((o) => {
      const [x, z] = toWorld(o.x, o.y);
      groups.get(o.id).userData.goal.set(x, 0, z);
    });
    request();
  }

  // click or tap a model to select its physical object (a tap, not a scroll)
  const hitMaterial = new THREE.MeshBasicMaterial({ visible: false });
  const hitBoxes = [];
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let down = null;
  canvas.addEventListener('pointerdown', (e) => { down = { x: e.clientX, y: e.clientY }; });
  canvas.addEventListener('pointerup', (e) => {
    if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 6) return;
    const r = canvas.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(hitBoxes, false)[0];
    if (!hit) return;
    let o = hit.object;
    while (o && o.userData.id === undefined) o = o.parent;
    if (o) select(o.userData.id);
  });

  subscribe(update);
  // first placement without a glide
  getState().objs.forEach((o) => { const [x, z] = toWorld(o.x, o.y); groups.get(o.id).position.set(x, 0, z); });
  update(getState());
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; last = 0; request(); }).observe(host);
  new ResizeObserver(request).observe(canvas);

  // recorded meshes at their recorded target sizes (assignments.json)
  await Promise.all(objs.map(async (o) => {
    const mesh = normalise(await loadGLB(o.slug), o.target);
    const g = groups.get(o.id);
    g.add(mesh);
    const box = new THREE.Box3().setFromObject(mesh);
    const size = box.getSize(new THREE.Vector3());
    g.userData.height = size.y;
    g.userData.footprint = Math.max(size.x, size.z);
    // an invisible box is the click target, so thin models (horse, fire truck) are easy to pick
    const hitBox = new THREE.Mesh(new THREE.BoxGeometry(Math.max(0.9, size.x), Math.max(0.9, size.y), Math.max(0.9, size.z)), hitMaterial);
    hitBox.position.y = Math.max(0.9, size.y) / 2;
    g.add(hitBox);
    hitBoxes.push(hitBox);
  }));
  status.textContent = '';
  status.hidden = true;
  host.classList.add('is-ready');
  request();
}
