import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import testcmd  # noqa: E402


def project(**files):
    d = Path(tempfile.mkdtemp())
    (d / ".agents").mkdir()
    (d / ".agents/pipeline.yaml").write_text("stages: []\n")
    for rel, content in files.items():
        p = d / rel.replace("__", "/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return d


def run_cli(d, *args):
    return subprocess.run([sys.executable, str(ROOT / "tools/testcmd.py"), *args, "--root", str(d)],
                          text=True, capture_output=True)


class Discovery(unittest.TestCase):
    def labels(self, d):
        src, items = testcmd.plan(d)
        return src, [(f, l) for f, l, _ in items]

    def test_root_marker(self):
        src, items = self.labels(project(**{"Cargo.toml": "[package]\n"}))
        self.assertEqual(items, [(".", "cargo")])
        self.assertEqual(src, "repository root")

    def test_monorepo_one_level_down(self):
        d = project(**{"backend__Cargo.toml": "[workspace]\n",
                       "ui__package.json": json.dumps({"scripts": {"test": "vitest run"}}),
                       "docs__package.json": json.dumps({"scripts": {"test": "x"}}),       # skipped folder
                       "node_modules__pkg__package.json": json.dumps({"scripts": {"test": "x"}})})
        src, items = self.labels(d)
        self.assertEqual(items, [("backend", "cargo"), ("ui", "npm")])
        self.assertIn("one level down", src)

    def test_npm_without_a_real_test_script_is_not_a_test_setup(self):
        d = project(**{"ui__package.json": json.dumps({"scripts": {"test": 'echo "Error: no test specified" && exit 1'}})})
        self.assertEqual(testcmd.plan(d)[1], [])

    def test_root_marker_wins_over_subfolders(self):
        d = project(**{"go.mod": "module x\n", "svc__Cargo.toml": "[package]\n"})
        self.assertEqual(self.labels(d)[1], [(".", "go")])

    def test_configured_command_wins_over_everything(self):
        d = project(**{"Cargo.toml": "[package]\n"})
        (d / ".agents/pipeline.yaml").write_text('commands:\n  test: "make check"\nstages: []\n')
        src, items = testcmd.plan(d)
        self.assertEqual(items, [(".", "configured", "make check")])

    def test_project_script_beats_discovery_but_not_config(self):
        d = project(**{"Cargo.toml": "[package]\n", ".agents__commands__test.sh": "echo mine\n"})
        self.assertEqual(self.labels(d)[1], [(".", "script")])

    def test_nothing_found_is_an_error_with_instructions(self):
        d = project()
        r = run_cli(d, "list")
        self.assertEqual(r.returncode, 1)
        self.assertIn("commands:", r.stderr)
        self.assertIn(".agents/commands/test.sh", r.stderr)


class Running(unittest.TestCase):
    def test_runs_the_projects_script_and_propagates_failure(self):
        ok = project(**{".agents__commands__test.sh": "echo ran-ok\n"})
        r = run_cli(ok, "run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ran-ok", r.stdout)
        bad = project(**{".agents__commands__test.sh": "exit 3\n"})
        self.assertNotEqual(run_cli(bad, "run").returncode, 0)

    def test_every_discovered_project_runs_and_one_failure_fails_the_run(self):
        d = project(**{"a__package.json": json.dumps({"scripts": {"test": "node -e 0"}}),
                       "b__package.json": json.dumps({"scripts": {"test": "node -e 0"}})})
        src, items = testcmd.plan(d)
        self.assertEqual([i[0] for i in items], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
