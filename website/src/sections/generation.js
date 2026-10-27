import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { loadGLB, normalise, disposeTree } from '../lib/meshes.js';
import { MODELS_GOOD, MODELS_WEAK } from '../data.js';

// a lighter pixel budget on narrow, short or touch screens
const light = () => matchMedia('(max-width: 820px), (max-height: 520px), (pointer: coarse)').matches;
const ratio = () => Math.min(devicePixelRatio, light() ? 1.5 : 2);

// a lost context is announced and redrawn when the browser restores it
function watchContext(canvas, say, redraw) {
  canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); say('3D view paused by the browser'); });
  canvas.addEventListener('webglcontextrestored', () => { say(''); redraw(); });
}

function makeRenderer(canvas) {
  const r = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'high-performance' });
  r.setPixelRatio(ratio());
  r.outputColorSpace = THREE.SRGBColorSpace;
  r.toneMapping = THREE.ACESFilmicToneMapping;
  r.toneMappingExposure = 0.95;
  r.shadowMap.enabled = true;
  r.shadowMap.type = THREE.PCFSoftShadowMap;
  return r;
}

function studio(renderer, bg) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(bg);
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  pmrem.dispose();
  scene.environmentIntensity = 0.55;
  const key = new THREE.DirectionalLight(0xfff4e6, 2.2);
  key.position.set(3, 5, 2.5);
  key.castShadow = true;
  key.shadow.mapSize.setScalar(light() ? 512 : 1024);
  Object.assign(key.shadow.camera, { left: -3, right: 3, top: 3, bottom: -3, near: 0.5, far: 20 });
  key.shadow.bias = -0.0008;
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xb9c8ff, 0.6);
  rim.position.set(-4, 2, -3);
  scene.add(rim);
  const floor = new THREE.Mesh(new THREE.CircleGeometry(6, 64), new THREE.ShadowMaterial({ opacity: 0.35 }));
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);
  return { scene, key };
}

