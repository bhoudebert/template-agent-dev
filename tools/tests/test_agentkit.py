import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import agentkit  # noqa: E402

HOST_AGENTS = "# My project rules\n\nUse tabs. Never touch billing/.\n"
HOST_MISE = '[tasks.build]\nrun = "echo project build"\n'
HOST_CI = "name: ci\non: [push]\njobs: {}\n"


def git(d, *a):
    return subprocess.run(["git", "-C", str(d), "-c", "user.name=T", "-c", "user.email=t@example.com",
                           "-c", "commit.gpgsign=false", *a], check=True, capture_output=True, text=True)


def host_repo():
    d = Path(tempfile.mkdtemp())
    (d / "AGENTS.md").write_text(HOST_AGENTS)
    (d / "mise.toml").write_text(HOST_MISE)
    (d / ".gitignore").write_text("node_modules/\n")
    (d / ".github/workflows").mkdir(parents=True)
    (d / ".github/workflows/ci.yml").write_text(HOST_CI)
    (d / "package.json").write_text('{"name":"host"}\n')
    git(d, "init", "-q", "-b", "main")
    # the engine commits with the repository's own identity, as a user's would
    git(d, "config", "user.name", "Host Dev")
    git(d, "config", "user.email", "dev@example.com")
    git(d, "add", "-A")
    git(d, "commit", "-q", "-m", "init")
    return d


def kit_copy(edit=None):
    """A modified copy of this kit, standing in for a newer release."""
    d = Path(tempfile.mkdtemp()) / "kit"
    shutil.copytree(ROOT, d, ignore=shutil.ignore_patterns(".git", "__pycache__", "site", ".agents/runs", ".agents/out"))
    if edit:
        edit(d)
    return d


def cli(*args):
    return agentkit.main([str(a) for a in args])


