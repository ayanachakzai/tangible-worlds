// Chapter 04: how a word becomes a world. Five stages of the production
// object-assignment route, one presented at a time. The progression and its
// controls stay put; only the stage presentation beneath them changes. Every
// example-specific line comes from the selected recorded assignment. Wording,
// routes and values are taken from the production index.html, serve.py and the
// session logs; nothing on this page runs them.
import { gsap } from 'gsap';

const STAGES = 5;
const EASE = 'cubic-bezier(0.22, 1, 0.36, 1)';
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const cap = (t) => t[0].toUpperCase() + t.slice(1);
const noun = (m) => m.replace(/^an? /, '');
const pad2 = (n) => String(n).padStart(2, '0');

// each stage has its own composition; data-r marks the reveal order:
// h heading, x supporting copy, m media or evidence
const VIEWS = {
  1: (a) => `
    <div class="fx-s1">
      <figure class="fx-s1__photo" data-r="m">
        <img src="/media/img/prop-${a.id}.webp" alt="The ${esc(a.prop)} on the tabletop, as the tracker camera saw it." width="400" height="400" />
      </figure>
      <div class="fx-s1__text">
        <p class="fx-kicker" data-r="h">01 · Physical object</p>
        <p class="fx-title" data-r="h">The tracker follows the ${esc(a.prop)}, not ${esc(a.meaning)}.</p>
        <p class="fx-copy" data-r="x">The ${esc(a.prop)} keeps its physical identity while it moves. Its assigned meaning is stored separately.</p>
        <dl class="fx-ev" data-r="x">
          <div><dt>tracked id</dt><dd>${a.id}</dd></div>
          <div><dt>label</dt><dd>"object"</dd></div>
        </dl>
      </div>
    </div>`,

  2: (a) => {
    const words = a.said.split(' ');
    const m0 = words.indexOf('is') + 1, m1 = m0 + a.meaningWords.split(' ').length;
    const said = `${esc(words.slice(0, m0).join(' '))} <mark>${esc(words.slice(m0, m1).join(' '))}</mark>${m1 < words.length ? ` ${esc(words.slice(m1).join(' '))}` : ''}`;
    return `
    <div class="fx-s2">
      <p class="fx-kicker" data-r="h">02 · Spoken instruction</p>
      <p class="fx-s2__said" data-r="h">“${said}”</p>
      <p class="fx-copy" data-r="x">Parakeet turned the participant’s speech into this text on the local machine. The words are not accepted yet: the system reads them back first.</p>
      <dl class="fx-ev fx-ev--row" data-r="m">
        <div><dt>model</dt><dd>Parakeet TDT 0.6B v3</dd></div>
        <div><dt>transcription time, this recording</dt><dd>${a.stt} s</dd></div>
      </dl>
    </div>`;
  },

  3: (a, open) => `
    <div class="fx-s3">
      <p class="fx-kicker" data-r="h">03 · Confirmation</p>
      <div class="fx-s3__talk">
        <p class="fx-s3__who" data-r="h">System</p>
        <p class="fx-s3__line" data-r="h">“Did you say: ${esc(a.said)}?”</p>
        <p class="fx-s3__who" data-r="x">Participant</p>
        <p class="fx-s3__line fx-s3__line--yes" data-r="x">“yes”</p>
        <p class="fx-s3__who" data-r="x">System</p>
        <p class="fx-s3__line fx-s3__line--small" data-r="x">“Got it.”</p>
      </div>
      <p class="fx-copy" data-r="m">Pocket TTS reads the transcript back in the Alba voice. Only a whole-word yes sends the instruction on; an unclear answer is asked again.</p>
      ${branch('no', 'What if the answer is no?', open.no, 'The system says “Okay, try again.” and waits; the participant speaks the instruction again and the new transcript is read back. A rejected instruction does not change the generated scene. The abandoned transcript stays in the log and the retry count rises. This is how the system handles a no; in this recording the answer was yes.')}
    </div>`,

  4: (a) => `
    <div class="fx-s4">
     <div class="fx-s4__main">
      <p class="fx-kicker" data-r="h">04 · Meaning assigned</p>
      <div class="fx-s4__pair">
        <p class="fx-s4__obj" data-r="h"><span>${pad2(a.id)}</span> · ${esc(cap(a.prop))}</p>
        <span class="fx-s4__link" data-r="x" aria-hidden="true"></span>
        <p class="fx-s4__meaning" data-r="h">${esc(a.meaning)}</p>
      </div>
      <p class="fx-title fx-title--s4" data-r="x">The meaning changes. The physical object does not.</p>
     </div>
     <div class="fx-s4__side">
      <dl class="fx-ev fx-ev--col" data-r="m">
        <div><dt>meaning</dt><dd>${esc(a.meaning)}</dd></div>
        <div><dt>scale</dt><dd>${a.scale ? `${esc(a.scale)} · target ${a.target}` : 'no marker · target 1.00'}</dd></div>
        <div><dt>stored against</dt><dd>tracked id ${a.id}</dd></div>
      </dl>
      <p class="fx-copy fx-copy--small" data-r="m">The sentence matched the assignment grammar, so the browser parsed it locally and sent it to <code>/api/assign</code>; no language model read it. The scale marker is kept apart from the meaning and never reaches generation.</p>
     </div>
    </div>`,

  5: (a, open) => `
    <div class="fx-s5">
      <figure class="fx-s5__img" data-r="m">
        <img src="/media/img/src-${a.slug}.webp" alt="The cached image generated for the meaning ${esc(a.meaning)}." width="512" height="512" />
        <figcaption>${esc(a.meaning)}</figcaption>
      </figure>
      <div class="fx-s5__text">
        <p class="fx-kicker" data-r="h">05 · Generated world</p>
        <p class="fx-title" data-r="h">The generated model is cached under its meaning and placed at the tracked object’s position.</p>
        <p class="fx-copy" data-r="x">This recording was a cache hit: <code>${esc(a.slug)}.glb</code> already existed, so it was reused, scaled to ${a.target} and placed where the ${esc(a.prop)} sits. The image is the cached SDXL Turbo source the model was built from.</p>
        ${branch('miss', 'What happens if the model isn’t cached?', open.miss, '', `<p class="fx-route"><span>Prompt preparation <code>Qwen3-8B</code></span><span>SDXL Turbo</span><span>SPAR3D</span><span>Cached GLB</span><span>Three.js</span></p><p>Qwen3-8B frames the meaning as an image prompt without adding to it, SDXL Turbo makes the source image, SPAR3D reconstructs the mesh on a rented GPU, and the GLB is saved under the meaning for every later use. Not what happened in this recording.</p>`)}
      </div>
    </div>`,
};

