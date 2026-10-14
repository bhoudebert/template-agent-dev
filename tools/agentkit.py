#!/usr/bin/env python3
"""agentkit: install and update this workflow kit in another repository (stdlib only, needs git).

    agentkit.py install [--target DIR] [--from SRC] [--with ci,docs,release] [--plan]
    agentkit.py status  [--target DIR]
    agentkit.py update  [scope ...] [--target DIR] [--from SRC] [--plan]   scopes: tools agents docs ci all
    agentkit.py check   [--target DIR]                                      unresolved conflict markers

Every write happens on a branch with one commit and nothing is pushed: you review the diff as a PR.
File classes (see kit.json): managed, tailorable (3-way merged), block (region inside a shared file),
side (placed next to the project's own file), seed (copied once, then yours).
"""
import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent.parent
LOCK = ".agentkit/lock.json"
BASE_DIR = ".agentkit/base"
IGNORE = ".agentkit/ignore"
CHANGES = ".agentkit/CHANGES.md"
MARK_MD = ("<!-- agentkit:begin -->", "<!-- agentkit:end -->")
MARK_HASH = ("# agentkit:begin", "# agentkit:end")
DEFAULT_UPDATE_SCOPES = ["tools", "agents", "docs"]   # `ci` is refreshed only when asked for
ALL_SCOPES = ["tools", "agents", "docs", "ci"]
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
import re

# A real conflict region (from `git merge-file -L local -L base -L kit`) has these exact marker lines.
# Anchored, so documentation or code that merely *mentions* them is not a conflict.
_OPEN = re.compile(r"^<<<<<<< local$", re.M)
_CLOSE = re.compile(r"^>>>>>>> kit$", re.M)


def has_conflict(text):
    return bool(_OPEN.search(text) and _CLOSE.search(text))


