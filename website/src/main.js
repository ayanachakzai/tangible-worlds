import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { initMapping } from './sections/mapping.js';
import { initLanguage } from './sections/language.js';

gsap.registerPlugin(ScrollTrigger);
if (import.meta.env.DEV) Object.assign(window, { gsap, ScrollTrigger }); // test hooks, dev only

export const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

/* ───────────── Rail and mobile index ───────────── */
function initRail() {
  const links = $$('.rail__list a');
  const chapters = $$('main [data-chapter]').filter((el) => el.id);
  const num = $('.index-toggle__num');
  const setActive = (id) => {
    links.forEach((a) => a.classList.toggle('is-active', a.dataset.chapter === id));
    const i = links.findIndex((a) => a.dataset.chapter === id);
    if (num && i >= 0) num.textContent = String(i).padStart(2, '0');
  };
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting) setActive(e.target.id); });
  }, { rootMargin: '-45% 0px -50% 0px' });
  chapters.forEach((c) => io.observe(c));
  setActive('top');

  const bar = $('.rail__progress span');
  const onScroll = () => {
    const max = document.documentElement.scrollHeight - innerHeight;
    bar.style.transform = `scaleY(${max > 0 ? scrollY / max : 0})`;
  };
  addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // mobile sheet reuses the rail's list
  const toggle = $('.index-toggle');
  const sheet = $('#index-sheet');
  const list = document.createElement('ol');
  links.forEach((a) => {
    const li = document.createElement('li');
    li.innerHTML = `<a href="${a.getAttribute('href')}"><b>${a.querySelector('b').textContent}</b><span>${a.querySelector('i').textContent}</span></a>`;
    list.appendChild(li);
  });
  sheet.appendChild(list);
  const close = () => { sheet.hidden = true; toggle.setAttribute('aria-expanded', 'false'); toggle.querySelector('.index-toggle__label').textContent = 'Index'; };
  toggle.addEventListener('click', () => {
    const open = sheet.hidden;
    sheet.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    toggle.querySelector('.index-toggle__label').textContent = open ? 'Close' : 'Index';
    if (open) sheet.querySelector('a')?.focus();
  });
  sheet.addEventListener('click', (e) => { if (e.target.closest('a')) close(); });
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && !sheet.hidden) { close(); toggle.focus(); } });
}

/* ───────────── Hero ───────────── */
function initHero() {
  const hero = $('.hero');
  const video = $('.hero__video');
  const btn = $('.js-hero-play');
  const tall = matchMedia('(max-aspect-ratio: 1/1)');

  let userPaused = reduced; // the visitor's intent; off-screen pausing does not change it
  const setPlaying = (on) => {
    btn.setAttribute('aria-pressed', String(on));
    btn.querySelector('span').textContent = on ? 'Pause film' : 'Play film';
  };
  const tryPlay = () => video.play().catch((err) => {
    if (err && err.name === 'NotAllowedError') { userPaused = true; setPlaying(false); }
  });
  video.addEventListener('play', () => setPlaying(true));
  video.addEventListener('pause', () => { if (userPaused) setPlaying(false); });

  const pick = () => {
    const isTall = tall.matches;
    const src = isTall ? video.dataset.srcTall : video.dataset.srcWide;
    if (video.getAttribute('src') !== src) {
      video.poster = isTall ? video.dataset.posterTall : video.dataset.posterWide;
      video.src = src;
      if (!userPaused) tryPlay();
    }
    placeTags();
  };

  // The split between tracker view and renderer sits at 706 / 1600 of the
  // desktop cut. Compute where it lands after object-fit: cover.
  const placeTags = () => {
    if (tall.matches) { hero.style.removeProperty('--tag-r'); return; }
    const W = hero.clientWidth, H = hero.clientHeight;
    const s = Math.max(W / 1600, H / 900);
    const offX = (W - 1600 * s) / 2;
    const splitX = offX + 706 * s;
    hero.style.setProperty('--tag-l', `${Math.max(16, offX + 16)}px`);
    hero.style.setProperty('--tag-r', `${splitX + 16}px`);
  };

  btn.addEventListener('click', () => {
    if (video.paused) { userPaused = false; tryPlay(); } else { userPaused = true; video.pause(); }
  });

  setPlaying(!reduced);
  pick();
  tall.addEventListener('change', pick);
  addEventListener('resize', placeTags);

  // pause when off screen, resume only if the visitor has not paused it
  new IntersectionObserver(([e]) => {
    if (!e.isIntersecting) video.pause();
    else if (!userPaused) tryPlay();
  }, { threshold: 0.05 }).observe(hero);

  if (reduced) return;
  // Scroll transition: the film is framed, the title steps back and the premise is stated.
  const tl = gsap.timeline({
    scrollTrigger: { trigger: hero, start: 'top top', end: '+=110%', scrub: 0.6, pin: true, anticipatePin: 1 },
  });
  tl.to('.hero__copy, .hero__controls, .hero__caption, .hero__tags', { opacity: 0, y: -40, duration: 0.3, ease: 'none' }, 0)
    .to('.hero__frame', { clipPath: 'inset(9% 7% 9% 7% round 4px)', duration: 0.55, ease: 'power1.inOut' }, 0.05)
    .to('.hero__video', { opacity: 0.32, duration: 0.5, ease: 'none' }, 0.15)
    .to('.hero__thesis span', { opacity: 1, duration: 0.18, stagger: 0.08, ease: 'none' }, 0.3)
    .to({}, { duration: 0.25 });
}

