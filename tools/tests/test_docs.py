import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


class DocsAgreeWithTheCode(unittest.TestCase):
    """Cheap guard against the most common rot: docs that name a command that no longer exists."""

    def tasks(self):
        text = (ROOT / "mise.toml").read_text()
        names = set(re.findall(r'^\[tasks\.(?:"([^"]+)"|([A-Za-z0-9_-]+))\]', text, re.M))
        out = {a or b for a, b in names}
        out |= set(re.findall(r'^alias = "([^"]+)"', text, re.M))
        return out

    def test_every_mise_task_named_in_the_docs_exists(self):
        tasks = self.tasks()
        files = list((ROOT / "docs").glob("*.md")) + [ROOT / "README.md", ROOT / "AGENTS.md"]
        files += list((ROOT / ".agents").rglob("*.md"))
        unknown = {}
        for p in files:
            for m in re.finditer(r"mise run ([a-z][a-z0-9:_-]*)", p.read_text()):
                if m.group(1) not in tasks and m.group(1) != "stage":
                    unknown.setdefault(m.group(1), set()).add(p.name)
        self.assertEqual(unknown, {})

    def test_every_pipeline_stage_has_a_mise_task(self):
        import miniyaml
        tasks = self.tasks()
        stages = [s["name"] for s in miniyaml.loads((ROOT / ".agents/pipeline.yaml").read_text())["stages"]]
        for s in stages:
            self.assertTrue(s in tasks or f"agent:{s}" in tasks, f"no mise task for stage {s}")


sys.path.insert(0, str(ROOT / "tools"))

if __name__ == "__main__":
    unittest.main()