function branch(key, label, isOpen, text, html = '') {
  return `<div class="fx-branch" data-r="m">
      <button type="button" class="fx-branch__btn js-flow-branch" data-branch="${key}" aria-expanded="${isOpen}">${esc(label)}</button>
      <div class="fx-branch__body"${isOpen ? '' : ' hidden'}>${html || `<p>${esc(text)}</p>`}</div>
    </div>`;
}

// the technical evidence, grouped; example-specific values follow the selection
const EVIDENCE = (a) => [
  ['Tracking and physical identity', `The depth tracker publishes geometry and a persistent numeric id for each prop, with the generic label "object". The ${esc(a.prop)} is tracked as id ${a.id}; the tracker never names what it sees.`, 'Frozen tracker, write_scene(); chapter 01'],
  ['Speech recognition and confirmation', `Hold the DualSense touchpad and speak; Parakeet TDT 0.6B v3 transcribes locally (${a.stt} s for this command). Kyutai Pocket TTS (voice alba, <code>/api/tts</code>) reads it back; a whole-word yes or no decides. Each accepted command logs <code>raw_transcript</code>, <code>transcript_attempts</code>, <code>retry_count</code>, <code>confirmation_transcript</code> and <code>stt_s</code>.`, 'Production index.html; conversation_log.json'],
  ['Assignment routing and semantic parsing', '“object &lt;number&gt; is &lt;meaning&gt;” is parsed in the browser and posted to <code>/api/assign</code>; the renderer polls <code>/api/assignments</code>. Every other command goes to <code>/api/converse</code> and Qwen3-8B in LM Studio, which returns atmosphere fields (chapter 06) and never assigns objects. In the typed condition the same grammar is typed and sent with Assign.', 'parseVoiceAssignment(); serve.py'],
  ['Scale grammar and caching', `An optional terminal <code>scale &lt;tiny|miniature|small|big|large|huge&gt;</code> becomes a relative display target (0.35, 0.65, 1.80, 3.00; 1.00 without a marker). Voice also accepts the measured mis-hearing “scaled &lt;size&gt;”. Meshes are cached by meaning: “${esc(a.meaningFull)}” is stored as “${esc(a.meaning)}” and cached as <code>${esc(a.slug)}.glb</code>. Automatic scale was rejected after the best Qwen design matched 50 of 72 held-out cases.`, 'MARKED_SCALE_TARGETS, serve.py; assignments.json'],
  ['Image-to-3D generation and rendering', 'On a cache miss: Qwen3-8B prompt framing, SDXL Turbo source image, SPAR3D mesh, saved under the meaning. The browser scales the longest bounding-box side to the target and rests the mesh on the table (normalizeAndAddModel()).', 'serve.py shape_prompt(); production index.html; chapter 05'],
  ['Recorded sessions and source references', 'The four assignments, read-backs and yes answers are session AYANTEST07; assignments.json records all four as cache hits. The five-attempt retry case is session AYANTEST03. Images and models are copied from the production cache unaltered.', 'conversation_log.json; assignments.json; generated_meshes/'],
];