/* ───────────── 01 Sensing ───────────── */
async function initSensing() {
  const steps = $$('.sense .step');
  const ro = $$('.sense__readout .ro');
  const L = {
    overhead: $('.sv--overhead'), depth: $('.sv--depth'), grid: $('.sv--grid'),
    rgb: $('.pix--rgb'), plane: $('.sv--grid .plane'), scan: $('.sv--grid .plane span'), mask: $('.pix--mask'), boxes: $('.boxes'),
  };
  const frameEl = $('.js-cal-frame'), noiseEl = $('.js-cal-noise');

  // draw boxes from the tracker mask's connected components
  try {
    const comps = await fetch('/media/tracker-components.json').then((r) => r.json());
    const ns = 'http://www.w3.org/2000/svg';
    comps.a.components.slice(0, 3).forEach((c, i) => {
      const g = document.createElementNS(ns, 'g');
      g.innerHTML = `<rect x="${c.x0 - 1}" y="${c.y0 - 1}" width="${c.x1 - c.x0 + 2}" height="${c.y1 - c.y0 + 2}"/>`
        + `<rect class="tagbg" x="${c.x0 - 1}" y="${c.y0 - 13}" width="14" height="12"/>`
        + `<text x="${c.x0 + 2}" y="${c.y0 - 4}">${i + 1}</text>`;
      g.style.opacity = 0;
      L.boxes.appendChild(g);
    });
  } catch { /* boxes are decorative */ }

  const setStep = (i) => {
    steps.forEach((s, k) => s.classList.toggle('is-on', k === i));
    ro.forEach((r, k) => r.classList.toggle('is-on', k === i));
  };
  setStep(0);

  if (reduced) {
    // static: show the final segmented state
    gsap.set(L.overhead, { opacity: 0 }); gsap.set(L.grid, { opacity: 1 }); gsap.set(L.mask, { opacity: 0.85 });
    gsap.set(L.boxes.children, { opacity: 1 });
    steps.forEach((s) => s.classList.add('is-on'));
    return;
  }

  // One timeline; each step plays it forward or back to that step's end state
  // when the step reaches the middle of the viewport.
  const cal = { f: 0 };
  const tl = gsap.timeline({ paused: true, defaults: { ease: 'power2.inOut' } });
  tl.addLabel('e0', 0)
    .fromTo(L.depth, { opacity: 0, clipPath: 'inset(0 0 100% 0)' }, { opacity: 1, clipPath: 'inset(0 0 0% 0)', duration: 0.6 }, 0)
    .addLabel('e1')
    .to(L.grid, { opacity: 1, duration: 0.3 }, 'e1')
    .to(L.depth, { opacity: 0, duration: 0.3 }, 'e1+=0.1')
    .fromTo(L.rgb, { filter: 'brightness(1)' }, { filter: 'brightness(0.3)', duration: 0.3 }, 'e1+=0.1')
    .to(L.plane, { opacity: 1, duration: 0.15 }, 'e1+=0.15')
    .fromTo(L.scan, { top: '0%' }, { top: '100%', duration: 0.9, ease: 'none' }, 'e1+=0.2')
    .to(cal, { f: 30, duration: 0.9, ease: 'none', onUpdate: () => {
      const f = Math.round(cal.f);
      frameEl.textContent = f;
      noiseEl.textContent = f < 4 ? '–' : (0.679 + (30 - f) * 0.04 * Math.abs(Math.sin(f * 1.7))).toFixed(3);
    } }, 'e1+=0.2')
    .to(L.plane, { opacity: 0.3, duration: 0.15 }, 'e1+=1.1')
    .addLabel('e2')
    .to(L.plane, { opacity: 0, duration: 0.2 }, 'e2')
    .to(L.rgb, { filter: 'brightness(1)', duration: 0.3 }, 'e2')
    .fromTo(L.mask, { opacity: 0, clipPath: 'inset(0 0 100% 0)' }, { opacity: 0.88, clipPath: 'inset(0 0 0% 0)', duration: 0.7 }, 'e2+=0.05')
    .addLabel('e3')
    .to(L.mask, { opacity: 0.35, duration: 0.3 }, 'e3')
    .to(L.boxes.children, { opacity: 1, duration: 0.2, stagger: 0.12 }, 'e3+=0.05')
    .addLabel('e4');

  let current = 0;
  const go = (i) => {
    if (i === current) return;
    current = i;
    setStep(i);
    tl.tweenTo(`e${i}`, { duration: Math.min(1.6, Math.abs(tl.labels[`e${i}`] - tl.time()) * 1.1 + 0.2), ease: 'none' });
  };
  steps.forEach((st, i) => ScrollTrigger.create({
    trigger: st, start: 'top 55%', end: 'bottom 55%',
    onToggle: (self) => { if (self.isActive) go(i); },
  }));
}

