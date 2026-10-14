"""Shared repository walk for validate.py and trace_check.py (stdlib only).

Template-owned folders are skipped only at the repository ROOT, so a project's
own `docs/examples/` or `src/tools/` is still scanned. Vendor and cache folders
are skipped at any depth.
"""
import os
from pathlib import Path

ROOT_SKIP = {".agents", "tools", "tests", "evals", "adapters", "examples"}
ANY_DEPTH_SKIP = {".git", "node_modules", ".venv", "__pycache__"}


def iter_markdown(root):
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        at_root = Path(dirpath) == root
        dirnames[:] = [
            d for d in dirnames
            if d not in ANY_DEPTH_SKIP and not (at_root and d in ROOT_SKIP)
        ]
        for name in filenames:
            if name.endswith(".md"):
                yield Path(dirpath) / name
