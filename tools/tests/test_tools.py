import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
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
    # overlay the worked example (US-001) so tests have real artifacts
    example = ROOT / "examples" / "password-reset"
    for name in ("docs", "openspec"):
        shutil.copytree(example / name, tmp / name, dirs_exist_ok=True)
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
    def test_template_repo_clean(self):
        self.assertEqual(validate.scan(ROOT), [])
        self.assertEqual(trace_check.check(ROOT), [])

    def test_every_template_satisfies_its_schema(self):
        tmp = sandbox()
        for tpl in sorted((ROOT / ".agents" / "templates").glob("*.md")):
            import miniyaml as _y
            meta, _ = _y.split_frontmatter(tpl.read_text())
            stem = str(meta.get("id") or meta.get("story"))
            target = tmp / "docs" / "tmp" / f"{stem}-{tpl.stem}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(tpl.read_text())
            self.assertEqual(validate.check_file(target, tmp), [], tpl.name)

    def test_every_stage_references_existing_parts(self):
        stages = agentrun.load_pipeline(ROOT)["stages"]
        for st in stages:
            self.assertTrue((ROOT / ".agents/roles" / f"{st['role']}.md").exists(), st["name"])
            for s in st.get("skills") or []:
                self.assertTrue((ROOT / ".agents/skills" / f"{s}.md").exists(), s)
            t = st.get("template") or []
            for name in [t] if isinstance(t, str) else t:
                self.assertTrue((ROOT / ".agents/templates" / f"{name}.md").exists(), name)

    def test_qa_report_must_cite_existing_files(self):
        tmp = sandbox()
        p = tmp / "docs" / "qa" / "US-001.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("---\ntype: qa-report\nstory: US-001\nverdict: pass\ndate: 2026-01-01\n---\n"
                     "## Summary\nok\n## Traceability\n| a | `tests/ghost.test.js` | pass |\n## Findings\nnone\n## Not verified\nNothing\n")
        self.assertTrue(any("tests/ghost.test.js" in e for e in validate.check_file(p, tmp)))
        (tmp / "tests" / "ghost.test.js").write_text("// x")
        self.assertEqual(validate.check_file(p, tmp), [])

    def test_template_folders_skipped_only_at_root(self):
        tmp = sandbox()
        bad = "---\nid: US-777\ntype: story\ntitle: x\nstatus: enriched\nowner: po\n---\nno sections\n"
        (tmp / "examples").mkdir(exist_ok=True)
        (tmp / "examples" / "US-777.md").write_text(bad)           # template examples: skipped
        (tmp / "docs" / "examples").mkdir(parents=True)
        (tmp / "docs" / "examples" / "US-778.md").write_text(bad.replace("US-777", "US-778"))  # project folder: scanned
        (tmp / "node_modules" / "pkg").mkdir(parents=True)
        (tmp / "node_modules" / "pkg" / "US-779.md").write_text(bad)  # vendor: skipped
        errs = validate.scan(tmp)
        self.assertTrue(any("docs/examples/US-778.md" in e for e in errs), errs)
        self.assertFalse(any("US-777" in e or "US-779" in e for e in errs), errs)

    def test_file_name_must_match_id(self):
        tmp = sandbox()
        p = tmp / "docs/stories/US-002.md"
        p.write_text("---\nid: US-001\ntype: story\ntitle: x\nstatus: draft\nowner: po\n---\nraw\n")
        self.assertTrue(any("file name must be" in e for e in validate.check_file(p, tmp)))
        ok = tmp / "docs/decisions/ADR-0002-some-slug.md"
        ok.write_text((tmp / "docs/decisions/ADR-0001-hash-reset-tokens.md").read_text().replace("ADR-0001", "ADR-0002"))
        self.assertEqual(validate.check_file(ok, tmp), [])

    def test_worked_example_is_valid(self):
        tmp = sandbox()
        self.assertEqual(validate.scan(tmp), [])
        self.assertEqual(trace_check.check(tmp), [])

    def test_openspec_frontmatter_rejected(self):
        tmp = sandbox()
        p = tmp / "openspec/changes/US-001/tasks.md"
        p.write_text("---\nstory: US-001\n---\n" + p.read_text())
        errs = validate.scan(tmp)
        self.assertTrue(any("must not have frontmatter" in e for e in errs))
        self.assertEqual(validate.check_file(p, tmp), [])  # not judged as a typed artifact

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


