import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "tests"))

import agentrun  # noqa: E402
import config  # noqa: E402
import evidence  # noqa: E402
import index  # noqa: E402
import items  # noqa: E402
import orient  # noqa: E402
import trace_check  # noqa: E402
import validate  # noqa: E402
from test_tools import sandbox  # noqa: E402


def custom_project(extra_ids="", extra_paths=""):
    """A sandbox whose pipeline.yaml renames the story prefix and moves two folders."""
    import shutil
    d = sandbox()
    for rel in ("docs/stories", "docs/architecture", "docs/decisions", "openspec/changes"):   # a fresh project
        shutil.rmtree(d / rel, ignore_errors=True)
    p = d / ".agents" / "pipeline.yaml"
    head = ("ids:\n  story: PROJ\n" + extra_ids +
            "paths:\n  stories: specs/stories\n  decisions: docs/adr\n  changes: spec-changes\n  specs: specs/current\n"
            + extra_paths)
    p.write_text(head + p.read_text())
    config._CACHE.clear()
    return d


class Defaults(unittest.TestCase):
    def test_stock_layout_is_unchanged(self):
        cfg = config.Config(sandbox())
        self.assertEqual(cfg.prefix("story"), "US")
        self.assertEqual(cfg.path("stories"), "docs/stories")
        self.assertEqual(cfg.format_id("story", 7), "US-007")
        self.assertEqual(cfg.format_id("adr", 3), "ADR-0003")
        self.assertTrue(cfg.is_kind("story", "US-12345"))      # any number of digits
        self.assertFalse(cfg.is_kind("story", "PROJ-12"))
        self.assertEqual(cfg.kind_of("INC-004"), "incident")


class TestCommand(unittest.TestCase):
    def test_a_configured_test_command_wins_and_a_missing_one_says_so(self):
        import shutil
        d = Path(tempfile.mkdtemp())
        (d / "tools").mkdir()
        for n in ("config.py", "miniyaml.py", "projecttest.sh"):
            shutil.copy(ROOT / "tools" / n, d / "tools" / n)
        (d / ".agents").mkdir()
        (d / ".agents/pipeline.yaml").write_text("commands:\n  test: \"echo RAN-CONFIGURED\"\nstages: []\n")
        r = subprocess.run(["sh", "tools/projecttest.sh"], cwd=d, text=True, capture_output=True)
        self.assertEqual(r.stdout.strip(), "RAN-CONFIGURED")
        (d / ".agents/pipeline.yaml").write_text("stages: []\n")
        r = subprocess.run(["sh", "tools/projecttest.sh"], cwd=d, text=True, capture_output=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("commands:", r.stderr)


class CustomPrefixAndPaths(unittest.TestCase):
    def setUp(self):
        config._CACHE.clear()

    def tearDown(self):
        config._CACHE.clear()

    def test_new_allocates_with_the_prefix_in_the_configured_folder(self):
        d = custom_project()
        sid, path = items.new_story("Export invoices", root=d, text="Finance wants a CSV export of invoices.")
        self.assertEqual(sid, "PROJ-001")
        self.assertEqual(path, d / "specs/stories/PROJ-001.md")
        sid2, _ = items.new_story("Second", root=d, text="Another request, long enough to count.")
        self.assertEqual(sid2, "PROJ-002")

    def test_adopt_an_external_key(self):
        d = custom_project()
        sid, path = items.new_story("From Jira", root=d, text="Imported from the tracker with its key.", explicit_id="PROJ-4821")
        self.assertEqual(sid, "PROJ-4821")
        self.assertEqual(path.name, "PROJ-4821.md")
        with self.assertRaises(SystemExit):
            items.new_story("again", root=d, explicit_id="PROJ-4821")      # exists
        with self.assertRaises(SystemExit):
            items.new_story("wrong", root=d, explicit_id="US-1")           # not this project's format

    def test_free_form_pattern_accepts_any_tracker_key(self):
        d = custom_project(extra_ids='  story_pattern: "[A-Z][A-Z0-9]+-[0-9]+"\n')
        sid, _ = items.new_story("Other board", root=d, text="Work tracked on another Jira board.", explicit_id="PLAT-99017")
        self.assertEqual(sid, "PLAT-99017")

    def test_validate_trace_and_index_follow_the_config(self):
        d = custom_project()
        items.new_story("Export invoices", root=d, text="Finance wants a CSV export of invoices.")
        p = d / "specs/stories/PROJ-001.md"
        self.assertEqual(validate.check_file(p, d), [])                    # id pattern comes from the config
        p.write_text(p.read_text().replace("status: draft", "status: specified"))
        self.assertTrue(any("spec-changes/PROJ-001/ missing" in e for e in trace_check.check(d)))
        (d / "spec-changes/PROJ-001").mkdir(parents=True)
        self.assertEqual(trace_check.check(d), [])
        text = index.build(d)
        self.assertIn("PROJ-001", text)
        self.assertIn("specs/stories/PROJ-001.md", text)

    def test_a_default_prefixed_story_is_now_rejected(self):
        d = custom_project()
        bad = d / "specs/stories/US-001.md"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("---\nid: US-001\ntype: story\ntitle: x\nstatus: draft\nowner: po\n---\nraw request here\n")
        self.assertTrue(any("does not match" in e for e in validate.check_file(bad, d)))

    def test_evidence_and_orient_find_the_id_in_a_branch_name(self):
        d = custom_project()
        self.assertEqual(evidence.story_id(d, branch="feature/PROJ-4821-export"), "PROJ-4821")
        self.assertIsNone(evidence.story_id(d, branch="feature/US-12-old"))
        import re
        self.assertEqual(re.search(config.load(d).regex("any"), "fix/PROJ-7-x").group(0), "PROJ-7")

    def test_pipeline_globs_are_rewritten_to_the_configured_folders(self):
        d = custom_project()
        stage = agentrun.find_stage(agentrun.load_pipeline(d), "story")
        self.assertEqual(stage["out"], ["specs/stories/{id}.md"])
        design = agentrun.find_stage(agentrun.load_pipeline(d), "design")
        self.assertIn("docs/adr/ADR-*.md", design["out"])
        spec = agentrun.find_stage(agentrun.load_pipeline(d), "spec")
        self.assertEqual(spec["out"], ["spec-changes/{id}/**"])

    def test_shell_helpers_print_posix_regex_and_paths(self):
        d = custom_project()
        (d / "tools").mkdir(exist_ok=True)
        for n in ("config.py", "miniyaml.py"):
            (d / "tools" / n).write_text((ROOT / "tools" / n).read_text())
        out = subprocess.run([sys.executable, "tools/config.py", "regex", "story"], cwd=d, text=True, capture_output=True).stdout.strip()
        self.assertIn("PROJ-[0-9]", out)
        self.assertNotIn("(?:", out)
        r = subprocess.run(["grep", "-oE", out], input="feature/PROJ-4821-x", text=True, capture_output=True)
        self.assertEqual(r.stdout.strip(), "PROJ-4821")
        p = subprocess.run([sys.executable, "tools/config.py", "path", "stories"], cwd=d, text=True, capture_output=True).stdout.strip()
        self.assertEqual(p, "specs/stories")


if __name__ == "__main__":
    unittest.main()
