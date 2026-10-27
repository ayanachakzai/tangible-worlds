// Chapter 04 scale comparison: the cached a-house.glb sized as the production
// renderer sizes it. normalizeAndAddModel() sets the longest side of the model's
// Box3 to target_size and rests it on the table; here the model is normalised once
// to 1 and a parent group carries the target, so every size is computed from the
// same original bounds and nothing accumulates.
//
// The camera is fixed: an orthographic front view framed once for the largest
// target (huge, 3.00) at any turn of the model. It never refits to the selected
// size, so tiny, none, large and huge appear at their true relative sizes. The
// dashed box is the bounding box the renderer scales, at no marker (1.00); it turns
// with the model but never scales.
import * as THREE from 'three';
import { gsap } from 'gsap';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { loadGLB, normalise } from '../lib/meshes.js';

const MAX_TARGET = 3.0; // MARKED_SCALE_TARGETS.huge
const START_TURN = -0.6;

export async function init(host, { reduced, slug, initial }) {
  const canvas = host.querySelector('.js-sc-canvas');
  const status = host.querySelector('.js-sc-status');

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75));
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.75;
  pmrem.dispose();
  const key = new THREE.DirectionalLight(0xfff4e6, 1.4);
  key.position.set(-3, 5, 4);
  scene.add(key);

  // the model, normalised once with no parent so its Box3 is in its own frame:
  // longest side 1, centred on the vertical axis, resting on y = 0
  const mesh = normalise(await loadGLB(slug), 1);
  const box = new THREE.Box3().setFromObject(mesh);
  const size = box.getSize(new THREE.Vector3());
  const centre = box.getCenter(new THREE.Vector3());

  const turn = new THREE.Group();        // turns model and reference together
  turn.rotation.y = START_TURN;
  scene.add(turn);
  const holder = new THREE.Group();      // carries the target size only
  holder.add(mesh);
  turn.add(holder);

  // the unmarked reference: the normalised Box3 itself, drawn over the model
  const outline = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(size.x, size.y, size.z)),
    new THREE.LineDashedMaterial({ color: 0x171717, dashSize: 0.05, gapSize: 0.04, transparent: true, opacity: 0.6, depthTest: false }),
  );
  outline.position.copy(centre);
  outline.computeLineDistances();
  outline.renderOrder = 1;
  turn.add(outline);

  // the table line
  const ground = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-50, 0, 0), new THREE.Vector3(50, 0, 0)]),
    new THREE.LineBasicMaterial({ color: 0x171717 }),
  );
  scene.add(ground);

  // fixed frame: wide enough for the huge model's footprint at any turn (the box
  // corners' distance from the axis), tall enough for its height, ground near the
  // bottom edge
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 200);
  camera.position.set(0, 0, 50);
  camera.lookAt(0, 0, 0);
  const reach = Math.max(...[box.min.x, box.max.x].flatMap((x) => [box.min.z, box.max.z].map((z) => Math.hypot(x, z))));
  const needW = 2 * reach * MAX_TARGET * 1.06, needH = size.y * MAX_TARGET * 1.08;
  function frame() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return false;
    renderer.setSize(w, h, false);
    let hw = needW / 2, hh = needH / 2;
    if (hw / hh > w / h) hh = hw / (w / h); else hw = hh * (w / h);
    const bottom = -needH * 0.04;
    Object.assign(camera, { left: -hw, right: hw, bottom, top: bottom + 2 * hh });
    camera.updateProjectionMatrix();
    return true;
  }
  const render = () => renderer.render(scene, camera);

  // the longest side of the model's Box3 in its own frame, as the renderer measures it
  const measured = new THREE.Box3(), dims = new THREE.Vector3();
  function measure() {
    const r = turn.rotation.y;
    turn.rotation.y = 0;
    turn.updateMatrixWorld(true);
    measured.setFromObject(mesh).getSize(dims);
    turn.rotation.y = r;
    turn.updateMatrixWorld(true);
    canvas.dataset.longest = Math.max(dims.x, dims.y, dims.z).toFixed(4);
    canvas.dataset.dims = [dims.x, dims.y, dims.z].map((v) => v.toFixed(4)).join(' ');
  }

  let target = initial;
  holder.scale.setScalar(target);
  measure();
  status.hidden = true;
  if (frame()) render();
  new ResizeObserver(() => { if (frame()) render(); }).observe(canvas);

  // drag sideways, or use the arrow keys, to turn the model and its reference
  let drag = null;
  canvas.addEventListener('pointerdown', (e) => { drag = e.clientX; try { canvas.setPointerCapture(e.pointerId); } catch { /* ignore */ } });
  canvas.addEventListener('pointermove', (e) => {
    if (drag === null) return;
    turn.rotation.y += (e.clientX - drag) * 0.012;
    drag = e.clientX;
    render();
  });
  const end = () => { drag = null; };
  canvas.addEventListener('pointerup', end);
  canvas.addEventListener('pointercancel', end);
  canvas.addEventListener('keydown', (e) => {
    const d = e.key === 'ArrowLeft' ? -1 : e.key === 'ArrowRight' ? 1 : 0;
    if (!d) return;
    e.preventDefault();
    turn.rotation.y += d * (Math.PI / 12);
    render();
  });

  let tween = null;
  return {
    // always set from the target, never multiplied from the current scale
    setTarget(t) {
      tween?.kill();
      target = t;
      canvas.dataset.longest = '';
      if (reduced) { holder.scale.setScalar(t); measure(); render(); return; }
      tween = gsap.to(holder.scale, { x: t, y: t, z: t, duration: 0.3, ease: 'power2.out', overwrite: true, onUpdate: render,
        onComplete: () => { holder.scale.setScalar(t); measure(); render(); } });
    },
  };
}
