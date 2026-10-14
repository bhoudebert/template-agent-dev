#!/usr/bin/env python3
"""Reject commits/PR text that name an AI agent or tool (stdlib only).

    python tools/check_attribution.py FILE            # commit message file (commit-msg hook)
    python tools/check_attribution.py --range A..B    # every commit in a range: message + author + committer
    python tools/check_attribution.py --stdin         # arbitrary text, e.g. PR title and body

Policy: history never shows which assistant helped. See .agents/policies/git.md.
"""
import re
import subprocess
import sys

NAMES = r"claude|anthropic|chatgpt|openai|codex|copilot|aider|gpt-?\d"
RULES = [
    ("co-author trailer naming an AI", re.compile(rf"^\s*co-authored-by:.*({NAMES}|noreply@anthropic|\[bot\])", re.I | re.M)),
    ("generated-with line", re.compile(r"generated (with|by)\b", re.I)),
    ("robot emoji", re.compile("\U0001F916")),
    ("AI/agent tool name", re.compile(rf"\b({NAMES})\b", re.I)),
]


def find_violations(text):
    found = []
    for label, rx in RULES:
        m = rx.search(text)
        if m:
            found.append(f"{label}: {m.group(0).strip()[:80]!r}")
    return found


def _range(rev_range):
    fmt = "%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%B%x1e"
    out = subprocess.run(["git", "log", f"--format={fmt}", rev_range], capture_output=True, text=True, check=True).stdout
    problems = []
    for rec in out.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        sha, an, ae, cn, ce, body = rec.split("\x1f", 5)
        for v in find_violations(f"{an} {ae} {cn} {ce}\n{body}"):
            problems.append(f"{sha[:8]}: {v}")
    return problems


def main(argv):
    if argv[:1] == ["--range"] and len(argv) == 2:
        problems = _range(argv[1])
    elif argv == ["--stdin"]:
        problems = find_violations(sys.stdin.read())
    elif len(argv) == 1 and not argv[0].startswith("-"):
        with open(argv[0], encoding="utf-8") as f:
            text = "\n".join(l for l in f.read().splitlines() if not l.startswith("#"))
        problems = find_violations(text)
    else:
        print(__doc__, file=sys.stderr)
        return 64
    for p in problems:
        print(f"ATTRIBUTION {p}", file=sys.stderr)
    if problems:
        print("Never name an AI agent or tool in commits, PR titles/bodies, branches or tags. "
              "Remove it and retry.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
