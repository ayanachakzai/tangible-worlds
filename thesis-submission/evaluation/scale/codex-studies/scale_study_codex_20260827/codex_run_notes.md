# Codex Run Notes

## Scope

The run created and changed files only inside `phase3-tabletop/rendering/scale_study_codex_20260827/`. Existing production, test, documentation, mapping, voice, generation, atmosphere, and runtime-state files were not edited.

## Pass record

1. Recorded initial SHA-256 hashes for `index.html`, `serve.py`, and `track_tabletop.py` before creating study files.
2. Audited current renderer normalization, camera, table, grouping, position conversion, and grounding paths.
3. Verified all seven calibration GLBs by file presence, byte size, SHA-256 hash, browser load, and render.
4. Verified the three named primary research papers and official Three.js mechanisms used by the harness.
5. Built a deterministic isolated harness with five ladders, four compositions, and three cameras.
6. Ran 60 browser conditions through the already installed Playwright CLI and Chrome channel. No dependency was installed.
7. Captured 60 PNG screenshots and 60 raw JSON result files with zero capture failures.
8. Aggregated raw records into `results.json` and inspected reference, crowding, adjacency, edge, production, top-down, and lower-oblique evidence.
9. Performed a separate adversarial pass that challenged small-object visibility, middle-class separation, crowding, edge behavior, top-down stability, aspect-ratio effects, unlabelled rank reading, and calibration overfitting.
10. Selected `C_compact`, not the current proposal and not the Codex-derived candidate.

## Important failures preserved

- The first direct Chrome check wrote `logs/harness_check.png` but the raw headless Chrome process did not exit cleanly. The process was terminated by exact study-process PID only. The valid image was preserved.
- `D_expanded` produced the highest crowding footprint and a third mixed-adjacency overlap.
- All semantic ladders produced one out-of-bounds mountain in edge stress.
- The mixed-adjacency mug can be fully occluded beside the mountain when footprints overlap.

## Dependency statement

No package, library, model, API, browser, or browser automation dependency was installed. The run used existing Python standard-library static serving, existing Google Chrome, existing Playwright CLI, existing Node.js for a syntax check, existing `jq` for JSON aggregation, and the project's pinned Three.js r170 CDN imports.

## Runtime-state statement

The study did not call production APIs and did not write assignment, relation, conversation, modifier, tracking, or generation state. Pre-existing dirty worktree entries were left untouched.

## Completion summary

Recommended tested ladder: `0.35, 0.65, 1.00, 1.35, 1.80, 2.35, 3.00` for handheld through landform_scale. `micro` and `colossal_scale` remain unresolved due missing suitable stimuli.

## Final verification results

- `study_harness.html` module syntax: PASS with Node static module parsing.
- `preview.html` script syntax: PASS with Node static script parsing.
- `results.json` and all 60 raw records: PASS with `jq empty`.
- Aggregate record count: 60.
- PNG screenshot count: 60.
- PNG dimensions: all 1440 by 1000.
- Missing screenshot links from `REPORT.md`: none.
- Em dash characters in study Markdown and HTML: none.
- Production before and after hashes: identical.
- Production git diff on `index.html`, `serve.py`, and `track_tabletop.py`: empty.
- Runtime-state file writes after the initial hash marker: none.
- Package or lockfile writes outside the study directory after the initial marker: none.
- Playwright browser session: closed.
- Local static server: stopped.
