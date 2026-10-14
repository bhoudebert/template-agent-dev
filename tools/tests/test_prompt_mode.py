import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "tests"))

import index  # noqa: E402
import items  # noqa: E402
import orient  # noqa: E402
import promptmode  # noqa: E402
import trace_check  # noqa: E402
import validate  # noqa: E402
from test_tools import sandbox  # noqa: E402

QA = ("---\ntype: qa-report\nstory: US-001\nverdict: pass\ndate: 2026-10-14\n---\n"
      "## Summary\nok\n## Traceability\nall covered\n## Findings\nnone\n## Not verified\nNothing\n")


def git(d, *a):
    return subprocess.run(["git", "-C", str(d), "-c", "user.name=T", "-c", "user.email=t@example.com", *a],
                          check=True, capture_output=True, text=True)


def repo():
    d = sandbox()
    git(d, "init", "-q", "-b", "main")
    git(d, "add", "-A")
    git(d, "commit", "-q", "-m", "init")
    return d


class Receipt(unittest.TestCase):
    def test_prepare_writes_bundle_with_recipe_and_receipt(self):
        d = repo()
        out, code, stage, out_globs, _ = promptmode.prepare("qa", "US-001", d)
        text = out.read_text()
        self.assertIn("# Role: QA", text)                     # the bible is inlined, not referenced
        self.assertIn("policy: security.md", text)
        self.assertIn('<input path="docs/INDEX.md">', text)   # the knowledge map is always present
        self.assertTrue(text.rstrip().endswith(f"RECEIPT: {code}"))
        self.assertEqual(out_globs, ["docs/qa/US-001.md"])

    def test_apply_refuses_without_or_with_wrong_receipt(self):
        d = repo()
        code, msgs = promptmode.apply("qa", "US-001", "x", response="-", root=d)
        self.assertEqual(code, promptmode.EXIT_RECEIPT)       # nothing prepared
        promptmode.prepare("qa", "US-001", d)
        resp = d / "r.txt"
        resp.write_text(f"<<<FILE: docs/qa/US-001.md>>>\n{QA}<<<END>>>\n")
        code, msgs = promptmode.apply("qa", "US-001", "deadbeef", response=str(resp), root=d)
        self.assertEqual(code, promptmode.EXIT_RECEIPT)
        self.assertFalse((d / "docs/qa/US-001.md").exists())

    def test_stale_receipt_when_the_recipe_changed(self):
        d = repo()
        _, code, *_ = promptmode.prepare("qa", "US-001", d)
        (d / "AGENTS.md").write_text((d / "AGENTS.md").read_text() + "\nNew rule.\n")
        resp = d / "r.txt"
        resp.write_text(f"<<<FILE: docs/qa/US-001.md>>>\n{QA}<<<END>>>\n")
        rc, msgs = promptmode.apply("qa", "US-001", code, response=str(resp), root=d)
        self.assertEqual(rc, promptmode.EXIT_RECEIPT)
        self.assertTrue(any("recipe changed" in m for m in msgs))

    def test_apply_response_writes_only_allowed_paths_and_validates(self):
        d = repo()
        _, code, *_ = promptmode.prepare("qa", "US-001", d)
        resp = d / "r.txt"
        resp.write_text(f"<<<FILE: docs/qa/US-001.md>>>\n{QA}<<<END>>>\n<<<FILE: src/evil.js>>>\nx\n<<<END>>>\n")
        rc, msgs = promptmode.apply("qa", "US-001", code, response=str(resp), root=d)
        self.assertEqual(rc, 0, msgs)
        self.assertTrue((d / "docs/qa/US-001.md").exists())
        self.assertFalse((d / "src/evil.js").exists())
        self.assertTrue(any("REJECTED" in m for m in msgs))

    def test_worktree_mode_accepts_in_scope_and_rejects_out_of_scope(self):
        d = repo()
        _, code, *_ = promptmode.prepare("qa", "US-001", d)
        (d / "docs/qa").mkdir(parents=True, exist_ok=True)
        (d / "docs/qa/US-001.md").write_text(QA)
        rc, msgs = promptmode.apply("qa", "US-001", code, worktree=True, root=d)
        self.assertEqual(rc, 0, msgs)
        (d / "src").mkdir(exist_ok=True)
        (d / "src/sneaky.js").write_text("x")
        rc, msgs = promptmode.apply("qa", "US-001", code, worktree=True, root=d)
        self.assertEqual(rc, promptmode.EXIT_SCOPE)
        self.assertTrue(any("src/sneaky.js" in m for m in msgs))

    def test_preexisting_dirty_files_are_not_blamed(self):
        d = repo()
        (d / "notes.txt").write_text("mine")                  # dirty before prepare
        _, code, *_ = promptmode.prepare("qa", "US-001", d)
        (d / "docs/qa").mkdir(parents=True, exist_ok=True)
        (d / "docs/qa/US-001.md").write_text(QA)
        rc, msgs = promptmode.apply("qa", "US-001", code, worktree=True, root=d)
        self.assertEqual(rc, 0, msgs)


