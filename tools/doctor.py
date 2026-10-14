#!/usr/bin/env python3
"""Check the local setup and say what is missing (stdlib only)."""
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    bad = 0

    def row(ok, label, hint=""):
        nonlocal bad
        bad += 0 if ok else 1
        print(f"[{'ok' if ok else '!!'}] {label}" + (f"  -> {hint}" if hint and not ok else ""))

    row(sys.version_info >= (3, 10), f"python {sys.version.split()[0]}", "need >= 3.10")
    git = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT, capture_output=True, text=True)
    row(git.returncode == 0, "git repository", "run: git init && git add -A && git commit -m init  (needed for @diff)")
    for rel in ("AGENTS.md", "CONTEXT.md", ".agents/pipeline.yaml"):
        row((ROOT / rel).exists(), rel)

    provider = os.environ.get("AGENT_PROVIDER", "openai")
    print(f"provider: {provider}")
    if provider == "cmd":
        cmd = os.environ.get("AGENT_CMD", "")
        row(bool(cmd) and shutil.which(cmd.split()[0]) is not None, f"AGENT_CMD={cmd!r}", "set AGENT_CMD to an installed CLI")
    elif provider == "openai":
        model = os.environ.get("AGENT_MODEL") or os.environ.get("AGENT_MODEL_STRONG")
        row(bool(model), f"model={model!r}", "set AGENT_MODEL in .env")
        base = os.environ.get("AGENT_BASE_URL", "http://localhost:11434/v1").rstrip("/")
        try:
            with urllib.request.urlopen(f"{base}/models", timeout=3) as r:
                ids = [m.get("id") for m in json.load(r).get("data", [])]
            row(True, f"endpoint {base} reachable")
            wanted = {m for m in (model, os.environ.get("AGENT_MODEL_STRONG"), os.environ.get("AGENT_MODEL_CHEAP")) if m}
            for m in sorted(wanted):
                row(m in ids, f"model {m!r} served", f"available: {ids[:8]}; set AGENT_MODEL in .env")
        except Exception as e:  # noqa: BLE001 - any failure means unreachable
            row(False, f"endpoint {base} reachable", f"{type(e).__name__}: start your server or fix AGENT_BASE_URL")
    print("all good" if not bad else f"{bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
