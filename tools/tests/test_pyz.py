import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "tests"))

import build_pyz  # noqa: E402
import json  # noqa: E402
from test_agentkit import git, host_repo, kit_copy  # noqa: E402


def run(args, cwd=None):
    return subprocess.run([sys.executable, *map(str, args)], cwd=cwd, text=True, capture_output=True)


class Zipapp(unittest.TestCase):
    def test_release_asset_installs_updates_and_explains_itself(self):
        out = Path(tempfile.mkdtemp())
        v1 = out / "v1.pyz"
        digest, n = build_pyz.build("1.0.0", v1)
        self.assertGreater(n, 50)
        self.assertEqual((out / "v1.pyz.sha256").read_text().split()[0], digest)

        d = host_repo()
        r = run([v1, "install", "--target", d, "--with", "ci"])
        self.assertEqual(r.returncode, 0, r.stderr)
        lock = json.loads((d / ".agentkit/lock.json").read_text())
        self.assertEqual(lock["version"], "1.0.0")
        self.assertEqual(lock["source"], "release:1.0.0")
        self.assertTrue((d / "tools/agentrun.py").exists())
        git(d, "switch", "-q", "main"); git(d, "merge", "-q", "--ff-only", "chore/agentkit-install")

        # the adopting repo has no kit beside its own copy of the engine: status still works locally
        r = run(["tools/agentkit.py", "status"], cwd=d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("kit changes cannot be shown", r.stdout)
        # ...and update explains what to do instead of failing obscurely
        r = run(["tools/agentkit.py", "update"], cwd=d)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("run the newer `agentkit`", r.stderr)

        # a newer release carries a newer payload: no clone, no network
        def release(k):
            (k / "tools/validate.py").write_text((k / "tools/validate.py").read_text() + "\n# 1.1.0\n")
        v2 = out / "v2.pyz"
        build_pyz.build("1.1.0", v2, root=kit_copy(release))
        r = run([v2, "update", "--target", d])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("# 1.1.0", (d / "tools/validate.py").read_text())
        self.assertEqual(json.loads((d / ".agentkit/lock.json").read_text())["version"], "1.1.0")
        self.assertTrue(git(d, "branch", "--show-current").stdout.startswith("chore/agentkit-update-1.1.0"))

    def test_zipapp_is_executable_and_self_describing(self):
        out = Path(tempfile.mkdtemp()) / "a.pyz"
        build_pyz.build("0.0.1", out)
        self.assertTrue(out.stat().st_mode & 0o111)
        r = subprocess.run([str(out), "--help"], text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("install", r.stdout)


if __name__ == "__main__":
    unittest.main()
