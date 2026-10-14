import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_attribution as ca  # noqa: E402


class Violations(unittest.TestCase):
    def test_clean_messages(self):
        for msg in ("feat(US-002): export invoices as CSV\n\n- add writer",
                    "fix: handle empty set\n\nCo-authored-by: Jane Doe <jane@example.com>"):
            self.assertEqual(ca.find_violations(msg), [], msg)

    def test_blocks_ai_trailer_and_names(self):
        for msg in ("x\n\nCo-Authored-By: Some Model 5 <noreply@anthropic.com>",
                    "x\n\nGenerated with a tool",
                    "feat: ask Claude to do it",
                    "chore: via Copilot",
                    "x \U0001F916",
                    "Co-authored-by: dependabot[bot] <x@y.z>"):
            self.assertTrue(ca.find_violations(msg), msg)


class Cli(unittest.TestCase):
    def run_cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, str(ROOT / "tools/check_attribution.py"), *args],
                              input=stdin, text=True, capture_output=True)

    def test_message_file_ignores_comment_lines(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("feat: ok\n# Please enter a message about Claude\n")
        self.assertEqual(self.run_cli(f.name).returncode, 0)

    def test_message_file_rejects(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("feat: ok\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n")
        self.assertEqual(self.run_cli(f.name).returncode, 1)

    def test_stdin(self):
        self.assertEqual(self.run_cli("--stdin", stdin="a normal PR body").returncode, 0)
        self.assertEqual(self.run_cli("--stdin", stdin="made with ChatGPT").returncode, 1)

    def test_range_checks_author_and_message(self):
        with tempfile.TemporaryDirectory() as d:
            def git(*a):
                return subprocess.run(["git", "-C", d, *a], check=True, capture_output=True, text=True)
            git("init", "-q", "-b", "main")
            git("-c", "user.name=Human", "-c", "user.email=h@example.com", "commit", "-q", "--allow-empty", "-m", "init")
            git("-c", "user.name=Human", "-c", "user.email=h@example.com", "commit", "-q", "--allow-empty", "-m", "feat: fine")
            git("-c", "user.name=Claude", "-c", "user.email=h@example.com", "commit", "-q", "--allow-empty", "-m", "feat: author is an agent")
            import os
            cwd = os.getcwd()
            os.chdir(d)
            try:
                self.assertEqual(ca._range("HEAD~2..HEAD~1"), [])
                self.assertEqual(len(ca._range("HEAD~1..HEAD")), 1)
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
