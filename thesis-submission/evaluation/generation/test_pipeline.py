"""
test_pipeline.py
-----------------
one-word-at-a-time terminal test of the real generation pipeline. imports
_real_generate straight from serve.py, so this runs the exact live code
(shape_prompt -> sdxl -> spar3d), not a separate copy that could drift.

usage:
    cd phase3-tabletop/rendering
    python test_pipeline.py "coffee mug"
"""

import sys
import re
from pathlib import Path
import serve

serve.GENERATED_MESH_DIR = Path("test_pipeline")
serve.GENERATED_MESH_DIR.mkdir(exist_ok=True)

from serve import _real_generate

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('usage: python test_pipeline.py "<meaning>"')
        sys.exit(1)

    meaning = sys.argv[1]
    slug = re.sub(r"[^a-z0-9]+", "-", meaning.lower()).strip("-")
    object_key = f"test-{slug}"

    print(f"[test] running real pipeline for: '{meaning}'")
    print(f"[test] output dir: {serve.GENERATED_MESH_DIR.resolve()}")
    _real_generate(object_key, meaning)
    print(f"[test] done: '{meaning}'")