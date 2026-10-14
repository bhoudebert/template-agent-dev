#!/usr/bin/env python3
"""Build agentkit.pyz: one executable file holding the engine and the exact kit payload (stdlib only).

    python tools/build_pyz.py [--version 0.2.0] [--out dist/agentkit.pyz]

The payload is every file any feature of kit.json can install, so `agentkit install` / `update`
need no network and a given release always installs the same files.
"""
import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import agentkit  # noqa: E402

MAIN = '''import agentkit

agentkit.cli_entry()
'''


def build(version, out, root=ROOT):
    root, out = Path(root), Path(out)
    kit = agentkit.Kit(root)
    sources = {e["src"] for e in kit.entries(sorted(kit.manifest["features"]))}
    sources |= {"kit.json", ".agents/roles/integrator.md"}
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        for name in ("agentkit.py", "providers.py"):
            shutil.copy(root / "tools" / name, stage / name)
        (stage / "__main__.py").write_text(MAIN, encoding="utf-8")
        payload = stage / "payload"
        for rel in sorted(sources):
            dst = payload / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(root / rel, dst)
        (payload / "VERSION").write_text(version + "\n", encoding="utf-8")
        out.parent.mkdir(parents=True, exist_ok=True)
        zipapp.create_archive(stage, out, interpreter="/usr/bin/env python3", compressed=True)
    out.chmod(out.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    Path(str(out) + ".sha256").write_text(f"{digest}  {out.name}\n", encoding="utf-8")
    return digest, len(sources)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--version")
    ap.add_argument("--out", default="dist/agentkit.pyz")
    a = ap.parse_args(argv)
    version = a.version
    if not version:
        p = ROOT / ".release-please-manifest.json"
        version = json.loads(p.read_text())["."] if p.exists() else "0.0.0"
    digest, n = build(version, a.out)
    print(f"built {a.out} ({n} payload files, version {version})\nsha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
