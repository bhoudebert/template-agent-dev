#!/usr/bin/env python3
"""Where am I and what is next? (stdlib only)

    python tools/orient.py [ID]        # rules in force + state + next action
    python tools/orient.py next [ID]   # only the state and next action
ID defaults to the US-/INC- id in the current branch name.
"""
import re
import subprocess
import sys
from pathlib import Path

import miniyaml
import trace_check
import validate

ROOT = Path(__file__).resolve().parent.parent
STAGE_AFTER = {"draft": "story", "approved": "spec", "specified": "design",
               "designed": "implement", "implemented": "qa", "done": "release"}
STATUS_FOR = {"spec": "specified", "design": "designed"}   # stages that may be skipped


def current_branch(root):
    p = subprocess.run(["git", "branch", "--show-current"], cwd=root, text=True, capture_output=True)
    if p.returncode != 0:  # git < 2.22
        p = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root, text=True, capture_output=True)
    name = p.stdout.strip() if p.returncode == 0 else ""
    return "" if name == "HEAD" else name


def load_story(root, sid):
    p = Path(root) / "docs" / "stories" / f"{sid}.md"
    if not p.exists():
        return None
    meta, _ = miniyaml.split_frontmatter(p.read_text(encoding="utf-8"))
    return meta


def next_action(sid, meta):
    """(who, text) for a story's frontmatter."""
    status, skip = meta.get("status"), meta.get("skip") or []
    skip = skip if isinstance(skip, list) else [skip]
    if status == "enriched":
        return "you", f"read the story, answer open questions, then `mise run advance {sid} approved`"
    stage = STAGE_AFTER.get(status)
    if stage is None:
        return "you", f"unknown status {status!r}"
    target = None
    while stage in skip:
        target = STATUS_FOR[stage]
        stage = STAGE_AFTER[target]
    if target:
        return "you", (f"stages skipped for {sid} ({meta.get('skip_reason', 'no reason given')}): "
                       f"`mise run advance {sid} {target}`, then `mise run {stage} {sid}`")
    if status == "done":
        return "agent", f"`mise run release {sid}` (notes and go/no-go), then the PR and release PR"
    return "agent", f"`mise run {stage} {sid}` (or `mise run prepare {stage} {sid}` in prompt mode)"


def main(argv):
    only_next = bool(argv) and argv[0] == "next"
    args = argv[1:] if only_next else argv
    sid = args[0] if args else None
    branch = current_branch(ROOT)
    if not sid:
        m = re.search(r"(US|INC)-\d+", branch)
        sid = m.group(0) if m else None

    if not only_next:
        print("ORIENT")
        print("Bible (always in force): AGENTS.md, CONTEXT.md, .agents/{roles,skills,policies,templates,schemas}, .agents/pipeline.yaml")
        print("Knowledge map: docs/INDEX.md (search it before changing behaviour; cite ids; `Refs: none` is valid)")
        print("Protocol: orient -> prepare <stage> <id> -> do the work -> apply <stage> <id> --receipt <code> -> gate (the user)")
        print("Gates: never advance, ship or merge without the user's explicit yes. No assistant names in history.")
        print()
    print(f"branch: {branch or '(none)'}")
    if sid is None:
        print("story:  none inferred from the branch; pass an id, or `mise run new <title>`")
        return 0
    if sid.startswith("INC-"):
        print(f"incident: {sid}. next: agent `mise run diagnose {sid}`; a human executes any mitigation")
        return 0
    meta = load_story(ROOT, sid)
    if meta is None:
        print(f"story:  {sid} not found in docs/stories/")
        return 1
    skip = meta.get("skip") or []
    print(f"story:  {sid}  status={meta.get('status')}  title={meta.get('title')!r}"
          + (f"  skips={skip}" if skip else ""))
    who, text = next_action(sid, meta)
    print(f"next:   [{who}] {text}")
    problems = validate.scan(ROOT) + trace_check.check(ROOT)
    print(f"checks: {len(problems)} problem(s)" + ("".join(f"\n  - {p}" for p in problems[:5])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
