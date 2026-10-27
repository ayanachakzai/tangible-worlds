import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { gsap } from 'gsap';
import { Atmosphere, TABLE_SIZE } from '../lib/atmosphere.js';
import { loadGLB, normalise } from '../lib/meshes.js';
import { SESSION, ATMOSPHERE_COMMANDS, FIELDS } from '../data.js';
import { distance, NEAR_THRESHOLD, FAR_THRESHOLD, proximity, toWorld } from '../lib/grammar.js';

// Proximity case documented in dissertation Fig. 5.24b: mountain + tent,
// connector "a stone cairn" (the prompt's own example). Scales are neutral.
const RELATION = [
  { id: 1, meaning: 'a mountain', generation: 'a mountain', slug: 'a-mountain', target: 1.0, x: 0.30, y: 0.52 },
  { id: 2, meaning: 'a tent', generation: 'a tent', slug: 'a-tent', target: 1.0, x: 0.70, y: 0.48 },
];
const CONNECTOR = { slug: 'a-stone-cairn', target: 0.65 };
const MOVE_THRESHOLD = 0.01; // browser movement logger threshold
const NEUTRAL = ATMOSPHERE_COMMANDS[0]; // schema default, used by Reset
const ACCENT = 0xf2c230;

// What distinguishes commands whose words repeat in the log
const CONTEXT = {
  'make it foggy|by day': 'said over a daytime scene',
  'make it foggy|at night': 'said over a clear moonlit night',
  'make it night|': 'said on its own',
  'make it night|after a thunderstorm': 'said straight after a thunderstorm',
};

// Field labels for the fine controls, grouped as the renderer uses them
const GROUPS = [
  ['Sun and lighting', ['light_elevation', 'light_azimuth', 'light_level', 'light_warmth']],
  ['Sky and haze', ['sky_elevation', 'sky_haze']],
  ['Mist', ['mist_amount', 'mist_height', 'mist_motion']],
  ['Rain and lightning', ['rain_amount', 'lightning_amount']],
];
const LABELS = {
  light_elevation: 'Light elevation', light_azimuth: 'Light direction', light_level: 'Light level', light_warmth: 'Light warmth',
  sky_elevation: 'Sun height in the sky', sky_haze: 'Haze', mist_amount: 'Mist amount', mist_height: 'Mist height',
  mist_motion: 'Mist motion', rain_amount: 'Rain', lightning_amount: 'Lightning',
};

const fmt = (v, step) => (+v).toFixed(step < 1 ? 2 : 0);