class Index(unittest.TestCase):
    def test_index_is_deterministic_and_lists_what_exists(self):
        d = sandbox()
        a, b = index.build(d), index.build(d)
        self.assertEqual(a, b)
        self.assertIn("US-001", a)
        self.assertIn("ADR-0001", a)
        self.assertIn("Not every story needs", a)

    def test_empty_project_has_empty_sections_not_errors(self):
        d = Path(tempfile.mkdtemp())
        text = index.build(d)
        self.assertIn("None yet.", text)

    def test_committed_index_is_current(self):
        proc = subprocess.run([sys.executable, str(ROOT / "tools/index.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


class Skip(unittest.TestCase):
    def story(self, d, **extra):
        p = d / "docs/stories/US-001.md"
        t = p.read_text()
        fm = "".join(f"{k}: {v}\n" for k, v in extra.items())
        p.write_text(t.replace("status: designed\n", "status: designed\n" + fm, 1))
        return p

    def drop_design_artifacts(self, d):
        (d / "docs/architecture/US-001.md").unlink()
        for adr in (d / "docs/decisions").glob("ADR-*.md"):
            adr.unlink()

    def test_design_required_unless_skipped(self):
        d = sandbox()
        self.drop_design_artifacts(d)
        self.assertTrue(any("no ADR/design" in e for e in trace_check.check(d)))
        self.story(d, skip="[design]", skip_reason="copy change")
        self.assertEqual(trace_check.check(d), [])

    def test_skip_needs_a_reason_and_known_stages(self):
        d = sandbox()
        p = self.story(d, skip="[design]")
        self.assertTrue(any("skip_reason" in e for e in validate.check_file(p, d)))
        d = sandbox()
        p = self.story(d, skip="[qa]", skip_reason="x")
        self.assertTrue(any("only contain spec and design" in e for e in validate.check_file(p, d)))

    def test_advance_may_jump_skipped_statuses_only(self):
        d = sandbox()
        p = d / "docs/stories/US-001.md"
        p.write_text(p.read_text().replace("status: designed", "status: approved"))
        with self.assertRaises(SystemExit):
            items.set_status("US-001", "implemented", root=d)       # skips spec and design, not declared
        p.write_text(p.read_text().replace("status: approved\n",
                                           "status: approved\nskip: [spec, design]\nskip_reason: copy tweak\n", 1))
        shutil_ok = items.set_status("US-001", "implemented", root=d)
        self.assertEqual(shutil_ok, ("approved", "implemented"))


class Next(unittest.TestCase):
    def test_next_action(self):
        who, text = orient.next_action("US-1", {"status": "enriched"})
        self.assertEqual(who, "you")
        self.assertIn("advance US-1 approved", text)
        who, text = orient.next_action("US-1", {"status": "approved"})
        self.assertEqual(who, "agent")
        self.assertIn("prepare spec US-1", text)
        who, text = orient.next_action("US-1", {"status": "approved", "skip": ["spec", "design"], "skip_reason": "tiny"})
        self.assertEqual(who, "you")
        self.assertIn("advance US-1 designed", text)
        self.assertIn("mise run implement US-1", text)


if __name__ == "__main__":
    unittest.main()
