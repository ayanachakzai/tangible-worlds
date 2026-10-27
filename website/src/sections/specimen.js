// Chapter 03 specimen: the selected object's cached GLB on its own, turning slowly
// against the page. It shows a stored result, so there is no table, grid or
// atmosphere; materials are left exactly as they were generated.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { loadGLB, normalise } from '../lib/meshes.js';

const TURN = (Math.PI * 2) / 20; // radians per second: one turn every 20 s
const SIZE = 2;                  // common display size (longest side), not the scene scale

export function init(host, { reduced, getState, subscribe, isShown, onShownChange }) {
  const canvas = host.querySelector('.c03-specimen__canvas');
  const status = host.querySelector('.c03-specimen__status');

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1;

  const scene = new THREE.Scene();
  // neutral studio light: a soft room environment for the PBR materials, a warm key
  // from the upper left and a cool rim from behind, so form reads without shadows
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.7;
  pmrem.dispose();
  const key = new THREE.DirectionalLight(0xfff4e6, 1.6);
  key.position.set(-3, 4, 3);
  const rim = new THREE.DirectionalLight(0xdfe8ff, 0.9);
  rim.position.set(2, 2.5, -4);
  scene.add(key, rim);

  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  const turntable = new THREE.Group(); // rotates about the vertical axis
  scene.add(turntable);
  let model = null, slug = null, loading = 0;

  // frame the space the model sweeps as it turns (its horizontal half-diagonal and
  // half-height), so no angle of the turn is clipped
  let reach = 1, half = 1;
  function measure() {
    const size = new THREE.Box3().setFromObject(model).getSize(new THREE.Vector3());
    reach = Math.hypot(size.x, size.z) / 2;
    half = size.y / 2;
  }
  function frame() {
    if (!model) return;
    const tv = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    const th = tv * camera.aspect;
    const d = Math.max(half / tv, reach / th) * 1.0 + reach;
    camera.position.set(0, d * 0.16, d);
    camera.lookAt(0, 0, 0);
  }

  async function show(o) {
    if (o.slug === slug) return;
    slug = o.slug;
    const ticket = ++loading;
    status.hidden = false;
    const mesh = normalise(await loadGLB(o.slug), SIZE);
    if (ticket !== loading) return; // a newer selection arrived meanwhile
    mesh.traverse((n) => { if (n.isMesh) { n.castShadow = false; n.receiveShadow = false; } });
    // centre it vertically too, so it floats rather than stands
    const b = new THREE.Box3().setFromObject(mesh);
    mesh.position.y -= (b.min.y + b.max.y) / 2;
    if (model) turntable.remove(model); // shared cached geometry: removed, never disposed
    model = mesh;
    turntable.add(model);
    measure();
    status.hidden = true;
    canvas.setAttribute('aria-label', `The cached 3D model of ${o.generation}${reduced ? '' : ', turning slowly'}.`);
    frame();
    request();
  }

  // drag to turn; automatic turning pauses during the drag and eases back after it
  let dragging = false, lastX = 0, resumeAt = 0, spin = reduced ? 0 : 1;
  canvas.addEventListener('pointerdown', (e) => {
    dragging = true; lastX = e.clientX;
    try { canvas.setPointerCapture(e.pointerId); } catch { /* ignore */ }
    host.classList.add('is-dragging');
    request();
  });
  canvas.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    turntable.rotation.y += (e.clientX - lastX) * 0.012;
    lastX = e.clientX;
    request();
  });
  const end = () => {
    if (!dragging) return;
    dragging = false;
    host.classList.remove('is-dragging');
    resumeAt = performance.now() + 1200;
    spin = 0;
    request();
  };
  canvas.addEventListener('pointerup', end);
  canvas.addEventListener('pointercancel', end);

  // render only while the panel is open and on screen; stop otherwise
  let raf = 0, last = 0, onScreen = false;
  const active = () => onScreen && isShown();
  function tick(now) {
    raf = 0;
    if (!active()) { last = 0; return; }
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    if (canvas.width !== Math.round(w * renderer.getPixelRatio()) || canvas.height !== Math.round(h * renderer.getPixelRatio())) {
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      frame();
    }
    // a 20 s turn reads smoothly at 30 frames a second; dragging stays at full rate
    if (!dragging && last && now - last < 24) { raf = requestAnimationFrame(tick); return; }
    const dt = last ? Math.min(0.1, (now - last) / 1000) : 0;
    last = now;
    if (!reduced && !dragging) {
      if (now >= resumeAt) spin = Math.min(1, spin + dt / 0.8); // ease back in over 0.8 s
      turntable.rotation.y += TURN * spin * dt;
    }
    renderer.render(scene, camera);
    if (!reduced || dragging) raf = requestAnimationFrame(tick); // reduced motion: draw on demand only
  }
  function request() { if (!raf && active()) raf = requestAnimationFrame(tick); }

  new IntersectionObserver(([e]) => { onScreen = e.isIntersecting; request(); }).observe(host);
  new ResizeObserver(request).observe(canvas);
  onShownChange(request);
  subscribe(({ active: o }) => show(o));
  show(getState().active);
}
