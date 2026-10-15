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

Optional features: `github-actions` (GitHub Actions workflows, as `agentkit-*.yml`; the old name `ci` still works), `docs` (these docs under `docs/agentkit/`),
`release` (release-please), `pointers` (so Claude Code, Copilot and Cursor load `AGENTS.md`).

## The mental model (read this once)

Two things exist, and people confuse them:

| | The **program** | The **copy in your repo** |
|---|---|---|
| What | `agentkit`: one file on your computer, installed by mise from a GitHub release | `tools/`, `.agents/`, `.config/mise/conf.d/agentkit.toml`, ... committed in your repository |
| Where | your `PATH` (`which agentkit`) | your git repository, shared with your team |
| Contains | the installer **and a frozen snapshot of the whole kit** for one release | the files the program installed, plus `.agentkit/lock.json` saying which version they came from |
| Changes when | **you** run `mise upgrade agentkit` | **you** run `agentkit update` and merge the PR |

```
GitHub release v0.2.0          your computer                 your repository
 agentkit-*.tar.gz  --mise-->  agentkit (v0.2.0 inside) --install/update--> tools/, .agents/, ...
                               (mise upgrade agentkit)      (a branch + one commit, then a PR)
```

What follows from that:

- **Nothing updates itself.** `agentkit status`, `mise run kit:status` and the other `kit:*` tasks only run
  the program you already have and compare it with `.agentkit/lock.json`. They do not look at GitHub and
  download nothing.