/* ───────────── 02 Hands ───────────── */
function initHands() {
  const range = $('#reveal');
  const frames = $$('.frame');
  // one control drives the reveal across all three recorded frames
  const apply = (v) => {
    frames.forEach((f) => { f.style.setProperty('--r', `${v}%`); f.style.setProperty('--rn', v > 0 && v < 100 ? 1 : 0); });
    range.style.setProperty('--fill', `${v}%`);
    range.setAttribute('aria-valuetext', `${Math.round(v)}% depth mask`);
  };
  let touched = false;
  let sweep = null;
  range.addEventListener('input', () => { touched = true; sweep?.kill(); apply(+range.value); });

  if (!reduced) {
    // restrained entrance for the three frames: 400 ms, 80 ms stagger (CSS)
    const strip = $('.strip');
    strip.classList.add('c02-reveal');
    new IntersectionObserver((entries, io) => {
      if (entries.some((e) => e.isIntersecting)) { strip.classList.add('is-in'); io.disconnect(); }
    }, { threshold: 0.15 }).observe(strip);

    // the existing demonstrative sweep, colour to the 50% default, the first time the strip is seen
    apply(0); range.value = 0;
    const o = { v: 0 };
    ScrollTrigger.create({
      trigger: '.strip', start: 'top 65%', once: true,
      onEnter: () => {
        if (touched) return;
        sweep = gsap.to(o, { v: 50, duration: 2.2, delay: 0.3, ease: 'power2.inOut', onUpdate: () => { range.value = o.v; apply(o.v); } });
      },
    });
  } else { range.value = 50; apply(50); }

  // latch diagram: a looped explanatory animation, paused when off screen
  const states = $$('.latch__states li');
  const on = (i) => () => states.forEach((s, k) => s.classList.toggle('is-on', k === i));
  const prop = $('.lt-prop'), ghost = $('.lt-ghost'), hand = $('.lt-hand'), ring = $('.lt-radius');
  const P0 = { x: 200, y: 110 }, P1 = { x: 420, y: 120 };
  gsap.set(prop, { x: P0.x, y: P0.y }); gsap.set(ghost, { x: P0.x, y: P0.y, opacity: 0 });
  gsap.set(ring, { attr: { cx: P0.x, cy: P0.y } });
  gsap.set(hand, { x: 420, opacity: 0 });
  if (reduced) { states.forEach((s) => s.classList.add('is-on')); return; }
  const tl = gsap.timeline({ repeat: -1, repeatDelay: 0.8, paused: true });
  tl.call(on(0))
    .to(prop, { x: P0.x, duration: 1 })
    .call(on(1))
    .to(hand, { opacity: 1, x: -150, duration: 1.2, ease: 'power2.out' })
    .call(on(2))
    .to(ghost, { opacity: 1, duration: 0.2 })
    .to(ring, { opacity: 0.9, duration: 0.2 }, '<')
    .to([prop, hand], { x: (i) => (i === 0 ? P1.x : 70), y: (i) => (i === 0 ? P1.y : 10), duration: 1.4, ease: 'power1.inOut' })
    .to(ring, { attr: { cx: P1.x, cy: P1.y }, duration: 1.4, ease: 'power1.inOut' }, '<')
    .to(hand, { x: 420, y: 0, opacity: 0, duration: 0.9, ease: 'power2.in' })
    .to(ring, { opacity: 0, duration: 0.2 }, '<')
    .call(on(3))
    .to({}, { duration: 0.6 })
    .call(on(4))
    .to(ghost, { x: P1.x, y: P1.y, duration: 0.35, ease: 'power3.out' })
    .to(ghost, { opacity: 0, duration: 0.4 }, '+=0.6')
    .to({}, { duration: 0.8 })
    .set(prop, { x: P0.x, y: P0.y, opacity: 0 })
    .set(ghost, { x: P0.x, y: P0.y })
    .set(ring, { attr: { cx: P0.x, cy: P0.y } })
    .to(prop, { opacity: 1, duration: 0.4 });
  ScrollTrigger.create({ trigger: '.latch', start: 'top bottom', end: 'bottom top', onToggle: (s) => (s.isActive ? tl.play() : tl.pause()) });

  // merge bars
  gsap.from('.mg--a, .mg--b', { scaleX: 0, transformOrigin: 'left', duration: 0.9, stagger: 0.15, ease: 'power3.out', scrollTrigger: { trigger: '.merge', start: 'top 75%' } });
  gsap.from('.mg--sum', { scaleX: 0, transformOrigin: 'left', duration: 1.1, delay: 0.5, ease: 'power3.out', scrollTrigger: { trigger: '.merge', start: 'top 75%' } });
  gsap.from('.mg-band', { opacity: 0, duration: 0.6, delay: 1.2, scrollTrigger: { trigger: '.merge', start: 'top 75%' } });

  // count-up tally
  $$('.tally dd').forEach((dd) => {
    const end = +dd.dataset.count; const o = { v: 0 };
    ScrollTrigger.create({ trigger: '.tally', start: 'top 80%', once: true, onEnter: () => gsap.to(o, { v: end, duration: 1.6, ease: 'power2.out', onUpdate: () => { dd.textContent = Math.round(o.v).toLocaleString('en-GB'); } }) });
  });
}

