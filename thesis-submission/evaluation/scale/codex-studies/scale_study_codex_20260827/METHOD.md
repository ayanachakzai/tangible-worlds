# Method

## Study boundary

This is an isolated renderer evaluation. It does not modify or call the production tracking, assignment, generation, Qwen, voice, atmosphere, or runtime-state paths. All ladder values are project test values.

## Literature-supported design principles

Stoakley, Conway, and Pausch introduced the World in Miniature as a second viewport that offers context and direct manipulation at a scale different from the represented world. They explicitly observed that a scale can become too small for selection and manipulation. This supports compression with a legibility floor, not literal metres and not a specific numeric ladder.

Source: Richard Stoakley, Matthew J. Conway, and Randy Pausch. 1995. Virtual Reality on a WIM: Interactive Worlds in Miniature. CHI 1995, 265-272. DOI: https://doi.org/10.1145/223904.223938. Author-hosted HTML: https://www.cs.cmu.edu/~stage3/publications/95/conferences/chi/paper.html

Danyluk et al. distinguish the physical size of a World in Miniature, the scope represented inside it, and its scale. They found a relationship between size and scope across prior systems, but also identify useful exceptions and abstraction strategies. This supports treating Tangible Worlds as a bounded overview representation whose semantic scope is wider than its physical display.

Source: Kurtis Danyluk, Barrett Ens, Bernhard Jenny, and Wesley Willett. 2021. A Design Space Exploration of Worlds in Miniature. CHI 2021. DOI: https://doi.org/10.1145/3411764.3445098. Author-hosted PDF: https://barrettens.github.io/files/Danyluk_2021_WorldsInMiniature.pdf

Macaranas, Antle, and Riecke distinguish physical attributes such as big-small from spatial properties such as near-far. In their 20-participant tangible-interface study, big-small mappings were identified strongly for several abstract pairs, including more-less. This supports a monotonic size cue as a potentially readable semantic attribute. It does not establish target-size ratios or validate this project's class meanings.

Source: Anna Macaranas, Alissa N. Antle, and Bernhard E. Riecke. 2012. Bridging the Gap: Attribute and Spatial Metaphors for Tangible Interface Design. TEI 2012, 161-168. DOI: https://doi.org/10.1145/2148131.2148166. Author-hosted PDF: https://antle.iat.sfu.ca/wp-content/uploads/2018/02/MacaranasAntleRiecke_TEI12_Metaphors.pdf

## Project-specific empirical tuning

The harness uses the production 10 unit plane, the production 50 degree perspective camera at `(0, 12, 5)`, and the production longest-bounding-box-dimension normalization principle. Three fixed additional conditions vary composition and camera without changing object size dynamically.

Each ladder is tested with the same seven GLBs. Four deterministic compositions challenge hierarchy, crowding, mixed adjacency, and table-edge behavior. Three deterministic cameras challenge dependence on the normal view. Metrics describe world-space bounding boxes, x-z footprints, pairwise footprint overlap, table-boundary crossings, and projected rectangles. They are engineering descriptors, not a perceptual model.

## Candidate hypotheses

1. `A_baseline`: a common 0.9 size should erase semantic hierarchy.
2. `B_current`: the current manual non-uniform ladder should make all seven ranks legible.
3. `C_compact`: a reduced upper range may preserve lower and middle separation while improving coexistence.
4. `D_expanded`: stronger middle and upper separation may improve ranking but risk domination and edge failure.
5. `E_balanced`: added after the first implementation pass as a bounded interpolation to preserve the current lower and middle anchors while testing lower infrastructure and landform maxima. Its final status depends on captured evidence.

## Inference boundary

No verified paper supplies a defensible ratio progression for this renderer. Ordinal monotonicity is supported as a readable mapping direction, but linear, geometric, and hand-tuned ratios remain project design choices. The final recommendation therefore depends on this study's screenshots and quantitative stress evidence, not a claim that a published law produced the values.

## Reproduction

Serve `phase3-tabletop/rendering` with an existing local static server, then open:

`scale_study_codex_20260827/study_harness.html?ladder=B_current&composition=reference&camera=production`

Valid ladder ids are `A_baseline`, `B_current`, `C_compact`, `D_expanded`, and `E_balanced`. Valid compositions are `reference`, `crowding`, `adjacency`, and `edge`. Valid cameras are `production`, `topdown`, and `low_oblique`.