- **A new release reaches you in two steps, both yours:** (1) `mise upgrade github:bhoudebert/template-agent-dev` (or the forced install in [Update](#upgrading-the-program-when-mise-upgrade-does-nothing)) gets the newer
  program; (2) `agentkit update` in each repository copies the new files in, as a PR you review and merge.
- **Until you do that, nothing breaks.** The old program keeps working and the repository keeps the files it
  has. You only miss what is new: a command that does not exist yet (`agentkit todo`, `--version`, test
  discovery) fails with `invalid choice: 'todo'`, or a `mise run` task is absent because its definition ships in the
  repo copy and arrives with `agentkit update`.
- **Upgrading the program alone is often enough** for installer commands (`install`, `todo`, `status`,
  `update`, `uninstall`). **Updating the repo** is needed for the tools and `mise run` tasks that live in the
  repository.
- **Which version do I have?** `agentkit --version` is the program. `agentkit status` also prints the version
  the repository was installed from. Different numbers mean you have an update to apply.
- **Two repositories, two copies.** Each repository records its own version. Upgrading the program does not
  touch any repository; you run `agentkit update` in each.

The "stuck" cases:

| Symptom | Cause | Fix |
|---|---|---|
| `agentkit: command not found` | not installed, or mise shims not on `PATH` | step 1; `mise reshim` |
| `agentkit --version` says the old number after upgrading, or `mise upgrade` does nothing | mise hides releases younger than its cooldown, or treats the old `latest` folder as current | `mise install "github:bhoudebert/template-agent-dev@<version>" --force --minimum-release-age 0` ([details](#upgrading-the-program-when-mise-upgrade-does-nothing)) |
| `invalid choice: 'todo'` (or another command) | the program is older than the feature | `mise upgrade agentkit` |
| a `mise run` task is missing in the repo | the repo copy is older than the program | `agentkit update`, merge the PR |
| `no kit source here ...` | the repo was installed from a release and the program is not on `PATH` | install or upgrade `agentkit`, or pass `--from <kit clone or URL>` |

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

> **Which command do I type?** `agentkit ...` manages the kit (install, update, status, todo, uninstall);
> `mise run ...` does the day-to-day work (stories, stages, review, ship, tests). The `kit:*` mise tasks just
> call `agentkit`. Full table: [Three ways to run things](REFERENCE.md#three-ways-to-run-things).

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
agentkit install --with pointers,github-actions   # core + assistant entry files + GitHub Actions workflows
```

Before writing, it says what it is about to do (a new branch, one commit, nothing pushed) and, on a
terminal, asks to continue. `--yes` skips the question; `--plan` writes nothing. When done it prints the
steps that follow:

```
installed on branch chore/agentkit-install.

next steps:
  1. review what changed: `git show --stat HEAD`
  2. publish: `git push -u origin chore/agentkit-install`, then open a PR and merge it
     (`gh pr create --fill-first`, or `mise trust && mise run ship`)
  3. after the merge: `git switch main && git pull`
  4. then, on the base branch: `mise trust; mise run hooks`
  5. fill in CONTEXT.md (stack, test command)
  6. `agentkit todo` lists what is left; `mise run doctor` checks the setup
```

Nothing is on `main` until you merge that PR. `update` and `uninstall` work the same way.
`agentkit --version` (or `agentkit version`) prints the release you have.

### Turning on CI (GitHub Actions)

CI is optional and off by default. Only GitHub Actions is supported today; if you use another CI, skip it
(a GitLab adapter is not built).

```sh
agentkit install --with github-actions            # at install time, or
agentkit update  --with github-actions            # on a repository that already has the kit
```

What it does, and does not do:

- It **copies three files** into `.github/workflows/`: `agentkit-ci.yml`, `agentkit-agent-review.yml` and
  `agentkit-agent-triage.yml`. It configures nothing on GitHub and starts nothing: GitHub runs them by
  itself once they are pushed, because that is what it does with files in that folder.
- `agentkit-ci.yml` needs no setup: PR title is a Conventional Commit, no assistant names, evidence floor,
  validators, kit tests, and **your project tests** (`tools/projecttest.sh`, the same discovery as
  `mise run test`).
- The two `agent-*` workflows need a reachable model (repository variables `AGENT_BASE_URL`,
  `AGENT_MODEL_STRONG` / `AGENT_MODEL_CHEAP` and secret `AGENT_API_KEY`). Without them they **skip with a
  notice**; they do not fail. A GitHub-hosted runner cannot reach a model on your laptop.
- Adding it on a repository that is already installed goes on the same `chore/agentkit-*` branch if you are
  on one, otherwise on a new one. Merge that PR and the workflows start running.
- Make `checks` a required check in the repository's branch protection, or CI only advises.
- The workflow does not install your project's dependencies (`npm ci`, `cargo fetch`, ...). A monorepo
  usually needs a step for that added to `agentkit-ci.yml`; then list the file in `.agentkit/ignore` so an
  update does not overwrite your edit.

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
| 1 | **`.agents/tests.yaml`** (yours, the kit never ships or updates it) | declared suites: a name, a folder and a command each |
| 2 | `commands.test` in `.agents/pipeline.yaml` | one command line: `test: "make check"` |
| 3 | `.agents/commands/test.sh` | a script **you own** |
| 4 | the repo root: `Cargo.toml`, `go.mod`, `package.json` with a test script, `pyproject.toml`/`pytest.ini`, `pom.xml` | a single-project repo |
| 5 | **one folder down**: each sub-folder with one of those markers (so `backend/` and `ui/` are found) | a monorepo, zero config |

**No config file? It tries on its own.** Rows 4 and 5 are automatic: it looks for these files at the repo
root, then one folder down (skipping `node_modules`, `target`, `vendor`, `dist`, `build`, `docs`, `examples`,
`tools`, `site`, `openspec`, `venv`), and runs the usual command. The suite name is the folder name.

| It finds | It runs |
|---|---|
| `Cargo.toml` | `cargo test` |
| `go.mod` | `go test ./...` |
| `package.json` with a real `test` script | `npm test` |
| `pyproject.toml`, `pytest.ini`, `setup.cfg` | `pytest` |
| `pom.xml` | `mvn test` |

That is a guess from conventions. Declare suites (below) when you need a different command, env vars, a
timeout, a suite that only runs on request, or when it picks up a folder that is not a project.

The declared form, for when you want control:

```yaml
# .agents/tests.yaml
suites:
  - name: backend
    dir: backend              # folder, default: the repo root
    run: cargo test           # the command (required)
    env: [RUST_LOG=warn]      # optional
    timeout: 900              # optional, seconds
  - name: ui
    dir: ui
    run: npm test
  - name: e2e
    dir: ui
    run: npx playwright test
    manual: true              # only when named: mise run test e2e
    optional: true            # a failure is reported but does not fail the run
```

`run` is any shell command, executed in `dir`: a mise task, a script, a `docker compose` call, or several
commands chained with `&&`. That is how you add a heavy end-to-end or non-regression suite:

```yaml
  - name: nrt
    dir: .
    run: mise r nrt           # a task defined in YOUR mise.toml (or: sh scripts/nrt.sh)
    env: [API_URL=http://localhost:8080]
    timeout: 1800
    manual: true              # not in a plain `mise run test`; run it with `mise run test nrt`
```

`env` is a list of `KEY=value` strings, not a map. The task named in `run` is yours: the kit does not define it.

```sh
mise run test              # every suite that is not manual; all run, a failure fails the run and names the suite
mise run test backend ui   # only these
mise run test:list         # what would run and why; runs nothing
mise run test:init         # write .agents/tests.yaml from what was discovered, for you to edit
```

Do **not** edit `tools/projecttest.sh`: it is kit-managed and an update overwrites it. If nothing is found,
`mise run test` stops with instructions instead of pretending that nothing failed.

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
agentkit update               # branch chore/agentkit-update-<version>, one commit, a new entry in .agentkit/CHANGES.md
```

| Command | Touches |
|---|---|
| `agentkit update` | tools, agents (roles, policies, pipeline), docs |
| `agentkit update tools` | tools, hooks, schemas, templates, the mise task file |
| `agentkit update agents` | roles, skills, policies, `pipeline.yaml`, the blocks in `AGENTS.md` / `.gitignore` |
| `agentkit update docs` | the kit docs |
| `agentkit update github-actions` | the GitHub Actions workflows (`ci` is accepted as an alias). **Only when you ask**: they are installed once and refreshed on purpose. |

Get the newer program first (`mise upgrade agentkit`, or re-download the release file, or `git pull` your clone): `update` copies what is **inside the program you run**, it does not fetch anything. See [The mental model](#the-mental-model-read-this-once).

### Upgrading the program when `mise upgrade` does nothing

If your config says `"github:bhoudebert/template-agent-dev" = "latest"`, mise may report
`All tools are up to date` while an older release sits in its `latest` folder, and the cooldown can hide
the newest releases (`N newer ... releases hidden by minimum_release_age`). Name the tool in full (`agentkit`
alone is not a mise tool name) and force the version you want:

```sh
GITHUB_TOKEN=$(gh auth token) \
  mise install "github:bhoudebert/template-agent-dev@0.2.0" --force --minimum-release-age 0
mise exec -- agentkit --version      # or: agentkit --version, once mise is activated in your shell
```

`GITHUB_TOKEN` avoids GitHub's 60 requests/hour anonymous limit. If it still looks stale, `mise cache clear`
and run it again. Replace `0.2.0` with the release you want (see the
[releases page](https://github.com/bhoudebert/template-agent-dev/releases)).

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
| `mise upgrade` says `All tools are up to date` but `agentkit --version` is old | the `latest` folder holds an old release, or the cooldown hides the new one: see [Upgrading the program when `mise upgrade` does nothing](#upgrading-the-program-when-mise-upgrade-does-nothing) |
| `mise upgrade` says `All tools are up to date` but `agentkit --version` is old | the `latest` folder holds an old release, or the cooldown hides the new one: see [Upgrading the program when `mise upgrade` does nothing](#upgrading-the-program-when-mise-upgrade-does-nothing) |
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
a merge never needs the network. `.agentkit/CHANGES.md` keeps the last 10 updates, newest first; older ones are in git history.