/* ───────────── Film dialog ───────────── */
function initFilm() {
  const dlg = $('#film');
  const v = $('.film__video');
  const hero = $('.hero__video');
  let opener = null;
  $$('.js-open-film').forEach((b) => b.addEventListener('click', () => {
    opener = b;
    hero.pause();
    dlg.showModal();
    v.play().catch(() => {});
  }));
  const close = () => dlg.close();
  $('.film__close').addEventListener('click', close);
  dlg.addEventListener('click', (e) => { if (e.target === dlg) close(); });
  dlg.addEventListener('close', () => {
    v.pause();
    // resume the opening film if the visitor had not paused it and it is in view
    if ($('.js-hero-play').getAttribute('aria-pressed') === 'true' && $('.hero').getBoundingClientRect().bottom > 0) hero.play().catch(() => {});
    opener?.focus();
  });
}

/* ───────────── Lazy 3D chapters ───────────── */
// The generation pin is created up front so the page height never changes
// when the Three.js module arrives; the module only subscribes to progress.
// Narrow or short screens read the five stages in order instead, unpinned (the
// same query is used in styles.css); the pin is added or removed as it changes.
const GEN_FLOW = '(max-width: 820px), (max-height: 520px)';
const genProgress = { p: 0, listener: null, flowQuery: GEN_FLOW };
function initGenerationPin() {
  if (reduced) return;
  // 'all' always matches, so this runs in both layouts and again whenever flow changes
  gsap.matchMedia().add({ flow: GEN_FLOW, all: 'all' }, ({ conditions }) => {
    if (conditions.flow) return;
    gsap.to(genProgress, {
      p: 1, ease: 'none',
      // 2.5 viewport heights for the five stages (was 4.2), with a short catch-up so
      // the scene follows the scroll closely (was 0.6 s)
      scrollTrigger: { trigger: '.gen__stage', start: 'top top', end: '+=250%', pin: true, scrub: 0.2, anticipatePin: 1 },
      onUpdate: () => genProgress.listener?.(genProgress.p),
    });
  });
}

function lazy(selector, loader) {
  const el = $(selector);
  let done = false;
  const io = new IntersectionObserver(([e]) => {
    if (e.isIntersecting && !done) {
      done = true; io.disconnect();
      loader().then((m) => m.init(el, { reduced, genProgress })).then(() => ScrollTrigger.refresh()).catch((err) => console.error(err));
    }
  }, { rootMargin: '120% 0px' });
  io.observe(el);
}

initRail();
initHero();
initSensing();
initHands();
initMapping({ reduced });
initLanguage({ reduced });
initGenerationPin(); // after the pins above it, so its start includes their spacing
initFilm();
lazy('.generation', () => import('./sections/generation.js'));
lazy('.environment', () => import('./sections/environment.js'));

// Keep trigger positions right when content above them changes height
// (web fonts, lazy images, the 3D chapters' panels).
addEventListener('load', () => ScrollTrigger.refresh());
document.fonts?.ready.then(() => ScrollTrigger.refresh());
let lastH = 0, roTimer = 0;
new ResizeObserver(() => {
  const h = document.body.scrollHeight;
  if (Math.abs(h - lastH) < 2) return;
  lastH = h;
  clearTimeout(roTimer);
  roTimer = setTimeout(() => ScrollTrigger.refresh(), 200);
}).observe(document.body);
