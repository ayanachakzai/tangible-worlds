import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { SESSION, UTTERANCES, SCALE } from '../data.js';
import { initFlow } from './flow.js';

// what each physical prop is, in the project's own words (as in chapter 03)
const PROP = { 1: 'red box', 2: 'round object', 3: 'wallet', 4: 'small wallet' };
// Parakeet transcription time for each accepted command (stt_s, session AYANTEST07)
const STT = { 1: 0.18, 2: 0.062, 3: 0.133, 4: 0.059 };
const esc = (t) => t.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export function initLanguage({ reduced }) {
  const $ = (s) => document.querySelector(s);
  const tx = $('.js-tx');
  if (!tx) return;
  const E = {
    prop: $('.js-tx-prop'), objName: $('.js-tx-objname'), objId: $('.js-tx-objid'),
    frame: $('.js-tx-frame'), reveal: $('.js-tx-reveal'), pending: $('.js-tx-pending'), result: $('.js-tx-result'), tag: $('.js-tx-tag'), resultCap: $('.js-tx-resultcap'),
    heard: $('.tx-heard'), utter: $('.js-tx-utter'),
    readback: $('.js-tx-readback'), q: $('.js-tx-q'), yes: $('.js-tx-yes'), got: $('.tx-got'),
    replay: $('.js-tx-replay'), skip: $('.js-tx-skip'),
    model: $('.js-tx-model'), modelToggle: $('.js-tx-model-toggle'), modelLabel: $('.js-tx-model-label'), rcap: $('.tx-result__cap'),
    stage: $('.js-tx-stage-t'), progress: $('.js-tx-progress'), replayLabel: $('.js-tx-replay-label'),
  };
  const cmds = [...document.querySelectorAll('.tx-cmds__list [role="radio"]')];

  let id = 3;
  let done = true;
  let tl = null;
  let words = [];
  let mark = null;
  let flow = null;
  let playId = 0; // the newest play; an older one still waiting for its image gives up
  const listeners = new Set();
  const shownFns = new Set();
  const current = () => SESSION.find((s) => s.id === id);

  // the recorded images are small; fetch the other three so switching is instant
  SESSION.forEach((o) => { new Image().src = `/media/img/prop-${o.id}-hd.webp`; new Image().src = `/media/img/src-${o.slug}.webp`; });

  function setDone(v) {
    done = v;
    tx.dataset.done = String(v);
    // Skip is offered only while a replay is running, and is out of the tab order otherwise
    tx.classList.toggle('is-playing', !v);
    E.skip.setAttribute('aria-hidden', String(v));
    E.skip.tabIndex = v ? -1 : 0;
    // while playing the main action restarts, and says so
    E.replayLabel.textContent = v ? 'Replay assignment' : 'Restart replay';
    if (v) { setStage('Generated result available'); gsap.set(E.progress, { scaleX: 0 }); }
    shownFns.forEach((fn) => fn());
  }
  // one line of feedback, always in the same place, naming the recorded stage on screen
  const setStage = (t) => { if (E.stage.textContent !== t) E.stage.textContent = t; tx.dataset.stage = t; };

  // fill the composition with one recorded assignment
  function show(n) {
    id = n;
    const o = current();
    const u = UTTERANCES[id];
    cmds.forEach((b) => { const on = +b.dataset.cmd === id; b.setAttribute('aria-checked', String(on)); b.tabIndex = on ? 0 : -1; });

    E.prop.src = `/media/img/prop-${id}-hd.webp`;
    E.prop.alt = `The ${PROP[id]} on the tabletop, as the tracker camera saw it.`;
    E.objName.textContent = `The ${PROP[id]}`;
    E.objId.textContent = String(id);

    // the sentence, word by word, with the meaning held in one mark
    const all = u.said.split(' ');
    const m0 = all.indexOf('is') + 1;
    const m1 = m0 + u.meaning.split(' ').length;
    const w = (t) => `<span class="tx-w">${esc(t)}</span>`;
    E.utter.innerHTML = `${all.slice(0, m0).map(w).join(' ')} <mark class="tx-mean">${all.slice(m0, m1).map(w).join(' ')}</mark>${m1 < all.length ? ` ${all.slice(m1).map(w).join(' ')}` : ''}`;
    E.utter.setAttribute('aria-label', u.said);
    words = [...E.utter.querySelectorAll('.tx-w')];
    mark = E.utter.querySelector('.tx-mean');

    E.q.textContent = `Did you say: ${u.said}?`;
    E.result.src = `/media/img/src-${o.slug}.webp`;
    E.pending.src = E.result.src;
    E.result.alt = `The image generated for the meaning ${o.generation}.`;
    E.tag.textContent = o.generation;
    E.resultCap.textContent = `Generated for the meaning, not for the ${PROP[id]}.`;

    flow?.refresh();
    listeners.forEach((fn) => fn({ active: o }));
  }

  // where on the result the meaning lands: the tag's centre, inside the frame
  const landing = () => {
    const f = E.frame.getBoundingClientRect(), t = E.tag.getBoundingClientRect();
    return `${t.left - f.left + t.width / 2}px ${t.top - f.top + t.height / 2}px`;
  };

  function finalState() {
    gsap.set([E.heard, E.readback, E.yes, E.got, E.tag, E.rcap], { opacity: 1, y: 0 });
    gsap.set(words, { opacity: 1, y: 0 });
    gsap.set(mark, { '--fill': 1, color: '#F3EBD9' });
    gsap.set(E.reveal, { clipPath: 'circle(150% at 0% 100%)' });
    tx.querySelectorAll('.tx-fly').forEach((n) => n.remove());
    setDone(true);
  }
  function startState() {
    gsap.set([E.heard, E.readback, E.yes, E.got], { opacity: 0, y: 6 });
    gsap.set([E.tag, E.rcap], { opacity: 0 });
    gsap.set(words, { opacity: 0, y: '0.25em' });
    gsap.set(mark, { '--fill': 0, color: '#171717' });
    gsap.set(E.reveal, { clipPath: `circle(0% at ${landing()})` });
    setDone(false);
  }

  // instruction → meaning emphasised → read-back and yes → accepted → result, in about
  // 2.8 s. This is storytelling time, not the recorded timing: in the session the
  // system waited for the participant's answer. The timeline is built up front, so
  // Replay, Show result and a new selection can always cut it off.
  async function play() {
    const ticket = ++playId;
    tl?.kill();
    tl = null;
    tx.querySelectorAll('.tx-fly').forEach((n) => n.remove());
    if (reduced) { finalState(); return; }
    startState();
    // the result image is preloaded; wait at most a moment for it to decode
    await Promise.race([E.result.decode?.().catch(() => {}), new Promise((r) => setTimeout(r, 300))]);
    if (ticket !== playId) return;

    // a copy of the meaning travels from the sentence to the result; the sentence keeps it
    const base = tx.getBoundingClientRect();
    const a = mark.getBoundingClientRect(), b = E.tag.getBoundingClientRect();
    const ghost = mark.cloneNode(true);
    ghost.classList.add('tx-fly');
    ghost.setAttribute('aria-hidden', 'true');
    ghost.querySelectorAll('.tx-w').forEach((n) => { n.style.opacity = 1; n.style.transform = 'none'; });
    Object.assign(ghost.style, { left: `${a.left - base.left}px`, top: `${a.top - base.top}px`, width: `${a.width}px`, height: `${a.height}px`, opacity: 0, color: '#F3EBD9' });
    ghost.style.setProperty('--fill', '1');
    tx.appendChild(ghost);
    const at = landing();

    const ease = 'power2.out';
    tl = gsap.timeline({ onComplete: () => { ghost.remove(); setDone(true); } });
    // presentation timing, the same for all four recordings:
    // 0–400 ms instruction · 400–850 meaning · 850–1650 read-back and yes ·
    // 1650–2000 accepted · 2000–2700 result
    tl.fromTo(E.progress, { scaleX: 0 }, { scaleX: 1, duration: 2.75, ease: 'none' }, 0)
      .call(setStage, ['Instruction recognised'], 0)
      .call(setStage, ['Awaiting recorded confirmation'], 0.85)
      .call(setStage, ['Meaning accepted'], 1.65)
      .call(setStage, ['Generated result available'], 2.6);
    tl.to(E.heard, { opacity: 1, y: 0, duration: 0.2, ease }, 0)
      .to(words, { opacity: 1, y: 0, duration: 0.22, stagger: 0.02, ease }, 0.05)
      .to(mark, { '--fill': 1, color: '#F3EBD9', duration: 0.45, ease: 'power2.inOut' }, 0.4)
      .to(E.readback, { opacity: 1, y: 0, duration: 0.3, ease }, 0.85)
      .to(E.yes, { opacity: 1, y: 0, duration: 0.3, ease }, 1.3)
      .to(E.got, { opacity: 1, y: 0, duration: 0.3, ease }, 1.65)
      .set(ghost, { opacity: 1 }, 1.65)
      .to(ghost, { y: -10, duration: 0.3, ease }, 1.65)
      .to(ghost, { x: b.left - a.left, y: b.top - a.top, scale: b.height / a.height, duration: 0.6, ease: 'power3.inOut' }, 2.0)
      .to(E.reveal, { clipPath: `circle(150% at ${at})`, duration: 0.65, ease: 'power2.inOut' }, 2.05)
      .set(E.tag, { opacity: 1, y: 0 }, 2.57)
      .set(ghost, { opacity: 0 }, 2.6)
      .to(E.rcap, { opacity: 1, y: 0, duration: 0.2, ease }, 2.6);
  }

  const finish = () => { playId++; tl?.kill(); tl = null; finalState(); };

  E.replay.addEventListener('click', play);
  E.skip.addEventListener('click', () => { const f = document.activeElement === E.skip; finish(); if (f) E.replay.focus(); });
  cmds.forEach((b, i) => {
    b.addEventListener('click', () => { show(+b.dataset.cmd); play(); });
    b.addEventListener('keydown', (e) => {
      const d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
      if (!d) return;
      e.preventDefault();
      const n = cmds[(i + d + cmds.length) % cmds.length];
      n.focus();
      n.click();
    });
  });

  // inspect the result: the cached 3D model turning in place of the image
  let modelOn = false, specimen = null;
  E.modelToggle.addEventListener('click', () => {
    modelOn = !modelOn;
    E.modelToggle.setAttribute('aria-pressed', String(modelOn));
    E.modelLabel.textContent = modelOn ? 'Show generated image' : 'Inspect 3D model';
    E.model.hidden = !modelOn;
    tx.classList.toggle('is-model', modelOn);
    if (modelOn && !done) finish();
    shownFns.forEach((fn) => fn());
    if (!modelOn || specimen) return;
    specimen = import('./specimen.js')
      .then((m) => m.init(E.model, {
        reduced,
        getState: () => ({ active: current() }),
        subscribe: (fn) => listeners.add(fn),
        isShown: () => modelOn && done,
        onShownChange: (fn) => shownFns.add(fn),
      }))
      .catch((err) => { console.error(err); E.model.querySelector('.tx-model__status').textContent = 'The cached model could not be loaded.'; });
  });

  show(3);
  flow = initFlow($('.js-flow'), {
    reduced,
    getAssignment: () => {
      const o = current(), u = UTTERANCES[id];
      const sw = u.scale ? u.scale.split(' ')[1] : null;
      return { id, prop: PROP[id], said: u.said, meaningWords: u.meaning, scale: sw, stt: STT[id], meaning: o.generation, meaningFull: o.meaning, slug: o.slug, target: (sw ? SCALE[sw][1] : 1).toFixed(2) };
    },
  });
  // the chapter opens complete; the animation is something to replay, not a prerequisite
  finalState();

  // scale: the same cached house at each relative display target
  const scaleBtns = [...document.querySelectorAll('.c04-scale__row [role="radio"]')];
  const stageEl = $('.c04-scale__stage');
  const scM = $('.js-sc-m'), scT = $('.js-sc-t');
  const scCanvas = $('.js-sc-canvas');
  let scale3d = null, target = 1.8;
  const pick = (b) => {
    scaleBtns.forEach((x) => { const on = x === b; x.setAttribute('aria-checked', String(on)); x.tabIndex = on ? 0 : -1; });
    target = +b.dataset.t;
    scM.textContent = b.dataset.m || 'no marker';
    scT.textContent = `${target.toFixed(2)}×`;
    scCanvas.setAttribute('aria-label', `The cached house model drawn at display target ${target.toFixed(2)}, beside a dashed outline of its unmarked size.`);
    scale3d?.setTarget(target);
  };
  scaleBtns.forEach((b, i) => {
    b.addEventListener('click', () => pick(b));
    b.addEventListener('keydown', (e) => {
      const d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
      if (!d) return;
      e.preventDefault();
      const n = scaleBtns[(i + d + scaleBtns.length) % scaleBtns.length];
      n.focus();
      pick(n);
    });
  });
  pick(scaleBtns.find((b) => b.getAttribute('aria-checked') === 'true'));
  // the model loads only as the scale section approaches
  const scIo = new IntersectionObserver(([e]) => {
    if (!e.isIntersecting) return;
    scIo.disconnect();
    import('./scale3d.js')
      .then((m) => m.init(stageEl, { reduced, slug: 'a-house', initial: target }))
      .then((api) => { scale3d = api; })
      .catch((err) => { console.error(err); $('.js-sc-status').textContent = 'The cached model could not be loaded.'; });
  }, { rootMargin: '50% 0px' });
  scIo.observe(stageEl);

  // retries: the five transcripts arrive in their recorded order
  const tries = [...document.querySelectorAll('.js-retries li')];
  if (!reduced) {
    gsap.from(tries, { opacity: 0, x: -8, duration: 0.35, stagger: 0.25, ease: 'power2.out', scrollTrigger: { trigger: '.js-retries', start: 'top 80%', once: true } });
  }
}
