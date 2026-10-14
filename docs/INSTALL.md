# Install guide

Add the agentic workflow to a repository you already have, keep it up to date, and take it out again.
Every step happens **on a branch, as one commit, with nothing pushed**: you review the change as a pull request.

## What it does to your repository

It adds files and one marked region in a few shared files. It never rewrites your code, your CI, or your
`mise.toml`.

| It adds | Where | Notes |
|---|---|---|
| Tools | `tools/*.py`, `tools/*.sh`, `.githooks/` | the runner, validators, helpers, git hooks |
| The recipe | `.agents/` | roles, skills, policies, templates, schemas, `pipeline.yaml` |
| Tasks | `.config/mise/conf.d/agentkit.toml` | next to your own `mise.toml`; your task names win a clash |
| Rules | a marked block inside `AGENTS.md` and `.gitignore` | your text is untouched; created if absent |
| Starters (copied once, then yours) | `CONTEXT.md`, `.env.example`, empty `docs/` folders, `openspec/` | never overwritten, never updated |
| Bookkeeping | `.agentkit/` | what was installed, so updates can tell your edits from the kit's |

Optional features: `ci` (GitHub workflows, as `agentkit-*.yml`), `docs` (these docs under `docs/agentkit/`),
`release` (release-please), `pointers` (so Claude Code, Copilot and Cursor load `AGENTS.md`).

## Before you start

