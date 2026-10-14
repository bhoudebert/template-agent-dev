"""Tiny YAML-subset parser (stdlib only).

Supports: block maps, block lists (of scalars or maps), inline lists `[a, b]`,
quoted/plain scalars, ints, true/false/null, `#` comments.
Does NOT support: anchors, multiline scalars, flow maps, nested inline lists.
Enough for pipeline.yaml and artifact frontmatter; keeps the repo dependency-free.
"""
import re

_KEY = re.compile(r"^([A-Za-z0-9_.\-/{}]+):(?:\s+(.*))?$")
_INT = re.compile(r"^-?\d+$")


def _strip_comment(line):
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] == " "):
            return line[:i]
    return line


def _split_inline(s):
    parts, buf, quote = [], "", None
    for ch in s:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf += ch
        elif ch == ",":
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)
    return parts


def _scalar(s):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        return [_scalar(p) for p in _split_inline(s[1:-1])]
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "~", ""):
        return None
    if _INT.match(s):
        return int(s)
    return s


def _is_item(text):
    return text == "-" or text.startswith("- ")


def _block(lines, i, indent):
    if _is_item(lines[i][1]):
        return _list(lines, i, indent)
    return _map(lines, i, indent)


def _list(lines, i, indent):
    out = []
    while i < len(lines) and lines[i][0] == indent and _is_item(lines[i][1]):
        text = lines[i][1]
        content = text[1:].strip()
        if content == "":
            i += 1
            if i < len(lines) and lines[i][0] > indent:
                v, i = _block(lines, i, lines[i][0])
                out.append(v)
            else:
                out.append(None)
        elif _KEY.match(content):
            offset = indent + (len(text) - len(content))
            lines[i] = [offset, content]
            v, i = _map(lines, i, offset)
            out.append(v)
        else:
            out.append(_scalar(content))
            i += 1
    return out, i


def _map(lines, i, indent):
    out = {}
    while i < len(lines) and lines[i][0] == indent and not _is_item(lines[i][1]):
        m = _KEY.match(lines[i][1])
        if not m:
            raise ValueError(f"cannot parse line: {lines[i][1]!r}")
        key, rest = m.group(1), m.group(2)
        i += 1
        if rest is None or rest.strip() == "":
            nested = i < len(lines) and (
                lines[i][0] > indent or (lines[i][0] == indent and _is_item(lines[i][1]))
            )
            if nested:
                out[key], i = _block(lines, i, lines[i][0])
            else:
                out[key] = None
        else:
            out[key] = _scalar(rest)
    return out, i


def loads(text):
    lines = []
    for raw in text.splitlines():
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ValueError("tabs not allowed for indentation")
        s = _strip_comment(raw.rstrip())
        if s.strip():
            lines.append([len(s) - len(s.lstrip(" ")), s.strip()])
    if not lines:
        return {}
    value, i = _block(lines, 0, lines[0][0])
    if i != len(lines):
        raise ValueError(f"unexpected content: {lines[i][1]!r}")
    return value


def split_frontmatter(text):
    """Return (meta_dict | None, body). None when no leading `---` block."""
    if not text.startswith("---"):
        return None, text
    m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", text, re.DOTALL)
    if not m:
        return None, text
    return loads(m.group(1)), text[m.end():]