export function initFlow(root, { reduced, getAssignment }) {
  const stage = root.querySelector('.js-flow-stage');
  const steps = [...root.querySelectorAll('.fx-step')];
  const hits = steps.map((s) => s.querySelector('.fx-step__hit'));
  const prev = root.querySelector('.js-flow-prev');
  const next = root.querySelector('.js-flow-next');
  const evidence = root.querySelector('.js-flow-evidence');
  const open = { no: false, miss: false };
  let step = 1, tl = null, ticket = 0, guard = 0;

  stage.id = 'flow-stage';
  hits.forEach((h) => h.setAttribute('aria-controls', 'flow-stage'));

  function markers() {
    steps.forEach((s, i) => {
      s.classList.toggle('is-active', i + 1 === step);
      s.classList.toggle('is-done', i + 1 < step);
      hits[i].setAttribute('aria-current', i + 1 === step ? 'step' : 'false');
    });
    prev.disabled = step === 1;
    next.disabled = step === STAGES;
  }

  function content() {
    const a = getAssignment();
    stage.dataset.stage = String(step);
    stage.innerHTML = VIEWS[step](a, open);
    root.querySelector('.js-flow-example').textContent = `${cap(a.prop)} → ${cap(noun(a.meaning))}`;
    evidence.innerHTML = EVIDENCE(a).map(([h, t, src]) => `<section class="fx-evg"><h4>${h}</h4><p>${t}</p><p class="fx-evg__src">${src}</p></section>`).join('');
  }

  // the marker moves at once; the old stage fades in 100 ms, then the new one
  // arrives heading, copy, media (220, 240, 280 ms). A newer request cancels all.
  function go(n) {
    const target = Math.max(1, Math.min(STAGES, n));
    if (target === step && !tl) return;
    step = target;
    markers();
    const mine = ++ticket;
    tl?.kill();
    clearTimeout(guard);
    if (reduced) { content(); tl = null; return; }
    let swapped = false;
    tl = gsap.timeline({ onComplete: () => { if (mine === ticket) { tl = null; clearTimeout(guard); } } });
    // if animation frames are not running (a hidden or throttled page), the stage
    // must still show the right content: finish it without the motion
    guard = setTimeout(() => {
      if (mine !== ticket || !tl) return;
      tl.kill();
      tl = null;
      if (!swapped) content();
      gsap.set(stage, { opacity: 1 });
      gsap.set(stage.querySelectorAll('[data-r]'), { opacity: 1, y: 0 });
    }, 700);
    tl.to(stage, { opacity: 0, duration: 0.1, ease: 'none' })
      .add(() => {
        if (mine !== ticket) return;
        swapped = true;
        content();
        gsap.set(stage, { opacity: 1 });
        const by = (k) => stage.querySelectorAll(`[data-r="${k}"]`);
        const t2 = gsap.timeline();
        t2.fromTo(by('h'), { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: 0.22, ease: EASE }, 0)
          .fromTo(by('x'), { opacity: 0, y: 6 }, { opacity: 1, y: 0, duration: 0.24, ease: EASE }, 0.03)
          .fromTo(by('m'), { opacity: 0, y: 4 }, { opacity: 1, y: 0, duration: 0.28, ease: EASE }, 0.02);
        tl.add(t2, tl.time());
      });
  }

  hits.forEach((h, i) => h.addEventListener('click', () => go(i + 1)));
  prev.addEventListener('click', () => go(step - 1));
  next.addEventListener('click', () => go(step + 1));
  root.querySelector('.js-flow-restart').addEventListener('click', () => go(1));
  stage.addEventListener('click', (e) => {
    const b = e.target.closest('.js-flow-branch');
    if (!b) return;
    const k = b.dataset.branch;
    open[k] = !open[k];
    b.setAttribute('aria-expanded', String(open[k]));
    b.nextElementSibling.hidden = !open[k];
  });

  // a new recorded assignment updates the presented stage immediately
  function refresh() {
    ticket++;
    clearTimeout(guard);
    tl?.kill();
    tl = null;
    gsap.set(stage, { opacity: 1 });
    content();
  }

  markers();
  content();
  return { refresh };
}
