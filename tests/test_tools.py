import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import agentrun  # noqa: E402
import miniyaml  # noqa: E402
import trace_check  # noqa: E402
import validate  # noqa: E402


def sandbox():
    """Copy the repo skeleton (no .git/runs) to a temp dir."""
    tmp = Path(tempfile.mkdtemp())
    for name in (".agents", "docs", "openspec", "AGENTS.md", "CONTEXT.md"):
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, tmp / name, ignore=shutil.ignore_patterns("runs", "out"))
        else:
            shutil.copy(src, tmp / name)
    (tmp / "src").mkdir()
    (tmp / "tests").mkdir()
    return tmp


class MiniYaml(unittest.TestCase):
    def test_pipeline_shape(self):
        data = miniyaml.loads((ROOT / ".agents/pipeline.yaml").read_text())
        names = [s["name"] for s in data["stages"]]
        self.assertEqual(names[0], "story")
        self.assertIn("diagnose", names)
        spec = data["stages"][1]
        self.assertEqual(spec["out"], ["openspec/changes/{id}/**"])
        self.assertEqual(spec["skills"], ["write-openspec"])

    def test_scalars_and_comments(self):
        d = miniyaml.loads("a: 1\nb: true # c\nc: 'x: y'\nd: [1, two, \"3\"]\ne:\n  - k: v\n    n: 2\n  - plain\n")
        self.assertEqual(d, {"a": 1, "b": True, "c": "x: y", "d": [1, "two", "3"], "e": [{"k": "v", "n": 2}, "plain"]})

    def test_frontmatter(self):
        meta, body = miniyaml.split_frontmatter("---\nid: US-1\n---\n## Hi\n")
        self.assertEqual(meta, {"id": "US-1"})
        self.assertEqual(body, "## Hi\n")
        self.assertIsNone(miniyaml.split_frontmatter("no front")[0])


class Validate(unittest.TestCase):
    def test_example_repo_clean(self):
        self.assertEqual(validate.scan(ROOT), [])
        self.assertEqual(trace_check.check(ROOT), [])

    def test_story_missing_section_and_bad_status(self):
        tmp = sandbox()
        p = tmp / "docs/stories/US-001.md"
        p.write_text(p.read_text().replace("## Edge cases", "## Misc").replace("status: designed", "status: wat"))
        errs = validate.check_file(p, tmp)
        self.assertTrue(any("Edge cases" in e for e in errs))
        self.assertTrue(any("status" in e for e in errs))

    def test_acceptance_needs_gwt(self):
        tmp = sandbox()
        p = tmp / "docs/stories/US-001.md"
        text = p.read_text()
        start = text.index("## Acceptance criteria")
        end = text.index("## Edge cases")
        p.write_text(text[:start] + "## Acceptance criteria\n- It works.\n\n" + text[end:])
        self.assertTrue(any("Acceptance criteria" in e for e in validate.check_file(p, tmp)))

    def test_raw_draft_story_only_checks_frontmatter(self):
        tmp = sandbox()
        p = tmp / "docs/stories/US-002.md"
        p.write_text("---\nid: US-002\ntype: story\ntitle: Raw\nstatus: draft\nowner: po\n---\nmake it faster\n")
        self.assertEqual(validate.check_file(p, tmp), [])

    def test_change_requires_scenarios(self):
        tmp = sandbox()
        spec = tmp / "openspec/changes/US-001/specs/password-reset/spec.md"
        spec.write_text("## ADDED Requirements\n### Requirement: x\nThe system SHALL y.\n")
        errs = validate.check_change(tmp / "openspec/changes/US-001", tmp)
        self.assertTrue(any("Scenario" in e for e in errs))

    def test_trace_done_needs_qa(self):
        tmp = sandbox()
        p = tmp / "docs/stories/US-001.md"
        p.write_text(p.read_text().replace("status: designed", "status: done"))
        errs = trace_check.check(tmp)
        self.assertTrue(any("no qa-report" in e for e in errs))

    def test_trace_orphan_adr(self):
        tmp = sandbox()
        adr = next((tmp / "docs/decisions").glob("ADR-0001*.md"))
        adr.write_text(adr.read_text().replace("story: US-001", "story: US-999"))
        self.assertTrue(any("US-999" in e for e in trace_check.check(tmp)))


class Runner(unittest.TestCase):
    RESP = (
        "notes\n<<<FILE: docs/qa/US-001.md>>>\n---\ntype: qa-report\nstory: US-001\nverdict: pass\ndate: 2026-10-14\n---\n"
        "## Summary\nok\n## Traceability\nall\n## Findings\nnone\n## Not verified\nNothing\n<<<END>>>\n"
        "<<<FILE: ../evil.txt>>>\nx\n<<<END>>>\n<<<FILE: src/app.py>>>\nx\n<<<END>>>\n"
    )

    def test_parse_files_filters_paths(self):
        ok, bad = agentrun.parse_files(self.RESP, ["docs/qa/US-001.md"])
        self.assertEqual(list(ok), ["docs/qa/US-001.md"])
        self.assertEqual(sorted(bad), ["../evil.txt", "src/app.py"])

    def test_prompt_wraps_inputs_and_contract(self):
        stage = agentrun.find_stage(agentrun.load_pipeline(ROOT), "qa")
        system, user, out = agentrun.build_prompt(stage, "US-001", ROOT)
        self.assertIn("Role: QA", system)
        self.assertIn("policy: security.md", system)
        self.assertIn('<input path="docs/stories/US-001.md">', user)
        self.assertEqual(out, ["docs/qa/US-001.md"])

    def test_end_to_end_cmd_provider(self):
        tmp = sandbox()
        fixture = tmp / "resp.txt"
        fixture.write_text(self.RESP)
        env = dict(os.environ, AGENT_PROVIDER="cmd", AGENT_CMD=f"cat {fixture}")
        old = os.environ.copy()
        os.environ.update(env)
        try:
            args = agentrun.argparse.Namespace(stage="qa", id="US-001", provider=None, apply=True, dry_run=False)
            rc = agentrun.cmd_run(args, tmp)
        finally:
            os.environ.clear()
            os.environ.update(old)
        self.assertEqual(rc, 0)
        self.assertTrue((tmp / "docs/qa/US-001.md").exists())
        self.assertFalse((tmp / "src/app.py").exists())
        self.assertFalse((tmp.parent / "evil.txt").exists())


if __name__ == "__main__":
    unittest.main()
