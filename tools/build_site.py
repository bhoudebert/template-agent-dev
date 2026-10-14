#!/usr/bin/env python3
"""Render docs/*.md to static HTML pages under site/docs/ (stdlib only).

    python tools/build_site.py          # build
    python tools/build_site.py --serve  # build, then serve ./site on :8000

Supports the Markdown subset used in docs/: headings, paragraphs, fenced code,
tables, flat lists (with task checkboxes), blockquotes, rules, `code`, **bold**, links.
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = [  # (slug, source file, nav title)
    ("tutorial", "TUTORIAL.md", "Tutorial"),
    ("workflow", "WORKFLOW.md", "Workflow"),
    ("guide", "GUIDE.md", "Guide"),
    ("architecture", "ARCHITECTURE.md", "Architecture"),
    ("reference", "REFERENCE.md", "Reference"),
]
_SLUG_OF = {src: slug for slug, src, _ in PAGES}


def slugify(text):
    text = re.sub(r"<[^>]+>|`", "", text)
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _href(url):
    path, _, frag = url.partition("#")
    name = Path(path).name
    if path.endswith(".md") and name in _SLUG_OF:
        path = f"{_SLUG_OF[name]}.html"
    elif path.endswith(".md"):
        return None  # link to a repo file we do not publish
    return path + (f"#{frag}" if frag else "")


def inline(text):
    out = []
    for i, part in enumerate(re.split(r"(`[^`]+`)", text)):
        if i % 2:
            out.append(f"<code>{html.escape(part[1:-1])}</code>")
            continue
        s = html.escape(part, quote=False)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"<em>\1</em>", s)

        def link(m):
            href = _href(html.unescape(m.group(2)))
            label = m.group(1)
            if href is None:
                return label
            ext = ' rel="noopener"' if href.startswith("http") else ""
            return f'<a href="{html.escape(href, quote=True)}"{ext}>{label}</a>'

        out.append(re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, s))
    return "".join(out)


def _cells(line):
    line = line.strip().strip("|")
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line)]


def render(md):
    """Return (html, toc[(level, id, text)])."""
    lines, out, toc, i = md.splitlines(), [], [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("```"):
            lang, buf, i = line[3:].strip(), [], i + 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="lang-{html.escape(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(buf))}</code></pre>")
        elif re.match(r"^#{1,4} ", line):
            level = len(line) - len(line.lstrip("#"))
            text = line[level:].strip()
            hid = slugify(text)
            if level in (2, 3):
                toc.append((level, hid, re.sub(r"[`*]", "", text)))
            out.append(f'<h{level} id="{hid}">{inline(text)}</h{level}>')
            i += 1
        elif line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|?\s*$", lines[i + 1]):
            head = _cells(line)
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            th = "".join(f"<th>{inline(c)}</th>" for c in head)
            body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f'<div class="tbl"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>')
        elif re.match(r"^(- |\* |\d+\. )", line):
            ordered = bool(re.match(r"^\d+\. ", line))
            items = []
            while i < len(lines) and re.match(r"^(- |\* |\d+\. )", lines[i]):
                item = re.sub(r"^(- |\* |\d+\. )", "", lines[i])
                m = re.match(r"^\[( |x|X)\] (.*)", item)
                if m:
                    box = "checked " if m.group(1) != " " else ""
                    item = f'<input type="checkbox" disabled {box}> {inline(m.group(2))}'
                else:
                    item = inline(item)
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip():
                    item += " " + inline(lines[i].strip())
                    i += 1
                items.append(f"<li>{item}</li>")
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>{''.join(items)}</{tag}>")
        elif line.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip("> "))
                i += 1
            out.append(f"<blockquote>{inline(' '.join(buf))}</blockquote>")
        elif re.match(r"^-{3,}\s*$", line):
            out.append("<hr>")
            i += 1
        else:
            buf = []
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4} |```|\||- |\* |\d+\. |>)", lines[i]):
                buf.append(lines[i].strip())
                i += 1
            if not buf:  # unknown construct: avoid an infinite loop
                buf.append(lines[i].strip())
                i += 1
            out.append(f"<p>{inline(' '.join(buf))}</p>")
    return "\n".join(out), toc


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · AgenticDev</title>
<meta name="description" content="{title}: AgenticDev documentation.">
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../style.css">
</head>
<body class="doc">
<a class="skip" href="#main">Skip to content</a>
<header><div class="wrap"><nav aria-label="Main">
  <a class="brand" href="../index.html"><span class="mark" aria-hidden="true">A</span>AgenticDev</a>
  <div class="links">{nav}</div>
</nav></div></header>
<div class="wrap docwrap">
  <aside aria-label="On this page"><div class="toc"><strong>On this page</strong>{toc}</div></aside>
  <main id="main" class="prose">
{body}
  <p class="edit">Source: <code>docs/{src}</code>. Generated by <code>tools/build_site.py</code>.</p>
  </main>
</div>
</body>
</html>
"""


def build(root=ROOT):
    root = Path(root)
    out_dir = root / "site" / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for slug, src, title in PAGES:
        md_path = root / "docs" / src
        body, toc = render(md_path.read_text(encoding="utf-8"))
        current = ' aria-current="page"'
        nav = '<a href="../index.html">Home</a>' + "".join(
            f'<a href="{s}.html"{current if s == slug else ""}>{t}</a>' for s, _, t in PAGES)
        toc_html = "".join(f'<a class="l{lvl}" href="#{hid}">{html.escape(txt)}</a>' for lvl, hid, txt in toc)
        page = PAGE.format(title=html.escape(title), nav=nav, toc=toc_html, body=body, src=src)
        target = out_dir / f"{slug}.html"
        target.write_text(page, encoding="utf-8")
        written.append(target)
    return written


def main(argv):
    for p in build():
        print(f"wrote {p.relative_to(ROOT)}")
    if "--serve" in argv:
        import functools
        import http.server
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "site"))
        print("serving http://localhost:8000  (ctrl-c to stop)")
        http.server.ThreadingHTTPServer(("127.0.0.1", 8000), handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
