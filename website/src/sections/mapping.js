import { SESSION } from '../data.js';
import { pairwise, clusters, layout, distance, proximity, direction, NEAR_THRESHOLD, toWorld } from '../lib/grammar.js';

const NS = 'http://www.w3.org/2000/svg';
const S = 1000; // svg units per normalised unit
const pad2 = (n) => String(n).padStart(2, '0');

// what each physical prop is, in the project's own words (design diary: red box,
// white object, large and small wallet)
const PROP = { 1: 'red box', 2: 'round object', 3: 'wallet', 4: 'small wallet' };
const noun = (o) => o.generation.replace(/^an? /, '');
const PHRASE = { near: 'near', medium: 'a medium distance from', far: 'far from' };

export function initMapping({ reduced } = {}) {
  const svg = document.querySelector('.map__svg');
  const gGrid = svg.querySelector('.map__gridlines');
  const gRings = svg.querySelector('.map__rings');
  const gLines = svg.querySelector('.map__lines');
  const gProps = svg.querySelector('.map__props');
  const gLabels = svg.querySelector('.map__labels');
  const $ = (s) => document.querySelector(s);
  const jsonEl = $('.js-map-json');
  const statusEl = $('.js-map-status');
  const canvas = $('.js-scene3d-canvas');
  const T = {
    cta: $('.js-map-cta'), sentence: $('.js-map-sentence'), why: $('.js-map-why'),
    subject: $('.js-compare-subject'), opts: $('.js-compare-opts'),
    trigger: $('.c03-trigger'), relateMsg: $('.js-relate-msg'),
    specMeaning: $('.js-spec-meaning'), specProp: $('.js-spec-prop'),
  };
  const R = {
    id: $('.js-mr-id'), meaning: $('.js-mr-meaning'), prop: $('.js-mr-prop'),
    x: $('.js-mr-x'), y: $('.js-mr-y'), ref: $('.js-mr-ref'), refname: $('.js-mr-refname'),
    dist: $('.js-mr-dist'), prox: $('.js-mr-prox'), dir: $('.js-mr-dir'), dirnote: $('.js-mr-dirnote'),
    world: $('.js-mr-world'),
  };

  const objs = SESSION.map((o) => ({ ...o }));
  const home = () => objs.find((o) => o.slug === 'a-house') || objs[0];
  let prevJson = '';
  const listeners = new Set();

  // The selected object is compared with one explicit object. It is chosen when the
  // selection changes (the nearest one; the windmill for the house at the start),
  // can be changed with the "Compare with" buttons, and never switches during a
  // gesture. After a move, if the selected object has entered another object's near
  // zone while its comparison is not near, the comparison follows to that object.
  let active, ref, baseProx, moved;
  function select(o) {
    if (active === o) return;
    active = o;
    ref = nearestTo(o);
    baseProx = proximity(distance(active, ref));
    moved = false;
  }
  function compareWith(o) {
    ref = o;
    baseProx = proximity(distance(active, ref));
  }
  function afterMove(from) {
    moved = true;
    const near = nearestTo(active);
    if (near !== ref && proximity(distance(active, ref)) !== 'near' && proximity(distance(active, near)) === 'near') {
      ref = near;
      baseProx = proximity(distance(from, ref));
    }
  }

  // the production renderer's 10 × 10 table grid: one cell is 0.1 normalised
  for (let i = 1; i < 10; i++) {
    gGrid.insertAdjacentHTML('beforeend', `<line x1="${i * 100}" y1="0" x2="${i * 100}" y2="1000"/><line x1="0" y1="${i * 100}" x2="1000" y2="${i * 100}"/>`);
  }

  const defs = document.createElementNS(NS, 'defs');
  defs.innerHTML = `<clipPath id="propclip" clipPathUnits="objectBoundingBox"><circle cx=".5" cy=".5" r=".5"/></clipPath>`;
  svg.prepend(defs);

  // ── sizes in svg units, recomputed from the rendered width so objects stay
  //    recognisable and at least 44 × 44 px to touch on narrow screens ──
  let u = 1.5;      // svg units per CSS pixel
  let rad = 80;     // object radius in svg units
  const font = { id: 12, name: 13, sel: 14, rel: 13 };
  let narrow = false;

  const propEls = objs.map((o) => {
    const g = document.createElementNS(NS, 'g');
    g.setAttribute('class', 'prop');
    g.setAttribute('tabindex', '0');
    g.setAttribute('role', 'button');
    g.setAttribute('aria-label', `Object ${pad2(o.id)}: the ${PROP[o.id]}, which places ${o.generation} in the generated world. Arrow keys move it.`);
    g.innerHTML = `
      <circle class="p-hit"/>
      <circle class="p-ring"/>
      <image class="p-img" href="/media/img/prop-${o.id}.webp" preserveAspectRatio="xMidYMid slice" clip-path="url(#propclip)"/>
      <rect class="p-idbg" rx="2"/>
      <text class="p-id" text-anchor="middle">${pad2(o.id)}</text>`;
    gProps.appendChild(g);
    // its correspondence label: physical prop → meaning
    const chip = document.createElementNS(NS, 'rect');
    chip.setAttribute('class', 'p-chip');
    const name = document.createElementNS(NS, 'text');
    name.setAttribute('class', 'p-name');
    name.setAttribute('text-anchor', 'middle');
    gLabels.append(chip, name);
    g._name = name; g._chip = chip;

    g.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      try { g.setPointerCapture(e.pointerId); } catch { /* window listeners cover this */ }
      g.focus({ preventScroll: true });
      select(o);
      const from = { x: o.x, y: o.y };
      const p0 = svgPoint(e);
      const off = { x: o.x - p0.x / S, y: o.y - p0.y / S }; // keep the grab point under the pointer
      let didMove = false;
      g.classList.add('is-drag');
      raise(g);
      const move = (ev) => {
        const p = svgPoint(ev);
        o.x = clampPos(p.x / S + off.x); o.y = clampPos(p.y / S + off.y);
        didMove = didMove || Math.hypot(o.x - from.x, o.y - from.y) > 0.002;
        render();
      };
      const up = () => {
        g.classList.remove('is-drag');
        restoreOrder(g);
        removeEventListener('pointermove', move); removeEventListener('pointerup', up); removeEventListener('pointercancel', up);
        if (didMove) afterMove(from);
        render();
      };
      addEventListener('pointermove', move);
      addEventListener('pointerup', up);
      addEventListener('pointercancel', up);
      render();
    });
    g.addEventListener('focus', () => { if (active !== o) { select(o); render(); } });
    g.addEventListener('keydown', (e) => {
      const step = e.shiftKey ? 0.05 : 0.01;
      const k = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
      if (!k) return;
      e.preventDefault();
      select(o);
      const from = { x: o.x, y: o.y };
      o.x = clampPos(o.x + k[0]); o.y = clampPos(o.y + k[1]);
      afterMove(from);
      render();
    });
    return g;
  });

  // tap or click an empty spot on the table: the selected object moves there
  svg.addEventListener('click', (e) => {
    if (e.target.closest('.prop')) return;
    const p = svgPoint(e);
    const from = { x: active.x, y: active.y };
    active.x = clampPos(p.x / S); active.y = clampPos(p.y / S);
    afterMove(from);
    render();
  });

  // the selection ring and keyboard focus ring sit in the top layer so they stay
  // visible over a neighbour
  const selRing = document.createElementNS(NS, 'circle');
  selRing.setAttribute('class', 'sel-ring');
  const focusRing = document.createElementNS(NS, 'circle');
  focusRing.setAttribute('class', 'focus-ring');
  gLabels.prepend(selRing, focusRing);
  function placeFocusRing() {
    const i = propEls.findIndex((g) => g === document.activeElement && g.matches(':focus-visible'));
    focusRing.classList.toggle('is-on', i >= 0);
    if (i < 0) return;
    focusRing.setAttribute('cx', objs[i].x * S); focusRing.setAttribute('cy', objs[i].y * S);
    focusRing.setAttribute('r', rad + 5 * u);
  }
  propEls.forEach((g) => { g.addEventListener('focus', placeFocusRing); g.addEventListener('blur', placeFocusRing); });

  // while dragging, draw the prop above the others by moving the others behind it
  // (re-inserting the prop itself would take keyboard focus away from it), then put
  // the original order back so Tab still visits 01 to 04
  function raise(g) {
    while (g.nextSibling) gProps.insertBefore(g.nextSibling, g);
  }
  function restoreOrder(g) {
    const at = propEls.indexOf(g);
    propEls.forEach((p, i) => { if (i < at) gProps.insertBefore(p, g); else if (i > at) gProps.appendChild(p); });
  }

  const minPos = () => Math.max(0.03, (rad + 2 * u) / S);
  const clampPos = (v) => Math.min(1 - minPos(), Math.max(minPos(), v));

  function sizeProps() {
    const w = svg.getBoundingClientRect().width || 620;
    u = S / w;
    rad = Math.max(80, 22 * u);
    const small = w < 480;
    narrow = small;
    font.id = 12 * u; font.name = (small ? 12 : 13) * u; font.sel = (small ? 13 : 14) * u; font.rel = (small ? 12 : 13) * u;
    const inset = Math.max(5, 3 * u);
    propEls.forEach((g) => {
      g.querySelector('.p-hit').setAttribute('r', rad + 4 * u);
      g.querySelector('.p-ring').setAttribute('r', rad);
      const img = g.querySelector('.p-img');
      img.setAttribute('x', -rad + inset); img.setAttribute('y', -rad + inset);
      img.setAttribute('width', (rad - inset) * 2); img.setAttribute('height', (rad - inset) * 2);
      const bw = font.id * 2.1, bh = font.id * 1.5;
      const bg = g.querySelector('.p-idbg');
      bg.setAttribute('x', -rad * 0.92); bg.setAttribute('y', -rad * 0.92 - bh * 0.4); bg.setAttribute('width', bw); bg.setAttribute('height', bh);
      const t = g.querySelector('.p-id');
      t.setAttribute('x', -rad * 0.92 + bw / 2); t.setAttribute('y', -rad * 0.92 - bh * 0.4 + bh * 0.72);
      t.style.fontSize = `${font.id}px`;
    });
    objs.forEach((o) => { o.x = clampPos(o.x); o.y = clampPos(o.y); });
  }

  function svgPoint(ev) {
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX; pt.y = ev.clientY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  }

  function nearestTo(a) {
    let best = null, bd = Infinity;
    objs.forEach((o) => { if (o !== a) { const d = distance(a, o); if (d < bd) { bd = d; best = o; } } });
    return best;
  }

  // place a label box of half-size (hw, hh) clear of every object and of boxes
  // already placed; candidates are tried in order and the first clear one wins
  function clearSpot(cands, hw, hh, placed) {
    const fit = ([x, y]) => [Math.min(S - hw - 4 * u, Math.max(hw + 4 * u, x)), Math.min(S - hh - 4 * u, Math.max(hh + 4 * u, y))];
    const cost = ([x, y]) =>
      objs.reduce((n, o) => n + (Math.abs(o.x * S - x) < rad + hw && Math.abs(o.y * S - y) < rad + hh ? 1 : 0), 0)
      + placed.reduce((n, b) => n + (Math.abs(b.x - x) < b.hw + hw + 4 * u && Math.abs(b.y - y) < b.hh + hh + 2 * u ? 1 : 0), 0);
    let best = null, bestScore = Infinity;
    cands.map(fit).forEach((c, i) => {
      const score = cost(c) * 1e6 + i;
      if (score < bestScore) { bestScore = score; best = c; }
    });
    return best;
  }

  let statusTimer = 0;
  function render() {
    const byId = Object.fromEntries(objs.map((o) => [o.id, o]));
    const d = distance(active, ref);
    const prox = proximity(d);
    const dir = direction(ref, active); // where the selected object lies relative to its comparison

    // objects
    objs.forEach((o, i) => {
      const g = propEls[i];
      g.setAttribute('transform', `translate(${o.x * S} ${o.y * S})`);
      const on = o === active;
      g.classList.toggle('is-active', on);
      g.classList.toggle('is-ref', o === ref);
      g.setAttribute('aria-pressed', String(on));
    });
    selRing.setAttribute('cx', active.x * S); selRing.setAttribute('cy', active.y * S); selRing.setAttribute('r', rad);
    placeFocusRing();

    // correspondence labels, the selected one first so it gets the clearest spot
    const placed = [];
    [active, ...objs.filter((o) => o !== active)].forEach((o) => {
      const g = propEls[objs.indexOf(o)];
      const on = o === active;
      const t = g._name, chip = g._chip;
      const fs = on ? font.sel : font.name;
      // on narrow tables the other tags break into two lines: prop, then → meaning
      const lines = on || !narrow ? [`${PROP[o.id]} → ${noun(o)}`] : [PROP[o.id], `→ ${noun(o)}`];
      const lh = fs * 1.2;
      t.innerHTML = lines.map((l) => `<tspan>${l.toUpperCase()}</tspan>`).join('');
      t.style.fontSize = `${fs}px`;
      t.classList.toggle('is-active', on);
      chip.classList.toggle('is-active', on);
      const tw = Math.max(...[...t.children].map((ts) => ts.getComputedTextLength()));
      const hw = tw / 2 + (on ? 8 : 3) * u, hh = (lines.length - 1) * lh / 2 + fs * (on ? 0.95 : 0.7);
      const gap = rad + hh + 4 * u;
      const ox = o.x * S, oy = o.y * S;
      const [x, y] = clearSpot([[ox, oy + gap], [ox, oy - gap - font.id * 0.6], [ox + rad + hw + 4 * u, oy], [ox - rad - hw - 4 * u, oy]], hw, hh, placed);
      placed.push({ x, y, hw, hh });
      const y0 = y - (lines.length - 1) * lh / 2 + fs * 0.36;
      [...t.children].forEach((ts, i) => { ts.setAttribute('x', x); ts.setAttribute('y', y0 + i * lh); });
      chip.setAttribute('x', x - hw); chip.setAttribute('y', y - hh); chip.setAttribute('width', hw * 2); chip.setAttribute('height', hh * 2);
      chip.setAttribute('rx', 2 * u);
    });

    // proximity guide: the comparison object's near zone
    const nr = NEAR_THRESHOLD * S;
    gRings.innerHTML = `<circle class="r-near${prox === 'near' ? ' is-in' : ''}" cx="${ref.x * S}" cy="${ref.y * S}" r="${nr}"/>`;

    // the active relation: selected → comparison, with its proximity word
    const word = prox;
    const hw = word.length * font.rel * 0.34 + 6 * u, hh = font.rel * 0.85;
    const mx = (active.x + ref.x) / 2 * S, my = (active.y + ref.y) / 2 * S;
    const len = Math.hypot(ref.x - active.x, ref.y - active.y) * S || 1;
    const nx = -(ref.y - active.y) * S / len, ny = (ref.x - active.x) * S / len;
    const k = rad * 0.6 + hh;
    const spot = clearSpot([[mx, my], [mx + nx * k, my + ny * k], [mx - nx * k, my - ny * k], [mx + nx * 2 * k, my + ny * 2 * k], [mx - nx * 2 * k, my - ny * 2 * k]], hw, hh, placed);
    gLines.innerHTML = `<line class="l-active l-${prox}" x1="${active.x * S}" y1="${active.y * S}" x2="${ref.x * S}" y2="${ref.y * S}" vector-effect="non-scaling-stroke"/>`
      + `<rect class="t-bg" x="${spot[0] - hw}" y="${spot[1] - hh}" width="${hw * 2}" height="${hh * 2}" rx="${2 * u}"/>`
      + `<text class="t-active" x="${spot[0]}" y="${spot[1] + font.rel * 0.36}" style="font-size:${font.rel}px">${word}</text>`;

    // the consequence, in words
    const A = noun(active), B = noun(ref);
    T.cta.textContent = `Move the ${PROP[active.id]}. Watch the ${A}.`;
    T.sentence.innerHTML = `The ${A} is <span class="c03-hl">${prox !== baseProx ? 'now ' : ''}${PHRASE[prox]}</span> the ${B}.`;
    T.why.textContent = moved
      ? `The same generated ${A} has moved. Its meaning and cached 3D model have not changed.`
      : `Drag the ${PROP[active.id]} ${prox === 'near' ? 'away from' : 'towards'} the ${PROP[ref.id]}. The ${A} will move ${prox === 'near' ? 'away from' : 'towards'} the ${B}.`;
    T.subject.textContent = `the ${A}`;
    const others = objs.filter((o) => o !== active);
    if (T.opts.dataset.for !== String(active.id)) {
      T.opts.dataset.for = String(active.id);
      T.opts.innerHTML = others.map((o) => `<button type="button" class="c03-opt" data-id="${o.id}">${noun(o)}</button>`).join('');
    }
    T.opts.querySelectorAll('.c03-opt').forEach((b) => b.setAttribute('aria-pressed', String(+b.dataset.id === ref.id)));

    // technical details
    const [wx, wz] = toWorld(active.x, active.y);
    R.id.textContent = pad2(active.id);
    R.prop.textContent = PROP[active.id];
    R.meaning.textContent = active.generation;
    R.x.textContent = active.x.toFixed(3);
    R.y.textContent = active.y.toFixed(3);
    R.ref.textContent = pad2(ref.id);
    R.refname.textContent = `${PROP[ref.id]} → ${ref.generation}`;
    R.dist.textContent = d.toFixed(3);
    R.prox.textContent = prox;
    R.dir.textContent = dir;
    R.dirnote.textContent = `(object ${pad2(active.id)} relative to object ${pad2(ref.id)})`;
    R.world.textContent = `(${wx.toFixed(2)}, ${wz.toFixed(2)})`;

    // computed scene description (compute_scene.py output shape)
    const rel = pairwise(objs);
    const cl = clusters(objs);
    const lay = layout(objs);
    const lines = [];
    lines.push('<span class="k">"objects"</span>: [');
    objs.forEach((o, i) => {
      const [ox, oz] = toWorld(o.x, o.y);
      lines.push(`  { <span class="k">"id"</span>: ${o.id}, <span class="k">"x"</span>: <span class="n">${o.x.toFixed(3)}</span>, <span class="k">"y"</span>: <span class="n">${o.y.toFixed(3)}</span> }${i < objs.length - 1 ? ',' : ''}  <span class="k">→ world (${ox.toFixed(2)}, ${oz.toFixed(2)})</span>`);
    });
    lines.push('],');
    lines.push('<span class="k">"relationships"</span>: [');
    rel.forEach((r, i) => {
      const cls = r.proximity === 'near' ? 'near' : 'n';
      lines.push(`  { ${r.from_id}→${r.to_id}, <span class="k">"distance"</span>: <span class="n">${r.distance.toFixed(4)}</span>, <span class="k">"proximity"</span>: <span class="${cls}">"${r.proximity}"</span>, <span class="k">"direction"</span>: "${r.direction}" }${i < rel.length - 1 ? ',' : ''}`);
    });
    lines.push('],');
    lines.push(`<span class="k">"clusters"</span>: ${JSON.stringify(cl)},  <span class="k">// by id; the production file lists labels</span>`);
    lines.push(`<span class="k">"layout"</span>: { <span class="k">"centre_x"</span>: ${lay.centre_x}, <span class="k">"centre_y"</span>: ${lay.centre_y}, <span class="k">"spread"</span>: ${lay.spread}, <span class="k">"count"</span>: ${lay.count} }`);
    const json = lines.join('\n');
    if (json !== prevJson) { jsonEl.innerHTML = json; prevJson = json; }

    // relation trigger: what production would do when a pair is near
    const near = rel.filter((r) => r.proximity === 'near');
    T.trigger.classList.toggle('is-live', near.length > 0);
    if (!near.length) {
      T.relateMsg.innerHTML = 'No pair is near. Bring two objects within 0.15 of each other.';
    } else {
      const r = near[0];
      const a = byId[r.from_id], b = byId[r.to_id];
      T.relateMsg.innerHTML = `<b>${noun(a)}</b> and <b>${noun(b)}</b> are near (${r.distance.toFixed(3)}). Both meanings are ready, so the production browser would send <code>POST /api/relate</code>: Qwen3-8B proposes one bounded connector object, which is generated or reused from cache and rendered at the midpoint at target size 0.65. No connector was recorded for this pair, so none is shown here.`;
    }

    T.specMeaning.textContent = active.generation;
    T.specProp.textContent = PROP[active.id];

    canvas.setAttribute('aria-label', `Generated world: ${objs.map((o) => `the ${noun(o)}${o === active ? ' (selected)' : ''}`).join(', ')}, each placed where its physical object is on the table.`);

    // a short, debounced announcement for screen readers
    clearTimeout(statusTimer);
    statusTimer = setTimeout(() => { statusEl.textContent = `${T.sentence.textContent} ${T.why.textContent}`; }, 600);

    listeners.forEach((fn) => fn({ objs, active, ref, prox }));
  }

  T.opts.addEventListener('click', (e) => {
    const b = e.target.closest('.c03-opt');
    if (!b) return;
    compareWith(objs.find((o) => o.id === +b.dataset.id));
    render();
  });

  // Reset to the recorded starting positions
  $('.js-map-reset').addEventListener('click', () => {
    objs.forEach((o, i) => { o.x = SESSION[i].x; o.y = SESSION[i].y; });
    active = null;
    select(home());
    sizeProps();
    render();
  });

  // touch devices get the tap-to-place instruction
  if (matchMedia('(pointer: coarse)').matches) { $('.c03-try__how').classList.add('is-touch'); $('.c03-specimen__how').classList.add('is-touch'); }

  // the cached-model specimen beside the calculations: loaded the first time they
  // are opened, drawn only while they stay open and on screen
  const calc = $('.c03-calc');
  const shownFns = new Set();
  let specimen = null;
  calc.addEventListener('toggle', () => {
    shownFns.forEach((fn) => fn());
    if (!calc.open || specimen) return;
    specimen = import('./specimen.js')
      .then((m) => m.init($('.c03-specimen'), {
        reduced,
        getState: () => ({ active }),
        subscribe: (fn) => listeners.add(fn),
        isShown: () => calc.open,
        onShownChange: (fn) => shownFns.add(fn),
      }))
      .catch((err) => { console.error(err); $('.c03-specimen__status').textContent = 'The cached model could not be loaded.'; });
  });

  select(home());
  new ResizeObserver(() => { sizeProps(); render(); }).observe(svg);
  sizeProps();
  render();

  // the generated scene is loaded only when the chapter approaches
  const sceneHost = $('.scene3d');
  const io = new IntersectionObserver(([e]) => {
    if (!e.isIntersecting) return;
    io.disconnect();
    import('./mapping3d.js')
      .then((m) => m.init(sceneHost, {
        reduced,
        getState: () => ({ objs, active, ref, prox: proximity(distance(active, ref)) }),
        subscribe: (fn) => listeners.add(fn),
        // selecting a model in the generated world selects its physical object
        select: (id) => { select(objs.find((o) => o.id === id)); render(); },
        label: (o) => noun(o),
      }))
      .catch((err) => { console.error(err); $('.js-scene3d-status').textContent = 'The generated scene could not be loaded.'; });
  }, { rootMargin: '100% 0px' });
  io.observe(sceneHost);
}
