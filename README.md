# Tangible Worlds

Physical arrangement as spatial prompting for generative 3D environments.

MSc Applied Machine Learning for Creatives, Creative Computing Institute,
University of the Arts London, September 2026. Muhammad Ayan Achakzai.
Supervisor: Dr Terence Broad.

> How might tangible interfaces that translate physical arrangements into
> generative 3D environments support new forms of spatial authorship and
> creative exploration?

## The project

Ordinary props on a table are read from above by iPhone LiDAR depth and kept as
numbered, persistent physical handles. Meaning is assigned to each prop
separately, by typing or speaking. A local language model shapes that meaning
into a prompt, an image model generates a source image, and a reconstruction
model turns it into a 3D mesh, which is cached against the meaning. Moving a
prop moves its object without generating it again; words change what objects
are and the atmosphere around them.

**Implemented with:** iPhone LiDAR via Record3D · Qwen3-8B in LM Studio ·
SDXL Turbo · SPAR3D · Parakeet TDT 0.6B v3 via NeMo-Speech.cpp ·
Kyutai Pocket TTS · Three.js r170.

## What is in this repository

| Folder | Contents |
|---|---|
| [`thesis-submission/`](thesis-submission/) | The submitted research artefact, in its original structure |
| [`thesis-submission/system/`](thesis-submission/system/) | The working prototype: tracking, mapping, conversation, voice, generation and rendering |
| [`thesis-submission/evaluation/`](thesis-submission/evaluation/) | Frozen data and scripts behind the dissertation's Section 5: tracking and threshold reanalysis, scale studies, speech, the generation battery and atmosphere repeatability |
| [`thesis-submission/prototypes/`](thesis-submission/prototypes/) | Directions built and not adopted: tracker variants, terrain, mesa and the depth probe |
| [`thesis-submission/logs/`](thesis-submission/logs/) | Session records quoted by the dissertation, including the frozen tracker session of 1,039 seconds and 26,503 frames |
| [`website/`](website/) | An interactive visual documentary of the project, built with Vite and Three.js |

**Setting up the prototype:** the original technical documentation, setup and
reproduction instructions are in
[`thesis-submission/README.md`](thesis-submission/README.md). As submitted, the
prototype runs with LM Studio, a RunPod GPU for generation and local speech
services, all described there; model weights are not included.

## Dissertation and recordings

- Dissertation (PDF):
  [`website/public/media/doc/tangible-worlds-dissertation.pdf`](website/public/media/doc/tangible-worlds-dissertation.pdf).
  The student ID has been removed from the cover page; nothing else is changed.
- Working prototype demonstration: <https://youtu.be/XNu7JBYMaUo>
- Project presentation: <https://youtu.be/r9R8zmedLDQ>

## The website

The website runs entirely in the browser. It does not connect to the tracker,
LM Studio, RunPod or any model: every interactive scene is a reconstruction
driven by recorded project data, and is labelled as such.

```bash
cd website
npm ci
npm run dev        # http://127.0.0.1:5173
npm run build      # static output in website/dist/
```

See [`website/README.md`](website/README.md) for its structure and
[`website/public/media/provenance.json`](website/public/media/provenance.json)
for the source and evidence class of every asset it uses.

## Limitations

No participant study was conducted. A comparison of typed and spoken input was
designed and instrumented but not run, so nothing here shows that people find
the mapping intuitive, feel greater ownership or explore more freely. Generated
quality across arbitrary meanings, and interstitial relations across arbitrary
object pairs, were not systematically evaluated. The website's applications
chapter describes proposed uses, none of which was tested. The dissertation's
Sections 5 to 8 set out the evidence and its limits.

## Publication notes and attribution

This public copy differs from the private submission only where publishing
required it: personal file paths and credential-like strings were removed, and
some files were excluded. Every change is listed in
[`PUBLICATION_NOTES.md`](PUBLICATION_NOTES.md).

Third-party software and models remain under their own licences. The archived
SPAR3D source in `thesis-submission/system/generation/pod/` is distributed by
Stability AI under the Stability AI Community License, included in that
archive. No licence has yet been chosen for the original work in this
repository.
