#!/usr/bin/env python3
"""Find and run the project's own tests (stdlib only).

    python tools/testcmd.py list     # what would run, and why; runs nothing
    python tools/testcmd.py run      # run it (the default)
    python tools/testcmd.py list --root /path/to/repo      # inspect another repository

Resolution, first match wins:
  1. `commands.test` in .agents/pipeline.yaml       one command line, for anything
  2. .agents/commands/test.sh                       a script the PROJECT owns; the kit never updates it
  3. the repository root: Cargo.toml, go.mod, package.json (with a test script),
     pyproject.toml / pytest.ini / setup.cfg, pom.xml
  4. one level down (monorepos): every sub-folder with one of those markers, run one after the other
  5. the kit's own tests (tools/tests), only inside the kit repository
Nothing found is an error with instructions: "no tests" must never look like "tests pass".
"""
import json
import subprocess
import sys
from pathlib import Path

import config

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"node_modules", "target", "vendor", "dist", "build", "docs", "examples", "tools", "site", "openspec", "venv"}


def marker(d):
    """(label, command) for a folder that has a recognised test setup, else None."""
    d = Path(d)
    if (d / "Cargo.toml").exists():
        return "cargo", "cargo test"
    if (d / "go.mod").exists():
        return "go", "go test ./..."
    pj = d / "package.json"
    if pj.exists():
        try:
            test = (json.loads(pj.read_text()).get("scripts") or {}).get("test", "")
        except ValueError:
            test = ""
        if test and "no test specified" not in test:
            return "npm", "npm test"
    if any((d / f).exists() for f in ("pytest.ini", "pyproject.toml", "setup.cfg")):
        return "pytest", "python3 -m pytest"
    if (d / "pom.xml").exists():
        return "maven", "mvn -q test"
    return None


def plan(root=ROOT):
    """Return (source, [(folder, label, command)])."""
    root = Path(root)
    cmd = config.load(root).commands.get("test")
    if cmd:
        return "commands.test in .agents/pipeline.yaml", [(".", "configured", cmd)]
    script = root / ".agents" / "commands" / "test.sh"
    if script.exists():
        return ".agents/commands/test.sh (yours)", [(".", "script", f"sh {script.relative_to(root)}")]
    m = marker(root)
    if m:
        return "repository root", [(".", m[0], m[1])]
    found = []
    for d in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name not in SKIP):
        m = marker(d)
        if m:
            found.append((d.name, m[0], m[1]))
    if found:
        return "auto-discovered one level down", found
    if (root / "tools" / "tests").is_dir():
        return "the kit's own tests", [(".", "unittest", "python3 -m unittest discover -s tools/tests")]
    return "nothing found", []


def main(argv):
    argv = list(argv)
    root = ROOT
    if "--root" in argv:
        i = argv.index("--root")
        root = Path(argv[i + 1]).expanduser().resolve()
        del argv[i:i + 2]
    mode = argv[0] if argv else "run"
    source, items = plan(root)
    if not items:
        print("no test command found at the repository root or one level down.", file=sys.stderr)
        print("Tell the kit how to run your tests, either way:", file=sys.stderr)
        print("  1. one line in .agents/pipeline.yaml:", file=sys.stderr)
        print("       commands:", file=sys.stderr)
        print('         test: "cargo test --manifest-path backend/Cargo.toml && npm --prefix ui test"', file=sys.stderr)
        print("  2. or a script of yours, which the kit never overwrites: .agents/commands/test.sh", file=sys.stderr)
        return 1
    print(f"tests ({source}):")
    for folder, label, cmd in items:
        print(f"  - {folder:<18} {label:<10} {cmd}")
    if mode == "list":
        return 0
    worst = 0
    for folder, label, cmd in items:
        print(f"\n=== {folder} ({label}): {cmd}", flush=True)
        rc = subprocess.run(cmd, shell=True, cwd=root / folder).returncode
        if rc:
            print(f"=== FAILED ({rc}): {folder}", file=sys.stderr)
        worst = max(worst, rc)
    if len(items) > 1:
        print("\nall passed" if worst == 0 else "\nsome test commands failed", file=sys.stdout if worst == 0 else sys.stderr)
    return 1 if worst else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