// One table, its meshes and its atmosphere. The chapter builds two: the recorded
// session and, separately, the proximity case.
function createWorld(viewport, canvas, { reduced, list, distance: camDist, target, fit = 0, bounds = [0.02, 0.98], loading, onSelect, onLive, onCommit, onShow }) {
  canvas.tabIndex = 0;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 1000);
  camera.position.set(0, 8.6, 12.4);
  const controls = new OrbitControls(camera, canvas);
  controls.target.copy(target);
  controls.enableDamping = true;
  controls.enablePan = false;
  controls.enableZoom = false; // the wheel keeps scrolling the page
  controls.minDistance = 4; controls.maxDistance = 20;
  // on touch screens let vertical swipes scroll the page instead of trapping it
  if (matchMedia('(pointer: coarse)').matches) canvas.style.touchAction = 'pan-y';
  controls.minPolarAngle = 0.15; controls.maxPolarAngle = 1.38;

  // production table: fixed material, never changed by mood
  const table = new THREE.Mesh(new THREE.PlaneGeometry(TABLE_SIZE, TABLE_SIZE), new THREE.MeshStandardMaterial({ color: 0x777777, roughness: 0.8 }));
  table.rotation.x = -Math.PI / 2;
  table.receiveShadow = true;
  scene.add(table);
  const grid = new THREE.GridHelper(TABLE_SIZE, 10, 0x46515a, 0x364049);
  grid.position.y = 0.012;
  scene.add(grid);

  const atmo = new Atmosphere(renderer, scene);

  // selection: a thin ring on the table under the selected object
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(0.93, 1, 72),
    new THREE.MeshBasicMaterial({ color: ACCENT, transparent: true, opacity: 0, depthWrite: false, toneMapped: false, side: THREE.DoubleSide }),
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.03;
  ring.renderOrder = 5;
  ring.visible = false;

  // DOM labels like the production label sprites
  const labelLayer = document.createElement('div');
  labelLayer.className = 'c06-labels';
  viewport.appendChild(labelLayer);
  const makeLabel = (text) => {
    const s = document.createElement('span');
    s.className = 'c06-label';
    s.textContent = text;
    labelLayer.appendChild(s);
    return s;
  };

  const objects = []; // { data, group, label, x, y, lastX, lastY, height, radius }
  const extras = [];  // other labelled groups, e.g. the connector
  let selected = null;

  function select(o) {
    if (selected === o) return;
    selected?.label.classList.remove('is-sel');
    selected = o;
    if (!o) { ring.visible = false; return; }
    o.label.classList.add('is-sel');
    o.group.add(ring);
    ring.scale.setScalar(o.radius);
    ring.visible = true;
    gsap.killTweensOf(ring.material);
    if (reduced) ring.material.opacity = 0.95;
    else gsap.fromTo(ring.material, { opacity: 0 }, { opacity: 0.95, duration: 0.15, ease: 'power1.out' });
    onSelect?.(o);
  }

  function setPos(o, x, y) {
    o.x = Math.min(bounds[1], Math.max(bounds[0], x));
    o.y = Math.min(bounds[1], Math.max(bounds[0], y));
    const [wx, wz] = toWorld(o.x, o.y);
    o.group.position.set(wx, 0, wz);
    onLive?.(o);
  }

  function committed(o) {
    const moved = Math.hypot(o.x - o.lastX, o.y - o.lastY);
    if (moved < MOVE_THRESHOLD) return;
    o.lastX = o.x; o.lastY = o.y;
    onCommit?.(o, moved);
  }

  const ready = Promise.all(list.map((d) => loadGLB(d.slug).then((m) => normalise(m, d.target)))).then((loaded) => {
    loaded.forEach((mesh, i) => {
      const d = list[i];
      const group = new THREE.Group();
      group.add(mesh);
      const [wx, wz] = toWorld(d.x, d.y);
      group.position.set(wx, 0, wz);
      group.userData.index = i;
      scene.add(group);
      const box = new THREE.Box3().setFromObject(mesh);
      const size = box.getSize(new THREE.Vector3());
      objects.push({
        data: d, group, label: makeLabel(`${d.id} · ${d.meaning}`), x: d.x, y: d.y, lastX: d.x, lastY: d.y,
        height: box.max.y, radius: Math.max(0.42, Math.hypot(size.x, size.z) * 0.58),
      });
      if (!reduced) { const s = mesh.scale.x; mesh.scale.setScalar(s * 0.6); gsap.to(mesh.scale, { x: s, y: s, z: s, duration: 0.3, delay: i * 0.05, ease: 'power3.out' }); }
    });
    loading.classList.add('is-done');
    req();
  });

  // ── pointer: drag an object on the table plane; on touch, tap an object
  // then tap where it should go ──
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  const ground = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const hit = new THREE.Vector3();
  let drag = null, press = null;
  const toNDC = (e) => { const r = canvas.getBoundingClientRect(); ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); };
  const pick = (e) => {
    toNDC(e);
    ray.setFromCamera(ndc, camera);
    const hits = ray.intersectObjects(objects.map((o) => o.group), true);
    if (!hits.length) return null;
    let g = hits[0].object; while (g && g.userData.index === undefined) g = g.parent;
    return g ? objects[g.userData.index] : null;
  };
  canvas.addEventListener('pointerdown', (e) => {
    press = { x: e.clientX, y: e.clientY, type: e.pointerType };
    const o = pick(e);
    if (!o) return;
    drag = o;
    select(o);
    controls.enabled = false;
    try { canvas.setPointerCapture(e.pointerId); } catch { /* window listeners cover this */ }
    canvas.style.cursor = 'grabbing';
  });
  addEventListener('pointermove', (e) => {
    if (!drag && e.target !== canvas) return;
    toNDC(e);
    ray.setFromCamera(ndc, camera);
    if (drag) {
      if (ray.ray.intersectPlane(ground, hit)) setPos(drag, hit.x / TABLE_SIZE + 0.5, hit.z / TABLE_SIZE + 0.5);
      return;
    }
    if (e.pointerType === 'mouse') canvas.style.cursor = ray.intersectObjects(objects.map((o) => o.group), true).length ? 'grab' : '';
  });
  const end = (e) => {
    const tap = press && Math.hypot(e.clientX - press.x, e.clientY - press.y) < 8;
    if (drag) { committed(drag); drag = null; controls.enabled = true; canvas.style.cursor = ''; }
    else if (tap && press.type === 'touch' && selected && e.target === canvas) {
      toNDC(e);
      ray.setFromCamera(ndc, camera);
      if (ray.ray.intersectPlane(ground, hit)) { setPos(selected, hit.x / TABLE_SIZE + 0.5, hit.z / TABLE_SIZE + 0.5); committed(selected); }
    }
    press = null;
  };
  addEventListener('pointerup', end);
  addEventListener('pointercancel', end);

  // ── keyboard: number keys select, arrows move ──
  let keyTimer = 0;
  canvas.addEventListener('keydown', (e) => {
    const n = parseInt(e.key, 10);
    if (n >= 1 && n <= objects.length) { select(objects[n - 1]); return; }
    const step = e.shiftKey ? 0.05 : 0.02;
    const k = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
    if (!k || !objects.length) return;
    e.preventDefault();
    if (!selected) select(objects[0]);
    const o = selected;
    setPos(o, o.x + k[0], o.y + k[1]);
    clearTimeout(keyTimer);
    keyTimer = setTimeout(() => committed(o), 450);
  });

  // ── render loop, only while on screen ──
  let visible = false, raf = 0, sizedFor = '';
  const v = new THREE.Vector3();
  // labels sit above their object; `below` puts one under it instead, for a
  // connector standing between two labelled objects
  function placeLabel(el, group, h, below = false) {
    v.set(group.position.x, below ? 0 : h + 0.25, group.position.z).project(camera);
    el.style.opacity = v.z > 1 ? 0 : 1;
    el.style.transform = `translate(${(v.x * 0.5 + 0.5) * viewport.clientWidth}px, ${(-v.y * 0.5 + 0.5) * viewport.clientHeight}px) translate(-50%, ${below ? '10px' : '-100%'})`;
  }
  const onScreen = () => { const r = viewport.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; };
  function loop() {
    raf = 0;
    if (!visible && !onScreen()) return;
    const w = viewport.clientWidth, h = viewport.clientHeight;
    if (sizedFor !== `${w}x${h}`) {
      sizedFor = `${w}x${h}`;
      renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
      // portrait screens: keep the table in frame by stepping back
      // and never closer than keeps `fit` table units across the frame
      const k = Math.pow(Math.max(1, 1.08 / camera.aspect), 0.75);
      const d = Math.max(camDist * k, fit / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.aspect));
      const dir = camera.position.clone().sub(controls.target).normalize();
      camera.position.copy(controls.target).addScaledVector(dir, d);
      controls.maxDistance = Math.max(20, d * 1.3);
    }
    controls.update();
    // the lightning clock in Atmosphere is performance.now() based
    atmo.update(performance.now() * 0.001);
    objects.forEach((o) => placeLabel(o.label, o.group, o.height));
    extras.forEach((x) => { if (x.group.visible) placeLabel(x.label, x.group, x.height, x.below); });
    renderer.render(scene, camera);
    raf = requestAnimationFrame(loop);
  }
  function req() { if (!raf && (visible || onScreen())) raf = requestAnimationFrame(loop); }
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) { onShow?.(); req(); } }).observe(viewport);

  return { atmo, scene, camera, controls, renderer, objects, extras, ready, select, setPos, makeLabel, get selected() { return selected; } };
}

