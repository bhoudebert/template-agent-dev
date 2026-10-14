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
        self.assertTrue(any("may only contain spec, design and tests" in e for e in validate.check_file(p, d)))

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


class SkipHelper(unittest.TestCase):
    def test_set_skip_writes_keys_that_validate_and_advance_works(self):
        d = Path(tempfile.mkdtemp())
        import shutil
        shutil.copytree(ROOT / ".agents", d / ".agents")
        sid, path = items.new_story("Fix a typo", root=d, text="Fix the typo on the pricing page heading.")
        with self.assertRaises(SystemExit):
            items.set_skip(sid, ["spec", "design"], "", root=d)            # a reason is required
        with self.assertRaises(SystemExit):
            items.set_skip(sid, ["qa"], "x", root=d)                       # only spec/design
        items.set_skip(sid, ["spec", "design"], "copy fix, no behaviour change", root=d)
        text = path.read_text()
        self.assertIn("skip: [spec, design]", text)
        self.assertIn("skip_reason: copy fix, no behaviour change", text)
        self.assertEqual(validate.check_file(path, d), [])
        path.write_text(text.replace("status: draft", "status: approved"))
        self.assertEqual(items.set_status(sid, "implemented", root=d), ("approved", "implemented"))
        items.set_skip(sid, [], "", root=d)                                 # clear
        self.assertNotIn("skip", path.read_text())

    def test_rewrite_keeps_skip_keys_but_not_overrides(self):
        import agentrun
        old = "---\nid: US-1\ntype: story\nstatus: draft\nskip: [spec]\nskip_reason: tiny\n---\nraw\n"
        new = "---\nid: US-1\ntype: story\nstatus: enriched\n---\n## Story\nx\n"
        out = agentrun.preserve_keys(old, new)
        self.assertIn("skip: [spec]", out)
        self.assertIn("skip_reason: tiny", out)
        self.assertIn("status: enriched", out)
        self.assertTrue(out.endswith("## Story\nx\n"))
        mine = "---\nid: US-1\ntype: story\nskip: [design]\nskip_reason: other\n---\nb\n"
        self.assertEqual(agentrun.preserve_keys(old, mine), mine)           # never overwrite what the rewrite set

    def test_story_stage_response_keeps_skip(self):
        d = repo()
        p = d / "docs/stories/US-001.md"
        p.write_text(p.read_text().replace("status: designed\n", "status: designed\nskip: [design]\nskip_reason: tiny\n", 1))
        git(d, "add", "-A"); git(d, "commit", "-q", "-m", "skip")
        _, code, *_ = promptmode.prepare("story", "US-001", d)
        rewritten = p.read_text().replace("skip: [design]\n", "").replace("skip_reason: tiny\n", "")
        resp = d / "r.txt"
        resp.write_text(f"<<<FILE: docs/stories/US-001.md>>>\n{rewritten}<<<END>>>\n")
        rc, msgs = promptmode.apply("story", "US-001", code, response=str(resp), root=d)
        self.assertEqual(rc, 0, msgs)
        self.assertIn("skip: [design]", p.read_text())


class Evidence(unittest.TestCase):
    """The floor: a story at `implemented` must change a spec or a test, or waive tests."""

    def setup_repo(self, status="implemented", skip=""):
        import evidence
        self.ev = evidence
        d = Path(tempfile.mkdtemp())
        (d / "docs/stories").mkdir(parents=True)
        (d / "docs/stories/US-001.md").write_text(
            f"---\nid: US-001\ntype: story\ntitle: t\nstatus: {status}\nowner: po\n{skip}---\nbody\n")
        (d / "src").mkdir()
        (d / "src/app.js").write_text("a")
        git(d, "init", "-q", "-b", "main"); git(d, "add", "-A"); git(d, "commit", "-q", "-m", "init")
        git(d, "switch", "-q", "-c", "feature/US-001-x")
        return d

    def run_ev(self, d, extra_changes=()):
        for rel, content in extra_changes:
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_text(content)
        git(d, "add", "-A"); git(d, "commit", "-q", "-m", "change", "--allow-empty")
        files = self.ev.changed_files(d, "main")
        return self.ev.evaluate(d, "US-001", files)

    def test_code_only_fails_even_when_spec_and_design_are_skipped(self):
        d = self.setup_repo(skip="skip: [spec, design]\nskip_reason: tiny\n")
        ok, lines = self.run_ev(d, [("src/app.js", "b")])
        self.assertFalse(ok)
        self.assertIn("no spec and no test file changed", "\n".join(lines))

    def test_a_test_change_is_enough(self):
        d = self.setup_repo(skip="skip: [spec, design]\nskip_reason: tiny\n")
        ok, _ = self.run_ev(d, [("src/app.js", "b"), ("tests/app.test.js", "t")])
        self.assertTrue(ok)

    def test_a_spec_change_is_enough(self):
        d = self.setup_repo()
        ok, _ = self.run_ev(d, [("src/app.js", "b"), ("openspec/specs/api/spec.md", "## ADDED Requirements\n")])
        self.assertTrue(ok)

    def test_tests_waiver_for_docs_or_config_only(self):
        d = self.setup_repo(skip="skip: [tests]\nskip_reason: docs only\n")
        ok, lines = self.run_ev(d, [("docs/guide.md", "x")])
        self.assertTrue(ok)
        self.assertIn("waived", "\n".join(lines))

    def test_not_enforced_before_implemented(self):
        d = self.setup_repo(status="approved")
        ok, lines = self.run_ev(d, [("docs/stories/US-001.md", "---\nid: US-001\ntype: story\ntitle: t\nstatus: approved\nowner: po\n---\nmore\n")])
        self.assertTrue(ok)
        self.assertIn("informational", "\n".join(lines))

    def test_tests_waiver_needs_a_reason_via_validate(self):
        d = sandbox()
        p = d / "docs/stories/US-001.md"
        p.write_text(p.read_text().replace("status: designed\n", "status: designed\nskip: [tests]\n", 1))
        self.assertTrue(any("skip_reason" in e for e in validate.check_file(p, d)))


class Preflight(unittest.TestCase):
    def test_story_stage_refuses_an_empty_request(self):
        d = Path(tempfile.mkdtemp())
        import shutil
        for n in (".agents", "AGENTS.md", "CONTEXT.md"):
            s = ROOT / n
            shutil.copytree(s, d / n) if s.is_dir() else shutil.copy(s, d / n)
        sid, path = items.new_story("Export invoices as CSV", root=d)   # title only
        import agentrun
        probs = agentrun.preflight("story", sid, d)
        self.assertTrue(probs and "no request yet" in probs[0])
        with self.assertRaises(SystemExit):
            promptmode.prepare("story", sid, d)
        items.new_story("Another", root=d, text="Finance wants all invoices of a month as CSV with VAT.")
        self.assertEqual(agentrun.preflight("story", "US-002", d), [])

    def test_other_stages_are_not_blocked(self):
        import agentrun
        self.assertEqual(agentrun.preflight("spec", "US-001", ROOT), [])


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