class Install(unittest.TestCase):
    def test_install_respects_the_host_project(self):
        d = host_repo()
        self.assertEqual(cli("install", "--target", d), 0)
        # the project's own files survive, the kit lives beside them
        agents = (d / "AGENTS.md").read_text()
        self.assertIn("Use tabs. Never touch billing/.", agents)
        self.assertIn("<!-- agentkit:begin -->", agents)
        self.assertEqual((d / "mise.toml").read_text(), HOST_MISE)
        self.assertTrue((d / ".config/mise/conf.d/agentkit.toml").exists())
        self.assertIn("node_modules/", (d / ".gitignore").read_text())
        self.assertIn("# agentkit:begin", (d / ".gitignore").read_text())
        self.assertEqual((d / ".github/workflows/ci.yml").read_text(), HOST_CI)
        self.assertFalse(list((d / ".github/workflows").glob("agentkit-*")))      # CI is opt-in
        for p in ("tools/agentrun.py", ".agents/pipeline.yaml", ".agents/roles/analyst.md", "CONTEXT.md",
                  ".agentkit/lock.json", ".agentkit/base/.agents/roles/analyst.md"):
            self.assertTrue((d / p).exists(), p)
        lock = json.loads((d / ".agentkit/lock.json").read_text())
        self.assertNotIn("CONTEXT.md", lock["files"])                               # seeds are not tracked
        # one commit on a branch, nothing on main
        self.assertEqual(git(d, "branch", "--show-current").stdout.strip(), "chore/agentkit-install")
        self.assertEqual(git(d, "log", "main", "--format=%s").stdout.split("\n")[0], "init")
        self.assertTrue(git(d, "log", "-1", "--format=%s").stdout.startswith("chore(agentkit): install"))

    def test_ci_is_installed_once_and_prefixed(self):
        d = host_repo()
        cli("install", "--target", d, "--with", "ci")
        names = sorted(p.name for p in (d / ".github/workflows").glob("*.yml"))
        self.assertIn("ci.yml", names)
        self.assertTrue(any(n.startswith("agentkit-") for n in names))
        self.assertEqual((d / ".github/workflows/ci.yml").read_text(), HOST_CI)

    def test_kit_only_things_are_not_installed_into_a_host(self):
        d = host_repo()
        cli("install", "--target", d, "--with", "ci")
        side = (d / ".config/mise/conf.d/agentkit.toml").read_text()
        for task in ("[tasks.site]", '[tasks."site:build"]', '[tasks."install:github"]', '[tasks."kit:install"]'):
            self.assertNotIn(task, side)
        self.assertIn("[tasks.orient]", side)
        self.assertIn('[tasks."kit:update"]', side)
        names = {p.name for p in (d / ".github/workflows").glob("agentkit-*")}
        self.assertNotIn("agentkit-pages.yml", names)
        self.assertNotIn("agentkit-release-please.yml", names)   # that one belongs to the `release` feature

    def test_drop_tasks_keeps_the_rest(self):
        text = '[env]\nA = "1"\n\n[tasks.keep]\nrun = "x"\n\n[tasks."drop:me"]\nrun = "y"\n\n[tasks.after]\nrun = "z"\n'
        out = agentkit.drop_tasks(text, ["drop:me"])
        self.assertIn("[tasks.keep]", out)
        self.assertIn("[tasks.after]", out)
        self.assertNotIn("drop:me", out)
        self.assertIn('A = "1"', out)

    def test_plan_writes_nothing(self):
        d = host_repo()
        self.assertEqual(cli("install", "--target", d, "--plan"), 0)
        self.assertFalse((d / ".agentkit").exists())
        self.assertEqual(git(d, "branch", "--show-current").stdout.strip(), "main")

    def test_collision_in_tools_blocks_the_install_instead_of_breaking_the_kit(self):
        d = host_repo()
        (d / "tools").mkdir()
        (d / "tools/validate.py").write_text("# my own validator\n")
        git(d, "add", "-A"); git(d, "commit", "-q", "-m", "own tool")
        with self.assertRaises(SystemExit):
            cli("install", "--target", d)
        self.assertFalse((d / ".agentkit").exists())
        self.assertEqual(git(d, "branch", "--show-current").stdout.strip(), "main")     # nothing was started
        self.assertEqual(cli("install", "--target", d, "--plan"), 1)                    # plan says so too

    def test_allow_collisions_keeps_yours_and_does_not_lock_it(self):
        d = host_repo()
        (d / "tools").mkdir()
        (d / "tools/validate.py").write_text("# my own validator\n")
        git(d, "add", "-A"); git(d, "commit", "-q", "-m", "own tool")
        cli("install", "--target", d, "--allow-collisions")
        self.assertEqual((d / "tools/validate.py").read_text(), "# my own validator\n")
        self.assertNotIn("tools/validate.py", json.loads((d / ".agentkit/lock.json").read_text())["files"])

    def test_a_collision_outside_tools_is_kept_with_a_note(self):
        d = host_repo()
        (d / ".agents/roles").mkdir(parents=True)
        (d / ".agents/roles/analyst.md").write_text("# our analyst\n")
        git(d, "add", "-A"); git(d, "commit", "-q", "-m", "own role")
        cli("install", "--target", d)
        self.assertEqual((d / ".agents/roles/analyst.md").read_text(), "# our analyst\n")

    def test_refuses_on_a_dirty_tree_and_a_second_install(self):
        d = host_repo()
        (d / "package.json").write_text('{"name":"changed"}\n')
        with self.assertRaises(SystemExit):
            cli("install", "--target", d)
        git(d, "checkout", "--", "package.json")
        cli("install", "--target", d)
        with self.assertRaises(SystemExit):
            cli("install", "--target", d)


class PointersAndGitignore(unittest.TestCase):
    def test_host_gitignore_block_has_no_kit_only_entries(self):
        d = host_repo()
        cli("install", "--target", d)
        text = (d / ".gitignore").read_text()
        self.assertIn("node_modules/", text)
        self.assertIn(".agents/runs/", text)
        for kit_only in ("site/docs/", "dist/"):
            self.assertNotIn(kit_only, text)

    def test_pointers_feature_writes_assistant_entry_files(self):
        d = host_repo()
        (d / "CLAUDE.md").write_text("# My Claude notes\nKeep answers short.\n")
        git(d, "add", "-A"); git(d, "commit", "-q", "-m", "claude")
        cli("install", "--target", d, "--with", "pointers")
        claude = (d / "CLAUDE.md").read_text()
        self.assertIn("Keep answers short.", claude)         # theirs untouched
        self.assertIn("@AGENTS.md", claude)                  # the import was added in a block
        self.assertIn("AGENTS.md", (d / ".github/copilot-instructions.md").read_text())
        self.assertTrue((d / ".cursor/rules/agentkit.mdc").exists())

    def test_pointers_are_opt_in(self):
        d = host_repo()
        cli("install", "--target", d)
        self.assertFalse((d / "CLAUDE.md").exists())


