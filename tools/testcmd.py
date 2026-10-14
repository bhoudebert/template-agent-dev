#!/usr/bin/env python3
"""Find and run the project's own tests (stdlib only).

    python tools/testcmd.py list [--root DIR]            what would run, and why; runs nothing
    python tools/testcmd.py run [suite ...]              run all suites, or only the named ones
    python tools/testcmd.py init                         write .agents/tests.yaml from what was discovered

Resolution, first match wins:
  1. .agents/tests.yaml          declared suites (below). Yours: the kit neither ships nor updates it.
  2. `commands.test` in .agents/pipeline.yaml        one command line
  3. .agents/commands/test.sh                        a script of yours
  4. the repository root: Cargo.toml, go.mod, package.json (with a test script),
     pyproject.toml / pytest.ini / setup.cfg, pom.xml
  5. one level down (monorepos): every sub-folder with one of those markers
  6. the kit's own tests (tools/tests), only inside the kit repository
Nothing found is an error with instructions: "no tests" must never look like "tests pass".

.agents/tests.yaml:

    suites:
      - name: backend
        dir: backend                # default: the repository root
        run: cargo test
        env: [RUST_LOG=warn]        # optional
        timeout: 900                # seconds, optional
      - name: ui
        dir: ui
        run: npm test
      - name: e2e
        dir: ui
        run: npx playwright test
        manual: true                # only runs when named: mise run test e2e
        optional: true              # a failure is reported but does not fail the run
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import config
import miniyaml

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"node_modules", "target", "vendor", "dist", "build", "docs", "examples", "tools", "site", "openspec", "venv"}
TESTS_FILE = ".agents/tests.yaml"


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


def load_suites(root):
    """Suites declared in .agents/tests.yaml, or None when the file is absent. Raises ValueError if malformed."""
    p = Path(root) / TESTS_FILE
    if not p.exists():
        return None
    data = miniyaml.loads(p.read_text(encoding="utf-8")) or {}
    suites = data.get("suites")
    if not isinstance(suites, list) or not suites:
        raise ValueError(f"{TESTS_FILE}: expected a non-empty `suites:` list")
    out, seen = [], set()
    for i, s in enumerate(suites, 1):
        if not isinstance(s, dict) or not s.get("run"):
            raise ValueError(f"{TESTS_FILE}: suite #{i} needs a `run:` command")
        name = str(s.get("name") or f"suite{i}")
        if name in seen:
            raise ValueError(f"{TESTS_FILE}: duplicate suite name {name!r}")
        seen.add(name)
        env = s.get("env") or []
        env = env if isinstance(env, list) else [env]
        out.append({
            "name": name, "dir": str(s.get("dir") or "."), "run": str(s["run"]),
            "env": [str(e) for e in env], "timeout": int(s["timeout"]) if s.get("timeout") else None,
            "manual": bool(s.get("manual")), "optional": bool(s.get("optional")),
        })
    return out


def discover(root):
    root = Path(root)
    m = marker(root)
    if m:
        return "repository root", [{"name": m[0], "dir": ".", "run": m[1]}]
    found = []
    for d in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name not in SKIP):
        m = marker(d)
        if m:
            found.append({"name": d.name, "dir": d.name, "run": m[1], "label": m[0]})
    return ("auto-discovered one level down", found) if found else ("nothing found", [])


def plan(root=ROOT):
    """Return (source, [suite dict]) with name, dir, run, env, timeout, manual, optional."""
    root = Path(root)
    suites = load_suites(root)
    if suites is not None:
        return f"{TESTS_FILE} (yours)", suites
    base = {"env": [], "timeout": None, "manual": False, "optional": False}
    cmd = config.load(root).commands.get("test")
    if cmd:
        return "commands.test in .agents/pipeline.yaml", [dict(base, name="configured", dir=".", run=cmd)]
    script = root / ".agents" / "commands" / "test.sh"
    if script.exists():
        return ".agents/commands/test.sh (yours)", [dict(base, name="script", dir=".", run=f"sh {script.relative_to(root)}")]
    source, found = discover(root)
    if found:
        return source, [dict(base, **f) for f in found]
    if (root / "tools" / "tests").is_dir():
        return "the kit's own tests", [dict(base, name="unittest", dir=".", run="python3 -m unittest discover -s tools/tests")]
    return "nothing found", []


def run_suite(root, s):
    env = dict(os.environ)
    for e in s["env"]:
        k, _, v = e.partition("=")
        env[k] = v
    try:
        return subprocess.run(s["run"], shell=True, cwd=Path(root) / s["dir"], env=env, timeout=s["timeout"]).returncode
    except subprocess.TimeoutExpired:
        print(f"=== TIMEOUT after {s['timeout']}s: {s['name']}", file=sys.stderr)
        return 124


def init(root):
    p = Path(root) / TESTS_FILE
    if p.exists():
        print(f"{TESTS_FILE} already exists; edit it, or delete it to regenerate.", file=sys.stderr)
        return 1
    source, found = discover(root)
    if not found:
        print("nothing discovered to write; create the file by hand (see `python tools/testcmd.py --help`).", file=sys.stderr)
        return 1
    lines = [f"# Declared test suites. Yours: the kit never ships or updates this file. ({source})",
             "# Run all: mise run test    One: mise run test <name>    See the plan: sh tools/projecttest.sh list", "suites:"]
    for f in found:
        lines += [f"  - name: {f['name']}", f"    dir: {f['dir']}", f"    run: {f['run']}"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {TESTS_FILE}:")
    print("\n".join(lines))
    return 0


def main(argv):
    argv = list(argv)
    root = ROOT
    if "--root" in argv:
        i = argv.index("--root")
        root = Path(argv[i + 1]).expanduser().resolve()
        del argv[i:i + 2]
    mode = argv[0] if argv else "run"
    names = argv[1:] if mode == "run" else []
    if mode == "init":
        return init(root)
    try:
        source, suites = plan(root)
    except ValueError as e:
        print(f"{e}", file=sys.stderr)
        return 2
    if not suites:
        print("no test command found at the repository root or one level down.", file=sys.stderr)
        print("Tell the kit how to run your tests, any one of:", file=sys.stderr)
        print("  1. python3 tools/testcmd.py init     (writes .agents/tests.yaml from what it can see)", file=sys.stderr)
        print('  2. one line in .agents/pipeline.yaml:  commands: {test: "make check"}', file=sys.stderr)
        print("  3. a script of yours the kit never overwrites: .agents/commands/test.sh", file=sys.stderr)
        return 1
    unknown = [n for n in names if n not in {s["name"] for s in suites}]
    if unknown:
        print(f"unknown suite(s) {unknown}; available: {[s['name'] for s in suites]}", file=sys.stderr)
        return 2
    selected = [s for s in suites if (s["name"] in names if names else not s["manual"])]
    print(f"tests ({source}):")
    for s in suites:
        tag = "" if s in selected else "   [not selected]"
        flags = " ".join(f for f in ("manual" if s["manual"] else "", "optional" if s["optional"] else "") if f)
        print(f"  - {s['name']:<14} {s['dir']:<12} {s['run']}{('   (' + flags + ')') if flags else ''}{tag}")
    if mode == "list":
        return 0
    failed, tolerated = [], []
    for s in selected:
        print(f"\n=== {s['name']} ({s['dir']}): {s['run']}", flush=True)
        rc = run_suite(root, s)
        if rc:
            print(f"=== FAILED ({rc}): {s['name']}" + (" [optional]" if s["optional"] else ""), file=sys.stderr)
            (tolerated if s["optional"] else failed).append(s["name"])
    if len(selected) > 1 or tolerated:
        ok = [s["name"] for s in selected if s["name"] not in failed + tolerated]
        print(f"\npassed: {', '.join(ok) or 'none'}"
              + (f"\nfailed (optional, ignored): {', '.join(tolerated)}" if tolerated else "")
              + (f"\nFAILED: {', '.join(failed)}" if failed else ""),
              file=sys.stderr if failed else sys.stdout)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