# ---------------------------------------------------------------- helpers
def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def run(cmd, cwd=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and p.returncode != 0:
        raise SystemExit(f"{' '.join(cmd)} failed: {p.stderr.strip() or p.stdout.strip()}")
    return p


def markers(dst):
    return MARK_MD if dst.endswith(".md") else MARK_HASH


def get_block(text, dst):
    begin, end = markers(dst)
    i = text.find(begin)
    if i < 0:
        return None
    j = text.find(end, i)
    if j < 0:
        return None
    return text[i + len(begin): j].strip("\n")


def set_block(text, dst, content):
    begin, end = markers(dst)
    wrapped = f"{begin}\n{content.rstrip()}\n{end}"
    i = text.find(begin)
    j = text.find(end, i) if i >= 0 else -1
    if i >= 0 and j >= 0:
        return text[:i] + wrapped + text[j + len(end):]
    if not text.strip():
        return wrapped + "\n"
    return text.rstrip("\n") + "\n\n" + wrapped + "\n"


def three_way(ours, base, theirs):
    """git merge-file. Returns (merged_text, conflicts)."""
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, content in (("local", ours), ("base", base), ("kit", theirs)):
            p = Path(d) / name
            p.write_text(content, encoding="utf-8")
            paths.append(str(p))
        p = subprocess.run(["git", "merge-file", "-p", "--diff3", "-L", "local", "-L", "base", "-L", "kit", *paths],
                           text=True, capture_output=True)
        if p.returncode < 0 or p.returncode > 127:
            raise SystemExit(f"git merge-file failed: {p.stderr}")
        return p.stdout, p.returncode


def drop_tasks(text, names):
    """Remove [tasks.<name>] / [tasks."<name>"] tables from a TOML document."""
    wanted = set()
    for n in names:
        wanted.add(f"tasks.{n}")
        wanted.add(f'tasks."{n}"')
    out, skipping = [], False
    for line in text.splitlines(keepends=True):
        s = line.strip()
        if s.startswith("["):
            skipping = s.strip("[]") in wanted
        if not skipping:
            out.append(line)
    return "".join(out)


# ---------------------------------------------------------------- kit source
class Kit:
    def __init__(self, root, label=None):
        self.root = Path(root)
        mf = self.root / "kit.json"
        if not mf.exists():
            raise SystemExit(f"{self.root} is not an agentkit source (no kit.json)")
        self.manifest = json.loads(mf.read_text(encoding="utf-8"))
        self.label = label or str(self.root)

    def files(self):
        out = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                out.append(Path(dirpath, name).relative_to(self.root).as_posix())
        return sorted(out)

    def read_text(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def version(self):
        p = self.root / ".release-please-manifest.json"
        base = "0.0.0"
        if p.exists():
            try:
                base = json.loads(p.read_text())["."]
            except (ValueError, KeyError):
                pass
        head = run(["git", "rev-parse", "--short", "HEAD"], cwd=self.root, check=False)
        return f"{base}+{head.stdout.strip()}" if head.returncode == 0 and head.stdout.strip() else base

    def entries(self, features):
        files = self.files()
        chosen = {"core"} | set(features)
        out, seen = [], {}
        for e in self.manifest["entries"]:
            if e["feature"] not in chosen:
                continue
            for rel in files:
                if not fnmatch.fnmatch(rel, e["match"]):
                    continue
                if any(fnmatch.fnmatch(rel, x) for x in e.get("exclude", [])):
                    continue
                dst = e["dst"].format(path=rel, name=os.path.basename(rel))
                content = self.read_text(rel)
                if e.get("drop_tasks"):
                    content = drop_tasks(content, e["drop_tasks"])
                item = {"src": rel, "dst": dst, "class": e["class"], "scope": e["scope"], "feature": e["feature"],
                        "content": content}
                if dst in seen:
                    continue
                seen[dst] = item
                out.append(item)
        return out


def open_source(src, ref=None):
    """Return (Kit, cleanup)."""
    if not src:
        return Kit(KIT_ROOT), lambda: None
    if "://" in src or src.startswith("git@"):
        tmp = tempfile.mkdtemp(prefix="agentkit-")
        cmd = ["git", "clone", "-q", "--depth", "1"] + (["--branch", ref] if ref else []) + [src, tmp]
        run(cmd)
        return Kit(tmp, label=src), lambda: shutil.rmtree(tmp, ignore_errors=True)
    return Kit(Path(src).expanduser().resolve()), lambda: None


# ---------------------------------------------------------------- target state
class Target:
    def __init__(self, root):
        self.root = Path(root).resolve()
        if run(["git", "rev-parse", "--is-inside-work-tree"], cwd=self.root, check=False).returncode != 0:
            raise SystemExit(f"{self.root} is not a git repository")

    def path(self, rel):
        return self.root / rel

    def lock(self):
        p = self.path(LOCK)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def write_lock(self, lock):
        p = self.path(LOCK)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def ignored(self):
        p = self.path(IGNORE)
        if not p.exists():
            return []
        return [l.strip() for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")]

    def local_sha(self, dst, cls):
        p = self.path(dst)
        if not p.is_file():
            return None
        if cls == "block":
            block = get_block(p.read_text(encoding="utf-8"), dst)
            return sha(block) if block is not None else None
        return sha(p.read_bytes())

    def base_copy(self, dst):
        p = self.path(f"{BASE_DIR}/{dst}")
        return p.read_text(encoding="utf-8") if p.exists() else None

    def save_base(self, dst, content):
        p = self.path(f"{BASE_DIR}/{dst}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def dirty_tracked(self):
        out = run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=self.root).stdout
        return [l for l in out.splitlines() if l.strip()]


def block_content(content):
    return content.strip("\n")


def entry_sha(item):
    return sha(block_content(item["content"])) if item["class"] == "block" else sha(item["content"])


# ---------------------------------------------------------------- actions
def write_file(target, dst, content):
    p = target.path(dst)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    if dst.endswith(".sh") or dst.startswith(".githooks/"):
        p.chmod(0o755)


def apply_block(target, dst, content):
    p = target.path(dst)
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    write_file(target, dst, set_block(text, dst, block_content(content)))


def plan_install(target, entries, lock=None):
    actions = []
    for e in entries:
        dst, cls = e["dst"], e["class"]
        exists = target.path(dst).exists()
        if cls == "seed":
            actions.append((dst, "keep-seed" if exists else "add-seed", e))
        elif cls == "block":
            if not exists:
                actions.append((dst, "create-block", e))
            elif get_block(target.path(dst).read_text(encoding="utf-8"), dst) is None:
                actions.append((dst, "append-block", e))
            else:
                actions.append((dst, "update-block", e))
        elif not exists:
            actions.append((dst, "add", e))
        elif target.path(dst).read_text(encoding="utf-8") == e["content"]:
            actions.append((dst, "adopt", e))
        else:
            actions.append((dst, "collision-kept", e))
    return actions


def new_branch(target, name):
    cur = run(["git", "branch", "--show-current"], cwd=target.root).stdout.strip()
    final, n = name, 1
    while run(["git", "rev-parse", "--verify", "-q", final], cwd=target.root, check=False).returncode == 0:
        n += 1
        final = f"{name}-{n}"
    run(["git", "switch", "-q", "-c", final], cwd=target.root)
    return cur, final


def commit(target, paths, message):
    run(["git", "add", "-A", "--", *paths], cwd=target.root)
    p = run(["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", message], cwd=target.root, check=False)
    if p.returncode != 0:
        err = (p.stderr or p.stdout).strip()
        hint = ("\nSet your identity first: git config user.name \"Your Name\"; git config user.email you@example.com"
                if "identity" in err.lower() or "user.name" in err.lower() or "user.email" in err.lower() else "")
        raise SystemExit(f"could not commit the kit changes (they are staged on the branch): {err}{hint}")


def cmd_install(args):
    target = Target(args.target)
    kit, cleanup = open_source(args.source, args.ref)
    try:
        if target.lock() and not args.plan:
            raise SystemExit("already installed here: use `update` (or `status`)")
        features = [f.strip() for f in (args.with_ or "").split(",") if f.strip()]
        unknown = [f for f in features if f not in kit.manifest["features"]]
        if unknown:
            raise SystemExit(f"unknown feature(s) {unknown}; available: {sorted(kit.manifest['features'])}")
        entries = kit.entries(features)
        actions = plan_install(target, entries)
        print(f"agentkit {kit.version()} -> {target.root}  features: core{''.join(',' + f for f in features)}")
        for dst, act, _ in actions:
            print(f"  {act:<15} {dst}")
        if args.plan:
            return 0
        dirty = target.dirty_tracked()
        if dirty and not args.no_branch:
            raise SystemExit("working tree has uncommitted changes to tracked files; commit or stash first")
        branch = None
        if not args.no_branch:
            _, branch = new_branch(target, "chore/agentkit-install")
        files = {}
        touched = [LOCK]
        for dst, act, e in actions:
            if act in ("add", "adopt") or act in ("add-seed",):
                if act != "adopt":
                    write_file(target, dst, e["content"])
            elif act in ("create-block", "append-block", "update-block"):
                apply_block(target, dst, e["content"])
            if act in ("keep-seed", "collision-kept"):
                continue
            touched.append(dst)
            if e["class"] != "seed":
                files[dst] = {"class": e["class"], "scope": e["scope"], "sha": entry_sha(e)}
            if e["class"] in ("tailorable", "block"):
                target.save_base(dst, block_content(e["content"]) if e["class"] == "block" else e["content"])
                touched.append(f"{BASE_DIR}/{dst}")
        lock = {"agentkit": 1, "version": kit.version(), "source": kit.label, "features": ["core"] + features,
                "files": files}
        target.write_lock(lock)
        if (target.root / "tools" / "index.py").exists():
            subprocess.run([sys.executable, "tools/index.py"], cwd=target.root, capture_output=True)
            if (target.root / "docs" / "INDEX.md").exists():
                touched.append("docs/INDEX.md")
        if not args.no_commit:
            commit(target, touched, f"chore(agentkit): install {kit.version()}")
        kept = [d for d, a, _ in actions if a == "collision-kept"]
        print(f"\ninstalled on branch {branch or '(current)'}; review the diff, then `mise run ship` or open a PR.")
        if kept:
            print("kept YOUR version (collision, not managed by the kit):\n  " + "\n  ".join(kept))
        print("next: fill in CONTEXT.md (stack, test command), then `mise run doctor`.")
        return 0
    finally:
        cleanup()


def classify(target, lock, entries):
    """Per locked entry: state in clean | local-edited | kit-changed | both | deleted | new."""
    rows, by_dst = [], {e["dst"]: e for e in entries}
    for dst, rec in sorted(lock["files"].items()):
        e = by_dst.get(dst)
        local = target.local_sha(dst, rec["class"])
        if e is None:
            rows.append((dst, rec["class"], "removed-upstream"))
            continue
        kit_changed = entry_sha(e) != rec["sha"]
        if local is None:
            state = "deleted"
        else:
            edited = local != rec["sha"]
            state = ("both" if edited and kit_changed else "local-edited" if edited
                     else "kit-changed" if kit_changed else "clean")
        rows.append((dst, rec["class"], state))
    for dst, e in by_dst.items():
        if dst not in lock["files"] and e["class"] != "seed":
            rows.append((dst, e["class"], "new"))
    return rows


def cmd_status(args):
    target = Target(args.target)
    lock = target.lock()
    if not lock:
        raise SystemExit("agentkit is not installed here: run `install`")
    kit, cleanup = open_source(args.source or lock.get("source"), args.ref)
    try:
        rows = classify(target, lock, kit.entries([f for f in lock["features"] if f != "core"]))
        print(f"installed {lock['version']}  kit {kit.version()}  features {lock['features']}")
        counts = {}
        for dst, cls, state in rows:
            counts[state] = counts.get(state, 0) + 1
            if state != "clean":
                print(f"  {state:<17} {cls:<10} {dst}")
        print("summary: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
        return 0
    finally:
        cleanup()


def cmd_update(args):
    target = Target(args.target)
    lock = target.lock()
    if not lock:
        raise SystemExit("agentkit is not installed here: run `install`")
    kit, cleanup = open_source(args.source or lock.get("source"), args.ref)
    try:
        scopes = ALL_SCOPES if "all" in args.scopes else (args.scopes or DEFAULT_UPDATE_SCOPES)
        bad = [s for s in scopes if s not in ALL_SCOPES]
        if bad:
            raise SystemExit(f"unknown scope(s) {bad}; use {ALL_SCOPES} or all")
        features = list(dict.fromkeys(lock["features"] + [f for f in (args.with_ or "").split(",") if f.strip()]))
        entries = [e for e in kit.entries([f for f in features if f != "core"]) if e["scope"] in scopes]
        ignore = target.ignored()
        actions = []   # (dst, action, entry, extra)
        for e in entries:
            dst, cls = e["dst"], e["class"]
            rec = lock["files"].get(dst)
            if any(fnmatch.fnmatch(dst, g) for g in ignore):
                actions.append((dst, "ignored", e, None))
                continue
            if rec is None:
                if cls == "seed":
                    if not target.path(dst).exists():
                        actions.append((dst, "new-seed-available", e, None))
                elif target.path(dst).exists() and cls != "block":
                    actions.append((dst, "collision-kept", e, None))
                else:
                    actions.append((dst, "add", e, None))
                continue
            kit_sha, local = entry_sha(e), target.local_sha(dst, cls)
            if local is None:
                actions.append((dst, "deleted-locally-kept", e, None))
            elif kit_sha == rec["sha"]:
                actions.append((dst, "unchanged", e, None))
            elif cls in ("managed", "side"):
                actions.append((dst, "update" if local == rec["sha"] else "overwrite-edited", e, None))
            elif local == rec["sha"]:
                actions.append((dst, "update", e, None))
            else:
                base = target.base_copy(dst)
                if base is None:
                    actions.append((dst, "needs-manual-merge", e, None))
                    continue
                ours = (get_block(target.path(dst).read_text(encoding="utf-8"), dst)
                        if cls == "block" else target.path(dst).read_text(encoding="utf-8"))
                merged, conflicts = three_way(ours, base, block_content(e["content"]) if cls == "block" else e["content"])
                actions.append((dst, "merged-clean" if conflicts == 0 else "CONFLICT", e, merged))
        for dst, rec in lock["files"].items():
            if rec["scope"] in scopes and dst not in {e["dst"] for e in entries}:
                actions.append((dst, "removed-upstream-kept", None, None))
        print(f"agentkit update {lock['version']} -> {kit.version()}  scopes: {', '.join(scopes)}")
        shown = [a for a in actions if a[1] != "unchanged"]
        for dst, act, _, _ in shown:
            print(f"  {act:<22} {dst}")
        if not shown:
            print("  nothing to do")
        if args.plan or not shown:
            return 0
        real = [a for a in shown if a[1] not in ("ignored", "new-seed-available", "collision-kept",
                                                 "deleted-locally-kept", "removed-upstream-kept", "needs-manual-merge")]
        if target.dirty_tracked() and not args.no_branch:
            raise SystemExit("working tree has uncommitted changes to tracked files; commit or stash first")
        branch = None
        if not args.no_branch:
            _, branch = new_branch(target, f"chore/agentkit-update-{kit.version().replace('+', '-')}")
        touched = [LOCK, CHANGES]
        conflicts = []
        for dst, act, e, merged in real:
            cls = e["class"]
            if act in ("update", "overwrite-edited", "add"):
                if cls == "block":
                    apply_block(target, dst, e["content"])
                else:
                    write_file(target, dst, e["content"])
            elif act in ("merged-clean", "CONFLICT"):
                if cls == "block":
                    apply_block(target, dst, merged)
                else:
                    write_file(target, dst, merged)
                if act == "CONFLICT":
                    conflicts.append(dst)
            lock["files"][dst] = {"class": cls, "scope": e["scope"], "sha": entry_sha(e)}
            touched.append(dst)
            if cls in ("tailorable", "block"):
                target.save_base(dst, block_content(e["content"]) if cls == "block" else e["content"])
                touched.append(f"{BASE_DIR}/{dst}")
        old = lock["version"]
        lock["version"], lock["features"] = kit.version(), features
        target.write_lock(lock)
        lines = [f"# agentkit update {old} -> {kit.version()}", "",
                 "Review this diff as you would any change. Files below need your attention.", ""]
        if conflicts:
            lines += ["## Conflicts to resolve (search for `<<<<<<< local`)", ""] + [f"- `{c}`" for c in conflicts] + [""]
        lines += ["## Actions", ""] + [f"- {a}: `{d}`" for d, a, _, _ in shown]
        target.path(CHANGES).write_text("\n".join(lines) + "\n", encoding="utf-8")
        if (target.root / "tools" / "index.py").exists():
            subprocess.run([sys.executable, "tools/index.py"], cwd=target.root, capture_output=True)
            if (target.root / "docs" / "INDEX.md").exists():
                touched.append("docs/INDEX.md")
        if not args.no_commit:
            commit(target, touched, f"chore(agentkit): update to {kit.version()}")
        print(f"\nupdated on branch {branch or '(current)'}; review the diff, then `mise run ship`.")
        if conflicts:
            print("CONFLICTS to resolve before merging:\n  " + "\n  ".join(conflicts))
        return 0
    finally:
        cleanup()


def _markers_in(text):
    return has_conflict(text)


def _local_side(text):
    """Lines of the `local` side of every conflict region, for the dropped-lines report."""
    out, mode = [], None
    for line in text.splitlines():
        if line.startswith("<<<<<<< local"):
            mode = "local"
        elif line.startswith("||||||| base") or line.startswith("======="):
            mode = None if line.startswith("=======") else "base"
        elif line.startswith(">>>>>>> kit"):
            mode = None
        elif mode == "local" and line.strip():
            out.append(line.strip())
    return out


def validate_resolution(dst, resolved):
    """Hard guards on a proposed merge. Returns a list of problems."""
    problems = []
    if not resolved.strip():
        problems.append("empty result")
    if _markers_in(resolved) or "||||||| base" in resolved:
        problems.append("conflict markers remain")
    if dst.endswith(".json"):
        try:
            json.loads(resolved)
        except ValueError as e:
            problems.append(f"invalid JSON: {e}")
    if dst.endswith(".toml"):
        try:
            import tomllib
            tomllib.loads(resolved)
        except Exception as e:  # noqa: BLE001 - any parse error is a rejection
            problems.append(f"invalid TOML: {e}")
    return problems


def parse_reply(reply):
    import re
    rat = re.search(r"RATIONALE:\s*(.+?)(?:\n<<<MERGED>>>|\Z)", reply, re.S)
    m = re.search(r"<<<MERGED>>>\n(.*?)\n?<<<END>>>", reply, re.S)
    return (rat.group(1).strip() if rat else ""), (m.group(1) if m else None)


def conflicted_files(target, lock):
    out = []
    for dst, rec in sorted((lock or {}).get("files", {}).items()):
        p = target.path(dst)
        if p.is_file() and _markers_in(p.read_text(encoding="utf-8", errors="replace")):
            out.append((dst, rec["class"]))
    return out


def cmd_reconcile(args):
    target = Target(args.target)
    lock = target.lock()
    if not lock:
        raise SystemExit("agentkit is not installed here")
    files = conflicted_files(target, lock)
    if not files:
        print("reconcile: no conflicted files")
        return 0
    role_p = target.path(".agents/roles/integrator.md")
    role = role_p.read_text(encoding="utf-8") if role_p.exists() else (KIT_ROOT / ".agents/roles/integrator.md").read_text()
    ctx_p = target.path("CONTEXT.md")
    context = ctx_p.read_text(encoding="utf-8") if ctx_p.exists() else "(no CONTEXT.md)"
    briefs = {}
    for dst, cls in files:
        text = target.path(dst).read_text(encoding="utf-8")
        inner = get_block(text, dst) if cls == "block" else text
        briefs[dst] = (cls, text, inner if inner is not None else text)
    if args.brief:
        outdir = target.path(".agentkit/reconcile")
        outdir.mkdir(parents=True, exist_ok=True)
        for dst, (cls, _, inner) in briefs.items():
            name = dst.replace("/", "__") + ".md"
            (outdir / name).write_text(
                f"# Reconcile `{dst}` ({cls})\n\nFollow `.agents/roles/integrator.md`. Resolve the markers below, "
                f"edit `{dst}` in place (for a block: only inside agentkit:begin/end), then run `mise run kit:check`.\n\n"
                f"## Project context\n\n{context}\n\n## File with conflict markers\n\n```\n{inner}\n```\n", encoding="utf-8")
            print(f"brief: .agentkit/reconcile/{name}")
        print("Give these briefs to your assistant (or run `agentkit reconcile` with a model configured).")
        return 0
    if args.plan:
        for dst, (cls, *_rest) in briefs.items():
            print(f"would reconcile {dst} ({cls})")
        return 0
    import providers
    done, failed, report = [], [], []
    for dst, (cls, text, inner) in briefs.items():
        user = (f"Project context (CONTEXT.md):\n{context}\n\nFile: {dst} (class: {cls})\n\n"
                f"File content with diff3 conflict markers:\n<<<FILE>>>\n{inner}\n<<<END>>>\n")
        try:
            reply = providers.complete(role, user, "strong", args.provider)
        except providers.ProviderError as e:
            raise SystemExit(f"reconcile needs a model: {e}\n(use `reconcile --brief` to hand the files to an assistant)")
        rationale, merged = parse_reply(reply)
        problems = validate_resolution(dst, merged or "")
        if merged is None:
            problems.append("no <<<MERGED>>> block in the reply")
        if problems:
            failed.append((dst, problems))
            continue
        dropped = [l for l in _local_side(inner) if l not in merged]
        new_text = set_block(text, dst, merged.strip("\n")) if cls == "block" else merged.rstrip("\n") + "\n"
        target.path(dst).write_text(new_text, encoding="utf-8")
        done.append(dst)
        report.append((dst, rationale, dropped))
    for dst, rationale, dropped in report:
        print(f"resolved {dst}: {rationale or '(no rationale)'}")
        for l in dropped[:5]:
            print(f"   not in result (review!): {l[:100]}")
    for dst, problems in failed:
        print(f"LEFT AS IS {dst}: {'; '.join(problems)}")
    if report:
        cp = target.path(CHANGES)
        extra = ["", "## Reconciled by a model (review each diff)", ""]
        for dst, rationale, dropped in report:
            extra.append(f"- `{dst}`: {rationale or 'no rationale given'}")
            extra += [f"  - project line not in the result: `{l[:100]}`" for l in dropped[:10]]
        cp.write_text((cp.read_text(encoding="utf-8") if cp.exists() else "# agentkit\n") + "\n".join(extra) + "\n",
                      encoding="utf-8")
        if not args.no_commit:
            commit(target, done + [CHANGES], "chore(agentkit): reconcile update conflicts")
    return 1 if failed else 0


def cmd_check(args):
    target = Target(args.target)
    lock = target.lock()
    bad = []
    for dst in (lock or {}).get("files", {}):
        p = target.path(dst)
        if p.is_file() and has_conflict(p.read_text(encoding="utf-8", errors="replace")):
            bad.append(dst)
    for b in bad:
        print(f"CONFLICT MARKERS in {b}")
    print(f"check: {len(bad)} file(s) with unresolved conflicts")
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--target", default=".", help="the repository to install into (default: current)")
        p.add_argument("--from", dest="source", help="kit source: a path or git URL (default: this kit)")
        p.add_argument("--ref", help="branch or tag when --from is a git URL")
        p.add_argument("--plan", action="store_true", help="show what would change, write nothing")
        p.add_argument("--no-branch", action="store_true", help="work on the current branch")
        p.add_argument("--no-commit", action="store_true", help="leave the changes uncommitted")

    i = sub.add_parser("install")
    common(i)
    i.add_argument("--with", dest="with_", default="", help="features: ci,docs,release")
    i.set_defaults(fn=cmd_install)
    s = sub.add_parser("status")
    common(s)
    s.set_defaults(fn=cmd_status)
    u = sub.add_parser("update")
    common(u)
    u.add_argument("scopes", nargs="*", help="tools agents docs ci all (default: tools agents docs)")
    u.add_argument("--with", dest="with_", default="", help="add features: ci,docs,release")
    u.set_defaults(fn=cmd_update)
    r = sub.add_parser("reconcile", help="resolve update conflicts with a model (or write briefs for an assistant)")
    r.add_argument("--target", default=".")
    r.add_argument("--provider", help="openai | cmd (default: AGENT_PROVIDER)")
    r.add_argument("--brief", action="store_true", help="write briefs to .agentkit/reconcile/ instead of calling a model")
    r.add_argument("--plan", action="store_true")
    r.add_argument("--no-commit", action="store_true")
    r.set_defaults(fn=cmd_reconcile)
    c = sub.add_parser("check")
    c.add_argument("--target", default=".")
    c.set_defaults(fn=cmd_check)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
