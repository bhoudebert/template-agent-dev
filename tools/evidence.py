#!/usr/bin/env python3
"""Evidence floor: a story that reaches `implemented` must leave something anchoring its behaviour.

    python tools/evidence.py [--base REF] [--story US-001]

A story's change must include at least ONE of:
  - a changed OpenSpec file (a spec added or updated), or
  - a changed test file (new, fixed or non-regression test), or
  - an explicit waiver `skip: [tests]` + `skip_reason` (docs, config or infra only).
Skipping `spec` and/or `design` never removes this floor. Enforced from the story's status
`implemented` onwards; before that it only informs, so early draft PRs are not blocked.
Globs live in .agents/pipeline.yaml under `evidence:`.
"""
import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path

import miniyaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TESTS = ["tests/*", "*/tests/*", "*__tests__*", "*.test.*", "*.spec.*", "*_test.*", "test_*", "*/test_*"]
DEFAULT_SPECS = ["openspec/specs/*", "openspec/changes/*"]
ENFORCED_FROM = ("implemented", "done")


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)


def globs(root):
    try:
        cfg = miniyaml.loads((Path(root) / ".agents" / "pipeline.yaml").read_text(encoding="utf-8")).get("evidence") or {}
    except (OSError, ValueError):
        cfg = {}
    return cfg.get("tests") or DEFAULT_TESTS, cfg.get("specs") or DEFAULT_SPECS


def base_ref(root):
    if os.environ.get("AGENT_BASE_REF"):
        return os.environ["AGENT_BASE_REF"]
    for cand in ("origin/main", "main"):
        if _git(root, "rev-parse", "--verify", "-q", cand).returncode == 0:
            return cand
    return None


def changed_files(root, base):
    files = set()
    if base:
        p = _git(root, "diff", "--name-only", f"{base}...HEAD")
        if p.returncode == 0:
            files |= {l for l in p.stdout.splitlines() if l}
    for args in (("diff", "--name-only", "HEAD"), ("ls-files", "--others", "--exclude-standard")):
        p = _git(root, *args)
        if p.returncode == 0:
            files |= {l for l in p.stdout.splitlines() if l}
    return sorted(files)


def story_id(root, explicit=None):
    if explicit:
        return explicit
    p = _git(root, "branch", "--show-current")
    m = re.search(r"US-\d+", p.stdout if p.returncode == 0 else "")
    return m.group(0) if m else None


def evaluate(root, sid, files):
    """Return (ok, lines)."""
    path = Path(root) / "docs" / "stories" / f"{sid}.md"
    if not path.exists():
        return True, [f"evidence: {sid} has no story file; nothing to enforce"]
    meta, _ = miniyaml.split_frontmatter(path.read_text(encoding="utf-8"))
    meta = meta or {}
    status = meta.get("status")
    skip = meta.get("skip") or []
    skip = skip if isinstance(skip, list) else [skip]
    test_globs, spec_globs = globs(root)
    match = lambda f, gs: any(fnmatch.fnmatch(f, g) for g in gs)
    tests = [f for f in files if match(f, test_globs)]
    specs = [f for f in files if match(f, spec_globs)]
    lines = [f"evidence: {sid} status={status} skip={skip or 'none'}",
             f"  spec files changed: {len(specs)}   test files changed: {len(tests)}"]
    if status not in ENFORCED_FROM:
        lines.append(f"  informational: enforced from status `implemented` (now `{status}`)")
        return True, lines
    if "tests" in skip:
        lines.append(f"  waived: skip tests ({meta.get('skip_reason', 'no reason')})")
        return True, lines
    if specs or tests:
        lines.append("  ok: behaviour is anchored by " + ("a spec change" if specs else "a test change"))
        return True, lines
    lines.append(f"  FAIL: {sid} is {status} but no spec and no test file changed. Add or update a test "
                 f"(a non-regression test counts) or a spec; for docs/config/infra only, declare "
                 f"`skip: [tests]` with a skip_reason (`mise run skip {sid} tests --reason \"...\"`).")
    return False, lines


def main(argv):
    base = None
    story = None
    it = iter(argv)
    for a in it:
        if a == "--base":
            base = next(it, None)
        elif a == "--story":
            story = next(it, None)
    if base:
        os.environ["AGENT_BASE_REF"] = base
    sid = story_id(ROOT, story)
    if not sid:
        print("evidence: no story id in the branch name (use --story); nothing to enforce")
        return 0
    ok, lines = evaluate(ROOT, sid, changed_files(ROOT, base_ref(ROOT)))
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