class Uninstall(unittest.TestCase):
    def test_removes_the_kit_and_keeps_what_is_yours(self):
        d = host_repo()
        cli("install", "--target", d, "--with", "pointers")
        git(d, "switch", "-q", "main"); git(d, "merge", "-q", "--ff-only", "chore/agentkit-install")
        (d / "CONTEXT.md").write_text("# my context\n")                      # a seed the project owns
        role = d / ".agents/roles/analyst.md"
        role.write_text(role.read_text() + "\n- our rule\n")               # an edited tailorable file
        git(d, "add", "-A"); git(d, "commit", "-q", "-m", "edits")
        self.assertEqual(cli("uninstall", "--target", d), 0)
        self.assertFalse((d / "tools/agentrun.py").exists())
        self.assertFalse((d / ".agentkit").exists())
        self.assertFalse((d / ".config/mise/conf.d/agentkit.toml").exists())
        self.assertEqual((d / "AGENTS.md").read_text().strip(), HOST_AGENTS.strip())   # block gone, theirs intact
        self.assertEqual((d / "mise.toml").read_text(), HOST_MISE)
        self.assertEqual((d / "CONTEXT.md").read_text(), "# my context\n")
        self.assertIn("our rule", role.read_text())                           # edited file kept
        self.assertFalse((d / "CLAUDE.md").exists())                          # only held our block: removed
        self.assertEqual(git(d, "branch", "--show-current").stdout.strip(), "chore/agentkit-uninstall")

    def test_plan_changes_nothing(self):
        d = host_repo()
        cli("install", "--target", d)
        git(d, "switch", "-q", "main"); git(d, "merge", "-q", "--ff-only", "chore/agentkit-install")
        self.assertEqual(cli("uninstall", "--target", d, "--plan"), 0)
        self.assertTrue((d / "tools/agentrun.py").exists())
        self.assertEqual(git(d, "branch", "--show-current").stdout.strip(), "main")


class KitCompleteness(unittest.TestCase):
    def test_every_tool_is_shipped_or_deliberately_not(self):
        k = agentkit.Kit(ROOT)
        shipped = {e["src"] for e in k.entries(sorted(k.manifest["features"]))}
        deliberately_not = {"tools/build_site.py"}      # the kit's own website generator
        for rel in k.files():
            if rel.startswith(("tools/", ".githooks/", ".agents/")) and not rel.startswith("tools/tests/"):
                self.assertTrue(rel in shipped or rel in deliberately_not, f"{rel} is not shipped by kit.json")

    def test_no_dead_manifest_entries(self):
        import fnmatch
        k = agentkit.Kit(ROOT)
        files = k.files()
        for e in k.manifest["entries"]:
            self.assertTrue(any(fnmatch.fnmatch(f, e["match"]) for f in files), f"dead entry {e['match']}")


