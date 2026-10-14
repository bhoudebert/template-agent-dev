#!/usr/bin/env python3
"""Traceability check: story -> openspec change -> ADR/design -> QA report.

Rules (by story `status`, see .agents/schemas/story.json):
  >= specified   openspec/changes/<id>/ (or archive) must exist
  >= designed    at least one ADR or design doc with `story: <id>`
  == done        docs/qa/<id>.md must exist with verdict `pass`
Plus: every ADR/design/qa-report `story` must point at an existing story.
"""
import os
import sys
from pathlib import Path

import miniyaml

ROOT = Path(__file__).resolve().parent.parent
ORDER = ["draft", "enriched", "approved", "specified", "designed", "implemented", "done"]
SKIP_DIRS = {".git", ".agents", "node_modules", ".venv", "tools", "tests", "evals", "adapters"}


def _artifacts(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not name.endswith(".md"):
                continue
            path = Path(dirpath) / name
            try:
                meta, _ = miniyaml.split_frontmatter(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if meta and meta.get("type"):
                yield path, meta


def check(root=ROOT):
    root = Path(root)
    errs, stories, linked, qa = [], {}, {}, {}
    for path, meta in _artifacts(root):
        rel = os.path.relpath(path, root)
        kind = meta["type"]
        if kind == "story":
            stories[meta.get("id")] = meta
        elif kind in ("adr", "design"):
            linked.setdefault(meta.get("story"), []).append(rel)
        elif kind == "qa-report":
            qa[meta.get("story")] = meta
        if kind in ("adr", "design", "qa-report") and meta.get("story") not in stories_ids(root):
            errs.append(f"{rel}: story {meta.get('story')!r} not found")
    for sid, meta in stories.items():
        status = meta.get("status")
        if status not in ORDER:
            continue
        rank = ORDER.index(status)
        change = root / "openspec" / "changes" / str(sid)
        archived = list((root / "openspec" / "changes" / "archive").glob(f"*{sid}*")) if (root / "openspec" / "changes" / "archive").is_dir() else []
        if rank >= ORDER.index("specified") and not (change.is_dir() or archived):
            errs.append(f"{sid}: status={status} but openspec/changes/{sid}/ missing")
        if rank >= ORDER.index("designed") and not linked.get(sid):
            errs.append(f"{sid}: status={status} but no ADR/design references it")
        if status == "done":
            report = qa.get(sid)
            if not report:
                errs.append(f"{sid}: status=done but no qa-report")
            elif report.get("verdict") != "pass":
                errs.append(f"{sid}: status=done but qa verdict={report.get('verdict')!r}")
    return errs


def stories_ids(root):
    return {m.get("id") for p, m in _artifacts(root) if m["type"] == "story"}


def main():
    errs = check(ROOT)
    for e in errs:
        print(f"TRACE {e}")
    print(f"trace_check: {len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
