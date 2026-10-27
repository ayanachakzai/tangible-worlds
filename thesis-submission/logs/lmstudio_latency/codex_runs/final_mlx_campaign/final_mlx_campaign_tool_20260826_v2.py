"""Corrected entrypoint for final_mlx_campaign_tool_20260826.py.

The original helper is preserved unchanged as evidence. This wrapper corrects
the repository root without overwriting the existing file.
"""

from __future__ import annotations

from pathlib import Path

import final_mlx_campaign_tool_20260826 as tool

repo_root = Path("~/Documents/UAL/tangible-worlds")
tool.REPO_ROOT = repo_root
tool.PHASE3_ROOT = repo_root / "phase3-tabletop"
tool.RENDERING_DIR = tool.PHASE3_ROOT / "rendering"
tool.SERVE_PATH = tool.RENDERING_DIR / "serve.py"

if __name__ == "__main__":
    tool.main()