| Need | Why | Check |
|---|---|---|
| git 2.23+ | branches and 3-way merges | `git --version` |
| Python 3.10+ | the tools are standard-library only: nothing to `pip install` | `python3 --version` |
| [mise](https://mise.jdx.dev) | the short commands (`mise run story ...`) | `mise --version` |
| `gh`, logged in | opening PRs with `mise run ship` | `gh auth status` |
| A model, only to run stages | any OpenAI-compatible API, a local Ollama, or a CLI such as `claude -p` | see step 4 |

mise is recommended, not required: every task is a plain `python3 tools/...` command underneath.
Your repository must be a git repository with a clean working tree (the installer refuses otherwise).

## 1. Get the installer

**From a release (no clone).** One executable file holds the engine and the exact kit for that version. It is published as `agentkit-<arch>-<os>.tar.gz` (the same bytes for every platform, named so mise and `curl | tar` find it) with an `agentkit.sha256`.

```sh
mkdir -p ~/.local/bin
os=$(uname -s); arch=$(uname -m)
case "$os" in Darwin) os=apple-darwin;; *) os=unknown-linux-gnu;; esac
case "$arch" in arm64|aarch64) arch=aarch64;; *) arch=x86_64;; esac
curl -fsSL "https://github.com/bhoudebert/template-agent-dev/releases/latest/download/agentkit-$arch-$os.tar.gz" \
  | tar -xz -C ~/.local/bin
agentkit --help
```

Or let mise manage it (verified against the `v0.1.0` release):

```sh
mise use -g "github:bhoudebert/template-agent-dev@latest"
```

Two things can stop that, both from mise, not from the kit:

| mise says | Why | Do |
|---|---|---|
| `no versions found ... matching date filter` | mise hides releases younger than its release-age cooldown (a supply-chain guard), so a **brand-new** release is invisible for a while | wait, or bypass once: `mise use -g --minimum-release-age 0 "github:bhoudebert/template-agent-dev@latest"`, or exempt it for good: `mise settings add minimum_release_age_excludes github:bhoudebert/template-agent-dev` |
| `No matching asset found for platform ...` | the release has no platform archive attached (`agentkit-<arch>-<os>.tar.gz`), **or mise is reading an old cached copy of the release** | see the cache row below; otherwise use the `curl` line above, or re-run the `release-pyz` workflow for that tag |
| `GitHub rate limit exceeded` / `no versions found` for a release you can see | without a token mise asks GitHub's API anonymously: **60 requests an hour per IP**, shared by everything on your network. Mise then reports "no versions" instead of a clear error | give mise a token for the command: `GITHUB_TOKEN=$(gh auth token) mise use -g ...`, or export `GITHUB_TOKEN` (no scopes needed) |
| `Available assets:` lists names that are **not** on the release page, or mise never sees a newer version | mise caches GitHub's release data for a long time. If it read the release while its assets were different (a draft, or edited afterwards), it keeps using that copy | `mise cache clear`, then retry. Your cache holds compressed files, so grepping it will not show the names |

**From a clone** (before the first release, or to contribute):

```sh
git clone https://github.com/bhoudebert/template-agent-dev ~/src/agentkit
cd ~/src/agentkit && mise trust
```

Below, `agentkit ...` is the release file; from a clone use `mise run kit:install ../my-repo ...` for install and
`python3 ~/src/agentkit/tools/agentkit.py ...` for the rest.

### What lands on your PATH, and what lands in the repo

Installing the kit puts **nothing** on your PATH by itself, and the repo does not need the release file to work
day to day. There are three entry points:

| Entry point | Lives | Use it for |
|---|---|---|
| `agentkit` (the release file) | on your PATH, once per machine | `install`, and `update`: it carries the newer kit |
| `mise run kit:status`, `kit:update`, `kit:reconcile`, `kit:check`, `kit:uninstall` | tasks in the repo | the same engine, inside the repo; they use `agentkit` if it is on your PATH, else the repo's own copy |
| `python3 tools/agentkit.py ...` | inside the repo | status, check, reconcile, uninstall without mise. It cannot *update* from a release: there is no kit beside it |

So in a repo, `mise run kit:update` is all you type, provided `agentkit` is on your PATH (or the repo was installed
from a clone, whose path the lock remembers).

### Getting all the commands in a repo (with or without its own mise)

After `agentkit install`, the repo has `.config/mise/conf.d/agentkit.toml`. Run `mise trust` once and
`mise tasks` lists them (about 40), whether or not the repo already has a `mise.toml`:

- **The repo has its own `mise.toml`**: its tasks and `[tools]` stay as they are; the kit's tasks sit beside them
  and **yours win a name clash**.
- **The repo has no mise config at all**: the kit's file alone is enough for mise to list and run the tasks.
- **mise is not installed**: every task is a plain command. The ones you use most:

| mise task | Without mise |
|---|---|
| `mise run orient` / `next` | `python3 tools/orient.py` / `python3 tools/orient.py next` |
| `mise run new "Title" --text "..."` | `python3 tools/items.py new-story Title --text "..."` |
| `mise run branch US-001` | `python3 tools/items.py branch US-001` |
| `mise run story US-001` (any stage) | `python3 tools/agentrun.py run story --id US-001 --apply` (`--dry-run` to preview) |
| `mise run prepare` / `apply` | `python3 tools/agentrun.py prepare ...` / `apply ...` |
| `mise run advance US-001 approved` | `python3 tools/items.py set-status US-001 approved` |
| `mise run check` | `python3 tools/validate.py && python3 tools/trace_check.py && sh tools/projecttest.sh` |
| `mise run review` | `sh tools/review.sh` |
| `mise run ship` | `sh tools/ship.sh main` |
| `mise run index` | `python3 tools/index.py` |

**Pin the kit for the whole team** (the one place the installer never edits for you is your `mise.toml`, so this
is yours to add): `mise use "github:bhoudebert/template-agent-dev@0.1.0"` records the version under `[tools]`,
and `mise install` then gives every teammate the same `agentkit` (subject to the release-age cooldown in step 1).

### "What is left to do?"

Any time, in any repo, before or after installing:

```sh
agentkit todo            # or, inside an installed repo: mise run kit:todo
```

It inspects *this* repository and prints an ordered checklist with the command that fixes each open item
(clean tree, no name collision in `tools/`, install, merged, `mise trust`, hooks, a filled `CONTEXT.md`, a test
command, a model in `.env`, a first story, assistant entry files). It writes nothing.

## 2. See what it would do

```sh
cd ~/code/my-repo
agentkit install --plan
```

Nothing is written. You get one line per file: `add`, `append-block`, `add-seed`, or `collision-kept` (a file
you already have with different content: **yours is kept**, and it is listed).

## 3. Install

```sh
agentkit install                       # core
agentkit install --with pointers,ci    # core + assistant entry files + GitHub workflows
```

You end up on a branch `chore/agentkit-install` with a single commit:

```
installed on branch chore/agentkit-install; review the diff, then `mise run ship` or open a PR.
```

Read the diff (`git show --stat`, then the files that matter: `AGENTS.md`, `.gitignore`, anything in the
collision list). When you are happy, open the PR the normal way, or:

```sh
mise trust            # lets mise read the new task file
mise run ship         # checks, push, open the PR; merge it like any other
```

## 4. Make it yours (10 minutes)

| Do | Why |
|---|---|
| Edit `CONTEXT.md` | every agent reads it first: what the product is, the stack, the test command, conventions |
| `cp .env.example .env`, set `AGENT_MODEL` | which model runs the stages; `.env` is git-ignored |
| `mise run hooks` | blocks assistant names in commit messages and any push to `main` |
| `mise run doctor` | checks python, git, hooks, endpoint, that the model is served |
| `mise run check` | runs the validators and **your** tests (npm, pytest, go, cargo and mvn are auto-detected **at the repo root**) |

How `mise run test` finds your tests (first match wins):

| # | Source | For |
|---|---|---|
| 1 | `commands.test` in `.agents/pipeline.yaml` | one command line: `test: "make check"` |
| 2 | `.agents/commands/test.sh` | a script **you own**; the kit never overwrites it |
| 3 | the repo root: `Cargo.toml`, `go.mod`, `package.json` with a test script, `pyproject.toml`/`pytest.ini`, `pom.xml` | a single-project repo |
| 4 | **one folder down**: each sub-folder with one of those markers (so `backend/` and `ui/` are found) | a monorepo |

See what it would run, without running it: `sh tools/projecttest.sh list`. Do **not** edit
`tools/projecttest.sh` itself: it is kit-managed and an update overwrites it. If nothing is found, `mise run test`
stops with instructions instead of pretending that nothing failed.

Pick a model (one of):

```sh
# local Ollama
AGENT_PROVIDER=openai
AGENT_BASE_URL=http://localhost:11434/v1
AGENT_MODEL=gemma4:12b
AGENT_REASONING_EFFORT=none        # for "thinking" models: otherwise a stage can spend minutes and return nothing

# hosted, any OpenAI-compatible API
AGENT_BASE_URL=https://api.example.com/v1
AGENT_API_KEY=...
AGENT_MODEL_STRONG=...
AGENT_MODEL_CHEAP=...

# or a CLI you already use (the prompt goes in on stdin)
AGENT_PROVIDER=cmd
AGENT_CMD="claude -p"
```

Using an assistant (Claude Code, Codex, Copilot) instead of an API? You need no model setting: it drives the same
steps with `mise run orient` and `prepare`/`apply`. Install with `--with pointers` so it loads `AGENTS.md`.

## 5. Check that it works

```sh
mise run doctor        # expect: all [ok]; if it says the model is not served, set AGENT_MODEL to one it lists
mise run check         # expect: validate 0 errors, trace_check 0 problems, your tests pass
mise run new "Try it out" --text "A small request, to prove the loop works end to end."
mise run story US-001 --dry     # prints the exact prompt; no model call, no cost
```

If those four work, the install is sound. The first real story is the tutorial: `docs/agentkit/TUTORIAL.md`
(install with `--with docs`), or [TUTORIAL.md](TUTORIAL.md) in the kit.

## 6. Update

```sh
agentkit status               # per file: clean / you edited / kit changed / both
agentkit update --plan        # what would change, nothing written
agentkit update               # branch chore/agentkit-update-<version>, one commit, a CHANGES.md
```

| Command | Touches |
|---|---|
| `agentkit update` | tools, agents (roles, policies, pipeline), docs |
| `agentkit update tools` | tools, hooks, schemas, templates, the mise task file |
| `agentkit update agents` | roles, skills, policies, `pipeline.yaml`, the blocks in `AGENTS.md` / `.gitignore` |
| `agentkit update docs` | the kit docs |
| `agentkit update ci` | workflows. **Only when you ask**: CI is installed once and refreshed on purpose. |

Get the newer kit first: re-download the release file (or `mise upgrade agentkit`), or `git pull` your clone.

What an update does to each kind of file:

| Your file is... | The kit... |
|---|---|
| a managed file you did not touch (tools, schemas, templates) | overwrites it |
| a managed file you edited | overwrites it; your edit shows as a deletion in the PR (use `.agentkit/ignore` to keep it) |
| a role, skill, policy or `pipeline.yaml` you tuned | **3-way merges**; a real conflict is left as markers |
| `AGENTS.md`, `.gitignore`, `CLAUDE.md` | rewrites only the marked block |
| a starter (`CONTEXT.md`, ...) | leaves it alone |

**Conflicts.** The update lists them in `.agentkit/CHANGES.md` and leaves diff3 markers
(`<<<<<<< local` / `||||||| base` / `>>>>>>> kit`). Resolve them one of three ways:

```sh
agentkit reconcile            # a model merges each file; validated, then shown to you as a diff
agentkit reconcile --brief    # writes .agentkit/reconcile/*.md for your assistant to resolve
# or edit the files by hand, then:
agentkit check                # fails while any marker remains (CI runs the same check)
```

`reconcile` never writes a reply that leaves markers, is empty, or is invalid JSON/TOML, and it lists any of
your lines that are missing from the result. You review the final diff either way.

Read `.agentkit/CHANGES.md` and the kit's release notes before merging an update PR: that is where a breaking
change is announced.

## 7. Keep your changes, stop the kit touching a file

Create `.agentkit/ignore` with one glob per line:

```
.agents/roles/reviewer.md
docs/agentkit/*
```

Those files are reported as `ignored` on every update. Also usual: tune `.agents/roles/*`, `policies/*` and
`pipeline.yaml` freely; the 3-way merge carries your changes forward.

Your own prefix and folders (a tracker key like `PROJ-4821`, `docs/adr/` instead of `docs/decisions/`) are a few
lines in `.agents/pipeline.yaml`; see the [reference](REFERENCE.md).

## 8. Remove it

```sh
agentkit uninstall --plan
agentkit uninstall            # branch chore/agentkit-uninstall
```

Removes the files and blocks the kit installed, and `.agentkit/`. It keeps your starters and anything you
edited (add `--force` to remove edited files too).

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `working tree has uncommitted changes` | commit or stash tracked changes first, then run again |
| `could not commit ... Set your identity` | `git config user.name "You"; git config user.email you@example.com` |
| `collision-kept` lines | you already had that file; yours was kept and is not managed. Rename it if you want the kit's. |
| `no kit source here` on `update` | nothing on your PATH carries a kit: put the `agentkit` release file on your PATH (then `mise run kit:update` works), or pass `--from <clone or URL>` |
| `kit:*` tasks missing | `mise trust` (mise must trust the new task file) |
| `mise: command not found` | install mise, or run the tools directly: see the table above |
| `agentkit: command not found` | the release file is not on your PATH: `~/.local/bin` must be on it, or call it by full path |
| `mise use github:...` finds no version, or no asset | see the table in step 1: the release-age cooldown, or a release without the asset |
| `agentkit check` fails | unresolved conflict markers: `agentkit reconcile`, or edit the files |
| A stage runs for minutes then `model returned no text` | a thinking model used its budget: `AGENT_REASONING_EFFORT=none` |
| `doctor` says hooks not enabled | `mise run hooks` |

## For maintainers: publishing a release

- Do **not** edit a release's assets after it is published. mise (and anyone who already installed) caches the
  release data; a release that changed after being read is invisible or wrong until each cache is cleared.
  Publish a new patch release instead.
- The assets must keep this shape, which mise detects with no options: the same executable as
  `agentkit-{x86_64,aarch64}-{unknown-linux-gnu,apple-darwin}.tar.gz` plus one `agentkit.sha256`. A platform-less
  or extension-less asset, a raw `agentkit` file, or one `.sha256` per archive stops mise resolving the release.
- `release-please.yml` builds and attaches them right after it creates the release (a release made with the
  default token does not trigger other workflows). To re-attach by hand: `gh workflow run release-pyz.yml -f tag=vX.Y.Z`.

## What gets recorded

`.agentkit/lock.json` (commit it): the kit version, the features, and per file its class and the hash that was
installed. `.agentkit/base/` holds the installed copy of the files that can be merged (roles, policies, blocks) so
a merge never needs the network. `.agentkit/CHANGES.md` is rewritten by each update.
