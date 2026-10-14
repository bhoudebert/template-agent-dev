#!/usr/bin/env python3
"""Validate agent artifacts against .agents/schemas/<type>.json (stdlib only).

Usage:
    python tools/validate.py                 # scan whole repo
    python tools/validate.py PATH [PATH...]  # files, or openspec/changes/<id> dirs
Exit code 1 when any error is found.
"""
import json
import os
import re
import sys
from pathlib import Path

import miniyaml
import repowalk

ROOT = Path(__file__).resolve().parent.parent
CHANGE_SECTIONS = ("why", "what changes", "impact")
SPEC_HEADERS = ("## added requirements", "## modified requirements", "## removed requirements", "## renamed requirements")


def _sections(body):
    out, title, buf = {}, None, []
    for line in body.splitlines():
        if line.startswith("## "):
            if title is not None:
                out[title] = "\n".join(buf)
            title, buf = line[3:].strip().lower(), []
        elif title is not None:
            buf.append(line)
    if title is not None:
        out[title] = "\n".join(buf)
    return out


def check_file(path, root=ROOT):
    path = Path(path)
    rel = os.path.relpath(path, root)
    if Path(rel).parts[:1] == ("openspec",):
        return []  # OpenSpec files are checked by check_change(), not by artifact schema
    try:
        meta, body = miniyaml.split_frontmatter(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return [f"{rel}: bad frontmatter ({e})"]
    if meta is None:
        return []  # not an agent artifact
    kind = meta.get("type")
    schema_path = Path(root) / ".agents" / "schemas" / f"{kind}.json"
    if not kind or not schema_path.exists():
        return [f"{rel}: unknown or missing `type` ({kind!r})"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errs = []
    fm = schema.get("frontmatter", {})
    for key in fm.get("required", []):
        if meta.get(key) in (None, "", []):
            errs.append(f"{rel}: missing frontmatter `{key}`")
    for key, allowed in fm.get("enums", {}).items():
        if key in meta and meta[key] not in allowed:
            errs.append(f"{rel}: `{key}`={meta[key]!r} not in {allowed}")
    for key, pattern in fm.get("patterns", {}).items():
        if key in meta and not re.match(pattern, str(meta[key])):
            errs.append(f"{rel}: `{key}`={meta[key]!r} does not match {pattern}")
    fname_key = schema.get("filename_starts_with")
    if fname_key and meta.get(fname_key):
        want = str(meta[fname_key])
        name = Path(path).name
        if name != f"{want}.md" and not name.startswith(f"{want}-"):
            errs.append(f"{rel}: file name must be `{want}.md` or `{want}-<slug>.md` (frontmatter {fname_key}: {want})")
    relaxed = schema.get("relaxed_when", {})
    if relaxed and all(meta.get(k) == v for k, v in relaxed.items()):
        return errs  # e.g. raw draft story: only frontmatter is enforced
    if kind == "story":
        skip = meta.get("skip") or []
        skip = skip if isinstance(skip, list) else [skip]
        bad = [s for s in skip if s not in ("spec", "design")]
        if bad:
            errs.append(f"{rel}: `skip` may only contain spec and design, not {bad}")
        if skip and not meta.get("skip_reason"):
            errs.append(f"{rel}: `skip` needs a `skip_reason` (say why this story needs no spec/design)")
    secs = _sections(body)
    for name in schema.get("sections", []):
        if name.lower() not in secs:
            errs.append(f"{rel}: missing section `## {name}`")
        elif not secs[name.lower()].strip():
            errs.append(f"{rel}: section `## {name}` is empty")
    if kind == "qa-report":
        for token in re.findall(r"`([^`\s]+\.[A-Za-z0-9]+)`", secs.get("traceability", "")):
            if "/" in token and not (Path(root) / token).exists():
                errs.append(f"{rel}: cited evidence file does not exist: {token}")
    for name, pattern in schema.get("section_patterns", {}).items():
        text = secs.get(name.lower(), "")
        if text.strip() and not re.search(pattern, text):
            errs.append(f"{rel}: section `## {name}` must match /{pattern}/")
    return errs


def check_change(change_dir, root=ROOT):
    """OpenSpec change folder: proposal.md, tasks.md, specs/**/spec.md."""
    change_dir = Path(change_dir)
    rel = os.path.relpath(change_dir, root)
    errs = []
    for md in sorted(change_dir.rglob("*.md")):
        if md.read_text(encoding="utf-8").startswith("---"):
            errs.append(f"{os.path.relpath(md, root)}: OpenSpec files must not have frontmatter (the folder name is the story id)")
    proposal = change_dir / "proposal.md"
    if not proposal.exists():
        errs.append(f"{rel}: missing proposal.md")
    else:
        secs = _sections(proposal.read_text(encoding="utf-8"))
        for name in CHANGE_SECTIONS:
            if not secs.get(name, "").strip():
                errs.append(f"{rel}/proposal.md: missing or empty `## {name.title()}`")
    tasks = change_dir / "tasks.md"
    if not tasks.exists():
        errs.append(f"{rel}: missing tasks.md")
    elif not re.search(r"^\s*- \[[ xX]\] ", tasks.read_text(encoding="utf-8"), re.M):
        errs.append(f"{rel}/tasks.md: no `- [ ]` task items")
    specs = list(change_dir.glob("specs/**/spec.md"))
    if not specs:
        errs.append(f"{rel}: no specs/**/spec.md delta")
    for spec in specs:
        text = spec.read_text(encoding="utf-8")
        low = text.lower()
        if not any(h in low for h in SPEC_HEADERS):
            errs.append(f"{os.path.relpath(spec, root)}: needs ADDED/MODIFIED/REMOVED Requirements header")
        if "#### scenario:" not in low:
            errs.append(f"{os.path.relpath(spec, root)}: no `#### Scenario:` found")
        if not re.search(r"\b(SHALL|MUST)\b", text):
            errs.append(f"{os.path.relpath(spec, root)}: requirements must use SHALL/MUST")
    return errs


def scan(root=ROOT):
    errs = []
    for path in repowalk.iter_markdown(root):
        errs += check_file(path, root)
    changes = Path(root) / "openspec" / "changes"
    if changes.is_dir():
        for d in sorted(changes.iterdir()):
            if d.is_dir() and d.name != "archive":
                errs += check_change(d, root)
    return errs


def check_paths(paths, root=ROOT):
    errs = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            errs += check_change(p, root)
        elif p.suffix == ".md":
            errs += check_file(p, root)
    return errs


def main(argv):
    errs = check_paths(argv, ROOT) if argv else scan(ROOT)
    for e in errs:
        print(f"ERROR {e}")
    print(f"validate: {len(errs)} error(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
