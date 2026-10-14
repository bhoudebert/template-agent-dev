#!/usr/bin/env python3
"""Work-item helpers so you never hand-edit ids or status lines (stdlib only).

    python tools/items.py new-story "Export invoices as CSV"     # next US-NNN, raw draft
    python tools/items.py new-incident "Checkout 500s"            # next INC-NNN from template
    python tools/items.py list                                    # stories + status + next step
    python tools/items.py branch US-002                           # git checkout -b feature/US-002-<slug>
    python tools/items.py set-status US-002 approved [--force]    # guarded status bump
"""
import argparse
import os
import re
import sys
from pathlib import Path

import miniyaml
import trace_check

ROOT = Path(__file__).resolve().parent.parent
ORDER = trace_check.ORDER
NEXT_STAGE = {
    "draft": "story", "enriched": "(PO approves story)", "approved": "spec",
    "specified": "design", "designed": "implement", "implemented": "qa", "done": "release",
}


def _next_id(prefix, folder, root):
    nums = [int(m.group(1)) for p in (Path(root) / folder).glob(f"{prefix}-*.md")
            if (m := re.match(rf"{prefix}-(\d+)", p.name))]
    return f"{prefix}-{max(nums, default=0) + 1:03d}"


def _clean(title):
    return re.sub(r"[:#\n]+", " ", title).strip()


def new_story(title, root=ROOT, text=""):
    sid = _next_id("US", "docs/stories", root)
    path = Path(root) / "docs" / "stories" / f"{sid}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nid: {sid}\ntype: story\ntitle: {_clean(title)}\nstatus: draft\nowner: product-owner\n---\n"
        f"{text or 'Describe the request in your own words here.'}\n", encoding="utf-8")
    return sid, path


def new_incident(title, root=ROOT):
    iid = _next_id("INC", "docs/incidents", root)
    tpl = (Path(root) / ".agents" / "templates" / "incident.md").read_text(encoding="utf-8")
    body = tpl.replace("INC-000", iid).replace("Incident title", _clean(title))
    body = body.replace("Quoted log lines, metrics, traces, recent deploys (with source and timestamp).",
                        "PASTE logs / metrics / deploys here (redact secrets).")
    for filler in ("Who/what is affected, since when, how bad.",):
        body = body.replace(filler, "TBD")
    body = re.sub(r"(## Hypotheses\n).*?(## Recommended actions)", r"\1TBD\n\n\2", body, flags=re.S)
    body = re.sub(r"(## Recommended actions\n).*?(## Not verified)", r"\1TBD\n\n\2", body, flags=re.S)
    body = re.sub(r"(## Not verified\n).*\Z", r"\1TBD\n", body, flags=re.S)
    path = Path(root) / "docs" / "incidents" / f"{iid}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return iid, path


def stories(root=ROOT):
    out = []
    for p in sorted((Path(root) / "docs" / "stories").glob("US-*.md")):
        meta, _ = miniyaml.split_frontmatter(p.read_text(encoding="utf-8"))
        if meta:
            out.append((meta.get("id", p.stem), meta.get("status", "?"), meta.get("title", ""), p))
    return out


def set_status(sid, new, force=False, root=ROOT):
    path = Path(root) / "docs" / "stories" / f"{sid}.md"
    if not path.exists():
        raise SystemExit(f"no such story: {path}")
    if new not in ORDER:
        raise SystemExit(f"status must be one of {ORDER}")
    text = path.read_text(encoding="utf-8")
    meta, _ = miniyaml.split_frontmatter(text)
    cur = meta.get("status")
    if cur in ORDER and not force and ORDER.index(new) > ORDER.index(cur) + 1:
        raise SystemExit(f"{sid}: {cur} -> {new} skips a step (use --force)")
    updated, n = re.subn(r"^status:.*$", f"status: {new}", text, count=1, flags=re.M)
    if n != 1:
        raise SystemExit(f"{path}: no status line in frontmatter")
    path.write_text(updated, encoding="utf-8")
    problems = trace_check.check(root)
    if problems and not force:
        path.write_text(text, encoding="utf-8")  # revert
        raise SystemExit("not applied; fix first:\n  " + "\n  ".join(problems))
    return cur, new


def branch_name(item_id, root=ROOT):
    """feature/<US-id>-<slug> from the story title; fix/<INC-id>-<slug> for incidents."""
    folder, prefix = ("stories", "feature") if item_id.startswith("US-") else ("incidents", "fix")
    path = Path(root) / "docs" / folder / f"{item_id}.md"
    if not path.exists():
        raise SystemExit(f"no such item: {path}")
    meta, _ = miniyaml.split_frontmatter(path.read_text(encoding="utf-8"))
    slug = re.sub(r"[^a-z0-9]+", "-", str(meta.get("title", "")).lower()).strip("-")[:40].strip("-")
    return f"{prefix}/{item_id}" + (f"-{slug}" if slug else "")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("new-story", "new-incident"):
        sub.add_parser(name).add_argument("title", nargs="+")
    sub.add_parser("list")
    sub.add_parser("branch").add_argument("id")
    s = sub.add_parser("set-status")
    s.add_argument("id")
    s.add_argument("status")
    s.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "new-story":
        sid, path = new_story(" ".join(a.title))
        print(f"created {os.path.relpath(path, ROOT)}\nnext: edit it, then `mise run story {sid}`")
    elif a.cmd == "new-incident":
        iid, path = new_incident(" ".join(a.title))
        print(f"created {os.path.relpath(path, ROOT)}\nnext: paste evidence, then `mise run diagnose {iid}`")
    elif a.cmd == "branch":
        import subprocess
        name = branch_name(a.id)
        rc = subprocess.run(["git", "checkout", "-b", name], cwd=ROOT).returncode
        print(name)
        return rc
    elif a.cmd == "list":
        for sid, status, title, _ in stories():
            print(f"{sid:<8} {status:<12} next: {NEXT_STAGE.get(status, '-'):<22} {title}")
    else:
        cur, new = set_status(a.id, a.status, a.force)
        print(f"{a.id}: {cur} -> {new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
