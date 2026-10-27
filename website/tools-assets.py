"""Copy selected thesis assets into public/media without modifying the originals.

Every output is recorded in public/media/provenance.json with its source path,
relative to the thesis repository (never a local absolute path), and an
evidence class:
  production      - captured from the frozen/final production system
  diagnostic      - development or qualification tooling, not the live runtime
  experiment      - an explored or rejected direction
  generated       - a real SDXL Turbo / SPAR3D output from the project cache
  derived         - computed here from a real asset (e.g. crops, mask boxes)
"""
import json, os, shutil
from pathlib import Path
from PIL import Image
import numpy as np

ROOT = Path('~/Documents/UAL/tangible-worlds').expanduser()  # the thesis repository; adjust to your checkout
PF = ROOT / 'Tangible-Worlds-Thesis/PORTFOLIO_1020'
GM = ROOT / 'phase3-tabletop/rendering/generated_meshes'
OUT = Path(__file__).parent / 'public/media'
IMG = OUT / 'img'
GLB = OUT / 'glb'
for d in (IMG, GLB, OUT / 'doc'):
    d.mkdir(parents=True, exist_ok=True)

prov = []

def rec(out, src, cls, note):
    # the file is published, so a path is recorded relative to the thesis repository;
    # a source from anywhere else must be given as a description instead
    if isinstance(src, Path):
        if not src.is_relative_to(ROOT):
            raise ValueError(f'source outside the thesis repository needs a description: {src.name}')
        src = src.relative_to(ROOT)
    prov.append({'file': str(out.relative_to(OUT.parent)), 'source': str(src), 'class': cls, 'note': note})

def img(src, name, cls, note, crop=None, max_side=1400, keep_pixels=False, q=84, source=None):
    src = Path(src)
    if not src.exists():
        # portfolio files were re-encoded after INDEX.csv was written; match by stem
        matches = sorted(src.parent.glob(src.stem + '.*'))
        if not matches:
            raise FileNotFoundError(src)
        src = matches[0]
    im = Image.open(src)
    im = im.convert('RGBA' if im.mode in ('RGBA', 'LA', 'P') else 'RGB')
    if crop:
        im = im.crop(crop)
    if not keep_pixels and max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    out = IMG / f'{name}.webp'
    im.save(out, 'WEBP', quality=q, lossless=keep_pixels)
    rec(out, source or src, cls, note)
    return im

# ── 01 sensing ─────────────────────────────────────────────
L = PF / '02_tracking_and_identity'
img(L / 'lidar_recognition/003_1.webp', 's01-overhead-rgb', 'diagnostic',
    'Overhead iPhone RGB of the tabletop during the move to depth-blob detection, 12 Aug 2026 (02-LID-003).')
img(L / 'lidar_recognition/005_2-1.webp', 's01-depth-probe', 'diagnostic',
    'depth_probe.py (read-only diagnostic): connected components above the fitted table plane, noise 1.7 mm (02-LID-005, cf. Fig 5.2).',
    crop=(2, 57, 520, 750))
img(L / 'lidar_recognition/006_2-2.webp', 's01-depth-probe-2', 'diagnostic',
    'depth_probe.py second capture, 12 Aug 2026 (02-LID-006).', crop=(2, 57, 520, 750))
img(L / 'live_qualification/001_image71.png', 's01-tracker-final', 'production',
    'Frozen study tracker window, 20 Aug 2026: threshold 6 mm, RGB 1440x1920, depth 192x256, LEARNING LOCKED / ROSTER LOCKED (02-LIV-001).')
img(L / 'live_qualification/002_image72.jpg', 's08-terrain-live', 'experiment',
    'terrain_live.html object-anchored terrain test, 20 Aug 2026 (02-LIV-002). Prototype only, not integrated.')

D = L / 'debug_runs_aug20_sep02'
pairs = {
    'a': ('061_anomaly_003_candidate_start_mask.png', '062_anomaly_003_candidate_start_preview.png'),
    'h1': ('021_anomaly_001_candidate_start_mask.png', '022_anomaly_001_candidate_start_preview.png'),
    'h2': ('023_anomaly_002_candidate_start_mask.png', '024_anomaly_002_candidate_start_preview.png'),
    'h3': ('025_anomaly_003_candidate_start_mask.png', '026_anomaly_003_candidate_start_preview.png'),
    'h4': ('100_anomaly_001_candidate_start_mask.png', '101_anomaly_001_candidate_start_preview.png'),
    'h5': ('102_anomaly_002_candidate_start_mask.png', '103_anomaly_002_candidate_start_preview.png'),
}

