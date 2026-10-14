#!/usr/bin/env python3
"""Project naming and layout: id prefixes and artifact folders (stdlib only).

Optional keys at the top level of .agents/pipeline.yaml; every default matches the stock layout:

    ids:
      story: PROJ                 # prefix: PROJ-1234 (a Jira-style key works as is)
      # story_pattern: "[A-Z][A-Z0-9]+-[0-9]+"   # or any regex, instead of PREFIX-<digits>
      incident: INC
      adr: ADR
      runbook: RB
    paths:
      stories: specs/stories
      decisions: docs/adr
      changes: openspec/changes   # also: architecture qa incidents runbooks releases specs
    commands:
      test: "cargo test --manifest-path backend/Cargo.toml && npm --prefix ui test"   # monorepo, or anything

    python tools/config.py regex story|incident|adr|runbook|any   # ERE for shell scripts
    python tools/config.py path stories
    python tools/config.py format story 12                         # PROJ-012
    python tools/config.py command test                            # the configured test command, if any
"""
import re
import sys
from pathlib import Path

import miniyaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IDS = {"story": "US", "incident": "INC", "adr": "ADR", "runbook": "RB"}
DEFAULT_PATHS = {
    "stories": "docs/stories", "architecture": "docs/architecture", "decisions": "docs/decisions",
    "qa": "docs/qa", "incidents": "docs/incidents", "runbooks": "docs/runbooks", "releases": "docs/releases",
    "specs": "openspec/specs", "changes": "openspec/changes",
}
MIN_DIGITS = {"story": 1, "incident": 1, "adr": 4, "runbook": 1}   # ADR-0001 style keeps four digits
_CACHE = {}


class Config:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.ids, self.paths, self.patterns, self.commands = dict(DEFAULT_IDS), dict(DEFAULT_PATHS), {}, {}
        p = self.root / ".agents" / "pipeline.yaml"
        if p.exists():
            try:
                data = miniyaml.loads(p.read_text(encoding="utf-8")) or {}
            except ValueError:
                data = {}
            for k, v in (data.get("ids") or {}).items():
                if k.endswith("_pattern"):
                    self.patterns[k[: -len("_pattern")]] = str(v)
                elif k in self.ids and v:
                    self.ids[k] = str(v)
            for k, v in (data.get("paths") or {}).items():
                if k in self.paths and v:
                    self.paths[k] = str(v).strip("/")
            for k, v in (data.get("commands") or {}).items():
                if v:
                    self.commands[k] = str(v)

    # ids
    def prefix(self, kind):
        return self.ids[kind]

    def core(self, kind):
        """Regex fragment (no anchors) matching one id of this kind."""
        if kind in self.patterns:
            return self.patterns[kind]
        return f"{re.escape(self.ids[kind])}-[0-9]{{{MIN_DIGITS[kind]},}}"

    def regex(self, kind="any"):
        if kind == "any":
            return "|".join(f"(?:{self.core(k)})" for k in ("story", "incident", "adr"))
        return self.core(kind)

    def is_kind(self, kind, value):
        return re.fullmatch(self.core(kind), str(value)) is not None

    def kind_of(self, value):
        return next((k for k in ("story", "incident", "adr", "runbook") if self.is_kind(k, value)), None)

    def format_id(self, kind, n):
        return f"{self.ids[kind]}-{n:0{max(3, MIN_DIGITS[kind])}d}"

    def number_of(self, kind, value):
        m = re.search(r"(\d+)$", str(value))
        return int(m.group(1)) if m else 0

    # paths
    def path(self, name):
        return self.paths[name]

    def apply_paths(self, text):
        """Rewrite stock folder names in a string (pipeline globs) to the configured ones."""
        for name in sorted(DEFAULT_PATHS, key=lambda n: -len(DEFAULT_PATHS[n])):
            if self.paths[name] != DEFAULT_PATHS[name]:
                text = text.replace(DEFAULT_PATHS[name], self.paths[name])
        return text

    def substitute(self, pattern):
        """Expand {story} {incident} {adr} {runbook} tokens in a schema pattern."""
        for k in ("story", "incident", "adr", "runbook"):
            pattern = pattern.replace("{" + k + "}", f"(?:{self.core(k)})")
        return pattern


def load(root=ROOT):
    key = str(Path(root).resolve())
    if key not in _CACHE:
        _CACHE[key] = Config(root)
    return _CACHE[key]


def main(argv):
    cfg = Config(ROOT)
    if len(argv) >= 2 and argv[0] == "regex":
        print(cfg.regex(argv[1]).replace("(?:", "("))   # POSIX ERE for grep -E
    elif len(argv) >= 2 and argv[0] == "path":
        print(cfg.path(argv[1]))
    elif len(argv) >= 2 and argv[0] == "command":
        print(cfg.commands.get(argv[1], ""))
    elif len(argv) >= 3 and argv[0] == "format":
        print(cfg.format_id(argv[1], int(argv[2])))
    else:
        print(__doc__, file=sys.stderr)
        return 64
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
