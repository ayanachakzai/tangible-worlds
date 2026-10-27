# Tangible Worlds — interactive visual documentary

A single-page website presenting the MSc project *Tangible Worlds: Physical
Arrangement as Spatial Prompting for Generative 3D Environments* (Muhammad Ayan
Achakzai, UAL Creative Computing Institute, 2026).

The page runs entirely in the browser. It does not connect to the iPhone,
Record3D, LM Studio, RunPod or any model. Every interactive scene is a
reconstruction driven by recorded project data, and is labelled as such.

## Run

```bash
npm install
npm run dev        # http://127.0.0.1:5173
npm run build      # static output in dist/
npm run preview    # serves dist/ on http://127.0.0.1:4173
```

`dist/` is a static site (about 62 MB, most of it video, GLBs and the
dissertation PDF) and can be served from any static host.

## Structure

| Path | Role |
|---|---|
| `index.html` | All chapter markup and copy |
| `src/styles.css` | Design tokens, layout, responsive and reduced-motion rules |
| `src/main.js` | Sidebar, hero, chapter 01 sensing, 02 hands, 07 applications, film dialog, lazy loading |
| `src/sections/mapping.js` | Chapter 03, draggable table and live relation grammar |
| `src/sections/language.js` | Chapter 04, recorded utterances, parse and scale grammar |
| `src/sections/generation.js` | Chapter 05, pinned Three.js pipeline sequence and mesh bench (lazy) |
| `src/sections/environment.js` | Chapter 06, reconstructed scene with recorded atmosphere states (lazy) |
| `src/lib/atmosphere.js` | Port of the production 12-field atmosphere mapping (Phase 5E) |
| `src/lib/grammar.js` | Port of `phase3-tabletop/mapping/compute_scene.py` |
| `src/lib/meshes.js` | GLB loading and the production normalise-and-rest rule |
| `src/data.js` | Recorded assignments, utterances and Qwen3-8B atmosphere outputs |
| `public/media/` | Copied and re-encoded project assets |
| `public/media/provenance.json` | Source path and evidence class for every copied asset |
| `tools-assets.py`, `tools-encode.sh` | Reproducible asset copy and video encoding (read-only on the thesis repo) |

## Evidence classes

`provenance.json` tags each asset as `production` (captured from the final
system), `diagnostic` (development tooling), `experiment` (explored or rejected
direction), `generated` (real SDXL Turbo / SPAR3D output from the meaning cache)
or `derived` (crops or measurements made here from a real asset).

Edits to footage are limited to cropping, side-by-side composition in the hero,
and re-encoding. Explanatory animation (for example the rising clip plane in
chapter 05) is labelled on the page as explanatory.

## Dependencies and screening

| Package | Licence | Cost | Provenance |
|---|---|---|---|
| three 0.170.0 | MIT | free | three.js authors (open-source project begun by Ricardo Cabello); the same version as the production renderer |
| gsap 3.13 (+ ScrollTrigger) | GreenSock standard licence, no-charge since 3.13 | free | GreenSock, owned by Webflow (USA) |
| vite 6 (dev only) | MIT | free | Vite / VoidZero team |
| Google Fonts: Funnel Sans, League Gothic, Reddit Mono | SIL OFL 1.1 | free | NORD ID (NL), The League of Moveable Type (US), Reddit (US) |

A provenance check of the developers and maintainers listed above found no
Israeli-origin concern. This is a desk check made while building the site,
not a substitute for the project's formal origin review. No paid API or
service is used.

## Known limitations

See the final report in the session. The main ones: reduced-motion paths are
implemented but were not verified in an emulated reduced-motion browser; the
largest GLBs are not compressed (Draco or meshopt would cut the 25 MB of meshes
substantially); the hand-latch diagram in chapter 02 is a schematic, not
recorded data.
