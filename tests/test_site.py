import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_site  # noqa: E402


class Render(unittest.TestCase):
    def test_heading_ids_and_toc(self):
        html, toc = build_site.render("# T\n\n## The developer loop\n\ntext\n")
        self.assertIn('<h2 id="the-developer-loop">', html)
        self.assertEqual(toc, [(2, "the-developer-loop", "The developer loop")])

    def test_table_with_escaped_pipe_in_code(self):
        html, _ = build_site.render("| a | b |\n|---|---|\n| `--dry\\|--plan` | x |\n")
        self.assertIn("<code>--dry|--plan</code>", html)
        self.assertEqual(html.count("<td>"), 2)

    def test_italics_and_bold(self):
        html, _ = build_site.render("is *right* and **bold** and a*b*c")
        self.assertIn("<em>right</em>", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("a*b*c", html)

    def test_code_fence_is_escaped(self):
        html, _ = build_site.render("```sh\necho <b> && ls\n```\n")
        self.assertIn("&lt;b&gt; &amp;&amp; ls", html)

    def test_doc_links_rewritten_and_unknown_md_dropped(self):
        html, _ = build_site.render("[w](WORKFLOW.md) [x](WORKFLOW.md#a) [r](src/foo.md) [e](https://e.com)")
        self.assertIn('href="workflow.html"', html)
        self.assertIn('href="workflow.html#a"', html)
        self.assertNotIn("foo.md", html)
        self.assertIn('rel="noopener"', html)

    def test_lists_and_checkboxes(self):
        html, _ = build_site.render("- [ ] a\n- [x] b\n\n1. one\n2. two\n")
        self.assertIn('<input type="checkbox" disabled >', html)
        self.assertIn("checked", html)
        self.assertIn("<ol>", html)


class Balanced(HTMLParser):
    VOID = {"meta", "link", "br", "hr", "input", "img", "circle", "path", "line", "rect"}

    def __init__(self):
        super().__init__()
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}> (open: {self.stack[-3:]})")
        else:
            self.stack.pop()


class Site(unittest.TestCase):
    def test_build_all_pages_and_balanced_html(self):
        pages = build_site.build(ROOT)
        self.assertEqual(len(pages), len(build_site.PAGES))
        for path in pages + [ROOT / "site" / "index.html"]:
            p = Balanced()
            p.feed(path.read_text(encoding="utf-8"))
            self.assertEqual(p.errors, [], path.name)
            self.assertEqual(p.stack, [], path.name)

    def test_landing_covers_every_pipeline_stage(self):
        import miniyaml
        stages = [s["name"] for s in miniyaml.loads((ROOT / ".agents/pipeline.yaml").read_text())["stages"]]
        index = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        for name in stages:
            self.assertIn(f'id="s-{name}"', index, f"landing page misses stage {name}")

    def test_internal_links_resolve(self):
        import re
        index = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        ids = set(re.findall(r'id="([^"]+)"', index))
        for frag in re.findall(r'href="#([^"]+)"', index):
            self.assertIn(frag, ids, f"dangling #{frag}")
        build_site.build(ROOT)
        for slug, _, _ in build_site.PAGES:
            doc = (ROOT / "site" / "docs" / f"{slug}.html").read_text(encoding="utf-8")
            ids = set(re.findall(r'id="([^"]+)"', doc))
            for frag in re.findall(r'href="#([^"]+)"', doc):
                self.assertIn(frag, ids, f"{slug}: dangling #{frag}")
            for target, frag in re.findall(r'href="([a-z]+\.html)#([^"]+)"', doc):
                other = (ROOT / "site" / "docs" / target).read_text(encoding="utf-8")
                self.assertIn(f'id="{frag}"', other, f"{slug} -> {target}#{frag}")


if __name__ == "__main__":
    unittest.main()