def components(mask_path, min_px=12):
    """Connected components of the tracker's own mask, with bounding boxes."""
    m = np.array(Image.open(mask_path).convert('L')) > 127
    h, w = m.shape
    seen = np.zeros_like(m)
    comps = []
    for y in range(h):
        for x in range(w):
            if m[y, x] and not seen[y, x]:
                stack = [(y, x)]; seen[y, x] = True; pts = []
                while stack:
                    cy, cx = stack.pop(); pts.append((cy, cx))
                    for ny, nx in ((cy+1, cx), (cy-1, cx), (cy, cx+1), (cy, cx-1)):
                        if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True; stack.append((ny, nx))
                if len(pts) >= min_px:
                    ys = [p[0] for p in pts]; xs = [p[1] for p in pts]
                    comps.append({'x0': min(xs), 'y0': min(ys), 'x1': max(xs) + 1, 'y1': max(ys) + 1,
                                  'px': len(pts), 'cx': round(sum(xs) / len(xs), 1), 'cy': round(sum(ys) / len(ys), 1)})
    comps.sort(key=lambda c: -c['px'])
    return {'w': w, 'h': h, 'components': comps}

boxes = {}
for key, (mk, pv) in pairs.items():
    img(D / mk, f'trk-{key}-mask', 'production', f'Frozen tracker debug mask, 192x256 depth grid ({mk}).', keep_pixels=True)
    img(D / pv, f'trk-{key}-rgb', 'production', f'Frozen tracker debug preview at depth-grid resolution ({pv}).', keep_pixels=True)
    boxes[key] = components(D / mk)
(OUT / 'tracker-components.json').write_text(json.dumps(boxes, indent=1))
rec(OUT / 'tracker-components.json', D, 'derived', 'Connected components computed here from the tracker debug masks (bounding boxes only).')

# ── props, cropped from the Part 2.2 recording (tracker RGB inset) ─────────
frame = Path(os.environ['P22FRAME'])
props = {1: (135, 441, 244, 583), 2: (282, 527, 396, 637), 3: (128, 649, 266, 785), 4: (341, 649, 426, 763)}
for pid, box in props.items():
    img(frame, f'prop-{pid}', 'derived',
        f'Physical prop #{pid}, cropped from the tracker RGB inset at 4.0 s of Part 2.2.mov.', crop=box,
        source='Part 2.2.mov (frame at 4.0 s)')  # P22FRAME is a temporary frame extracted from it

# the same props from the same frame of Part 2.mov, the full-resolution (3024 x 1964)
# recording Part 2.2.mov was exported from; the boxes above, mapped by the measured
# export scale (1.570) and offset. Kept losslessly: they are video frames already.
frame = Path(os.environ['P2FRAME'])  # a temporary frame extracted at 4.0 s
props = {1: (219, 944, 390, 1167), 2: (450, 1079, 629, 1252), 3: (208, 1271, 424, 1484), 4: (542, 1271, 676, 1450)}
for pid, box in props.items():
    img(frame, f'prop-{pid}-hd', 'derived',
        f'Physical prop #{pid}, cropped from the tracker RGB inset at 4.0 s of Part 2.mov, the full-resolution screen recording that Part 2.2.mov was exported from (1.57x the pixels of prop-{pid}.webp).',
        crop=box, keep_pixels=True, source='Part 2.mov (frame at 4.0 s)')

# ── generation ────────────────────────────────────────────
good = ['a-windmill', 'a-fire-truck', 'a-house', 'a-horse', 'a-lighthouse', 'a-castle', 'a-tent',
        'a-dragon', 'a-truck', 'a-stone-cairn', 'a-mountain', 'a-petrol-station', 'a-car', 'a-stone-bridge']
weak = ['a-gravel-driveway', 'a-stone-foundation', 'a-cliff', 'a-stone-pathway', 'a-stone-retaining-wall']
for slug in good + weak:
    shutil.copy2(GM / f'{slug}.glb', GLB / f'{slug}.glb')
    rec(GLB / f'{slug}.glb', GM / f'{slug}.glb', 'generated', 'SPAR3D GLB from the production meaning cache.')
    src = GM / slug / 'source.png'
    if src.exists():
        # the four recorded assignments are shown large in chapter 04: encoded closer to the source
        q = 95 if slug in ('a-house', 'a-windmill', 'a-fire-truck', 'a-horse') else 84
        img(src, f'src-{slug}', 'generated', 'SDXL Turbo Stage 1 source image from the production meaning cache.', max_side=768, q=q)

B = PF / '04_generation_pipeline'
battery = {'001': 'acoustic-guitar', '002': 'backpack', '009': 'traffic-cone', '010': 'umbrella',
           '011': 'vintage-motorcycle', '012': 'wine-glass'}