export async function init(root, { reduced }) {
  const touch = matchMedia('(pointer: coarse)').matches;
  root.classList.toggle('is-touch', touch);
  const tryEl = root.querySelector('.js-env-try');
  const quiet = () => tryEl.classList.add('is-quiet');

  // ── 1 · the recorded session ──
  const movedEl = root.querySelector('.js-env-moved');
  const main = createWorld(root.querySelector('.env__viewport'), root.querySelector('.env__canvas'), {
    reduced, list: SESSION, distance: 15.2, target: new THREE.Vector3(0, 0.5, 0), loading: root.querySelector('.js-env-loading'),
    onSelect: (o) => {
      quiet();
      movedEl.innerHTML = `Selected <b>${o.data.meaning}</b>.${touch ? ' Tap where it should go.' : ''}`;
    },
    onCommit: (o, moved) => {
      movedEl.innerHTML = `Moved <b>${o.data.generation}</b>. Position updated. The cached model was reused.`
        + `<span class="c06-meta">${o.data.slug}.glb · Δ ${moved.toFixed(3)} · position (${o.x.toFixed(2)}, ${o.y.toFixed(2)}) · target ${o.data.target.toFixed(2)} kept</span>`;
    },
  });
  const atmo = main.atmo;

  // ── atmosphere: recorded commands ──
  const appliedEl = root.querySelector('.js-env-applied');
  const whyEl = root.querySelector('.js-env-why');
  const whyText = root.querySelector('.js-env-why-text');
  const cmdsHost = root.querySelector('.js-env-cmds');
  const fieldsHost = root.querySelector('.js-env-fields');
  const fieldEls = {};
  const FIELD = Object.fromEntries(FIELDS.map((f) => [f[0], f]));

  GROUPS.forEach(([title, keys]) => {
    const g = document.createElement('fieldset');
    g.className = 'c06-group';
    g.innerHTML = `<legend>${title}</legend>`;
    keys.forEach((name) => {
      const [, min, max, step] = FIELD[name];
      const id = `f-${name}`;
      const wrap = document.createElement('div');
      wrap.className = 'c06-field';
      wrap.innerHTML = `<label for="${id}" title="${name}">${LABELS[name]}</label><output for="${id}"></output><input id="${id}" type="range" min="${min}" max="${max}" step="${step}" data-key="${name}" />`;
      g.appendChild(wrap);
      const input = wrap.querySelector('input'), out = wrap.querySelector('output');
      input.addEventListener('input', () => {
        tween?.kill();
        quiet();
        paint(fieldEls[name], +input.value);
        setCommand(-1);
        atmo.apply({ [name]: +input.value, mood: 'manual' });
        stateVersion++;
        appliedEl.innerHTML = '<p class="c06-applied__t">Adjusted by hand in the browser reconstruction.</p><p class="c06-applied__m">The recorded values are unchanged.</p>';
        whyEl.hidden = true;
      });
      fieldEls[name] = { input, out, step, min, max };
    });
    fieldsHost.appendChild(g);
  });
  function paint(f, value) {
    f.input.value = value;
    f.out.textContent = fmt(value, f.step);
    f.input.style.setProperty('--fill', `${((value - f.min) / (f.max - f.min)) * 100}%`);
  }
  const syncFields = (m) => Object.entries(fieldEls).forEach(([k, f]) => paint(f, m[k]));

  const COMMANDS = ATMOSPHERE_COMMANDS.slice(1);
  const cmdBtns = COMMANDS.map((c, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'c06-cmd';
    b.setAttribute('role', 'radio');
    b.setAttribute('aria-checked', 'false');
    b.tabIndex = -1;
    const ctx = CONTEXT[`${c.cmd}|${c.label || ''}`];
    b.innerHTML = `<span class="c06-cmd__t">“${c.cmd}”</span>${ctx ? `<span class="c06-cmd__c">${ctx}</span>` : ''}`;
    b.addEventListener('click', () => { quiet(); runCommand(i); });
    b.addEventListener('keydown', (e) => {
      const d = e.key === 'ArrowDown' || e.key === 'ArrowRight' ? 1 : e.key === 'ArrowUp' || e.key === 'ArrowLeft' ? -1 : 0;
      if (!d) return;
      e.preventDefault();
      const j = (i + d + cmdBtns.length) % cmdBtns.length; cmdBtns[j].focus(); quiet(); runCommand(j);
    });
    cmdsHost.appendChild(b);
    return b;
  });
  function setCommand(i) {
    cmdBtns.forEach((b, k) => { b.setAttribute('aria-checked', String(k === i)); b.tabIndex = k === Math.max(0, i) ? 0 : -1; });
  }

  // a short reading of what the recorded state changes from the neutral default
  function describe(m) {
    const out = [];
    const n = (x) => `<span class="c06-num">${x.toFixed(2)}</span>`;
    if (m.sky_elevation < 0) out.push('sun below the horizon');
    else if (m.sky_elevation < 20) out.push('sun low in the sky');
    else if (m.sky_elevation > 60) out.push('sun high overhead');
    if (m.light_warmth >= 0.5) out.push('warm light');
    else if (m.light_warmth <= -0.2) out.push('cool light');
    if (m.light_level < 0.5) out.push('dim light');
    else if (m.light_level >= 0.8) out.push('bright light');
    if (m.sky_haze >= 0.6) out.push('heavy haze');
    if (m.mist_amount > 0) out.push(`mist ${n(m.mist_amount)}`);
    if (m.rain_amount > 0) out.push(`rain ${n(m.rain_amount)}`);
    if (m.lightning_amount > 0) out.push(`lightning ${n(m.lightning_amount)}`);
    return out.length ? out.join(' · ') : 'every field at its neutral default';
  }

  let tween = null, stateVersion = 0;
  function transition(target) {
    tween?.kill();
    stateVersion++;
    if (reduced) { atmo.apply(target, true); syncFields(atmo.active); return; }
    // The production renderer applies a new state at once; the site eases
    // between states so the change can be followed. Sky/haze refresh in steps.
    const from = { ...atmo.active };
    const o = { t: 0 };
    let lastEnvStep = 0;
    tween = gsap.to(o, {
      t: 1, duration: 0.5, ease: 'power2.out',
      onUpdate: () => {
        const m = {};
        FIELDS.forEach(([k]) => { m[k] = from[k] + (target[k] - from[k]) * o.t; });
        m.mood = target.mood;
        // rebuilding the PMREM environment is costly: refresh it in a few steps only
        const step = Math.floor(o.t * 3);
        atmo.apply(m, step !== lastEnvStep, true);
        lastEnvStep = step;
        syncFields(atmo.active);
      },
      onComplete: () => { atmo.apply(target, true); syncFields(atmo.active); },
    });
  }

  function runCommand(i) {
    const c = COMMANDS[i];
    setCommand(i);
    appliedEl.innerHTML = '<p class="c06-applied__t">Recorded command applied to the browser reconstruction.</p>'
      + `<p class="c06-applied__m">${describe(c.m)}</p>`
      + `<p class="c06-applied__mood">Mood “${c.m.mood}”: a description only.</p>`;
    whyEl.hidden = !c.evidence;
    if (c.evidence) whyText.textContent = c.evidence;
    transition({ ...c.m });
  }

  root.querySelector('.js-env-reset').addEventListener('click', () => {
    quiet();
    setCommand(-1);
    whyEl.hidden = true;
    appliedEl.innerHTML = '<p class="c06-applied__t">Atmosphere reset to the neutral defaults.</p><p class="c06-applied__m">The schema’s starting state: daylight at 45°, light haze, no mist, rain or lightning.</p>';
    transition({ ...NEUTRAL.m });
  });

  // ── 2 · the proximity case, built when it comes near the viewport ──
  const relViewport = root.querySelector('.env__viewport--rel');
  const stateEl = root.querySelector('.js-rel-state');
  const distEl = root.querySelector('.js-rel-dist');
  let rel = null, connector = null, relSeen = -1;

  function updateRelation() {
    if (!rel || rel.objects.length < 2) return;
    const [a, b] = rel.objects;
    const d = distance(a, b);
    const near = d < NEAR_THRESHOLD;
    const band = proximity(d);
    const pct = (x) => `${Math.min(100, (x / 0.6) * 100).toFixed(1)}%`;
    distEl.innerHTML = `<span class="c06-dist"><span class="c06-dist__near" style="width:${pct(NEAR_THRESHOLD)}"></span><span class="c06-dist__dot${near ? ' is-near' : ''}" style="left:${pct(d)}"></span></span>`
      + `<span class="c06-dist__t">Distance <span class="c06-num">${d.toFixed(3)}</span> · ${band}${near ? '' : `. Near is below <span class="c06-num">${NEAR_THRESHOLD.toFixed(2)}</span>.`}</span>`;
    if (connector) {
      const [wx, wz] = toWorld((a.x + b.x) / 2, (a.y + b.y) / 2);
      connector.group.position.set(wx, 0, wz);
      if (near && !connector.group.visible) {
        connector.group.visible = true;
        connector.label.hidden = false;
        if (!reduced) { const m = connector.mesh, s = connector.scale; m.scale.setScalar(s * 0.6); gsap.to(m.scale, { x: s, y: s, z: s, duration: 0.25, ease: 'power3.out', overwrite: true }); }
      } else if (!near && connector.group.visible) {
        // the pair left "near": the relation mesh is removed, as in the production renderer
        connector.group.visible = false;
        connector.label.hidden = true;
        stateEl.textContent = 'They are no longer near, so the cairn is removed, as in the production renderer.';
        stateEl.classList.remove('is-on');
        return;
      }
    }
    if (near) {
      stateEl.textContent = 'The near relationship places a cairn between them.';
      stateEl.classList.add('is-on');
    } else if (!stateEl.textContent.startsWith('They are no longer')) {
      stateEl.textContent = 'Bring the tent near the mountain.';
      stateEl.classList.remove('is-on');
    }
  }

  function buildRelation() {
    rel = createWorld(relViewport, root.querySelector('.js-rel-canvas'), {
      reduced, list: RELATION, distance: 6.4, target: new THREE.Vector3(0, 0.35, 0), fit: 6.4, bounds: [0.16, 0.84], loading: root.querySelector('.js-rel-loading'),
      onLive: updateRelation,
      // the relation scene shows the atmosphere chosen above
      onShow: () => { if (relSeen !== stateVersion && !tween?.isActive()) { rel.atmo.apply(atmo.active, true); relSeen = stateVersion; } },
    });
    rel.atmo.apply(atmo.active, true);
    relSeen = stateVersion;
    // the cached cairn is loaded once and shown or hidden; it is never regenerated
    Promise.all([rel.ready, loadGLB(CONNECTOR.slug)]).then(([, m]) => {
      normalise(m, CONNECTOR.target);
      const group = new THREE.Group();
      group.add(m);
      group.visible = false;
      rel.scene.add(group);
      const label = rel.makeLabel('a stone cairn · relation');
      label.hidden = true;
      label.classList.add('is-rel');
      connector = { group, mesh: m, scale: m.scale.x, label, below: true, height: new THREE.Box3().setFromObject(m).max.y };
      rel.extras.push(connector);
      updateRelation();
    });
    if (import.meta.env.DEV) window.__env.rel = rel;
  }
  const relIO = new IntersectionObserver(([e]) => { if (e.isIntersecting && !rel) { relIO.disconnect(); buildRelation(); } }, { rootMargin: '60% 0px' });
  relIO.observe(relViewport);

  if (import.meta.env.DEV) window.__env = { main, atmo, runCommand, COMMANDS, NEAR_THRESHOLD, FAR_THRESHOLD }; // test hook, dev only
  await main.ready;
  // the opening state: the logged golden-hour command
  const first = COMMANDS.findIndex((c) => c.cmd === 'make it a golden hour');
  setCommand(first);
  runCommand(first);
}