class Reconcile(unittest.TestCase):
    def conflicted(self):
        d = host_repo()
        cli("install", "--target", d)
        git(d, "switch", "-q", "main"); git(d, "merge", "-q", "--ff-only", "chore/agentkit-install")
        role = d / ".agents/roles/analyst.md"
        role.write_text(role.read_text().replace("Mission:", "Our mission:"))
        git(d, "commit", "-qam", "local mission")

        def release(k):
            r = k / ".agents/roles/analyst.md"
            r.write_text(r.read_text().replace("Mission:", "Purpose:"))
        cli("update", "--target", d, "--from", kit_copy(release))
        self.assertIn("<<<<<<< local", role.read_text())
        return d, role

    def run_with_reply(self, d, reply_text):
        import os
        script = d / "model.sh"
        reply = d / "reply.txt"
        reply.write_text(reply_text)
        script.write_text(f"#!/bin/sh\ncat > /dev/null\ncat {reply}\n")
        old = dict(os.environ)
        os.environ.update(AGENT_PROVIDER="cmd", AGENT_CMD=f"sh {script}")
        try:
            return cli("reconcile", "--target", d)
        finally:
            os.environ.clear(); os.environ.update(old)

    def test_diff3_markers_carry_the_base(self):
        d, role = self.conflicted()
        text = role.read_text()
        self.assertIn("||||||| base", text)
        self.assertIn(">>>>>>> kit", text)

    def test_model_resolution_is_validated_written_and_committed(self):
        d, role = self.conflicted()
        good = ("RATIONALE: kept our mission wording, adopted the kit's purpose rename.\n<<<MERGED>>>\n"
                "# Role: Analyst\n\nOur purpose: turn requests into stories.\n<<<END>>>\n")
        self.assertEqual(self.run_with_reply(d, good), 0)
        self.assertNotIn("<<<<<<<", role.read_text())
        self.assertIn("Our purpose", role.read_text())
        self.assertEqual(cli("check", "--target", d), 0)
        self.assertIn("Reconciled by a model", (d / ".agentkit/CHANGES.md").read_text())
        self.assertTrue(git(d, "log", "-1", "--format=%s").stdout.startswith("chore(agentkit): reconcile"))

    def test_a_bad_reply_leaves_the_file_untouched(self):
        d, role = self.conflicted()
        before = role.read_text()
        bad = "RATIONALE: done.\n<<<MERGED>>>\n<<<<<<< local\nstill conflicted\n=======\nx\n>>>>>>> kit\n<<<END>>>\n"
        self.assertEqual(self.run_with_reply(d, bad), 1)
        self.assertEqual(role.read_text(), before)
        self.assertEqual(self.run_with_reply(d, "no structure at all"), 1)
        self.assertEqual(role.read_text(), before)

    def test_brief_mode_writes_files_for_an_assistant(self):
        d, role = self.conflicted()
        self.assertEqual(cli("reconcile", "--target", d, "--brief"), 0)
        briefs = list((d / ".agentkit/reconcile").glob("*.md"))
        self.assertEqual(len(briefs), 1)
        self.assertIn("integrator.md", briefs[0].read_text())
        self.assertIn("<<<<<<< local", briefs[0].read_text())

    def test_block_conflicts_are_resolved_inside_the_block(self):
        d = host_repo()
        cli("install", "--target", d)
        git(d, "switch", "-q", "main"); git(d, "merge", "-q", "--ff-only", "chore/agentkit-install")
        a = d / "AGENTS.md"
        text = a.read_text()
        inner_marker = "Entry point for any coding agent"
        self.assertIn(inner_marker, text)
        a.write_text(text.replace(inner_marker, "Our entry point for any coding agent", 1))
        git(d, "commit", "-qam", "tune agents")

        def release(k):
            f = k / "AGENTS.md"
            f.write_text(f.read_text().replace(inner_marker, "Starting point for any coding agent", 1))
        cli("update", "--target", d, "--from", kit_copy(release))
        self.assertIn("<<<<<<< local", a.read_text())
        # the model resolves only the block's inner text
        reply = ("RATIONALE: kept ours.\n<<<MERGED>>>\n# AGENTS.md\n\nOur starting point for any coding agent.\n<<<END>>>\n")
        self.assertEqual(self.run_with_reply(d, reply), 0)
        out = a.read_text()
        self.assertIn("Use tabs. Never touch billing/.", out)      # the host's own text is intact
        self.assertIn("Our starting point for any coding agent.", out)
        self.assertNotIn("<<<<<<<", out)
        self.assertEqual(out.count("agentkit:begin"), 1)


class ConflictDetection(unittest.TestCase):
    def test_only_real_marker_lines_count(self):
        real = "a\n<<<<<<< local\nmine\n||||||| base\nold\n=======\ntheirs\n>>>>>>> kit\nb\n"
        self.assertTrue(agentkit.has_conflict(real))
        mention = 'CONFLICT = ("<<<<<<< local", ">>>>>>> kit")\n<<<<<<< local   the project version\n>>>>>>> kit  the new one\n'
        self.assertFalse(agentkit.has_conflict(mention))

    def test_a_fresh_install_has_no_conflicts_even_though_the_kit_documents_the_markers(self):
        d = host_repo()
        cli("install", "--target", d)
        self.assertEqual(cli("check", "--target", d), 0)