class Providers(unittest.TestCase):
    def serve(self, payload):
        import http.server
        import json
        import threading
        seen = {}

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                raw = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}/v1", seen

    def env(self, **kv):
        old = {k: os.environ.get(k) for k in kv}
        os.environ.update(kv)
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v) for k, v in old.items()])

    def test_reasoning_and_max_tokens_are_sent(self):
        import providers
        base, seen = self.serve({"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]})
        self.env(AGENT_BASE_URL=base, AGENT_MODEL="m", AGENT_REASONING_EFFORT="none", AGENT_MAX_TOKENS="123")
        self.assertEqual(providers.complete("s", "u", "strong", "openai"), "ok")
        self.assertEqual(seen["body"]["reasoning_effort"], "none")
        self.assertEqual(seen["body"]["max_tokens"], 123)

    def test_empty_content_explains_thinking_budget(self):
        import providers
        base, _ = self.serve({"choices": [{"message": {"content": "", "reasoning": "x" * 50}, "finish_reason": "length"}]})
        self.env(AGENT_BASE_URL=base, AGENT_MODEL="m")
        with self.assertRaises(providers.ProviderError) as ctx:
            providers.complete("s", "u", "strong", "openai")
        self.assertIn("AGENT_REASONING_EFFORT", str(ctx.exception))
        self.assertIn("length", str(ctx.exception))


class Diff(unittest.TestCase):
    def git(self, d, *a):
        import subprocess
        return subprocess.run(["git", "-C", str(d), "-c", "user.name=T", "-c", "user.email=t@example.com", *a],
                              check=True, capture_output=True, text=True)

    def test_diff_includes_branch_and_uncommitted_changes(self):
        d = Path(tempfile.mkdtemp())
        self.git(d, "init", "-q", "-b", "main")
        (d / "a.txt").write_text("one\n")
        self.git(d, "add", "-A"); self.git(d, "commit", "-q", "-m", "init")
        self.git(d, "switch", "-q", "-c", "feature/x")
        (d / "a.txt").write_text("one\ntwo\n")
        self.git(d, "commit", "-qam", "feat: two")
        (d / "a.txt").write_text("one\ntwo\nthree\n")  # uncommitted
        os.environ["AGENT_BASE_REF"] = "main"
        try:
            diff = agentrun._diff(d)
        finally:
            del os.environ["AGENT_BASE_REF"]
        self.assertIn("+two", diff)
        self.assertIn("+three", diff)
        self.assertIn("uncommitted changes", diff)

    def test_review_script_picks_id_from_branch(self):
        import subprocess
        d = Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "tools", d / "tools", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        for name in (".agents", "AGENTS.md", "CONTEXT.md"):
            src = ROOT / name
            shutil.copytree(src, d / name) if src.is_dir() else shutil.copy(src, d / name)
        self.git(d, "init", "-q", "-b", "main")
        (d / "f.txt").write_text("x\n")
        self.git(d, "add", "-A"); self.git(d, "commit", "-q", "-m", "init")
        self.git(d, "switch", "-q", "-c", "feature/US-042-thing")
        (d / "f.txt").write_text("y\n")
        self.git(d, "commit", "-qam", "feat(US-042): y")
        canned = d / "reply.txt"
        canned.write_text("## Review\nLooks fine.\n")
        env = dict(os.environ, AGENT_PROVIDER="cmd", AGENT_CMD=f"cat {canned}")
        proc = subprocess.run(["sh", "tools/review.sh"], cwd=d, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("id=US-042", proc.stderr)
        self.assertIn("Looks fine.", proc.stdout)
        self.assertTrue((d / ".agents/out/review-US-042.md").exists())


class ReviewScope(unittest.TestCase):
    """Whole-PR vs last-commit scope, stack-aware base, post+commit refusal."""

    def git(self, d, *a):
        import subprocess
        return subprocess.run(["git", "-C", str(d), "-c", "user.name=T", "-c", "user.email=t@example.com", *a],
                              check=True, capture_output=True, text=True)

    def repo(self):
        """main(init) <- stack(commit A) <- feature/US-042-x(commits B, C); PR base is `stack`."""
        d = Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "tools", d / "tools", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        for name in (".agents", "AGENTS.md", "CONTEXT.md"):
            src = ROOT / name
            shutil.copytree(src, d / name) if src.is_dir() else shutil.copy(src, d / name)
        self.git(d, "init", "-q", "-b", "main")
        (d / "f.txt").write_text("base\n")
        self.git(d, "add", "-A"); self.git(d, "commit", "-q", "-m", "init")
        self.git(d, "switch", "-q", "-c", "stack")
        (d / "a.txt").write_text("PARENT-PR-CHANGE\n")
        self.git(d, "add", "-A"); self.git(d, "commit", "-q", "-m", "feat: parent")
        self.git(d, "switch", "-q", "-c", "feature/US-042-x")
        (d / "b.txt").write_text("FIRST-COMMIT-OF-PR\n")
        self.git(d, "add", "-A"); self.git(d, "commit", "-q", "-m", "feat(US-042): first")
        (d / "c.txt").write_text("LAST-COMMIT-OF-PR\n")
        self.git(d, "add", "-A"); self.git(d, "commit", "-q", "-m", "feat(US-042): last")
        bin_dir = d / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "gh"
        fake.write_text("""#!/bin/sh
case "$*" in
  *baseRefName*) echo stack ;;
  *"--json number"*) echo 9 ;;
  *) exit 0 ;;
esac
""")
        fake.chmod(0o755)
        (d / "reply.txt").write_text("## Review\nok\n")
        (d / "cmd.sh").write_text("#!/bin/sh\ncat > stdin.txt\ncat reply.txt\n")
        return d

    def run_review(self, d, *args):
        import subprocess
        env = dict(os.environ, AGENT_PROVIDER="cmd", AGENT_CMD=f"sh {d}/cmd.sh",
                   PATH=f"{d}/bin:{os.environ['PATH']}")
        env.pop("AGENT_BASE_REF", None)
        return subprocess.run(["sh", "tools/review.sh", *args], cwd=d, env=env, capture_output=True, text=True)

    def test_default_reviews_whole_pr_against_its_own_base_not_main(self):
        d = self.repo()
        proc = self.run_review(d)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        prompt = (d / "stdin.txt").read_text()
        self.assertIn("FIRST-COMMIT-OF-PR", prompt)       # every commit of the PR
        self.assertIn("LAST-COMMIT-OF-PR", prompt)
        self.assertNotIn("PARENT-PR-CHANGE", prompt)      # the parent PR is not part of this review
        self.assertIn("# scope: whole branch: 2 commit(s) vs", prompt)
        self.assertIn("stack", prompt)

    def test_commit_flag_reviews_only_the_last_commit(self):
        d = self.repo()
        proc = self.run_review(d, "", "", "true")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        prompt = (d / "stdin.txt").read_text()
        self.assertIn("LAST-COMMIT-OF-PR", prompt)
        self.assertNotIn("FIRST-COMMIT-OF-PR", prompt)
        self.assertIn("# scope: last commit", prompt)

    def test_post_with_commit_is_refused(self):
        d = self.repo()
        proc = self.run_review(d, "", "true", "true")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("refusing --post with --commit", proc.stderr)
        self.assertFalse((d / "stdin.txt").exists())      # the model was never called


class PostReview(unittest.TestCase):
    """post_review.sh against a fake `gh` that logs its calls."""

    def run_script(self, existing_id, fail_list=False, expect_ok=True):
        import subprocess
        d = Path(tempfile.mkdtemp())
        log = d / "calls.log"
        bin_dir = d / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "gh"
        fake.write_text(f"""#!/bin/sh
echo "$@" >> {log}
case "$1 $2" in
  "repo view") echo "o/r" ;;
  "api user") echo "me" ;;
  "api --paginate") {'echo "denied" >&2; exit 1' if fail_list else f'echo "{existing_id}"'} ;;
esac
exit 0
""")
        fake.chmod(0o755)
        review = d / "review.md"
        review.write_text("# Review: PR-8\n\n## Findings\n- x\n")
        env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")
        proc = subprocess.run(["sh", str(ROOT / "tools/post_review.sh"), str(review), "8"],
                              cwd=ROOT, env=env, capture_output=True, text=True)
        if expect_ok:
            self.assertEqual(proc.returncode, 0, proc.stderr)
        return log.read_text(), proc.stdout + proc.stderr

    def test_listing_failure_never_creates_a_duplicate(self):
        calls, out = self.run_script("", fail_list=True, expect_ok=False)
        self.assertNotIn("pr comment", calls)
        self.assertNotIn("PATCH", calls)
        self.assertIn("cannot list comments", out)

    def test_updates_existing_comment_instead_of_adding(self):
        calls, out = self.run_script("12345")
        self.assertIn("-X PATCH repos/o/r/issues/comments/12345", calls)
        self.assertNotIn("pr comment", calls)
        self.assertIn("updated", out)

    def test_creates_when_none_exists(self):
        calls, out = self.run_script("")
        self.assertIn("pr comment 8 --body-file", calls)
        self.assertNotIn("PATCH", calls)
        self.assertIn("created", out)


class Branch(unittest.TestCase):
    def test_branch_name(self):
        import items
        self.assertEqual(items.branch_name("US-001", sandbox()), "feature/US-001-reset-password-by-email")


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

    def test_single_output_path_accepts_plain_reply(self):
        got = agentrun.single_target_fallback("## Review\nLooks fine", [".agents/out/review-US-001.md"])
        self.assertEqual(got, {".agents/out/review-US-001.md": "## Review\nLooks fine\n"})
        self.assertEqual(agentrun.single_target_fallback("x", ["docs/**", "tests/**"]), {})
        self.assertEqual(agentrun.single_target_fallback("x", ["docs/a.md", "docs/b.md"]), {})
        self.assertEqual(agentrun.single_target_fallback("  ", ["docs/a.md"]), {})

    def test_prompt_wraps_inputs_and_contract(self):
        tmp = sandbox()
        stage = agentrun.find_stage(agentrun.load_pipeline(tmp), "qa")
        system, user, out = agentrun.build_prompt(stage, "US-001", tmp)
        self.assertIn("Role: QA", system)
        self.assertIn("policy: security.md", system)
        self.assertIn('<input path="docs/stories/US-001.md">', user)
        self.assertEqual(out, ["docs/qa/US-001.md"])

    def test_design_stage_gets_both_templates_and_todays_date(self):
        tmp = sandbox()
        os.environ["AGENT_TODAY"] = "2031-02-03"
        try:
            stage = agentrun.find_stage(agentrun.load_pipeline(tmp), "design")
            _, user, _ = agentrun.build_prompt(stage, "US-001", tmp)
        finally:
            del os.environ["AGENT_TODAY"]
        self.assertIn("# Template `design`", user)
        self.assertIn("# Template `adr`", user)
        self.assertIn("Today: 2031-02-03", user)

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
