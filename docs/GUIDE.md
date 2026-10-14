# User guide

How to run a feature through the agentic SDLC, step by step.

## 0. Shortcut: mise tasks (no long commands)

Everything below has a short [mise](https://mise.jdx.dev) task. `mise tasks` lists them all.

```sh
mise trust                      # once
cp .env.example .env            # set AGENT_MODEL etc.; loaded automatically
mise run doctor                 # python, git, endpoint, model served?
mise run new Export invoices as CSV     # -> docs/stories/US-002.md (next id)
mise run story US-002 --dry             # preview prompt, no LLM
mise run story US-002                   # run stage: write files + checks
mise run advance US-002 approved        # guarded status bump after the gate
mise run spec US-002 / design / implement / test / qa / review / release
mise run incident Checkout 500s         # -> docs/incidents/INC-001.md, paste evidence
mise run diagnose INC-001
mise run check                          # validate + trace + unit tests
mise run status                         # all stories, status, next stage
```

| Task | Does |
|---|---|
| `new <title...>` / `incident <title...>` | create work item with next id |
| `story` `spec` `design` `implement` `qa` `review` `release` `diagnose` (alias of `agent:<stage>`) | run a stage on `<id>`; flags `--dry` (prompt only), `--plan` (call LLM, write nothing) |
| `agent:test <id>` | test-engineer stage (`test` is the unit-test task) |
| `agent <stage> <id>` | same, any stage |
| `branch <id>` | create `feature/<US-id>-<slug>` |
| `hooks` | enable the commit-msg hook (no agent names in history) |
| `ship [--draft] [--base b]` | checks + push + open PR; refuses on `main` |
| `advance <id> <status>` | set story status; refuses skipped steps or broken traceability (`--force` overrides) |
| `check`, `validate`, `trace`, `test` | deterministic checks |
| `doctor`, `env`, `stages`, `status` | inspect setup / pipeline / items |
| `install:github`, `install:tools` | wire CI and tool pointers |
| `site` / `site:build` | build and serve / only build the documentation website |

The plain `python3 tools/...` commands in the rest of this guide still work without mise.

## 1. Mental model

- A **work item** is a story id: `US-001`. Incidents use `INC-001`.
- Each **stage** (`story`, `spec`, `design`, ...) is one role-agent. It reads input files, calls an LLM, and writes output files.
- Files in git are the only memory between stages. Nothing is hidden in chat.
- After each stage a **human gate** reviews the result (normally a PR). Agents never merge or deploy.
- **You** move the story forward by editing `status:` in its frontmatter after approving a gate. Scripts check you did not skip a step.

```
draft -> enriched -> approved -> specified -> designed -> implemented -> done
 raw     story       PO ok        spec        design+ADR     code+tests     QA pass
```

| Stage | Command | Reads | Writes | Gate (you) |
|---|---|---|---|---|
| story | `run story --id US-002` | raw story | enriched story | product owner |
| spec | `run spec --id US-002` | story, `openspec/specs` | `openspec/changes/US-002/` | PO + tech lead |
| design | `run design --id US-002` | story, change, ADRs | `docs/architecture/US-002.md`, `docs/decisions/ADR-*.md` | tech lead |
| implement | `run implement --id US-002` | change, design, `src`, `tests` | `src/**`, `tests/**`, `tasks.md` | CI + code review |
| test | `run test --id US-002` | change, `src`, `tests` | `tests/**` | CI |
| qa | `run qa --id US-002` | story, change, tests, diff | `docs/qa/US-002.md` | QA / PO |
| review | `run review --id US-002` | diff, change, ADRs | `.agents/out/review-US-002.md` | human merge |
| release | `run release --id US-002` | story, QA, diff | `docs/releases/US-002.md` | release manager |
| diagnose | `run diagnose --id INC-001` | incident, runbooks | incident + runbooks | on-call |

## 2. One-time setup

Requires Python 3.10+. No packages to install.

```sh
python3 -m unittest discover -s tools/tests      # tooling healthy?
python3 tools/validate.py                  # artifacts valid?
python3 tools/trace_check.py               # story <-> spec <-> ADR <-> QA consistent?
git init && git add -A && git commit -m "init"   # needed for @diff (qa/review/release)
```

Edit `CONTEXT.md` for your project (product, glossary, stack, test commands). Every agent reads it.

### Choose an LLM provider

Pick one, export in your shell (or a `.env` you source; `.env` is git-ignored).

**A. Local model via Ollama (or vLLM, llama.cpp server, LM Studio):**
```sh
export AGENT_PROVIDER=openai
export AGENT_BASE_URL=http://localhost:11434/v1
export AGENT_MODEL=llama3.1            # or AGENT_MODEL_STRONG / AGENT_MODEL_CHEAP
```

**B. Hosted OpenAI-compatible API:**
```sh
export AGENT_PROVIDER=openai
export AGENT_BASE_URL=https://api.openai.com/v1
export AGENT_API_KEY=sk-...
export AGENT_MODEL_STRONG=<big model>  AGENT_MODEL_CHEAP=<small model>
```

**C. Any CLI agent (prompt on stdin, answer on stdout):**
```sh
export AGENT_PROVIDER=cmd
export AGENT_CMD="claude -p"           # or "codex exec -", "ollama run llama3.1"
```

Stages declare `model: cheap|strong` in `pipeline.yaml`; tiers map to `AGENT_MODEL_CHEAP` / `AGENT_MODEL_STRONG`, falling back to `AGENT_MODEL`.

Weak local models will struggle with strict output formats. Start with `--dry-run` and try a strong model for `spec` and `design`.

## 3. Walkthrough: a new feature

Worked example already in the repo: `US-001` (password reset). Study its files for what "good" looks like.

### Step 0 - capture the request
Create `docs/stories/US-002.md`. Free text is fine; only the frontmatter is required while `status: draft`:

```markdown
---
id: US-002
type: story
title: Export invoices as CSV
status: draft
owner: product-owner
---
Finance wants to download all invoices of a month as CSV. Needs VAT column.
```

### Step 1 - always preview first
```sh
python3 tools/agentrun.py run story --id US-002 --dry-run
```
Prints the exact system + user prompt, no LLM call, no cost. Check the inputs were found (`(missing)` means a wrong path).

### Step 2 - run the stage
```sh
python3 tools/agentrun.py run story --id US-002            # calls LLM, prints WOULD WRITE <paths>; writes nothing
python3 tools/agentrun.py run story --id US-002 --apply    # writes files + runs checks
```
`--apply` output tells you: files written, rejected paths (outside allowed `out`), check failures, and the gate to pass.

### Step 3 - human gate
```sh
git checkout -b feature/US-002 && git diff
```
Read the output. Answer `Open questions` in the story. Edit anything wrong by hand. Then set `status: approved` (PO decision) and commit/PR.

### Step 4..n - repeat per stage

| After you approve | Set `status:` | Why |
|---|---|---|
| story enriched and OK | `approved` | allows `spec` |
| `openspec/changes/US-002/` merged | `specified` | `trace_check` requires the change folder |
| design/ADR merged | `designed` | requires an ADR/design with `story: US-002` |
| code + tests merged, CI green | `implemented` | |
| QA report verdict `pass` | `done` | requires `docs/qa/US-002.md` with `verdict: pass` |

Implementation is iterative: `run implement` works the next unchecked tasks in `tasks.md`; run it again until all are checked. Run tests yourself - the runner does not execute your test suite.

### Review a PR
```sh
mise run review            # the WHOLE PR: all its commits vs its base branch (+ uncommitted), printed
mise run review --post     # same, and create/update THE review comment on the open PR
mise run review --commit   # only the last commit (never posted)
```

- **Scope**: the base is the PR's real base branch (read via `gh`), so a stacked PR is not reviewed together with its parent. Override with `AGENT_BASE_REF`.
- **One comment**: `--post` and CI update a single marked comment in place; they never add a second one and never touch your own comments. A failing comment lookup is an error, not a new comment.
- **Reviewing before you commit**: uncommitted changes to tracked files are included. New untracked files are not until you `git add` them.
- **It is advice**: it can miss things and can report things that are not there. Verify before acting.

### Production incident
```sh
cp .agents/templates/incident.md docs/incidents/INC-001.md
```
Fill frontmatter, write `TBD` in the other sections, and paste logs/metrics/deploys under `## Evidence` (redact secrets). Then:
```sh
python3 tools/agentrun.py run diagnose --id INC-001 --apply
```
Output is a ranked hypothesis list and recommended actions. A human executes any mitigation.

## Adopting the kit in an existing repository

The kit installs into another repo on a branch, as one commit, and updates the same way. You always review
the change as a diff in a PR; nothing is pushed for you and `main` is never touched.

```sh
git clone <kit-url> ~/src/agentkit                       # once
cd ~/src/agentkit
mise run kit:install ../my-repo --plan                   # see what it would do
mise run kit:install ../my-repo --with ci,docs           # branch chore/agentkit-install, one commit
cd ../my-repo && mise run ship                           # review the diff as a PR
```

Later, to update:

```sh
git -C ~/src/agentkit pull                               # a newer kit
cd ../my-repo
mise run kit:status                                      # clean / you edited / kit changed / both
mise run kit:update --plan                               # what would change
mise run kit:update                                      # branch chore/agentkit-update-<version>
mise run kit:update tools                                # only tools, hooks, schemas, templates
mise run kit:update ci                                   # CI is refreshed only when you ask
```

### From a release (no clone)

Every release carries one executable file, `agentkit.pyz`: the engine plus the exact kit payload of that
version, with a `.sha256` next to it. Nothing is cloned and nothing is fetched at install or update time.

```sh
# put it on your PATH (check the .sha256 first if you like)
curl -fsSL -o ~/.local/bin/agentkit \
  https://github.com/<owner>/<repo>/releases/latest/download/agentkit.pyz && chmod +x ~/.local/bin/agentkit
# or let mise manage it (confirm the asset is detected on your first release)
mise use -g "github:<owner>/<repo>@latest"

cd my-repo
agentkit install --with ci          # branch + one commit
agentkit status
# later
mise upgrade agentkit               # or re-download
agentkit update --plan && agentkit update
agentkit reconcile                  # a model resolves any conflicted file; --brief for your assistant instead
```

An adopting repo also carries its own `tools/agentkit.py` (so `mise run kit:status` works offline), but it has
no kit beside it: to *update*, run the newer `agentkit` (or pass `--from <clone or git URL>`).

When an update leaves conflicts, `agentkit reconcile` gives a model (any configured provider) the diff3 markers,
the `integrator` role and your `CONTEXT.md`, then validates the answer (no markers left, JSON/TOML parse) and lists
any of your lines missing from the result. A bad reply leaves the file untouched; `--brief` writes
`.agentkit/reconcile/*.md` for an assistant instead. You always review the result as a diff.

What happens to each kind of file:

| Class | Examples | On update |
|---|---|---|
| managed | `tools/*`, `.githooks/*`, `.agents/schemas`, `.agents/templates`, kit workflows | overwritten (a local edit shows as a deletion in the PR) |
| tailorable | `.agents/roles`, `skills`, `policies`, `pipeline.yaml` | 3-way merged; a real conflict is left as `<<<<<<< local` markers and listed in `.agentkit/CHANGES.md` |
| block | `AGENTS.md`, `.gitignore` | only the region between `agentkit:begin` and `agentkit:end` is rewritten; your text is untouched |
| side | kit tasks in `.config/mise/conf.d/agentkit.toml` | overwritten; your own `mise.toml` is never edited, and your task names win a clash |
| seed | `CONTEXT.md`, `.env.example`, the empty `docs/*` folders | copied once, then yours; never updated |

Your own files are never overwritten on install: a collision keeps yours and says so. To stop the kit
touching a file, list it (globs) in `.agentkit/ignore`. `mise run kit:check` (and CI) fails while conflict
markers remain.

## Driving everything from a prompt (Claude Code, Codex, Copilot)

You can run the same workflow from an assistant's prompt instead of typing `mise` commands. The recipe is
identical; the assistant is the model.

```
you:        start a story: export invoices as CSV
assistant:  mise run orient            # rules + state
            mise run new "Export invoices as CSV" ; mise run branch US-001
            mise run prepare story US-001     # reads the whole bundle, prints a receipt
            ...writes the story...
            mise run apply story US-001 --receipt <code> --worktree
            "Here is the story and 3 open questions. Approve? I will run advance US-001 approved."
```

- `mise run orient` / `mise run next` tell the assistant (and you) where things stand and who acts next.
- `apply` refuses without the receipt printed by `prepare`, and fails if anything outside the stage's allowed
  paths changed. Checks and gates are exactly the same as `mise run <stage>`.
- The assistant must wait for your explicit yes before `advance`, `ship` or a merge.
- The `mise run <stage>` path (any model API, Ollama, or a CLI) is unchanged and is what CI uses.

Not every story needs a spec, a design or an ADR: `mise run skip US-003 spec,design --reason "copy fix"`. A skipped spec still needs evidence: a changed test (a non-regression test counts) or a spec; `skip: [tests]` waives it for docs/config only.

## Using your tracker's keys and your own folders

Set `ids.story: PROJ` (or a `story_pattern`) and `paths:` at the top of `.agents/pipeline.yaml`; see the reference
page. `mise run new "Export invoices" --id PROJ-4821` adopts an existing Jira key, so the tracker stays the source of
the number and there is no second counter.

## Bugs and emergencies in one minute

- **A bug that can wait** is a story: `mise run new "Totals ignore VAT" --bug --text "..."`, then the usual flow. If the spec was already right: `mise run skip US-NNN spec,design --reason "spec already correct"`; you still add a non-regression test.
- **An emergency** (CI broken, production down) needs no story: `git switch -c fix/<what>`, fix, `mise run ship --emergency`, merge it yourself. Local checks are skipped; the branch and PR are not, and nothing is ever pushed to `main`.

## Git, versions, releases

- **Branches**: only `main` (always releasable) + one `feature/<US-id>-<slug>` per story. `mise run branch US-002` creates it. Squash-merge PRs.
- **Commits / PR title**: Conventional Commits with the story id as scope: `feat(US-002): export invoices as CSV`, `fix(US-002): ...`, `feat(US-002)!: ...` for breaking. CI rejects other PR titles.
- **Versions**: SemVer via [release-please](https://github.com/googleapis/release-please). It maintains a release PR on `main`; merging it tags `vX.Y.Z` and updates `CHANGELOG.md`. Never edit changelog, version or tags by hand. Set `release-type` in `release-please-config.json` for your stack.
- Policy text agents read: `.agents/policies/git.md`.

## 4. Automating in CI (GitHub)

```sh
adapters/install.sh github tools
```
- Copies workflows to `.github/workflows/`: `ci.yml` (PR title check, no assistant names, validate, trace, tool and project tests), `release-please.yml`, `agent-review.yml` (one review comment per PR, updated in place), `agent-triage.yml` (label an issue `agent:enrich` -> PR with enriched story).
- Configure the model in **Settings > Secrets and variables > Actions**:

  | Kind | Name | Example |
  |---|---|---|
  | Variable | `AGENT_BASE_URL` | `https://api.example.com/v1` |
  | Variable | `AGENT_MODEL_STRONG`, `AGENT_MODEL_CHEAP` | your model ids |
  | Secret | `AGENT_API_KEY` | token for that endpoint |
  | Variable (optional) | `AGENT_REASONING_EFFORT`, `AGENT_MAX_TOKENS`, `AGENT_PROVIDER`, `AGENT_CMD` | `none`, `16000` |

- **Not configured? The agent workflows skip** with a notice (they do not fail). The deterministic `ci` workflow is independent and always runs.
- A GitHub-hosted runner cannot reach a model on your own machine (`localhost`). Use a hosted OpenAI-compatible API, or register a self-hosted runner on a machine that can reach your model and set `runs-on: self-hosted`.
- Name PR branches `feature/US-002-...` so the reviewer finds the story id.
- The agent workflows read branch names, titles and issue text through `env`, never inline in shell. Still, try them on a throwaway repo first; triage treats issue text as untrusted input.

`tools` also writes `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursor/rules/agents.mdc`; each just points the tool at `AGENTS.md`.

## 5. Adapting to your project

| I want to... | Edit |
|---|---|
| Change how a role behaves | `.agents/roles/<role>.md` |
| Add a reusable procedure | `.agents/skills/<name>.md`, reference it in a stage's `skills:` |
| Change required sections/statuses | `.agents/schemas/<type>.json` and `.agents/templates/<type>.md` |
| Add or reorder a stage | `.agents/pipeline.yaml` (`name, role, goal, in, out, template, skills, check, gate, model`) |
| Add domain/stack knowledge | `CONTEXT.md` |
| Tighten/loosen autonomy | `.agents/policies/` (raising autonomy should be an ADR) |

`pipeline.yaml` fields: `in` = files/globs fed to the model (`{id}` substituted, `@diff` = git diff); `out` = the only paths the stage may write; `check` = `validate` and/or `trace`.

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `validate`: `file name must be ...` | the file name must start with its `id` (or `story`): rename the file, e.g. `ADR-0003-use-queue.md`, `US-012.md`. Existing projects adopting the template: run `mise run validate` once and rename what it lists |
| review comment not posted: `cannot list comments` | `gh` is not authenticated or lacks `pull-requests: write`. Nothing is posted on purpose (a failed lookup must not create duplicates) |
| `agent-review` check shows "skipped" | no model configured for CI; set the repository variables (section 4) |
| exit 3 `no model set` | export `AGENT_MODEL` (or `_STRONG/_CHEAP`) |
| exit 3 `model returned no text` | a thinking model spent its whole budget reasoning (minutes, empty answer). Set `AGENT_REASONING_EFFORT=none` (or `low`) and `AGENT_MAX_TOKENS=16000`, or use a non-thinking model |
| exit 3 `openai provider failed` | wrong `AGENT_BASE_URL`, server down, or timeout (`AGENT_TIMEOUT` seconds) |
| exit 2 `no files in response` | model ignored the `<<<FILE: path>>> ... <<<END>>>` format; use a stronger model or retry; raw reply printed on stderr |
| `REJECTED (outside allowed paths)` | model wrote a path not in the stage `out`; expected safety behaviour |
| `CHECK FAILED: ...` | output files are written already; fix by hand or rerun. Never edit validators to pass |
| `(missing)` in prompt inputs | input path does not exist yet; run the previous stage or fix the id |
| `@diff` empty | not a git repo, or no commits; set `AGENT_BASE_REF` |
| `trace_check: status=designed but no ADR` | you bumped `status:` before the artifact exists |

Every `--apply` run is logged to `.agents/runs/*.json` (stage, provider, prompt hash, files, check errors; git-ignored).

## 7. Limits to know

- Only structure is validated, not whether the content is right. The human gate is the quality control.
- The runner writes files; it does not run your build or tests, commit, or open PRs (except the GitHub workflows).
- Large repos: each input file is cut at 100k chars, but total prompt size is not managed. Narrow `in:` globs for big codebases.
- Evals, tracker sync and observability connectors are not built yet.