for n, word in battery.items():
    img(B / f'09_thirteen_word_battery/{n}_source.png', f'bat-{word}', 'experiment',
        f'Thirteen-meaning battery Stage 1 source, 29 Jul 2026 ({word}); a retained failure case (Figs 5.11/5.12).', max_side=640)
img(B / '05_spar3d_vs_sf3d/012_comparison_tree_shard_1.jpeg', 'tree-sf3d', 'experiment',
    'SF3D reconstruction of the tree source; canopy collapses to a shard (04-05-012, Fig 5.10).', max_side=900)
img(B / '05_spar3d_vs_sf3d/015_comparison_tree_fixed.jpeg', 'tree-spar3d', 'experiment',
    'SPAR3D reconstruction of the same tree source (04-05-015, Fig 5.10).', max_side=900)

# ── voice ─────────────────────────────────────────────────
V = PF / '06_voice_and_input'
for f in sorted((V / '01_moonshine').iterdir()):
    if f.name.startswith('moonshine-') and f.name[10] in '23456':
        img(f, f'voice-moonshine-{f.name[10]}', 'production',
            f'Moonshine-era voice interface capture: {f.stem} (Fig 5.20).', max_side=1200)
for i in (1, 5):
    f = next((V / '02_parakeet').glob(f'parakeet-{i}*'))
    img(f, f'voice-parakeet-{i}', 'production', f'Parakeet voice interface capture: {f.stem} (Fig 5.20).', max_side=1200)

# ── atmosphere evidence ───────────────────────────────────
A = PF / '07_atmosphere'
for i, f in enumerate(sorted((A / '04_battery_sequences').iterdir())[:5], 1):
    img(f, f'atmo-seq-{i}', 'diagnostic', f'Phase 5E qualification harness, sequence step {i}: {f.stem}.', max_side=1000)
img(A / '01_july_failure/001_image4.png', 'atmo-july-failure', 'experiment',
    'First atmosphere implementation, 20 Jul 2026: golden hour and midday failed (Fig 5.21 context).', max_side=1000)

# ── interstitials / terrain ───────────────────────────────
I = PF / '08_terrain_and_interstitials'
img(I / '05_interstitials/014_image41.png', 'inter-horse-stable', 'production',
    '14 Aug 2026: horse + stable produce a hitching post whose scale and placement fail (Fig 5.24a).', max_side=1200)
img(I / '05_interstitials/016_image51.png', 'inter-mountain-tent', 'production',
    '15 Aug 2026: mountain + tent produce a bounded stone cairn after the prompt was revised (Fig 5.24b).', max_side=1200)
img(I / '04_procedural/005_image66.png', 'terrain-procedural', 'experiment',
    'Object-anchored procedural terrain fields, 16 Aug 2026. Prototype only.', max_side=1200)
img(ROOT / 'figure_4_1_system_overview.png', 'fig-4-1', 'diagnostic', 'Dissertation Figure 4.1, system architecture.', max_side=1600)

# ── dissertation ──────────────────────────────────────────
pdf = ROOT / 'Muhammad Ayan Achakzai Thesis Submission/1. Tangible World Paper.pdf'
shutil.copy2(pdf, OUT / 'doc/tangible-worlds-dissertation.pdf')
rec(OUT / 'doc/tangible-worlds-dissertation.pdf', pdf, 'production', 'Submitted dissertation, September 2026.')

vids = {
    'video/hero-split.mp4': ('Part 2.2.mov', 'Edited: tracker RGB inset (left) and production renderer (right) cropped from one screen recording and placed side by side. No other alteration.'),
    'video/hero-split-mobile.mp4': ('Part 2.2.mov', 'As hero-split, stacked vertically for portrait screens.'),
    'video/part-2-2-full.mp4': ('Part 2.2.mov', 'Unedited frame, re-encoded.'),
    'video/voice-assignment.mp4': ('part 1.1.mov', 'Voice assignment session, re-encoded.'),
    'video/atmosphere-voice.mp4': ('Part 3.3.mov', 'Spoken atmosphere commands, re-encoded.'),
    'video/working-prototype.mp4': ('Tangible-Worlds-Thesis/Tangible World Working Prototype.mov', 'Full working prototype demonstration, re-encoded to 1280px.'),
}
for f, (src, note) in vids.items():
    rec(OUT / f, ROOT / src, 'production', note)

(OUT / 'provenance.json').write_text(json.dumps(prov, indent=1))
print(len(prov), 'records')
print(json.dumps(boxes['a'], indent=0)[:600])
