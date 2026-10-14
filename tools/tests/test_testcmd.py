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
        return src, [(s["dir"], s.get("label", s["name"])) for s in items]

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
        self.assertEqual([(s["name"], s["run"]) for s in items], [("configured", "make check")])

    def test_project_script_beats_discovery_but_not_config(self):
        d = project(**{"Cargo.toml": "[package]\n", ".agents__commands__test.sh": "echo mine\n"})
        self.assertEqual(self.labels(d)[1], [(".", "script")])

    def test_nothing_found_is_an_error_with_instructions(self):
        d = project()
        r = run_cli(d, "list")
        self.assertEqual(r.returncode, 1)
        self.assertIn("commands", r.stderr)
        self.assertIn(".agents/commands/test.sh", r.stderr)
        self.assertIn("init", r.stderr)


class DeclaredSuites(unittest.TestCase):
    YAML = ("suites:\n"
            "  - name: backend\n    dir: backend\n    run: echo backend-ran\n    env: [GREETING=hi]\n"
            "  - name: ui\n    dir: ui\n    run: echo ui-ran\n"
            "  - name: e2e\n    dir: ui\n    run: exit 7\n    manual: true\n    optional: true\n")

    def proj(self):
        d = project(**{"backend__x": "", "ui__x": "", "Cargo.toml": "[package]\n"})
        (d / ".agents/tests.yaml").write_text(self.YAML)
        return d

    def test_declared_suites_beat_discovery_and_config(self):
        d = self.proj()
        (d / ".agents/pipeline.yaml").write_text('commands:\n  test: "echo configured"\nstages: []\n')
        src, suites = testcmd.plan(d)
        self.assertIn("tests.yaml", src)
        self.assertEqual([s["name"] for s in suites], ["backend", "ui", "e2e"])

    def test_default_run_skips_manual_and_runs_each_in_its_folder(self):
        d = self.proj()
        r = run_cli(d, "run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("backend-ran", r.stdout)
        self.assertIn("ui-ran", r.stdout)
        self.assertIn("[not selected]", r.stdout)           # e2e is manual

    def test_named_suite_runs_alone_and_an_optional_failure_does_not_fail_the_run(self):
        d = self.proj()
        r = run_cli(d, "run", "e2e")
        self.assertEqual(r.returncode, 0, r.stderr)           # optional: reported, tolerated
        self.assertIn("FAILED (7)", r.stderr)
        self.assertNotIn("=== backend", r.stdout)         # not executed (it is only listed)
        self.assertIn("=== e2e", r.stdout)

    def test_a_required_failure_fails_and_names_the_suite(self):
        d = self.proj()
        (d / ".agents/tests.yaml").write_text("suites:\n  - name: api\n    run: exit 2\n  - name: ui\n    run: echo ok\n")
        r = run_cli(d, "run")
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAILED: api", r.stderr)
        self.assertIn("ok", r.stdout)                          # the others still ran

    def test_unknown_suite_and_malformed_file_are_clear_errors(self):
        d = self.proj()
        r = run_cli(d, "run", "nope")
        self.assertEqual(r.returncode, 2)
        self.assertIn("available", r.stderr)
        (d / ".agents/tests.yaml").write_text("suites:\n  - name: x\n")
        r = run_cli(d, "list")
        self.assertEqual(r.returncode, 2)
        self.assertIn("needs a `run:`", r.stderr)

    def test_env_and_timeout(self):
        d = project()
        (d / ".agents/tests.yaml").write_text(
            "suites:\n  - name: env\n    run: test \"$GREETING\" = hi\n    env: [GREETING=hi]\n"
            "  - name: slow\n    run: sleep 5\n    timeout: 1\n    optional: true\n")
        r = run_cli(d, "run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("TIMEOUT", r.stderr)

    def test_init_writes_a_file_from_discovery_and_will_not_overwrite(self):
        d = project(**{"backend__Cargo.toml": "[workspace]\n",
                       "ui__package.json": json.dumps({"scripts": {"test": "vitest run"}})})
        r = run_cli(d, "init")
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (d / ".agents/tests.yaml").read_text()
        self.assertIn("name: backend", text)
        self.assertIn("run: npm test", text)
        self.assertEqual(run_cli(d, "init").returncode, 1)
        self.assertEqual(testcmd.plan(d)[0], ".agents/tests.yaml (yours)")


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
        self.assertEqual([s["name"] for s in items], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