function sizeTo(renderer, camera, el) {
  const w = el.clientWidth, h = el.clientHeight;
  if (!w || !h) return;
  const c = renderer.domElement;
  if (c.width !== Math.round(w * renderer.getPixelRatio()) || c.height !== Math.round(h * renderer.getPixelRatio())) {
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
}

/* ───────────── Pipeline sequence ───────────── */
// Pinned (wide screens): one full-stage scene scrubbed by scroll through the five
// stages. Unpinned (narrow or short screens): the stages read in order and the same
// scene, in its final state, sits in the SPAR3D stage as a view the visitor turns.
// Either way there is one renderer, and it draws only when something has changed.
async function initPipeline(root, reduced, genProgress) {
  const stage = root.querySelector('.gen__stage');
  const canvas = root.querySelector('.gen__canvas');
  const view = root.querySelector('.js-gen-view');
  const status = root.querySelector('.js-gen-status');
  const steps = [...root.querySelectorAll('.gen__steps > li')];
  const meaningEl = root.querySelector('.js-gen-meaning');
  const rules = [...root.querySelectorAll('.js-gen-rules li')];
  const note = document.createElement('p');
  note.className = 'gen__note';
  note.textContent = 'Real source image and GLB · the reveal animation is explanatory';
  stage.appendChild(note);
  const say = (t) => { status.textContent = t; };
  const flowMQ = matchMedia(genProgress.flowQuery);
  let flow = flowMQ.matches;

  let apply = () => {};
  let req = () => {};
  let turn = -1.3; // the visitor's turn of the unpinned view; it opens at three-quarters, like the source image

  // canvas and status live in the stage when pinned, in the SPAR3D view when not
  const place = () => {
    flow = flowMQ.matches;
    const host = flow ? view : stage;
    if (canvas.parentElement !== host) host.prepend(canvas);
    if (status.parentElement !== host) host.appendChild(status);
    if (flow) {
      canvas.tabIndex = 0;
      canvas.setAttribute('aria-label', 'The cached a-windmill.glb mesh. Drag sideways, or use the arrow keys, to turn it.');
    } else {
      canvas.removeAttribute('tabindex');
      canvas.setAttribute('aria-label', "Three.js reconstruction of the generation stages for 'a windmill'");
    }
  };
  place();

  let renderer;
  try {
    renderer = makeRenderer(canvas);
  } catch (e) {
    say('3D view unavailable: this browser could not start WebGL');
    console.error(e);
    return;
  }
  const { scene } = studio(renderer, 0x090909);
  scene.fog = new THREE.Fog(0x090909, 8, 18);
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
  camera.position.set(0, 1.3, 6.2);
  const target = new THREE.Vector3(0, 0.9, 0);

  let tex, model;
  try {
    [tex, model] = await Promise.all([new THREE.TextureLoader().loadAsync('/media/img/src-a-windmill.webp'), loadGLB('a-windmill')]);
  } catch (e) {
    say('could not load a-windmill.glb');
    console.error(e);
    return;
  }
  say('');

  // Stage 1 image plane
  tex.colorSpace = THREE.SRGBColorSpace;
  const imgMat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, opacity: 0, toneMapped: false, side: THREE.DoubleSide });
  const img = new THREE.Mesh(new THREE.PlaneGeometry(1.9, 1.9), imgMat);
  img.position.set(0, 1.05, 0);
  scene.add(img);
  const frame = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.PlaneGeometry(1.9, 1.9)), new THREE.LineBasicMaterial({ color: 0xf2c230, transparent: true, opacity: 0 }));
  img.add(frame);

  // Stage 2 mesh with a rising clip plane
  const clip = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);
  renderer.localClippingEnabled = true;
  const mesh = normalise(model, 2.1);
  mesh.traverse((n) => { if (n.isMesh) { n.material = n.material.clone(); n.material.clippingPlanes = [clip]; n.material.clipShadows = true; } });
  const holder = new THREE.Group();
  holder.add(mesh);
  scene.add(holder);
  const mBox = new THREE.Box3().setFromObject(holder);
  const H = mBox.max.y;
  const scanRing = new THREE.Mesh(new THREE.RingGeometry(0.95, 0.965, 96), new THREE.MeshBasicMaterial({ color: 0xf2c230, transparent: true, opacity: 0, side: THREE.DoubleSide, toneMapped: false }));
  scanRing.rotation.x = -Math.PI / 2;
  scene.add(scanRing);
  const boxHelper = new THREE.Box3Helper(mBox, 0xf2c230);
  boxHelper.material.transparent = true; boxHelper.material.opacity = 0;
  scene.add(boxHelper);

  apply = (p) => {
    // 0–0.2 meaning, 0.2–0.4 shaping, 0.4–0.6 image, 0.6–0.8 reconstruction, 0.8–1 renderer
    const seg = (a, b) => THREE.MathUtils.clamp((p - a) / (b - a), 0, 1);
    const ease = (t) => t * t * (3 - 2 * t);
    const i = Math.min(4, Math.floor(p * 5 + 1e-6));
    steps.forEach((s, k) => { s.classList.toggle('is-on', k === i); s.style.setProperty('--fill', `${k < i ? 100 : k === i ? ((p * 5) % 1) * 100 : 0}%`); });

    const m = ease(seg(0.0, 0.08)) * (1 - ease(seg(0.36, 0.44)));
    meaningEl.style.opacity = m;
    meaningEl.style.transform = `translate(-50%, ${-50 - seg(0.2, 0.36) * 60}%) scale(${1 - seg(0.2, 0.36) * 0.35})`;
    rules.forEach((r, k) => { r.style.opacity = ease(seg(0.2 + k * 0.025, 0.25 + k * 0.025)) * (1 - ease(seg(0.38, 0.44))); });

    const im = ease(seg(0.4, 0.5));
    const down = ease(seg(0.6, 0.72));
    imgMat.opacity = im * (1 - 0.94 * down);
    frame.material.opacity = im * 0.9 * (1 - down);
    img.scale.setScalar(0.7 + 0.3 * im);
    img.rotation.x = -Math.PI / 2 * down;
    img.position.y = 1.05 * (1 - down) + 0.004;
    img.position.z = 0;

    const rec = ease(seg(0.62, 0.8));
    clip.constant = -0.01 + rec * (H + 0.05);
    holder.visible = rec > 0.001;
    scanRing.position.y = clip.constant;
    scanRing.material.opacity = rec > 0 && rec < 1 ? 0.85 : 0;

    const norm = seg(0.8, 1);
    boxHelper.material.opacity = Math.sin(Math.min(1, norm * 1.6) * Math.PI) * 0.8;
    holder.rotation.y = -0.6 + p * 2.2;
    const k = Math.pow(Math.max(1, 0.9 / camera.aspect), 0.85); // pull back on portrait screens
    camera.position.set(Math.sin(p * 0.6) * 0.9, 1.3 + rec * 0.5, (6.2 - norm * 0.6) * k);
    camera.lookAt(target);
  };

  // the pose for the current layout: scroll progress when pinned, the finished
  // mesh turned by the visitor when not
  const pose = () => {
    if (!flow) { apply(reduced ? 0.999 : genProgress.p); return; }
    apply(1);
    holder.rotation.y += turn;
  };

  let visible = false;
  let raf = 0;
  const tick = () => { raf = 0; const a = camera.aspect; sizeTo(renderer, camera, canvas.parentElement); if (a !== camera.aspect) pose(); renderer.render(scene, camera); };
  // whether the pinned stage is on screen is checked when a frame is wanted: an
  // observer flag could stay false after a jump straight into the pinned range
  // (a hash link or a fast scroll), leaving the stage undrawn while the captions moved
  const onScreen = () => { const r = canvas.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; };
  req = () => { if (!raf && (visible || onScreen())) raf = requestAnimationFrame(tick); };
  const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; req(); });
  io.observe(canvas);
  addEventListener('resize', req);
  watchContext(canvas, say, req);

  // the unpinned view turns with a sideways drag or the arrow keys; vertical
  // swipes keep scrolling the page (touch-action: pan-y)
  let dragX = null;
  canvas.addEventListener('pointerdown', (e) => { if (!flow) return; dragX = e.clientX; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', (e) => {
    if (dragX === null) return;
    turn += (e.clientX - dragX) * 0.012;
    dragX = e.clientX;
    pose(); req();
  });
  const release = () => { dragX = null; };
  canvas.addEventListener('pointerup', release);
  canvas.addEventListener('pointercancel', release);
  canvas.addEventListener('keydown', (e) => {
    if (!flow || (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight')) return;
    e.preventDefault();
    turn += e.key === 'ArrowLeft' ? -0.25 : 0.25;
    pose(); req();
  });

  // a layout change (rotation, a resized window) moves the canvas and its state
  flowMQ.addEventListener('change', () => {
    place();
    renderer.setPixelRatio(ratio());
    io.disconnect(); io.observe(canvas);
    pose(); req();
  });

  if (reduced) steps.forEach((s) => s.classList.add('is-on'));
  else genProgress.listener = (p) => { if (!flow) { apply(p); req(); } };
  pose();
  // compile the shaders now, while the stage is still ahead of the reader, rather
  // than in the first frame drawn on screen
  await renderer.compileAsync(scene, camera).catch(() => {});
  req();
}

/* ───────────── Bench ───────────── */
function initBench(root, reduced) {
  const view = root.querySelector('.bench__view');
  const canvas = root.querySelector('.bench__canvas');
  const nameEl = root.querySelector('.js-bench-name');
  const statusEl = root.querySelector('.js-bench-status');
  const srcImg = root.querySelector('.js-bench-src');
  const good = root.querySelector('.js-bench-good');
  const weak = root.querySelector('.js-bench-weak');

  let renderer;
  try {
    renderer = makeRenderer(canvas);
  } catch (e) {
    statusEl.textContent = '3D view unavailable: this browser could not start WebGL';
    console.error(e);
    return;
  }
  let req = () => {};
  const { scene } = studio(renderer, 0x121211);
  scene.background = null;
  renderer.setClearColor(0x000000, 0);
  const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 50);
  camera.position.set(2.6, 1.6, 3.4);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = false; // the model follows the pointer directly, with no glide after release
  controls.enablePan = false;
  controls.enableZoom = false; // the wheel keeps scrolling the page
  canvas.style.touchAction = 'pan-y'; // vertical swipes scroll; horizontal swipes orbit
  controls.minDistance = 1.6; controls.maxDistance = 7;
  controls.target.set(0, 0.55, 0);
  // on narrow, short or touch screens the model waits to be turned instead of
  // spinning, so the view draws nothing while the page scrolls past it
  controls.autoRotate = !reduced && !light();
  controls.autoRotateSpeed = 0.9;
  controls.addEventListener('start', () => { controls.autoRotate = false; });
  controls.addEventListener('change', () => req());

  let current = null;
  let token = 0;
  let grow = null;
  const buttons = [];
  const build = (list, host) => list.forEach(([slug, label]) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.setAttribute('role', 'option');
    b.setAttribute('aria-selected', 'false');
    b.dataset.slug = slug;
    b.innerHTML = `<img src="/media/img/src-${slug}.webp" alt="" loading="lazy" /><span>${label.replace(/^a /, '')}</span>`;
    b.setAttribute('aria-label', label);
    b.addEventListener('click', () => show(slug, label));
    // warm the cached model as soon as the visitor points at or focuses it
    const warm = () => loadGLB(slug).catch(() => {});
    b.addEventListener('pointerenter', warm, { once: true });
    b.addEventListener('focus', warm, { once: true });
    host.appendChild(b);
    buttons.push(b);
  });
  build(MODELS_GOOD, good);
  build(MODELS_WEAK, weak);

  async function show(slug, label) {
    const my = ++token;
    buttons.forEach((b) => b.setAttribute('aria-selected', String(b.dataset.slug === slug)));
    nameEl.textContent = label;
    srcImg.src = `/media/img/src-${slug}.webp`;
    statusEl.textContent = `loading ${slug}.glb…`;
    view.classList.add('is-loading');
    try {
      const obj = normalise(await loadGLB(slug), 1.25);
      if (my !== token) return;
      await renderer.compileAsync(obj, camera, scene).catch(() => {});
      if (my !== token) return;
      view.classList.remove('is-loading');
      grow?.kill();
      if (current) { scene.remove(current); disposeTree(current); }
      current = obj;
      scene.add(obj);
      const b = new THREE.Box3().setFromObject(obj);
      controls.target.set(0, (b.max.y) / 2, 0);
      let tris = 0;
      obj.traverse((n) => { if (n.isMesh) tris += (n.geometry.index ? n.geometry.index.count : n.geometry.attributes.position.count) / 3; });
      statusEl.textContent = `${slug}.glb · ${Math.round(tris).toLocaleString('en-GB')} triangles`;
      if (!reduced) { const s = obj.scale.x; obj.scale.setScalar(s * 0.6); grow = gsap.to(obj.scale, { x: s, y: s, z: s, duration: 0.28, ease: 'power3.out', onUpdate: () => req() }); }
      req();
    } catch (e) {
      if (my !== token) return;
      view.classList.remove('is-loading');
      statusEl.textContent = 'could not load this mesh';
      console.error(e);
    }
  }

  // frames are drawn while the model is turning on its own, and otherwise only
  // when it has changed (a drag, a new model, a resize)
  let visible = false, raf = 0;
  const loop = () => {
    // raf stays set while drawing, so a change event raised by update() cannot start a second loop
    if (!visible) { raf = 0; return; }
    sizeTo(renderer, camera, view);
    controls.update();
    renderer.render(scene, camera);
    raf = controls.autoRotate ? requestAnimationFrame(loop) : 0;
  };
  req = () => { if (!raf && visible) raf = requestAnimationFrame(loop); };
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; req(); }).observe(view);
  addEventListener('resize', req);
  watchContext(canvas, (t) => { statusEl.textContent = t; }, req);
  show('a-lighthouse', 'a lighthouse');
}

export async function init(root, { reduced, genProgress }) {
  initBench(root, reduced);
  await initPipeline(root, reduced, genProgress);
  ScrollTrigger.refresh();
}