class Identity(unittest.TestCase):
    def test_missing_git_identity_gives_a_clear_message(self):
        import os
        d = Path(tempfile.mkdtemp())
        (d / "a.txt").write_text("x")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=d, check=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(HOME=str(d), GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
        old = os.environ.copy()
        os.environ.clear(); os.environ.update(env)
        try:
            with self.assertRaises(SystemExit) as ctx:
                agentkit.commit(agentkit.Target(d), ["a.txt"], "chore: x")
        finally:
            os.environ.clear(); os.environ.update(old)
        self.assertIn("git config user.name", str(ctx.exception))


class Update(unittest.TestCase):
    def installed(self):
        d = host_repo()
        cli("install", "--target", d)
        git(d, "switch", "-q", "main")
        git(d, "merge", "-q", "--ff-only", "chore/agentkit-install")
        return d

    def test_status_is_clean_right_after_install(self):
        d = self.installed()
        rows = agentkit.classify(agentkit.Target(d), agentkit.Target(d).lock(),
                                 agentkit.Kit(ROOT).entries([]))
        self.assertTrue(all(state == "clean" for _, _, state in rows), [r for r in rows if r[2] != "clean"])

    def test_update_applies_each_class_correctly(self):
        d = self.installed()
        # local edits: a tailorable role and the project's own AGENTS.md text
        role = d / ".agents/roles/analyst.md"
        role.write_text(role.read_text() + "\n- Our house rule: always ask about audit logging.\n")
        git(d, "commit", "-qam", "tune role")

        def release(k):
            (k / "tools/validate.py").write_text((k / "tools/validate.py").read_text() + "\n# new in kit\n")
            r = k / ".agents/roles/analyst.md"
            r.write_text("# Role: Analyst (v2)\n" + r.read_text())          # touches a different part: clean merge
            (k / "CONTEXT.md").write_text("# a different seed\n")
            (k / "AGENTS.md").write_text((k / "AGENTS.md").read_text() + "\nNew kit rule.\n")
        kit = kit_copy(release)
        self.assertEqual(cli("update", "--target", d, "--from", kit), 0)
        self.assertIn("# new in kit", (d / "tools/validate.py").read_text())            # managed: overwritten
        merged = role.read_text()
        self.assertIn("Role: Analyst (v2)", merged)                                      # kit change kept
        self.assertIn("Our house rule: always ask about audit logging.", merged)         # local change kept
        self.assertNotIn("<<<<<<<", merged)
        agents = (d / "AGENTS.md").read_text()
        self.assertIn("New kit rule.", agents)                                            # block refreshed
        self.assertIn("Use tabs. Never touch billing/.", agents)                         # project text untouched
        self.assertNotEqual((d / "CONTEXT.md").read_text(), "# a different seed\n")      # seed never updated
        self.assertTrue(git(d, "branch", "--show-current").stdout.startswith("chore/agentkit-update-"))
        self.assertTrue((d / ".agentkit/CHANGES.md").exists())

    def test_conflict_is_marked_and_reported_not_hidden(self):
        d = self.installed()
        role = d / ".agents/roles/analyst.md"
        text = role.read_text()
        role.write_text(text.replace("Mission:", "Our mission:"))
        git(d, "commit", "-qam", "local mission")

        def release(k):
            r = k / ".agents/roles/analyst.md"
            r.write_text(r.read_text().replace("Mission:", "Purpose:"))
        self.assertEqual(cli("update", "--target", d, "--from", kit_copy(release)), 0)
        self.assertIn("<<<<<<< local", role.read_text())
        self.assertIn(".agents/roles/analyst.md", (d / ".agentkit/CHANGES.md").read_text())
        self.assertEqual(cli("check", "--target", d), 1)

    def test_ci_is_untouched_unless_asked(self):
        d = host_repo()
        cli("install", "--target", d, "--with", "ci")
        git(d, "switch", "-q", "main"); git(d, "merge", "-q", "--ff-only", "chore/agentkit-install")

        def release(k):
            f = next((k / "adapters/github/workflows").glob("*.yml"))
            f.write_text(f.read_text() + "\n# changed upstream\n")
        kit = kit_copy(release)
        cli("update", "--target", d, "--from", kit, "--plan")
        out_default = [p for p in (d / ".github/workflows").glob("agentkit-*")]
        self.assertTrue(all("# changed upstream" not in p.read_text() for p in out_default))
        cli("update", "ci", "--target", d, "--from", kit)
        self.assertTrue(any("# changed upstream" in p.read_text() for p in (d / ".github/workflows").glob("agentkit-*")))

    def test_ignore_globs_are_respected(self):
        d = self.installed()
        (d / ".agentkit/ignore").write_text("tools/validate.py\n")
        git(d, "add", "-A"); git(d, "commit", "-q", "-m", "ignore")

        def release(k):
            (k / "tools/validate.py").write_text("# upstream rewrite\n")
        cli("update", "--target", d, "--from", kit_copy(release))
        self.assertNotIn("# upstream rewrite", (d / "tools/validate.py").read_text())

    def test_nothing_to_do_makes_no_branch(self):
        d = self.installed()
        self.assertEqual(cli("update", "--target", d), 0)
        self.assertEqual(git(d, "branch", "--show-current").stdout.strip(), "main")


if __name__ == "__main__":
    unittest.main()
